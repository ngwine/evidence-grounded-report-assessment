"""Exercise parsing, context, two model stages, proof contracts and code scoring."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from research.core_mvp.llm_assessment import LlmAssessmentVerifier
from research.core_mvp.runner import run_core_mvp


MODEL = {"backend": "ollama", "model": "test:1", "digest": "sha256:" + "a" * 64}
POLICY = {"enabled": True, "citation_mode": "source_units", "citation_audit": True}
RUBRIC = {
    "schema_version": 1, "rubric_id": "two-stage-integration", "version": "1", "max_score": 10,
    "criteria": [{"criterion_id": "C", "title": "Completed evaluation", "weight": 10,
                  "checklists": [{"checklist_id": "C.1", "mode": "LOCAL",
                                  "statement": "The report describes completed interviews.",
                                  "requirements": [{"requirement_id": "interviews",
                                                    "description": "Interviews were completed with participants.",
                                                    "any_of": ["completed interviews"]}]}]}],
}


class TwoStageTransport:
    def __init__(self):
        self.model_inputs = []

    def request(self, method, path, payload=None, **kwargs):
        if path == "/api/tags":
            return {"models": [{"name": MODEL["model"], "digest": MODEL["digest"]}]}
        if path == "/api/show":
            return {"details": {"format": "gguf"}, "template": "test template", "model_info": {}}
        assert path == "/api/chat"
        data = json.loads(payload["messages"][-1]["content"])
        self.model_inputs.append(data)
        if "evidence_passages" in data:
            units = [unit for passage in data["evidence_passages"] for unit in passage["units"]]
            candidate = next(unit for unit in units if "completed interviews" in unit["text"])
            rows = [{"requirement_id": r["requirement_id"],
                     "evidence": [{"unit_id": candidate["unit_id"]}] if r["requirement_id"] == "interviews" else []}
                    for r in data["requirements"]]
        else:
            assert "evidence_passages" not in data
            rows = [{"requirement_id": r["requirement_id"], "relation": "SUPPORTED",
                     "rationale": "The selected sentence reports completed interviews.",
                     "used_unit_ids": [r["selected_units"][0]["unit_id"]]}
                    for r in data["requirements"]]
        content = {"checklist_id": data["checklist_id"], "requirements": rows}
        return {"model": MODEL["model"], "done": True, "done_reason": "stop",
                "message": {"content": json.dumps(content)}}


@pytest.mark.parametrize("missing_requirement", [False, True])
def test_two_stage_proofs_and_missing_requirements_control_real_core_scores(tmp_path, missing_requirement):
    report = tmp_path / "report.txt"
    report.write_text(
        "PRIVATE UNSELECTED BACKGROUND: details that the auditor must not see.\n\n"
        "The team completed interviews with six participants and recorded their observations.",
        encoding="utf-8",
    )
    rubric = deepcopy(RUBRIC)
    if missing_requirement:
        rubric["criteria"][0]["checklists"][0]["requirements"].append({
            "requirement_id": "release", "description": "A public code release is linked.",
            "any_of": ["public code release"],
        })
    rubric_path = tmp_path / "rubric.json"
    rubric_path.write_text(json.dumps(rubric))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "schema_version": 1, "experiment_id": "synthetic-integration", "seed": 1,
        "pipeline2": {"dense_enabled": False, "reranker_enabled": False,
                      "llm_verification": POLICY,
                      "evidence_context": {"strategy": "all_parsed_chunks_if_bounded"}},
    }))
    transport = TwoStageTransport()
    verifier = LlmAssessmentVerifier(MODEL, POLICY, transport=transport)
    run = run_core_mvp(
        report_path=report, source_paths=[], rubric_path=rubric_path, config_path=config_path,
        output_dir=tmp_path / "outputs", pipeline="assessment", llm_verifier=verifier,
    )
    result = json.loads(Path(run["output_paths"]["assessment_report"]).read_text())
    item = result["checklist_results"][0]
    assert len(transport.model_inputs) == 2
    audit = transport.model_inputs[1]
    assert "PRIVATE UNSELECTED BACKGROUND" not in json.dumps(audit)
    assert [r["requirement_id"] for r in audit["requirements"]] == ["interviews"]
    assert len(item["matched_evidence_spans"]) == 1
    proof = item["matched_evidence_spans"][0]["span"]
    assert proof["text"] == "The team completed interviews with six participants and recorded their observations."
    assert proof["source_spans"]
    assert item["checklist_outcome"] == ("CANNOT_ASSESS" if missing_requirement else "MET")
    assert result["proposed_total_score"] == (None if missing_requirement else 10)
    assert len(item["requirement_results"]) == (2 if missing_requirement else 1)
    assert result["human_review_required_before_publication"] is True
