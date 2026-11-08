"""Short-report coverage must improve without weakening scope or budget checks."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from research.core_mvp import assessment
from research.core_mvp.documents import parse_document


POLICY = {"strategy": "all_parsed_chunks_if_bounded", "max_chars": 14000,
          "max_utf8_bytes": 20000, "max_chunks": 32}
RUBRIC = {
    "schema_version": 1, "rubric_id": "context-test", "version": "1", "max_score": 10,
    "criteria": [{"criterion_id": "C", "title": "Completed evaluation", "weight": 10,
                  "checklists": [{"checklist_id": "C.1", "mode": "LOCAL",
                                  "statement": "The report describes a completed usability test.",
                                  "requirements": [{"requirement_id": "R", "any_of": ["completed a usability test"]}]}]}],
}


@pytest.fixture
def context_case(tmp_path, monkeypatch):
    report = tmp_path / "report.txt"
    report.write_text(
        "The system architecture describes storage, encryption, and a request queue.\n\n"
        "The researchers completed a usability test with participants and documented the observations.",
        encoding="utf-8",
    )
    parsed = parse_document(report, role="student-report", max_tokens=20, min_tokens=1)
    chunks = list(parsed.chunks)
    assert len(chunks) >= 2
    first = chunks[0]
    # Simulate the known failure mode: ranker omits the relevant final passage.
    ranked = [{"chunk_id": first["chunk_id"], "document_id": first["document_id"],
               "document_version_id": first["document_version_id"],
               "rank": 1, "score": 1.0, "score_type": "bm25"}]
    monkeypatch.setattr(assessment, "_rank_local", lambda *a, **kw: (deepcopy(ranked), {"mode": "LOCAL"}))
    seen = []

    def verify(checklist, evidence):
        seen.append(evidence)
        return assessment._verify(checklist, evidence)

    verifier = SimpleNamespace(metadata={"test_only": True}, verify=verify)
    config = {"dense_enabled": False, "reranker_enabled": False,
              "llm_verification": {"enabled": True}}
    return chunks, verifier, config, seen


def run(case, config):
    chunks, verifier, _, _ = case
    return assessment.run_assessment_pipeline(
        chunks, RUBRIC, config=config, encoder=None, reranker=None, llm_verifier=verifier,
    )["checklist_results"][0]


def test_bounded_context_recovers_unranked_evidence_with_original_scope(context_case):
    chunks, _, config, seen = context_case
    old = run(context_case, config)
    assert old["checklist_outcome"] == "CANNOT_ASSESS"
    new = run(context_case, {**config, "evidence_context": POLICY})
    assert new["checklist_outcome"] == "MET"
    assert [e.chunk["chunk_id"] for e in seen[-1]] == [c["chunk_id"] for c in chunks]
    assert all(e.chunk is c and e.record["source_spans"] == c["source_spans"]
               for e, c in zip(seen[-1], chunks))
    metadata = new["retrieval"]["evidence_context"]
    assert metadata["selected_all_report_chunks"] is True
    assert metadata["original_document_completeness_asserted"] is False


@pytest.mark.parametrize("limit", ["max_chars", "max_utf8_bytes", "max_chunks"])
def test_context_budget_falls_back_without_cropping_or_claiming_full_coverage(context_case, limit):
    _, _, config, seen = context_case
    result = run(context_case, {**config, "evidence_context": {**POLICY, limit: 1}})
    assert len(seen[-1]) == 1
    assert result["checklist_outcome"] == "CANNOT_ASSESS"
    metadata = result["retrieval"]["evidence_context"]
    assert metadata["selected_all_report_chunks"] is False
    assert metadata["fallback_reason"] == "CONTEXT_LIMIT_EXCEEDED"
    assert limit in metadata["exceeded_limits"]


def test_context_still_rejects_mixed_version_before_model_call(context_case):
    chunks, _, config, seen = context_case
    chunks[-1]["document_version_id"] = "foreign-version"
    with pytest.raises(ValueError, match="document version"):
        run(context_case, {**config, "evidence_context": POLICY})
    assert seen == []


def test_context_still_rejects_forged_source_span_before_model_call(context_case):
    chunks, _, config, seen = context_case
    chunks[-1]["source_spans"][0]["document_version_id"] = "foreign-version"
    with pytest.raises(ValueError, match="Cross-version"):
        run(context_case, {**config, "evidence_context": POLICY})
    assert seen == []


def test_phrase_mode_does_not_expand_evidence_when_policy_is_present(context_case):
    _, _, config, seen = context_case
    config = {**config, "llm_verification": {"enabled": False}, "evidence_context": POLICY}
    assert run(context_case, config)["checklist_outcome"] == "CANNOT_ASSESS"
    assert seen == []


@pytest.mark.parametrize("policy", [None, {}, {"strategy": "complete_raw_document"},
                                   {**POLICY, "max_chunks": True}, {**POLICY, "max_chars": 0},
                                   {**POLICY, "max_utf8_bytes": 999999}, {**POLICY, "extra": 1}])
def test_invalid_context_policies_rejected_before_inference(policy):
    with pytest.raises(ValueError):
        assessment.validate_assessment_config({"evidence_context": policy})
