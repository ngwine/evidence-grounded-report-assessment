"""Semantic proposals require their own scored sentence evidence, not relevance."""

from copy import deepcopy
import hashlib

import pytest

from research.core_mvp.contracts import validate_similarity_report
from research.core_mvp.semantic_verification import BidirectionalNliVerifier
from research.core_mvp.similarity import run_similarity_pipeline
from research.schema_validation import validate_json_schema


CONFIG = {"dense_enabled": False, "reranker_enabled": False,
          "candidate_depth": 3, "rerank_depth": 3, "top_k": 3,
          "semantic_verification": {"enabled": True}}
REPORT = "An operator signs in before a recording can be submitted."
SOURCE = "A recording upload requires the operator to authenticate first."


def chunk(key, document, text):
    return {"chunk_id": key, "document_id": document, "document_version_id": document + "-v1",
            "text": text, "normalized_text": text,
            "source_spans": [{"document_id": document, "document_version_id": document + "-v1",
                              "element_raw_char_start": 0, "element_raw_char_end": len(text)}]}


class NliDouble:
    metadata = {"test_double": True}

    def predict_relations(self, pairs):
        return [{"entailment": .98, "neutral": .01, "contradiction": .01} for _ in pairs]


def run(verifier=None, *, report=REPORT, source=SOURCE, config=None):
    return run_similarity_pipeline(
        [chunk("report", "report", report)], [chunk("source", "source", source)],
        config=config or CONFIG, encoder=None, reranker=None,
        semantic_verifier=verifier,
    )


def test_mutual_nli_proposal_retains_sentence_spans_but_never_adds_coverage():
    result = run(BidirectionalNliVerifier(NliDouble()))
    [match] = result["matches"]
    assert match["similarity_type"] == "PARAPHRASE"
    assert match["classification_status"] == "MODEL_SUPPORTED_SEMANTIC_MATCH"
    assert match["selected_for_manual_review"] is True
    assert match["selected_for_document_coverage"] is False
    assert result["exact_match_coverage_percentage"] == 0
    assert result["calibrated_similarity_percentage"] is None
    [evidence] = match["semantic_evidence"]
    assert evidence["report"]["text"] == REPORT
    assert evidence["source"]["text"] == SOURCE
    assert evidence["report"]["source_spans"]
    validate_similarity_report(result)
    validate_json_schema(result, kind="similarity")


def test_semantic_disabled_path_never_uses_a_verifier_implicitly():
    config = {k: v for k, v in CONFIG.items() if k != "semantic_verification"}
    result = run(config=config)
    assert result["semantic_classifier_available"] is False
    assert result["matches"][0]["similarity_type"] != "PARAPHRASE"
    with pytest.raises(ValueError, match="both enabled"):
        run(BidirectionalNliVerifier(NliDouble()), config=config)
    with pytest.raises(ValueError, match="both enabled"):
        run()


def test_substantial_exact_copy_bypasses_nli_including_short_vietnamese_syllables():
    class Never:
        metadata = {"test_double": True}

        def verify_pairs(self, pairs):
            raise AssertionError("Exact matches must bypass semantic scoring")

    text = ("Dữ liệu được ghi vào bộ nhớ sau mỗi lần đo và chỉ gửi lên máy chủ "
            "khi thiết bị đã nối mạng ổn định.")
    result = run(Never(), report=text, source=text)
    assert result["matches"][0]["classification_status"] == "EVIDENCE_BACKED_EXACT_MATCH"
    assert result["exact_match_coverage_percentage"] == 100
    validate_similarity_report(result)


def test_long_numeric_run_cannot_supply_diverse_lexical_exact_evidence():
    text = "123456789 234567891 345678912 456789123 567891234 678912345 789123456 891234567"
    config = {k: v for k, v in CONFIG.items() if k != "semantic_verification"}
    result = run(report=text, source=text, config=config)
    assert result["exact_match_coverage_percentage"] == 0


@pytest.mark.parametrize("fault", ["hash", "range", "label", "missing_span", "count"])
def test_malformed_semantic_evidence_fails_instead_of_attaching_a_label(fault):
    class Broken:
        metadata = {"test_double": True}

        def verify_pairs(self, pairs):
            data = BidirectionalNliVerifier(NliDouble()).verify_pairs(pairs)
            if fault == "hash":
                data[0]["report_text_sha256"] = hashlib.sha256(b"different").hexdigest()
            elif fault == "range":
                data[0]["evidence"][0]["report_range"]["end"] = len(REPORT) + 1
            elif fault == "label":
                data[0]["similarity_type"] = "NONE"
            elif fault == "missing_span":
                data[0]["evidence"] = []
            else:
                return []
            return data

    with pytest.raises(ValueError):
        run(Broken())


def test_report_contract_rejects_semantic_label_without_its_decision():
    result = run(BidirectionalNliVerifier(NliDouble()))
    corrupted = deepcopy(result)
    corrupted["matches"][0]["semantic_verification_status"] = "NOT_RUN"
    with pytest.raises(ValueError, match="semantic decision"):
        validate_similarity_report(corrupted)
