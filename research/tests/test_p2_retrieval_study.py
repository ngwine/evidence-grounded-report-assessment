"""Retrieval study integrity and fair input contrasts on synthetic DEV only."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from research.core_mvp.bounded_documents import parse_document_bounded
from research.core_mvp.llm_assessment import LlmAssessmentVerifier
from research.p2_comparison import retrieval_study as study
from research.p2_comparison import runner as base

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "VAR_ROOT", tmp_path)
    root = tmp_path / "source"
    (root / "cases/case-1").mkdir(parents=True)
    (root / "inputs").mkdir()
    body = root / "cases/case-1/body.txt"
    body.write_text("Researchers completed interviews with participants and improved the system. " * 10
        + "\n\n" + "The background explains climate, lakes, oceans and clouds. " * 10
        + "\n\n" + "The appendix describes gardens, greenhouses, plants and irrigation. " * 10)
    parsed = parse_document_bounded(body, role="student-report", max_tokens=35, min_tokens=1)
    assert len(parsed.chunks) > 1
    rubric = {"schema_version": 1, "rubric_id": "synthetic", "version": "1", "max_score": 1,
        "criteria": [{"criterion_id": "C", "title": "Interviews", "weight": 1,
            "checklists": [{"checklist_id": "CLM001", "mode": "LOCAL",
                "statement": "Interviews were completed.", "requirements": [{"requirement_id": "R",
                    "description": "Completed interviews are described.", "any_of": ["completed interviews"]}]}]}]}
    base._write(root / "inputs/authored-rubric.json", rubric)
    base._write(root / "cases/case-1/common-evidence.json", {"parsed_chunks": list(parsed.chunks)})
    reference = {"rows": [{"item_id": "case-1-CLM001", "case_id": "case-1", "label": "MET", "state": "VALID",
        "rationale": "REFERENCE_ONLY_SECRET_DO_NOT_PASS_TO_MODEL", "metadata": {
            "report_id": "original-report", "report_version": "original-version", "body_sha256": base._sha(body),
            "rubric_id": "original-rubric", "rubric_version": "1", "checklist_id": "CLM001"}}]}
    base._write(root / "reference.json", reference)
    base._write(root / "preparation-manifest.json", {
        "design": "SINGLE_ANNOTATOR_AI_ASSISTED_EXPLORATORY", "model_called": False,
        "approved_gold_claim": False, "independent_holdout_claim": False,
        "cases": [{"case_id": "case-1", "body_sha256": base._sha(body)}],
        "code_hashes": {"old-code-never-executed.py": "historical"},
        "locked_files": {str(p.relative_to(root)): base._sha(p) for p in root.rglob("*") if p.is_file()}})
    config = base._read_json(ROOT / "research/configs/p2-comparison/one-step.json")
    config["pipeline2"]["top_k"] = 1
    config_path = tmp_path / "config.json"
    base._write(config_path, config)
    return {"source_prepared_dir": root, "config_path": config_path,
            "output_dir": tmp_path / "prepared", "cohort": "AUTHOR_WRITTEN_SYNTHETIC"}


def factory(seen, *, technical=False, interrupt=False):
    def build(method, model, policy):
        class Transport:
            def request(self, verb, path, payload=None, **kwargs):
                if path == "/api/tags":
                    return {"models": [{"name": model["model"], "digest": model["digest"]}]}
                if path == "/api/show":
                    return {"details": {"format": "gguf"}, "template": "Synthetic test template", "model_info": {}}
                assert path == "/api/chat"
                if interrupt:
                    raise KeyboardInterrupt()
                if technical:
                    raise TimeoutError()
                data = json.loads(payload["messages"][-1]["content"])
                seen.setdefault(method, []).append(deepcopy(data))
                assert "REFERENCE_ONLY_SECRET" not in json.dumps(data)
                unit = data["evidence_passages"][0]["units"][0]["unit_id"]
                output = {"checklist_id": data["checklist_id"], "requirements": [{
                    "requirement_id": r["requirement_id"], "relation": "SUPPORTED",
                    "rationale": "The cited text describes completed interviews.", "evidence": [{"unit_id": unit}]}
                    for r in data["requirements"]]}
                return {"model": model["model"], "done": True, "done_reason": "stop",
                    "prompt_eval_count": 100, "eval_count": 20, "message": {"content": json.dumps(output)}}
        return LlmAssessmentVerifier(model, policy, transport=Transport())
    return build


def test_prepare_different_evidence_same_verifier_and_explicit_unavailable_graph(source):
    result = study.prepare_retrieval_study(**source)
    assert result["methods"] == ["no-retrieval", "local-bm25"]
    assert result["unavailable_methods"][study.GRAPH]["status"] == "NOT_IMPLEMENTED_NOT_RUN"
    root = source["output_dir"]
    full = base._read_json(root / "cases/case-1/no-retrieval.json")["items"][0]
    local = base._read_json(root / "cases/case-1/local-bm25.json")["items"][0]
    assert len(full["evidence_pack"]) > len(local["evidence_pack"]) == 1
    assert full["retrieval"]["retrieval_methods"] == []
    assert local["retrieval"]["retrieval_methods"] == ["bm25"]
    assert full["evidence_pack_sha256"] != local["evidence_pack_sha256"]
    assert "REFERENCE_ONLY_SECRET" not in json.dumps(full)
    definition = base._read_json(root / "inputs/verifier-definition.json")
    assert definition["model_called"] is False
    assert definition["metadata"]["prompt_sha256"]
    assert all(p.stat().st_mode & 0o222 == 0 for p in root.rglob("*") if p.is_file())


def test_run_uses_frozen_distinct_packs_and_preserves_full_denominator(source, tmp_path):
    study.prepare_retrieval_study(**source)
    seen = {}
    args = {"prepared_dir": source["output_dir"], "output_dir": tmp_path / "run", "verifier_factory": factory(seen)}
    result = study.run_retrieval_study(**args)
    assert result["status"] == "COMPLETE_DEV_COMPARISON"
    assert set(seen) == set(study.METHODS)
    assert len(seen["no-retrieval"][0]["evidence_passages"]) > len(seen["local-bm25"][0]["evidence_passages"])
    before = deepcopy(seen)
    study.run_retrieval_study(**args)
    assert seen == before  # Completed requests are never called again.
    output = base._read_json(tmp_path / "run/metrics.json")
    assert set(output["methods"]) == set(study.METHODS)
    assert study.GRAPH not in output["methods"]
    assert output["independent_holdout_claim"] is False
    assert output["teacher_score_agreement_evaluated"] is False
    assert output["always_met_baseline"]["items"] == 1


def test_technical_failure_is_not_ca_and_stays_in_metrics(source, tmp_path):
    study.prepare_retrieval_study(**source)
    result = study.run_retrieval_study(prepared_dir=source["output_dir"], output_dir=tmp_path / "technical",
        verifier_factory=factory({}, technical=True))
    assert all(m["technical_abstentions"] == 1 for m in result["methods"].values())
    output = base._read_json(tmp_path / "technical/metrics.json")
    for method in output["methods"].values():
        assert method["items"] == method["technical_abstentions"] == 1
        assert method["reference_label_agreement"]["rate"] == 0
        assert method["predicted_label_counts"]["CANNOT_ASSESS"] == 0


def test_interrupted_call_is_never_retried(source, tmp_path):
    study.prepare_retrieval_study(**source)
    args = {"prepared_dir": source["output_dir"], "output_dir": tmp_path / "interrupted"}
    with pytest.raises(KeyboardInterrupt):
        study.run_retrieval_study(**args, verifier_factory=factory({}, interrupt=True))
    with pytest.raises(ValueError, match="refusing automatic retry"):
        study.run_retrieval_study(**args, verifier_factory=lambda *a: pytest.fail("Retried request"))


def test_no_retrieval_context_overflow_rejected_without_fallback(source):
    config = base._read_json(source["config_path"])
    config["pipeline2"]["evidence_context"]["max_chars"] = 20
    source["config_path"].write_bytes(base._canonical(config))
    with pytest.raises(ValueError, match="exceeds locked context"):
        study.prepare_retrieval_study(**source)
    assert not source["output_dir"].exists()


def test_frozen_input_tamper_rejected_before_runtime_creation(source, tmp_path):
    study.prepare_retrieval_study(**source)
    path = source["output_dir"] / "cases/case-1/no-retrieval.json"
    path.chmod(0o600)
    path.write_text('{}')
    with pytest.raises(ValueError, match="frozen retrieval-study input"):
        study.run_retrieval_study(prepared_dir=source["output_dir"], output_dir=tmp_path / "rejected",
            verifier_factory=lambda *a: pytest.fail("Runtime constructed"))


def test_new_code_hashes_not_original_execution_are_enforced(source, tmp_path, monkeypatch):
    study.prepare_retrieval_study(**source)
    original = study.base._sha
    monkeypatch.setattr(study.base, "_sha", lambda p: "changed" if Path(p) == Path(study.__file__) else original(p))
    with pytest.raises(ValueError, match="implementation changed"):
        study.run_retrieval_study(prepared_dir=source["output_dir"], output_dir=tmp_path / "rejected",
            verifier_factory=lambda *a: pytest.fail("Runtime constructed"))


def test_real_execution_requires_flag_before_any_runtime_or_output(source, tmp_path):
    with pytest.raises(ValueError, match="allow-real-model"):
        study.run_retrieval_study(prepared_dir=source["output_dir"], output_dir=tmp_path / "run")
    assert not (tmp_path / "run").exists()


def test_context_bundle_policy_is_frozen_and_sent_consistently(source, tmp_path):
    config = base._read_json(source["config_path"])
    config["pipeline2"]["llm_verification"]["source_unit_policy"] = "context_bundles_v1"
    source["config_path"].write_bytes(base._canonical(config))
    study.prepare_retrieval_study(**source)
    definition = base._read_json(source["output_dir"] / "inputs/verifier-definition.json")
    assert definition["metadata"]["source_unit_policy"]["version"] == "source-span-context-bundles-v1"
    seen = {}
    study.run_retrieval_study(prepared_dir=source["output_dir"], output_dir=tmp_path / "bundles",
        verifier_factory=factory(seen))
    assert "source_span_index" in seen["no-retrieval"][0]["evidence_passages"][0]["units"][0]
