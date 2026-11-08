"""A paired preparation must share upstream evidence without reading gold labels."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from research.p2_comparison import runner


ROOT = Path(__file__).resolve().parents[2]
RUBRIC = {
    "schema_version": 1, "rubric_id": "comparison-test", "version": "1", "max_score": 10,
    "metadata_not_for_inference": "NOT_SENT_TO_MODEL",
    "criteria": [{"criterion_id": "C", "title": "Completed evaluation", "weight": 10,
                  "checklists": [{"checklist_id": "C.1", "mode": "LOCAL",
                                  "statement": "The report describes completed interviews.",
                                  "requirements": [{"requirement_id": "interviews",
                                                    "description": "Interviews were completed.",
                                                    "any_of": ["completed interviews"]}]}]}],
}


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    private = tmp_path / "var"
    private.mkdir()
    monkeypatch.setattr(runner, "VAR_ROOT", private)
    monkeypatch.setattr(runner, "PROTECTED_PACKET", tmp_path / "pending/v2")
    monkeypatch.setattr(runner, "PROTECTED_SOURCE", tmp_path / "pending-source")
    report = tmp_path / "report.txt"
    report.write_text("The researchers completed interviews with six participants.\n\nThe report explains the resulting interface changes.")
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps(RUBRIC))
    configs = {}
    for name in runner.METHODS:
        path = tmp_path / f"{name}.json"
        path.write_bytes((ROOT / "research/configs/p2-comparison" / f"{name}.json").read_bytes())
        configs[name] = path
    return {"report": report, "rubric": rubric, "configs": configs, "private": private}


def prepare(inputs, name="prepared"):
    out = inputs["private"] / name
    result = runner.prepare_comparison(
        report_path=inputs["report"], rubric_path=inputs["rubric"],
        one_step_config=inputs["configs"]["one-step"], two_step_config=inputs["configs"]["two-step"],
        output_dir=out, cohort="AUTHOR_WRITTEN_SYNTHETIC",
    )
    return out, result


def factory_capture(seen, *, technical=False, mutate=False):
    def factory(method, model, policy):
        assert policy["citation_audit"] is (method == "two-step")
        assert policy["max_citations_per_requirement"] == 3
        class Transport:
            def request(self, verb, path, payload=None, **kwargs):
                if path == "/api/tags":
                    return {"models": [{"name": model["model"], "digest": model["digest"]}]}
                if path == "/api/show":
                    return {"details": {"format": "gguf"}, "template": "test template", "model_info": {}}
                assert path == "/api/chat"
                if technical:
                    raise TimeoutError()
                data = json.loads(payload["messages"][-1]["content"])
                seen.setdefault("model_inputs_" + method, []).append(deepcopy(data))
                if "evidence_passages" in data:
                    unit_id = data["evidence_passages"][0]["units"][0]["unit_id"]
                    rows = [{"requirement_id": r["requirement_id"], "evidence": [{"unit_id": unit_id}]}
                            for r in data["requirements"]]
                    if method == "one-step":
                        for row in rows:
                            row.update(relation="SUPPORTED", rationale="The selected unit reports completed interviews.")
                    prompt, generated = (100, 10) if method == "one-step" else (80, 8)
                else:
                    rows = [{"requirement_id": r["requirement_id"], "relation": "SUPPORTED",
                             "rationale": "The selected unit reports completed interviews.",
                             "used_unit_ids": [r["selected_units"][0]["unit_id"]]} for r in data["requirements"]]
                    prompt, generated = 20, 4
                content = {"checklist_id": data["checklist_id"], "requirements": rows}
                return {"model": model["model"], "done": True, "done_reason": "stop",
                        "prompt_eval_count": prompt, "eval_count": generated,
                        "message": {"content": json.dumps(content)}}
        verifier = runner.LlmAssessmentVerifier(model, policy, transport=Transport())
        original = verifier.verify
        def verify(checklist, pack):
            seen.setdefault(method, []).append({"checklist": deepcopy(checklist),
                                               "pack": runner._serialized_pack(pack)})
            assert "NOT_SENT_TO_MODEL" not in json.dumps(seen[method][-1])
            if mutate:
                pack[0].record["excerpt"] = "mutated"
            return original(checklist, pack)
        verifier.verify = verify
        return verifier
    return factory


def test_checked_configs_have_same_model_context_budget_and_explicit_citation_cap(inputs):
    pair = runner.configuration_pair(inputs["configs"]["one-step"], inputs["configs"]["two-step"])
    a, b = pair.values()
    assert a["models"] == b["models"]
    assert a["documents"] == b["documents"]
    assert a["pipeline2"]["evidence_context"] == b["pipeline2"]["evidence_context"]


@pytest.mark.parametrize("field,value", [("num_predict", 1536), ("seed", 9),
                                         ("max_citations_per_requirement", 2), ("num_ctx", 16384)])
def test_budget_or_citation_confound_rejected(inputs, field, value):
    path = inputs["configs"]["two-step"]
    config = json.loads(path.read_text())
    config["pipeline2"]["llm_verification"][field] = value
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        runner.configuration_pair(inputs["configs"]["one-step"], path)


def test_model_difference_rejected(inputs):
    path = inputs["configs"]["two-step"]
    config = json.loads(path.read_text())
    config["models"]["assessment_verifier"]["digest"] = "sha256:" + "a" * 64
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="differ"):
        runner.configuration_pair(inputs["configs"]["one-step"], path)


def test_prepare_does_not_construct_or_call_model(inputs, monkeypatch):
    monkeypatch.setattr(runner.LlmAssessmentVerifier, "__init__", lambda *a, **kw: pytest.fail("prepare contacted model"))
    out, result = prepare(inputs)
    assert result["status"] == "PREPARED_NO_MODEL_CALLS_NOT_FROZEN_GOLD"
    manifest = json.loads((out / "preparation-manifest.json").read_text())
    common = json.loads((out / "common-evidence.json").read_text())
    assert manifest["model_run"] is False and manifest["gold_or_annotation_input"] is False
    assert manifest["formal_pack_approval"] is False and manifest["same_citation_cap"] == 3
    assert common["items"][0]["unit_count"] > 0
    assert "NOT_SENT_TO_MODEL" not in json.dumps(common)


def test_both_methods_receive_identical_frozen_pack_and_unit_catalog(inputs):
    prepared, _ = prepare(inputs)
    seen = {}
    result = runner.run_prepared_development(prepared_dir=prepared, output_dir=inputs["private"] / "run",
                                             verifier_factory=factory_capture(seen))
    assert seen["one-step"] == seen["two-step"]
    assert seen["model_inputs_one-step"][0] == seen["model_inputs_two-step"][0]
    assert "evidence_passages" not in seen["model_inputs_two-step"][1]
    assert result["same_upstream_evidence_verified"] is True
    assert result["accuracy_computed"] is False and result["real_model_execution"] is False
    assert result["methods"]["one-step"]["actual_model_calls"] == 1
    assert result["methods"]["two-step"]["actual_model_calls"] == 2
    # Top-level selection telemetry must not be counted a second time.
    assert result["methods"]["two-step"]["prompt_tokens_known"] == 100
    assert result["methods"]["two-step"]["generated_tokens_known"] == 12


def test_technical_ca_is_abstention_not_semantic_ca(inputs):
    prepared, _ = prepare(inputs)
    out = inputs["private"] / "technical"
    result = runner.run_prepared_development(prepared_dir=prepared, output_dir=out,
                                             verifier_factory=factory_capture({}, technical=True))
    assert result["methods"]["one-step"]["technical_abstentions"] == 1
    assert result["methods"]["one-step"]["accepted_labels"] == {}
    row = json.loads((out / "one-step-results.json").read_text())["items"][0]
    assert row["accepted_label"] is None
    assert row["raw_result"]["checklist_outcome"] == "CANNOT_ASSESS"


def test_mutating_verifier_cannot_change_input_for_other_method(inputs):
    prepared, _ = prepare(inputs)
    with pytest.raises(ValueError, match="mutated"):
        runner.run_prepared_development(prepared_dir=prepared, output_dir=inputs["private"] / "mutating",
                                        verifier_factory=factory_capture({}, mutate=True))


def test_changed_frozen_pack_rejects_before_factory(inputs):
    prepared, _ = prepare(inputs)
    path = prepared / "common-evidence.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="frozen common evidence"):
        runner.run_prepared_development(prepared_dir=prepared, output_dir=inputs["private"] / "tampered",
                                        verifier_factory=lambda *args: pytest.fail("tampered input reached model"))


def test_new_annotation_body_copy_is_blocked_before_parsing(inputs, monkeypatch):
    listing = runner.PROTECTED_PACKET / "common/DANH_SACH_15_BAI.csv"
    listing.parent.mkdir(parents=True)
    listing.write_text("body_sha256\n" + hashlib.sha256(inputs["report"].read_bytes()).hexdigest() + "\n")
    monkeypatch.setattr(runner, "parse_document_bounded", lambda *a, **kw: pytest.fail("pending body parsed"))
    with pytest.raises(ValueError, match="pending-annotation body"):
        prepare(inputs)


def test_no_implicit_live_model_execution(inputs, monkeypatch):
    prepared, _ = prepare(inputs)
    monkeypatch.setattr(runner.LlmAssessmentVerifier, "__init__", lambda *a, **kw: pytest.fail("implicit real model"))
    with pytest.raises(ValueError, match="allow-real-model"):
        runner.run_prepared_development(prepared_dir=prepared, output_dir=inputs["private"] / "implicit")


def test_prepare_refuses_overwrite_and_nonprivate_output(inputs):
    prepare(inputs)
    with pytest.raises(FileExistsError):
        prepare(inputs)
    with pytest.raises(ValueError, match="private var"):
        runner.prepare_comparison(report_path=inputs["report"], rubric_path=inputs["rubric"],
            one_step_config=inputs["configs"]["one-step"], two_step_config=inputs["configs"]["two-step"],
            output_dir=inputs["report"].parent / "outside", cohort="AUTHOR_WRITTEN_SYNTHETIC")


def test_cli_prepare_is_explicit_no_model_action(inputs, monkeypatch, capsys):
    monkeypatch.setattr(runner.LlmAssessmentVerifier, "__init__", lambda *a, **kw: pytest.fail("CLI prepare contacted model"))
    assert runner.main(["prepare", "--report", str(inputs["report"]), "--rubric", str(inputs["rubric"]),
        "--one-step-config", str(inputs["configs"]["one-step"]), "--two-step-config", str(inputs["configs"]["two-step"]),
        "--output-dir", str(inputs["private"] / "cli"), "--cohort", "AUTHOR_WRITTEN_SYNTHETIC", "--prepare-only"]) == 0
    assert "PREPARED_NO_MODEL_CALLS" in capsys.readouterr().out
