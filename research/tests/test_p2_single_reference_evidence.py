"""Coordinate-audit checks use synthetic reports and a fake model transport."""
from copy import deepcopy
import hashlib
import json

import pytest

from research.p2_comparison import runner
from research.p2_comparison.single_reference_evidence import audit_item
from test_p2_comparison import factory_capture, inputs, prepare  # noqa: F401


@pytest.fixture
def geometry(inputs):
    prepared, _ = prepare(inputs)
    output = inputs['private'] / 'fake-run'
    runner.run_prepared_development(prepared_dir=prepared, output_dir=output,
                                   verifier_factory=factory_capture({}))
    common = json.loads((prepared / 'common-evidence.json').read_text())['items'][0]
    prediction = json.loads((output / 'one-step-results.json').read_text())['items'][0]
    text = inputs['report'].read_text()
    paragraphs, start = [], 0
    for index, paragraph in enumerate(text.split('\n\n'), 1):
        paragraphs.append({'paragraph_id': f'P{index:04d}', 'start': start,
                           'end': start + len(paragraph), 'text': paragraph})
        start += len(paragraph) + 2
    context = {'report_id': 'synthetic-reference', 'report_version': 'source-v1',
               'body_sha256': hashlib.sha256(text.encode()).hexdigest(),
               'report_text': text, 'paragraphs': paragraphs}
    identity = {key: context[key] for key in ('report_id', 'report_version', 'body_sha256')}
    first = paragraphs[0]
    evidence = {'schema_version': 1, 'kind': 'SPAN_SET', **identity,
                'spans': [{key: first[key] for key in ('paragraph_id', 'start', 'end')}
                          | {'quote': first['text']}]}
    reference = {'evidence': evidence, 'metadata': {**identity, 'checklist_id': 'C.1'}}
    prediction['metadata'] = deepcopy(reference['metadata'])
    return prediction, reference, context, common


def test_exact_raw_coordinates_are_audited_without_semantic_truth_claim(geometry):
    result = audit_item(*geometry)
    assert result['audit_status'] == 'PASSED'
    assert result['all_present_proofs_source_bound']
    assert result['source_bound_proof_count'] == result['proof_count'] > 0
    assert result['location_overlap']['applicable']
    assert result['semantic_support_verified'] is False
    assert result['model_absence_detection_validated'] is False
    for proof in result['proof_records']:
        for segment in proof['mapped_segments']:
            assert geometry[2]['report_text'][segment['start']:segment['end']] == segment['quote']


@pytest.mark.parametrize('corruption', ['text', 'raw_range', 'version', 'source_map'])
def test_forged_prediction_geometry_is_rejected(geometry, corruption):
    prediction, reference, context, common = deepcopy(geometry)
    span = prediction['raw_result']['matched_evidence_spans'][0]['span']
    if corruption == 'text':
        span['text'] = 'An invented quotation.'
    elif corruption == 'raw_range':
        span['raw_end'] += 1
    elif corruption == 'version':
        span['document_version_id'] = 'wrong-version'
    else:
        span['source_spans'] = []
    result = audit_item(prediction, reference, context, common)
    assert result['audit_status'] == 'INVALID'
    assert result['issues']
    assert result['location_overlap'] is None


def test_missing_citations_are_not_perfect_span_evidence(geometry):
    prediction, reference, context, common = deepcopy(geometry)
    prediction.update(accepted_label='CANNOT_ASSESS', decision_status='SEMANTIC_DECISION')
    prediction['raw_result']['matched_evidence_spans'] = []
    result = audit_item(prediction, reference, context, common)
    assert result['audit_status'] == 'NO_CITATIONS'
    assert result['proof_count'] == 0
    assert result['location_overlap']['metrics']['f1'] == 0


def test_no_citations_never_become_verified_whole_document_absence(geometry):
    prediction, reference, context, common = deepcopy(geometry)
    reference['evidence'] = {
        'schema_version': 1, 'kind': 'DOCUMENT_ABSENCE',
        **{key: context[key] for key in ('report_id', 'report_version', 'body_sha256')},
        'scope': 'ENTIRE_CAPTURED_TEXT', 'reviewed_whole_text': True,
        'paragraph_ids': [paragraph['paragraph_id'] for paragraph in context['paragraphs']],
        'rationale': 'Synthetic absence record for adapter testing only.'}
    prediction.update(accepted_label='CANNOT_ASSESS', decision_status='SEMANTIC_DECISION')
    prediction['raw_result']['matched_evidence_spans'] = []
    result = audit_item(prediction, reference, context, common)
    assert not result['location_overlap']['applicable']
    assert result['document_absence']['applicable']
    assert result['document_absence']['matching_complete_scope_record'] is False
    assert result['document_absence']['semantic_absence_verified'] is False


def test_reference_body_tampering_is_rejected(geometry):
    prediction, reference, context, common = deepcopy(geometry)
    context['report_text'] += ' changed'
    with pytest.raises(ValueError):
        audit_item(prediction, reference, context, common)
