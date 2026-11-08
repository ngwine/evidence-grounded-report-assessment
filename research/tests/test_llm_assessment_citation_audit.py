"""Find/verify stage separation, scope and failures; fake transport only."""
import json

import pytest

from research.core_mvp import assessment
from research.core_mvp.llm_assessment import LlmAssessmentVerifier
from research.tests.test_llm_assessment_verifier import (
    CONFIG, DIGEST, MODEL, NEGATIVE, POSITIVE, FakeOllama, assert_report_contracts,
    assert_unknown, checklist, parsed_chunks, rubric, scoped_pack,
)


POLICY = {"enabled": True, "citation_mode": "source_units", "citation_audit": True}


def selector(data, empty_ids=()):
    unit_id = data["evidence_passages"][0]["units"][0]["unit_id"]
    return {"checklist_id": data["checklist_id"], "requirements": [{
        "requirement_id": r["requirement_id"],
        "evidence": [] if r["requirement_id"] in empty_ids else [{"unit_id": unit_id}],
    } for r in data["requirements"]]}


def auditor(data, relation="SUPPORTED"):
    return {"checklist_id": data["checklist_id"], "requirements": [{
        "requirement_id": r["requirement_id"], "relation": relation,
        "rationale": "The selected text directly states the relevant deployed traffic condition.",
        "used_unit_ids": [] if relation == "INSUFFICIENT" else [r["selected_units"][0]["unit_id"]],
    } for r in data["requirements"]]}


def verify(*, selection_fn=selector, audit_fn=auditor, pack=None, item=None, policy=None, **kwargs):
    def content(payload):
        data = json.loads(payload["messages"][1]["content"])
        return selection_fn(data) if "evidence_passages" in data else audit_fn(data)

    transport = FakeOllama(content, **kwargs)
    verifier = LlmAssessmentVerifier(MODEL, policy or POLICY, transport=transport)
    result = verifier.verify(item or checklist(), pack or scoped_pack())
    return result, transport, verifier


def test_auditor_sees_only_selected_text_and_no_initial_relation_or_rationale():
    marker = "UNSELECTED_CONTEXT_MARKER must never reach the auditor."
    result, transport, _ = verify(pack=scoped_pack(POSITIVE + " " + marker))
    assert result["checklist_outcome"] == "MET"
    first, second = [json.loads(c[2]["messages"][1]["content"]) for c in transport.chat_calls]
    assert marker in json.dumps(first)
    assert marker not in json.dumps(second)
    assert "evidence_passages" not in second
    assert "rationale" not in json.dumps(second) and "candidate_relation" not in second
    assert second["requirements"][0]["selected_units"] == [{"unit_id": "u1.1", "text": POSITIVE}]
    [proof] = result["matched_evidence_spans"]
    assert proof["span"]["text"] == POSITIVE
    assert result["llm_verification"]["model_calls"] == 2


def test_selected_only_auditor_can_reject_a_generic_topic_without_creating_proof():
    result, transport, _ = verify(
        pack=scoped_pack("Transport security is a topic of this report."),
        audit_fn=lambda data: auditor(data, "INSUFFICIENT"),
    )
    assert_unknown(result)
    assert not result["matched_evidence_spans"]
    assert len(transport.chat_calls) == 2
    assert result["llm_verification"]["citation_audit"]["status"] == "VALIDATED"


def test_negative_evidence_can_be_selected_and_verified_as_contradiction():
    result, _, _ = verify(pack=scoped_pack(NEGATIVE), audit_fn=lambda data: auditor(data, "CONTRADICTED"))
    assert result["checklist_outcome"] == "UNMET"
    assert result["contradiction_hits"][0]["span"]["text"] == NEGATIVE


def test_all_empty_selection_skips_auditor_and_preserves_every_requirement():
    result, transport, _ = verify(
        item=checklist("one", "two"),
        selection_fn=lambda data: selector(data, empty_ids=("one", "two")),
    )
    assert_unknown(result)
    assert len(result["requirement_results"]) == 2
    assert len(transport.chat_calls) == 1
    assert result["llm_verification"]["model_calls"] == 1
    assert result["llm_verification"]["citation_audit"]["status"] == "SKIPPED_EMPTY_SELECTION"


def test_mixed_empty_requirement_is_not_dropped_or_sent_for_unsupported_audit():
    result, transport, _ = verify(
        item=checklist("one", "two"), selection_fn=lambda data: selector(data, empty_ids=("two",)),
    )
    assert_unknown(result)
    assert result["requirements_total"] == 2 and result["requirements_satisfied"] == 1
    assert [r["relation"] for r in result["requirement_results"]] == ["SUPPORTED", "INSUFFICIENT"]
    data = json.loads(transport.chat_calls[1][2]["messages"][1]["content"])
    assert [r["requirement_id"] for r in data["requirements"]] == ["one"]


@pytest.mark.parametrize("mutate", [
    lambda item: item.update(relation="SUPPORTED"),
    lambda item: item.update(rationale="Unselected invented explanation"),
    lambda item: item["evidence"][0].update(unit_id="invented-unit"),
    lambda item: item.update(evidence=item["evidence"] * 2),
    lambda item: item.update(requirement_id="foreign-requirement"),
])
def test_selector_cannot_smuggle_judgments_or_fabricate_ids(mutate):
    def selection(data):
        output = selector(data)
        mutate(output["requirements"][0])
        return output

    result, transport, _ = verify(selection_fn=selection)
    assert_unknown(result)
    assert len(transport.chat_calls) == 1


@pytest.mark.parametrize("mutate", [
    lambda item: item.update(used_unit_ids=["u999.1"]),
    lambda item: item.update(used_unit_ids=[]),
    lambda item: item.update(used_unit_ids=item["used_unit_ids"] * 2),
    lambda item: item.update(requirement_id="foreign-requirement"),
    lambda item: item.update(rationale="x" * 401),
    lambda item: item.update(score=10),
])
def test_auditor_cannot_expand_selection_or_change_grade_contract(mutate):
    def audit(data):
        output = auditor(data)
        mutate(output["requirements"][0])
        return output

    result, transport, _ = verify(audit_fn=audit)
    assert_unknown(result)
    assert len(transport.chat_calls) == 2
    assert result["llm_verification"]["active_stage"] == "SELECTED_UNIT_VERIFICATION"
    assert result["llm_verification"]["citation_audit"]["status"] == "WITHHELD"


def test_auditor_can_choose_a_strict_subset_and_proof_contains_only_used_unit():
    def selection(data):
        units = data["evidence_passages"][0]["units"]
        result = selector(data)
        result["requirements"][0]["evidence"] = [{"unit_id": u["unit_id"]} for u in units]
        return result

    result, _, _ = verify(selection_fn=selection, pack=scoped_pack(POSITIVE + " Extra contextual sentence."))
    assert result["checklist_outcome"] == "MET"
    assert [h["span"]["text"] for h in result["matched_evidence_spans"]] == [POSITIVE]


def test_auditor_cannot_use_an_existing_but_unselected_unit():
    def audit(data):
        result = auditor(data)
        result["requirements"][0]["used_unit_ids"] = ["u1.2"]
        return result

    result, _, _ = verify(audit_fn=audit, pack=scoped_pack(POSITIVE + " Unselected different sentence."))
    assert_unknown(result)


def test_auditor_timeout_is_a_phase_specific_failure_not_an_automatic_retry():
    def fail(_data):
        raise TimeoutError()

    result, transport, _ = verify(audit_fn=fail)
    assert_unknown(result)
    assert result["reason_code"] == "LLM_CITATION_AUDIT_TIMEOUT"
    assert len(transport.chat_calls) == 2
    assert result["llm_verification"]["model_calls"] == 2


def test_model_digest_change_during_audit_invalidates_all_proposed_proofs():
    result, transport, _ = verify(digests=[DIGEST] * 4 + ["sha256:" + "b" * 64])
    assert_unknown(result)
    assert result["reason_code"] == "LLM_MODEL_DIGEST_MISMATCH"
    assert len(transport.chat_calls) == 2


@pytest.mark.parametrize("patch,reason", [
    ({"eval_count": 1537}, "LLM_CONTEXT_BUDGET_EXCEEDED"),
    ({"prompt_eval_count": 16384}, "LLM_CONTEXT_BUDGET_EXCEEDED"),
    ({"done_reason": "length"}, "LLM_OUTPUT_TRUNCATED"),
])
def test_second_stage_has_its_own_telemetry_and_completion_checks(patch, reason):
    def content(payload):
        data = json.loads(payload["messages"][1]["content"])
        return selector(data) if "evidence_passages" in data else auditor(data)

    class SecondStageFault(FakeOllama):
        def request(self, method, path, payload=None, **kwargs):
            response = super().request(method, path, payload, **kwargs)
            if path == "/api/chat" and len(self.chat_calls) == 2:
                response.update(patch)
            return response

    transport = SecondStageFault(content)
    verifier = LlmAssessmentVerifier(MODEL, POLICY, transport=transport)
    result = verifier.verify(checklist(), scoped_pack())
    assert_unknown(result)
    assert result["reason_code"] == reason
    assert result["llm_verification"]["model_calls"] == 2
    assert result["llm_verification"]["citation_audit"]["status"] == "WITHHELD"


def test_both_actual_model_calls_count_toward_the_fixed_instance_budget():
    _, transport, verifier = verify(policy={**POLICY, "max_checklists": 1})
    assert verifier.metadata["citation_audit"]["max_model_calls"] == 2
    assert len(transport.chat_calls) == 2
    again = verifier.verify(checklist(), scoped_pack())
    assert_unknown(again)
    assert len(transport.chat_calls) == 2


def test_real_pipeline_keeps_empty_requirement_unknown_and_score_null(tmp_path):
    chunks = parsed_chunks(tmp_path)
    raw_rubric = rubric()
    raw_rubric["criteria"][0]["checklists"][0] = checklist("one", "two")
    def content(payload):
        data = json.loads(payload["messages"][1]["content"])
        return selector(data, empty_ids=("two",)) if "evidence_passages" in data else auditor(data)
    verifier = LlmAssessmentVerifier(MODEL, POLICY, transport=FakeOllama(content))
    result = assessment.run_assessment_pipeline(
        chunks, raw_rubric, config={**CONFIG, "llm_verification": POLICY},
        encoder=None, reranker=None, llm_verifier=verifier,
    )
    assert_report_contracts(result)
    assert result["proposed_total_score"] is None
    assert result["checklist_results"][0]["requirements_total"] == 2
    assert result["verification_metadata"]["citation_audit"]["strategy"] == "SELECT_UNITS_THEN_VERIFY_SELECTED_ONLY_V1"


@pytest.mark.parametrize("policy", [{"enabled": True, "citation_audit": True},
                                   {**POLICY, "citation_audit": "yes"}])
def test_audit_requires_source_units_and_explicit_boolean(policy):
    with pytest.raises(ValueError, match="citation_audit"):
        LlmAssessmentVerifier(MODEL, policy, transport=FakeOllama({}))


def test_disabled_audit_does_not_change_source_unit_generation_contract():
    from research.tests.test_llm_assessment_source_units import chosen_units
    transport = FakeOllama(chosen_units)
    verifier = LlmAssessmentVerifier(MODEL, {**POLICY, "citation_audit": False}, transport=transport)
    result = verifier.verify(checklist(), scoped_pack())
    assert result["checklist_outcome"] == "MET"
    assert len(transport.chat_calls) == 1
    assert "citation_audit" not in result["llm_verification"]
