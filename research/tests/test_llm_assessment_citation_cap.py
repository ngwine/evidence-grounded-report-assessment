"""Match citation allowances without rewriting historical verifier defaults."""
import json

import pytest

from research.core_mvp import llm_assessment as llm
from research.tests.test_llm_assessment_verifier import MODEL, POSITIVE, FakeOllama, checklist, scoped_pack


def one_step_content(payload):
    data = json.loads(payload['messages'][1]['content'])
    units = data['evidence_passages'][0]['units']
    return {'checklist_id': data['checklist_id'], 'requirements': [{
        'requirement_id': r['requirement_id'], 'relation': 'SUPPORTED',
        'rationale': 'All selected source units report the deployed transport condition.',
        'evidence': [{'unit_id': unit['unit_id']} for unit in units],
    } for r in data['requirements']]}


def test_explicit_one_step_cap_accepts_three_real_units_but_default_does_not():
    pack = scoped_pack(' '.join([POSITIVE] * 3))
    base = {'enabled': True, 'citation_mode': 'source_units'}
    old = llm.LlmAssessmentVerifier(MODEL, base, transport=FakeOllama(one_step_content))
    assert old.verify(checklist(), pack)['checklist_outcome'] == 'CANNOT_ASSESS'
    transport = FakeOllama(one_step_content)
    new = llm.LlmAssessmentVerifier(MODEL, {**base, 'max_citations_per_requirement': 3}, transport=transport)
    result = new.verify(checklist(), pack)
    assert result['checklist_outcome'] == 'MET'
    assert len(result['matched_evidence_spans']) == 3
    assert len({proof['span']['normalized_start'] for proof in result['matched_evidence_spans']}) == 3
    assert 'select one to 3 units' in transport.chat_calls[0][2]['messages'][0]['content']
    assert new.metadata['source_unit_policy']['max_citations_per_requirement'] == 3


def test_explicit_two_stage_cap_bounds_both_generation_stages():
    def content(payload):
        data = json.loads(payload['messages'][1]['content'])
        if 'evidence_passages' in data:
            return {'checklist_id': data['checklist_id'], 'requirements': [{
                'requirement_id': r['requirement_id'],
                'evidence': [{'unit_id': data['evidence_passages'][0]['units'][0]['unit_id']}],
            } for r in data['requirements']]}
        return {'checklist_id': data['checklist_id'], 'requirements': [{
            'requirement_id': r['requirement_id'], 'relation': 'SUPPORTED',
            'rationale': 'The selected sentence states the transport condition.',
            'used_unit_ids': [r['selected_units'][0]['unit_id']],
        } for r in data['requirements']]}

    transport = FakeOllama(content)
    verifier = llm.LlmAssessmentVerifier(MODEL, {
        'enabled': True, 'citation_mode': 'source_units', 'citation_audit': True,
        'max_citations_per_requirement': 1,
    }, transport=transport)
    result = verifier.verify(checklist(), scoped_pack())
    assert result['checklist_outcome'] == 'MET'
    select, audit = [call[2] for call in transport.chat_calls]
    assert select['format']['properties']['requirements']['items']['properties']['evidence']['maxItems'] == 1
    assert 'zero to 1 exact unit_id values' in select['messages'][0]['content']
    for branch in audit['format']['properties']['requirements']['items']['oneOf']:
        if branch['properties']['relation']['const'] != 'INSUFFICIENT':
            assert branch['properties']['used_unit_ids']['maxItems'] == 1
    assert 'one to 1 IDs' in audit['messages'][0]['content']


def test_explicit_instances_cannot_mutate_default_prompts_schemas_or_policy_shape():
    for audit in (False, True):
        base = {'enabled': True, 'citation_mode': 'source_units', 'citation_audit': audit}
        before = llm.LlmAssessmentVerifier(MODEL, base, transport=FakeOllama())
        initial = (before.metadata['prompt_sha256'], before.metadata['output_schema_sha256'],
                   before.metadata['policy_sha256'])
        llm.LlmAssessmentVerifier(MODEL, {**base, 'max_citations_per_requirement': 1}, transport=FakeOllama())
        after = llm.LlmAssessmentVerifier(MODEL, base, transport=FakeOllama())
        assert initial == (after.metadata['prompt_sha256'], after.metadata['output_schema_sha256'],
                           after.metadata['policy_sha256'])
        assert 'max_citations_per_requirement' not in after.policy
        assert after.metadata['source_unit_policy']['max_citations_per_requirement'] == (3 if audit else 2)


@pytest.mark.parametrize('value', [True, False, 0, 4, 2.0, '3', None])
def test_invalid_caps_reject_before_model_loading(value):
    with pytest.raises(ValueError, match='max_citations_per_requirement'):
        llm.validate_llm_policy({'enabled': True, 'citation_mode': 'source_units',
                                 'max_citations_per_requirement': value})


def test_quote_protocol_does_not_silently_accept_source_unit_cap():
    with pytest.raises(ValueError, match='source_units'):
        llm.validate_llm_policy({'enabled': True, 'max_citations_per_requirement': 3})
