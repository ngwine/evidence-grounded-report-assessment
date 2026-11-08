"""Numeric citation hints require parser provenance and a unique bibliography key."""

from pathlib import Path

from docx import Document
import pytest

from research.core_mvp.documents import parse_document
from research.core_mvp.similarity import _linked_citation_number_ranges
from research.core_mvp.similarity import run_similarity_pipeline
from research.core_mvp.semantic_verification import BidirectionalNliVerifier


def parsed(tmp_path: Path, body: str, references=('[4] A sample technical source.',)):
    document = Document()
    document.add_paragraph(body)
    if references:
        document.add_heading('References', level=1)
        for reference in references:
            document.add_paragraph(reference)
    path = tmp_path / 'report.docx'
    document.save(path)
    return parse_document(path, role='student-report', min_tokens=1, max_tokens=220).chunks


def test_unique_linked_citation_has_original_offsets_and_unknown_validity(tmp_path):
    chunks = parsed(tmp_path, 'The lexical retrieval method [4] returns supporting passages.')
    hints = _linked_citation_number_ranges(chunks)
    markers = [marker for group in hints.values() for marker in group['markers']]
    assert len(markers) == 1
    assert markers[0]['verification_status'] == 'UNKNOWN'
    assert markers[0]['candidate_entry_ids']
    for chunk in chunks:
        for bounds in hints.get(chunk['chunk_id'], {}).get('ranges', []):
            assert chunk['normalized_text'][bounds['start']:bounds['end']] == '[4]'


@pytest.mark.parametrize('body', [
    'The dose [4] mg is stored in the patient record.',
    'The sample value [4] is recorded for the station.',
    'The array[4] contains the most recent observation.',
    'The interval [1,4] bounds the range of valid readings.',
    'The measurement equals = [4] before conversion.',
])
def test_measurements_arrays_and_intervals_remain_numeric(tmp_path, body):
    assert _linked_citation_number_ranges(parsed(tmp_path, body)) == {}


def test_marker_without_bibliography_is_not_an_exclusion_hint(tmp_path):
    chunks = parsed(tmp_path, 'The lexical retrieval method [4] returns supporting passages.', references=())
    assert _linked_citation_number_ranges(chunks) == {}


def test_duplicate_reference_key_is_ambiguous_not_an_exclusion_hint(tmp_path):
    chunks = parsed(tmp_path, 'The lexical retrieval method [4] returns supporting passages.',
                    references=('[4] First reference.', '[4] Different reference.'))
    assert _linked_citation_number_ranges(chunks) == {}


def test_mongo_envelope_preserves_parser_artifact_version(tmp_path):
    chunks = parsed(tmp_path, 'The lexical retrieval method [4] returns supporting passages.')
    expected = _linked_citation_number_ranges(chunks)
    for chunk in chunks:
        chunk['artifact_schema_version'] = 2
        chunk['schema_version'] = 1
    assert _linked_citation_number_ranges(chunks) == expected


def test_legacy_text_without_parser_mapping_never_guesses_citations():
    assert _linked_citation_number_ranges([{
        'chunk_id': 'legacy', 'document_id': 'doc', 'normalized_text': 'Method [4].',
    }]) == {}


def test_pipeline_excludes_only_linked_marker_from_guard_without_changing_model_text(tmp_path):
    class NliDouble:
        metadata = {"test_double": True}

        def predict_relations(self, pairs):
            return [{"entailment": .98, "neutral": .01, "contradiction": .01} for _ in pairs]

    report = parsed(tmp_path, 'The lexical search method [4] returns supporting passages and playback times.')
    source_path = tmp_path / 'source.txt'
    source_path.write_text('Search results contain relevant text together with a position for video playback.')
    source = parse_document(source_path, role='comparison-source', min_tokens=1, max_tokens=220).chunks
    config = {"dense_enabled": False, "reranker_enabled": False,
              "candidate_depth": 3, "rerank_depth": 3, "top_k": 3,
              "semantic_verification": {"enabled": True}}
    before = run_similarity_pipeline(report, source, config=config, encoder=None, reranker=None,
                                     semantic_verifier=BidirectionalNliVerifier(NliDouble()))
    config['semantic_verification']['citation_number_guard'] = 'LINKED_SINGLE_NUMERIC_MARKERS'
    after = run_similarity_pipeline(report, source, config=config, encoder=None, reranker=None,
                                    semantic_verifier=BidirectionalNliVerifier(NliDouble()))
    primary = next(c['chunk_id'] for c in report if 'search method [4]' in c['text'])
    old = next(m for m in before['matches'] if m['report_chunk_id'] == primary)
    new = next(m for m in after['matches'] if m['report_chunk_id'] == primary)
    assert old['similarity_type'] is None
    assert new['similarity_type'] == 'PARAPHRASE'
    assert '[4]' in new['semantic_evidence'][0]['report']['text']
    assert new['semantic_citation_context']['report']['markers']
    assert new['selected_for_document_coverage'] is False
    assert after['exact_match_coverage_percentage'] == 0
