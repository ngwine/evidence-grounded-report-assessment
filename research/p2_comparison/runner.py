"""Freeze one common evidence pack before comparing one- and two-step verifiers.

No annotation/gold input is accepted. The new fifteen-essay annotation packet is
protected by path and original-body hashes; this tool is for synthetic/old DEV
preparation while those independent labels are pending.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Callable, Mapping

from research.core_mvp import assessment
from research.core_mvp.bounded_documents import ParseLimits, parse_document_bounded
from research.core_mvp.contracts import validate_assessment_report
from research.core_mvp.llm_assessment import LlmAssessmentVerifier, _model_config, _source_unit_catalog
from research.core_mvp.rubric import compile_rubric
from research.schema_validation import validate_json_schema

ROOT = Path(__file__).resolve().parents[2]
VAR_ROOT = ROOT / "var"
METHODS = ("one-step", "two-step")
COHORTS = ("AUTHOR_WRITTEN_SYNTHETIC", "PREVIOUSLY_INSPECTED_DEV")
LABELS = {"MET", "UNMET", "CANNOT_ASSESS"}
MAX_JSON_BYTES = 64 * 1024 * 1024
PROTECTED_PACKET = ROOT / "var/paper/p2-annotation-2026-11-05/v2"
PROTECTED_SOURCE = ROOT / "var/datasets/raw/sefora-2026-10-30/source/SEFORA/Batch_1/Course_1/Class_2/Essay_1"


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Any:
    if path.is_symlink() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Comparison JSON is unavailable or exceeds its bound")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate comparison JSON key")
            result[key] = value
        return result
    def reject(_: str):
        raise ValueError("Non-finite comparison JSON")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=reject)


def _write(path: Path, value: Any) -> None:
    with path.open("xb") as stream:
        stream.write(_canonical(value))
    path.chmod(0o600)


def _private_output(path: Path) -> Path:
    path = path.expanduser().absolute()
    root = VAR_ROOT.absolute()
    if ".." in path.parts or path == root or not path.is_relative_to(root):
        raise ValueError("Comparison outputs must be below the private var directory")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Comparison output cannot use symlinks")
    if path.exists():
        raise FileExistsError("Use a new comparison directory; prior attempts are retained")
    path.mkdir(parents=True, mode=0o700)
    return path


def _protect_pending_input(report: Path) -> None:
    """Known new-body hashes come from metadata only; never inspect their text."""
    report = report.resolve(strict=True)
    if not report.is_file() or report.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Development report is unavailable or exceeds its input bound")
    if (report.is_relative_to(PROTECTED_PACKET.parent)
            or report.is_relative_to(PROTECTED_SOURCE)):
        raise ValueError("The pending fifteen-essay packet is excluded from development comparisons")
    listing = PROTECTED_PACKET / "common/DANH_SACH_15_BAI.csv"
    if listing.is_file():
        import csv
        with listing.open(encoding="utf-8-sig", newline="") as stream:
            protected_hashes = {row["body_sha256"] for row in csv.DictReader(stream)}
        if _sha(report) in protected_hashes:
            raise ValueError("A copied pending-annotation body is excluded from development comparisons")


def configuration_pair(one_step: Path, two_step: Path) -> dict[str, dict[str, Any]]:
    """Permit only the intentional workflow switch and run identities to differ."""
    pair = {"one-step": _read_json(Path(one_step)), "two-step": _read_json(Path(two_step))}
    normalized = {}
    for name, config in pair.items():
        if not isinstance(config, dict) or config.get("schema_version") != 1:
            raise ValueError("Comparison config requires schema_version 1")
        policy = config.get("pipeline2", {}).get("llm_verification", {})
        if (policy.get("enabled") is not True or policy.get("citation_mode") != "source_units"
                or policy.get("citation_audit") is not (name == "two-step")
                or policy.get("max_citations_per_requirement") != 3):
            raise ValueError("Comparison methods require their declared workflow and the same explicit citation cap 3")
        model = config.get("models", {}).get("assessment_verifier", {})
        if not isinstance(model.get("digest"), str) or not model["digest"].startswith("sha256:"):
            raise ValueError("Comparison requires a pinned local model digest")
        _model_config(model)
        resolved = assessment.validate_assessment_config(config["pipeline2"])
        if resolved["dense_enabled"] or resolved["reranker_enabled"]:
            raise ValueError("This preparation runner supports the shared BM25 context only")
        current = deepcopy(config)
        current.pop("config_id", None)
        current.pop("experiment_id", None)
        current["pipeline2"]["llm_verification"].pop("citation_audit")
        normalized[name] = current
    if normalized["one-step"] != normalized["two-step"]:
        raise ValueError("Comparison configs differ beyond the declared workflow switch")
    return pair


def _serialized_pack(pack) -> list[dict[str, Any]]:
    return [{"record": deepcopy(entry.record), "chunk": deepcopy(entry.chunk)} for entry in pack]


def _rehydrate_pack(values):
    pack = [assessment._ScopedEvidence(deepcopy(v["record"]), deepcopy(v["chunk"])) for v in values]
    LlmAssessmentVerifier._scope(pack)
    return pack


def _usage(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    """Do not double-count selection telemetry copied to the top-level record."""
    if "selection" in diagnostics:
        stages = [diagnostics["selection"]]
        audit = diagnostics.get("citation_audit", {})
        if audit.get("status") != "SKIPPED_EMPTY_SELECTION":
            stages.append(audit)
    else:
        stages = [diagnostics]
    complete = True
    prompt, output = 0, 0
    for stage in stages:
        for key in ("prompt_eval_count", "eval_count"):
            value = stage.get(key)
            if type(value) is not int or value < 0:
                complete = False
            elif key == "prompt_eval_count":
                prompt += value
            else:
                output += value
    return {"prompt_tokens_known": prompt, "generated_tokens_known": output, "telemetry_complete": complete}


def _contract_report(compiled, common_items, rows, metadata, configuration):
    """Reuse code-owned scoring and the ordinary report contracts, not model grades."""
    checklist_results = [{
        "criterion_id": item["criterion_id"], "checklist_id": item["checklist"]["checklist_id"],
        "statement": item["checklist"]["statement"], "mode": item["checklist"]["mode"],
        "importance": item["checklist"]["importance"], "retrieval": item["retrieval"],
        **row["raw_result"],
    } for item, row in zip(common_items, rows)]
    criteria, total, subtotal = assessment._score_criteria(compiled, checklist_results)
    report = {
        "schema_version": 1, "pipeline": "controlled-p2-verifier-development-comparison-v1",
        "research_status": "DEVELOPMENT_COMPARISON_NOT_INDEPENDENT_GRADING_EVALUATION",
        "verification_method": "LOCAL_LLM_REQUIREMENT_VERIFIER_V1",
        "verification_metadata": deepcopy(metadata), "human_review_required_before_publication": True,
        "compiled_rubric": compiled, "configuration": configuration,
        "checklist_results": checklist_results, "criterion_results": criteria,
        "checklist_outcome_counts": dict(Counter(r["checklist_outcome"] for r in checklist_results)),
        "proposed_total_score": total, "assessable_subtotal": subtotal, "max_score": compiled["max_score"],
        "requires_lecturer_review": total is None or any(c["requires_lecturer_review"] for c in criteria),
        "limitations": ["Same upstream pack, differing verifier architecture; not a single-stage causal ablation.",
                        "Code-owned proposal scores are not SEFORA teacher-score agreement.",
                        "Source-bound citations do not prove semantic correctness."],
    }
    validate_assessment_report(report)
    validate_json_schema(report, kind="assessment")
    return report


def prepare_comparison(
    *, report_path: Path, rubric_path: Path, one_step_config: Path,
    two_step_config: Path, output_dir: Path, cohort: str,
) -> dict[str, Any]:
    """Parse/retrieve once and freeze packs without loading a model or labels."""
    if cohort not in COHORTS:
        raise ValueError("Preparation is restricted to synthetic or previously inspected DEV inputs")
    report_path, rubric_path = Path(report_path).resolve(strict=True), Path(rubric_path).resolve(strict=True)
    _protect_pending_input(report_path)
    pair = configuration_pair(Path(one_step_config), Path(two_step_config))
    config = pair["one-step"]
    compiled = compile_rubric(_read_json(rubric_path))
    if any(c["mode"] != "LOCAL" for criterion in compiled["criteria"] for c in criterion["checklists"]):
        raise ValueError("This controlled preparation supports LOCAL checklists only")
    source_hashes = {"report": _sha(report_path), "rubric": _sha(rubric_path),
                     "one-step": _sha(Path(one_step_config)), "two-step": _sha(Path(two_step_config))}
    document = config.get("documents", {})
    parsed = parse_document_bounded(
        report_path, role="student-report", max_tokens=document.get("max_tokens", 220),
        min_tokens=document.get("min_tokens", 30), limits=ParseLimits.from_config(document.get("resource_limits")),
    )
    chunks = list(parsed.chunks)
    if not chunks:
        raise ValueError("Comparison needs nonempty parsed report chunks")
    report_map, report_id, version = assessment._report_scope(chunks)
    resolved = assessment.validate_assessment_config(config["pipeline2"])
    items = []
    for criterion in compiled["criteria"]:
        for checklist in criterion["checklists"]:
            candidates, retrieval = assessment._rank_local(checklist, chunks, config=resolved, encoder=None, reranker=None)
            if "evidence_context" in resolved:
                candidates, retrieval = assessment._bounded_report_context(candidates, retrieval, chunks, resolved["evidence_context"])
            pack = assessment._validated_evidence_pack(candidates, report_map, report_id=report_id, report_version=version)
            passages, catalog = _source_unit_catalog(LlmAssessmentVerifier._scope(pack))
            serialized = _serialized_pack(pack)
            items.append({"criterion_id": criterion["criterion_id"], "checklist": checklist,
                          "retrieval": retrieval, "evidence_pack": serialized,
                          "evidence_pack_sha256": _digest(serialized), "source_units": passages,
                          "source_units_sha256": _digest(passages), "unit_count": len(catalog)})
    if len(items) > resolved["llm_verification"]["max_checklists"]:
        raise ValueError("Comparison exceeds the common checklist budget")
    output = _private_output(Path(output_dir))
    inputs = output / "inputs"
    inputs.mkdir(mode=0o700)
    shutil.copyfile(report_path, inputs / ("report" + report_path.suffix.lower()))
    shutil.copyfile(rubric_path, inputs / "authored-rubric.json")
    _write(inputs / "compiled-rubric.json", compiled)
    _write(output / "common-evidence.json", {"schema_version": 1, "items": items})
    methods_dir = output / "methods"
    methods_dir.mkdir(mode=0o700)
    for name, method in pair.items():
        _write(methods_dir / f"{name}.json", method)
    # Record the code actually constructing the comparison, including its model protocols.
    code_paths = [Path(__file__), *sorted((ROOT / "research/core_mvp").glob("*.py")),
                  ROOT / "research/offline_retrieval/bm25.py", ROOT / "research/offline_retrieval/common.py",
                  ROOT / "services/backend/src/kltn_ai/integrations/indexing/chunking.py",
                  ROOT / "services/backend/src/kltn_ai/integrations/parsing/text_normalization.py"]
    code_hashes = {str(path.relative_to(ROOT)): _sha(path) for path in code_paths}
    snapshot = output / "code-snapshot"
    for path in code_paths:
        destination = snapshot / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    receipt = {
        "schema_version": 1, "status": "PREPARED_NO_MODEL_CALLS_NOT_FROZEN_GOLD",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "cohort_declared_by_caller": cohort,
        "formal_pack_approval": False, "independent_holdout_claim": False, "model_run": False,
        "comparison_unit": "Same parsed/retrieved evidence pack and source-unit catalog per checklist",
        "workflows": {"one-step": "RELATION_AND_CITATIONS_IN_ONE_CALL", "two-step": "SELECT_UNITS_THEN_VERIFY_SELECTED_ONLY"},
        "interpretation": "Architecture bundle comparison; differing selected units are method behavior. Does not isolate auditor causality.",
        "budget_regime": "SAME_PER_CALL_BUDGET_NOT_TOTAL_COMPUTE_MATCHED",
        "call_limits_per_checklist": {"one-step": 1, "two-step": 2},
        "same_citation_cap": 3, "gold_or_annotation_input": False,
        "execution_order": sorted(METHODS, key=lambda name: hashlib.sha256(
            (str(config.get("seed", 0)) + ":" + source_hashes["report"] + ":" + name).encode()).hexdigest()),
        "execution_order_policy": "Deterministic per-report hash order; hardware/cache effects remain uncontrolled",
        "original_document_completeness_asserted": False,
        "source_hashes": source_hashes, "code_hashes": code_hashes,
        "input_hashes": {str(p.relative_to(output)): _sha(p) for p in sorted(inputs.iterdir())},
        "common_evidence_sha256": _sha(output / "common-evidence.json"),
        "method_hashes": {name: _sha(methods_dir / f"{name}.json") for name in METHODS},
        "checklists": len(items), "shared_pack_receipts": [{"checklist_id": item["checklist"]["checklist_id"],
            "pack_sha256": item["evidence_pack_sha256"], "catalog_sha256": item["source_units_sha256"]} for item in items],
    }
    if source_hashes != {"report": _sha(report_path), "rubric": _sha(rubric_path),
                         "one-step": _sha(Path(one_step_config)), "two-step": _sha(Path(two_step_config))}:
        raise ValueError("Comparison source changed during preparation")
    _write(output / "preparation-manifest.json", receipt)
    return {"output_dir": str(output), "status": receipt["status"], "checklists": len(items),
            "common_evidence_sha256": receipt["common_evidence_sha256"]}


def run_prepared_development(
    *, prepared_dir: Path, output_dir: Path,
    verifier_factory: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Any] | None = None,
    allow_real_model: bool = False,
) -> dict[str, Any]:
    """Explicit DEV replay only. Fake injection is supported for tests; no gold is read."""
    prepared = Path(prepared_dir).resolve(strict=True)
    manifest = _read_json(prepared / "preparation-manifest.json")
    if manifest.get("cohort_declared_by_caller") not in COHORTS or manifest.get("model_run") is not False:
        raise ValueError("This runner accepts its unexecuted development preparations only")
    if verifier_factory is None and not allow_real_model:
        raise ValueError("Actual model execution requires explicit --allow-real-model")
    common_path = prepared / "common-evidence.json"
    if _sha(common_path) != manifest["common_evidence_sha256"]:
        raise ValueError("The frozen common evidence changed")
    for relative, digest in manifest["input_hashes"].items():
        path = prepared / relative
        if not path.resolve().is_relative_to(prepared) or _sha(path) != digest:
            raise ValueError("A frozen comparison input changed")
        if path.name.startswith("report."):
            _protect_pending_input(path)
    for relative, digest in manifest["code_hashes"].items():
        if not (ROOT / relative).resolve().is_relative_to(ROOT) or _sha(ROOT / relative) != digest:
            raise ValueError("Comparison implementation changed; prepare a new version")
    configs = configuration_pair(prepared / "methods/one-step.json", prepared / "methods/two-step.json")
    compiled = _read_json(prepared / "inputs/compiled-rubric.json")
    order = manifest.get("execution_order")
    if not isinstance(order, list) or sorted(order) != sorted(METHODS):
        raise ValueError("Comparison execution order is invalid")
    for name in order:
        if _sha(prepared / "methods" / f"{name}.json") != manifest["method_hashes"][name]:
            raise ValueError("A frozen method config changed")
    items = _read_json(common_path)["items"]
    for item in items:
        if _digest(item["evidence_pack"]) != item["evidence_pack_sha256"]:
            raise ValueError("Common evidence pack identity changed")
        passages, _ = _source_unit_catalog(LlmAssessmentVerifier._scope(_rehydrate_pack(item["evidence_pack"])))
        if _digest(passages) != item["source_units_sha256"] or passages != item["source_units"]:
            raise ValueError("Common source-unit catalog changed")
    out = _private_output(Path(output_dir))
    results, summaries = {}, {}
    for name in order:
        config = configs[name]
        model, policy = config["models"]["assessment_verifier"], config["pipeline2"]["llm_verification"]
        verifier = (verifier_factory(name, deepcopy(model), deepcopy(policy)) if verifier_factory else
                    LlmAssessmentVerifier(model, policy))
        if verifier.metadata.get("source_unit_policy", {}).get("max_citations_per_requirement") != 3:
            raise ValueError("Verifier runtime does not honor the matched citation cap")
        method_rows = []
        for item in items:
            pack = _rehydrate_pack(item["evidence_pack"])
            checklist = deepcopy(item["checklist"])
            before = _digest(_serialized_pack(pack))
            calls_before = getattr(verifier, "_model_calls", None)
            started = time.monotonic()
            result = verifier.verify(checklist, pack)
            calls_after = getattr(verifier, "_model_calls", None)
            if _digest(_serialized_pack(pack)) != before or checklist != item["checklist"]:
                raise ValueError("Verifier mutated the frozen common input")
            label = result.get("checklist_outcome")
            diagnostics = result.get("llm_verification", {})
            status = diagnostics.get("status")
            if label not in LABELS or status not in {"VALIDATED", "WITHHELD"}:
                raise ValueError("Verifier returned an invalid comparison decision")
            method_rows.append({"checklist_id": checklist["checklist_id"],
                "criterion_id": item["criterion_id"], "common_pack_sha256": before,
                "common_catalog_sha256": item["source_units_sha256"],
                "accepted_label": label if status == "VALIDATED" else None,
                "decision_status": "SEMANTIC_DECISION" if status == "VALIDATED" else "TECHNICAL_ABSTENTION",
                "model_calls_observed": (calls_after - calls_before
                    if type(calls_before) is int and type(calls_after) is int and calls_after >= calls_before else None),
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "token_usage": _usage(diagnostics), "raw_result": result})
        results[name] = method_rows
        report = _contract_report(compiled, items, method_rows, verifier.metadata,
                                  assessment.validate_assessment_config(config["pipeline2"]))
        _write(out / f"{name}-assessment-report.json", report)
        _write(out / f"{name}-results.json", {"method": name, "items": method_rows,
                                              "verification_metadata": deepcopy(verifier.metadata)})
        calls = [r["model_calls_observed"] for r in method_rows]
        summaries[name] = {"checklists": len(method_rows),
            "accepted_labels": dict(Counter(r["accepted_label"] for r in method_rows if r["accepted_label"] is not None)),
            "technical_abstentions": sum(r["accepted_label"] is None for r in method_rows),
            "actual_model_calls": sum(calls) if all(type(v) is int for v in calls) else None,
            "prompt_tokens_known": sum(r["token_usage"]["prompt_tokens_known"] for r in method_rows),
            "generated_tokens_known": sum(r["token_usage"]["generated_tokens_known"] for r in method_rows),
            "token_telemetry_complete": all(r["token_usage"]["telemetry_complete"] for r in method_rows),
            "elapsed_seconds": round(sum(r["elapsed_seconds"] for r in method_rows), 6)}
    if _sha(common_path) != manifest["common_evidence_sha256"]:
        raise ValueError("Frozen evidence changed during execution")
    for relative, digest in manifest["input_hashes"].items():
        if _sha(prepared / relative) != digest:
            raise ValueError("Frozen comparison input changed during execution")
    for name in METHODS:
        if _sha(prepared / "methods" / f"{name}.json") != manifest["method_hashes"][name]:
            raise ValueError("Frozen method config changed during execution")
    for relative, digest in manifest["code_hashes"].items():
        if _sha(ROOT / relative) != digest:
            raise ValueError("Comparison implementation changed during execution")
    shared = all(a["common_pack_sha256"] == b["common_pack_sha256"]
                 and a["common_catalog_sha256"] == b["common_catalog_sha256"]
                 for a, b in zip(results["one-step"], results["two-step"]))
    receipt = {"status": "DEV_REPLAY_COMPLETE_NOT_ANNOTATED_EVALUATION", "same_upstream_evidence_verified": shared,
               "methods": summaries, "gold_or_annotation_input": False, "accuracy_computed": False,
               "real_model_execution": verifier_factory is None, "execution_order": order,
               "budget_regime": manifest["budget_regime"],
               "preparation_manifest_sha256": _sha(prepared / "preparation-manifest.json")}
    _write(out / "comparison-summary.json", receipt)
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Freeze common evidence; no model calls")
    prep.add_argument("--report", type=Path, required=True)
    prep.add_argument("--rubric", type=Path, required=True)
    prep.add_argument("--one-step-config", type=Path, default=ROOT / "research/configs/p2-comparison/one-step.json")
    prep.add_argument("--two-step-config", type=Path, default=ROOT / "research/configs/p2-comparison/two-step.json")
    prep.add_argument("--output-dir", type=Path, required=True)
    prep.add_argument("--cohort", choices=COHORTS, required=True)
    prep.add_argument("--prepare-only", action="store_true", help="Explicit reminder; prepare never executes a model")
    run = sub.add_parser("run-development", help="Explicit replay of synthetic/old DEV only")
    run.add_argument("--prepared-dir", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--allow-real-model", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_comparison(report_path=args.report, rubric_path=args.rubric,
            one_step_config=args.one_step_config, two_step_config=args.two_step_config,
            output_dir=args.output_dir, cohort=args.cohort)
    else:
        result = run_prepared_development(prepared_dir=args.prepared_dir, output_dir=args.output_dir,
                                         allow_real_model=args.allow_real_model)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
