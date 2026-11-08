"""Locked DEV retrieval comparison; semantic GRAPH remains explicitly unavailable.

This entry point consumes an already-inspected, immutable single-reference
preparation. It reuses its parsed reports and keeps references outside inference.
Changing the verifier requires a new preparation, never rewriting an old run.
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
import time
from typing import Any, Callable

from research.core_mvp import assessment
from research.core_mvp.contracts import validate_assessment_report
from research.core_mvp.llm_assessment import LlmAssessmentVerifier, _model_config, _source_unit_catalog
from research.core_mvp.rubric import compile_rubric
from research.p2_comparison import runner as base
from research.p2_comparison import single_reference_metrics as metrics
from research.schema_validation import validate_json_schema

DESIGN = "P2_RETRIEVAL_DEV_COMPARISON_V1"
METHODS = ("no-retrieval", "local-bm25")
GRAPH = "local-semantic-graph"
COHORTS = ("PREVIOUSLY_INSPECTED_DEV", "AUTHOR_WRITTEN_SYNTHETIC")


def _checked_file(root: Path, relative: str) -> Path:
    path = root / relative
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or ".." in Path(relative).parts or path.is_symlink()
            or not path.resolve().is_relative_to(root)):
        raise ValueError("Frozen input path escapes its preparation")
    return path


def _checked_source(path: Path) -> dict[str, Any]:
    manifest = base._read_json(path / "preparation-manifest.json")
    if (manifest.get("design") != "SINGLE_ANNOTATOR_AI_ASSISTED_EXPLORATORY"
            or manifest.get("model_called") is not False
            or manifest.get("approved_gold_claim") is not False
            or manifest.get("independent_holdout_claim") is not False):
        raise ValueError("Use a frozen single-reference preparation, explicitly declared DEV")
    for relative, checksum in manifest["locked_files"].items():
        if base._sha(_checked_file(path, relative)) != checksum:
            raise ValueError("A frozen source input changed")
    # Old implementation hashes are historical provenance, not this new run's
    # executable code. Its input bytes must match; new code is frozen below.
    return manifest


def _config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = base._read_json(path)
    resolved = assessment.validate_assessment_config(config["pipeline2"])
    if resolved["dense_enabled"] or resolved["reranker_enabled"]:
        raise ValueError("This DEV comparison implements BM25 LOCAL only; do not relabel it hybrid")
    if not resolved.get("llm_verification", {}).get("enabled"):
        raise ValueError("An explicit local LLM verifier policy is required")
    if resolved["llm_verification"].get("citation_mode") != "source_units":
        raise ValueError("This experiment requires code-owned source-unit citations")
    if "evidence_context" not in resolved:
        raise ValueError("No-retrieval needs an explicit bounded full-parsed-report context policy")
    _model_config(config["models"]["assessment_verifier"])
    return config, resolved


def _catalog(pack, policy):
    return _source_unit_catalog(LlmAssessmentVerifier._scope(pack),
        policy=policy.get("source_unit_policy", "sentence_units_v1"))


def _offline_verifier_definition(config, resolved):
    class OfflineTransport:
        def request(self, method, path, payload=None, **kwargs):
            if (method, path) != ("GET", "/api/tags"):
                raise AssertionError("Preparation cannot issue a model request")
            return {"models": []}
    verifier = LlmAssessmentVerifier(config["models"]["assessment_verifier"],
        resolved["llm_verification"], transport=OfflineTransport())
    keys = ("prompt_version", "prompt_sha256", "output_schema_version", "output_schema_sha256",
            "policy_sha256", "source_unit_policy", "citation_audit")
    return {"offline_only": True, "model_called": False,
        "metadata": {key: deepcopy(verifier.metadata[key]) for key in keys if key in verifier.metadata},
        "prompt": verifier.prompt, "output_schema": verifier.output_schema,
        "audit_prompt": verifier.audit_prompt if verifier.citation_audit else None,
        "audit_schema": verifier.audit_schema if verifier.citation_audit else None}


def _prepare_items(common, compiled, resolved, method):
    chunks = common["parsed_chunks"]
    report_map, report_id, report_version = assessment._report_scope(chunks)
    # Use the core's exact bound check, but refuse its ranked fallback: such a
    # fallback would silently turn the no-retrieval baseline into retrieval.
    all_candidates, full_context = assessment._bounded_report_context([], {}, chunks,
        resolved["evidence_context"])
    if not full_context["evidence_context"]["selected_all_report_chunks"]:
        raise ValueError("No-retrieval report exceeds locked context; no cropping or retrieval fallback")
    items = []
    for criterion in compiled["criteria"]:
        for checklist in criterion["checklists"]:
            if checklist["mode"] != "LOCAL":
                raise ValueError("Semantic GRAPH is not implemented; only LOCAL DEV checklists may execute")
            if method == "no-retrieval":
                candidates = deepcopy(all_candidates)
                retrieval = {"mode": "NO_RETRIEVAL", "retrieval_methods": [],
                    "reranked": False, "query": None, **full_context}
            else:
                candidates, retrieval = assessment._rank_local(checklist, chunks,
                    config=resolved, encoder=None, reranker=None)
            pack = assessment._validated_evidence_pack(candidates, report_map,
                report_id=report_id, report_version=report_version)
            passages, catalog = _catalog(pack, resolved["llm_verification"])
            serialized = base._serialized_pack(pack)
            items.append({"criterion_id": criterion["criterion_id"],
                "checklist": deepcopy(checklist), "retrieval": retrieval,
                "evidence_pack": serialized, "evidence_pack_sha256": base._digest(serialized),
                "source_units": passages, "source_units_sha256": base._digest(passages),
                "source_unit_count": len(catalog)})
    return items


def prepare_retrieval_study(*, source_prepared_dir: Path, config_path: Path,
    output_dir: Path, cohort: str, case_ids: list[str] | None = None) -> dict[str, Any]:
    """Freeze changed retrieval packs and current code without calling a model."""
    if cohort not in COHORTS:
        raise ValueError("This entry point supports declared DEV/synthetic cohorts, never a held-out study")
    source = Path(source_prepared_dir).resolve(strict=True)
    source_manifest = _checked_source(source)
    config, resolved = _config(Path(config_path))
    rubric = base._read_json(source / "inputs/authored-rubric.json")
    compiled = compile_rubric(rubric)
    selected = [c for c in source_manifest["cases"] if case_ids is None or c["case_id"] in case_ids]
    if (not selected or len({c["case_id"] for c in selected}) != len(selected)
            or case_ids is not None and set(case_ids) != {c["case_id"] for c in selected}):
        raise ValueError("Unknown or duplicate DEV case selection")
    references = base._read_json(source / "reference.json")
    reference_rows = [r for r in references["rows"] if r["case_id"] in {c["case_id"] for c in selected}]
    expected_pairs = {(c["case_id"], q["checklist_id"]) for c in selected
        for criterion in compiled["criteria"] for q in criterion["checklists"]}
    if {(r["case_id"], r["metadata"]["checklist_id"]) for r in reference_rows} != expected_pairs:
        raise ValueError("Reference and compiled checklist scopes differ")
    metrics._index(reference_rows, reference=True)
    # Calculate every pack before output creation, so invalid/context-overflow
    # preparations do not leave a deceptively executable partial directory.
    packs = {}
    for case in selected:
        common = base._read_json(source / "cases" / case["case_id"] / "common-evidence.json")
        body = source / "cases" / case["case_id"] / "body.txt"
        if base._sha(body) != case["body_sha256"]:
            raise ValueError("Report body differs from frozen DEV identity")
        packs[case["case_id"]] = {m: _prepare_items(common, compiled, resolved, m) for m in METHODS}
    out = base._private_output(Path(output_dir))
    inputs = out / "inputs"
    inputs.mkdir(mode=0o700)
    base._write(inputs / "config.json", config)
    base._write(inputs / "verifier-definition.json", _offline_verifier_definition(config, resolved))
    base._write(inputs / "authored-rubric.json", rubric)
    base._write(inputs / "compiled-rubric.json", compiled)
    base._write(out / "reference.json", {**references, "rows": reference_rows})
    base._write(inputs / "source-preparation-manifest.json", source_manifest)
    cases = []
    for case in selected:
        current = case["case_id"]
        destination = out / "cases" / current
        destination.mkdir(parents=True, mode=0o700)
        shutil.copyfile(source / "cases" / current / "body.txt", destination / "body.txt")
        for method in METHODS:
            base._write(destination / (method + ".json"), {"case_id": current,
                "method": method, "items": packs[current][method]})
        order = sorted(METHODS, key=lambda m: hashlib.sha256(
            (str(config.get("seed", 0)) + ":" + case["body_sha256"] + ":" + m).encode()).hexdigest())
        cases.append({"case_id": current, "body_sha256": case["body_sha256"], "execution_order": order})
    code_paths = sorted({Path(__file__), Path(base.__file__), Path(metrics.__file__),
        *list((base.ROOT / "research/core_mvp").glob("*.py")),
        base.ROOT / "research/offline_retrieval/bm25.py",
        base.ROOT / "research/offline_retrieval/common.py",
        base.ROOT / "research/schema_validation.py",
        base.ROOT / "research/schemas/assessment-report-v1.schema.json"})
    code_hashes = {}
    for path in code_paths:
        relative = str(path.relative_to(base.ROOT))
        code_hashes[relative] = base._sha(path)
        destination = out / "code-snapshot" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    manifest = {"schema_version": 1, "design": DESIGN, "status": "PREPARED_DEV_NO_MODEL_CALLS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "cohort_declared_by_caller": cohort,
        "source_preparation_sha256": base._sha(source / "preparation-manifest.json"),
        "source_input_bytes_verified": True, "source_old_code_not_executed": True,
        "model_called": False, "independent_holdout_claim": False, "approved_gold_claim": False,
        "reference_not_given_to_verifier": True, "evidence_semantic_support_evaluated": False,
        "teacher_score_agreement_evaluated": False, "methods": list(METHODS),
        "unavailable_methods": {GRAPH: {"status": "NOT_IMPLEMENTED_NOT_RUN",
            "reason": "Semantic relation extraction/retrieval is not implemented; structure-term PPR is not substituted."}},
        "same_model_verifier_and_scorer": True, "same_evidence_pack_claim": False,
        "local_retriever": "BM25_ONLY", "context_overflow_policy": "REJECT_PREPARATION_NO_SILENT_FALLBACK",
        "cases": cases, "items_per_method": len(reference_rows), "code_hashes": code_hashes,
        "locked_files": {str(p.relative_to(out)): base._sha(p) for p in sorted(out.rglob("*")) if p.is_file()}}
    base._write(out / "preparation-manifest.json", manifest)
    for path in out.rglob("*"):
        if path.is_file():
            path.chmod(0o400)
    return {"status": manifest["status"], "reports": len(cases), "items_per_method": len(reference_rows),
        "methods": list(METHODS), "unavailable_methods": manifest["unavailable_methods"],
        "output_dir": str(out), "preparation_manifest_sha256": base._sha(out / "preparation-manifest.json")}


def _validated_preparation(prepared):
    manifest = base._read_json(prepared / "preparation-manifest.json")
    if (manifest.get("design") != DESIGN or manifest.get("cohort_declared_by_caller") not in COHORTS
            or manifest.get("methods") != list(METHODS) or manifest.get("model_called") is not False):
        raise ValueError("Only frozen DEV retrieval preparations may execute")
    for relative, checksum in manifest["locked_files"].items():
        if base._sha(_checked_file(prepared, relative)) != checksum:
            raise ValueError("A frozen retrieval-study input changed")
    for relative, checksum in manifest["code_hashes"].items():
        if base._sha(_checked_file(base.ROOT, relative)) != checksum:
            raise ValueError("Retrieval-study implementation changed after preparation; create a new version")
    return manifest


def _save_or_verify(path, value):
    if path.exists():
        if path.read_bytes() != base._canonical(value):
            raise ValueError("Recorded execution identity or result differs")
    else:
        base._write(path, value)


def run_retrieval_study(*, prepared_dir: Path, output_dir: Path, allow_real_model: bool = False,
    case_id: str | None = None, verifier_factory: Callable | None = None) -> dict[str, Any]:
    """Execute frozen DEV inputs once, persisting every checklist before continuing."""
    if verifier_factory is None and not allow_real_model:
        raise ValueError("Real execution requires explicit --allow-real-model")
    prepared = Path(prepared_dir).resolve(strict=True)
    manifest = _validated_preparation(prepared)
    config, resolved = _config(prepared / "inputs/config.json")
    definition = base._read_json(prepared / "inputs/verifier-definition.json")
    compiled = base._read_json(prepared / "inputs/compiled-rubric.json")
    reference = base._read_json(prepared / "reference.json")
    references = {(r["case_id"], r["metadata"]["checklist_id"]): r for r in reference["rows"]}
    selected = [c for c in manifest["cases"] if case_id is None or c["case_id"] == case_id]
    if not selected:
        raise ValueError("Unknown prepared DEV case")
    out = Path(output_dir).absolute()
    identity = {"design": DESIGN, "prepared_dir": str(prepared),
        "preparation_manifest_sha256": base._sha(prepared / "preparation-manifest.json"),
        "real_model_execution": verifier_factory is None}
    if out.exists():
        if (not out.is_relative_to(base.VAR_ROOT.absolute())
                or any(p.is_symlink() for p in (out, *out.parents))
                or base._read_json(out / "execution-identity.json") != identity):
            raise ValueError("Existing output is not this frozen execution")
    else:
        out = base._private_output(out)
        base._write(out / "execution-identity.json", identity)
    for case in selected:
        current = case["case_id"]
        for method in case["execution_order"]:
            items = base._read_json(prepared / "cases" / current / (method + ".json"))["items"]
            method_dir = out / current / method
            method_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            verifier, rows = None, []
            for item in items:
                checklist = deepcopy(item["checklist"])
                key = checklist["checklist_id"]
                ref = references[(current, key)]
                result_path = method_dir / (key + "-result.json")
                if result_path.exists():
                    row = base._read_json(result_path)
                    if (row.get("item_id") != ref["item_id"] or row.get("metadata") != ref["metadata"]
                            or row.get("method_pack_sha256") != item["evidence_pack_sha256"]
                            or row.get("method_catalog_sha256") != item["source_units_sha256"]):
                        raise ValueError("Recorded result differs from frozen item identity")
                    rows.append(row)
                    continue
                started_path = method_dir / (key + "-started.json")
                if started_path.exists():
                    raise ValueError("Interrupted request has no result; refusing automatic retry")
                pack = base._rehydrate_pack(item["evidence_pack"])
                passages, _ = _catalog(pack, resolved["llm_verification"])
                if (base._digest(item["evidence_pack"]) != item["evidence_pack_sha256"]
                        or passages != item["source_units"]):
                    raise ValueError("Frozen retrieval pack or unit catalog changed")
                if verifier is None:
                    model, policy = config["models"]["assessment_verifier"], resolved["llm_verification"]
                    verifier = (verifier_factory(method, deepcopy(model), deepcopy(policy)) if verifier_factory else
                                LlmAssessmentVerifier(model, policy))
                    if any(verifier.metadata.get(key) != value for key, value in definition["metadata"].items()):
                        raise ValueError("Runtime prompt/schema/policy differs from frozen verifier definition")
                    _save_or_verify(method_dir / "verification-metadata.json", deepcopy(verifier.metadata))
                base._write(started_path, {"item_id": ref["item_id"], "method": method,
                    "started_at_utc": datetime.now(timezone.utc).isoformat(), "retry_allowed": False})
                print(json.dumps({"event": "CHECKLIST_STARTED", "case_id": current,
                    "method": method, "checklist_id": key}), flush=True)
                calls_before = getattr(verifier, "_model_calls", None)
                start = time.monotonic()
                result = verifier.verify(checklist, pack)
                calls_after = getattr(verifier, "_model_calls", None)
                if (checklist != item["checklist"]
                        or base._digest(base._serialized_pack(pack)) != item["evidence_pack_sha256"]):
                    raise ValueError("Verifier mutated the frozen model input")
                status, label = result.get("llm_verification", {}).get("status"), result.get("checklist_outcome")
                if status not in {"VALIDATED", "WITHHELD"} or label not in base.LABELS:
                    raise ValueError("Unexpected verifier decision")
                row = {"item_id": ref["item_id"], "case_id": current, "metadata": deepcopy(ref["metadata"]),
                    "checklist_id": key, "criterion_id": item["criterion_id"],
                    "method_pack_sha256": item["evidence_pack_sha256"],
                    "method_catalog_sha256": item["source_units_sha256"],
                    "accepted_label": label if status == "VALIDATED" else None,
                    "decision_status": "SEMANTIC_DECISION" if status == "VALIDATED" else "TECHNICAL_ABSTENTION",
                    "model_calls_observed": calls_after - calls_before if type(calls_before) is int and type(calls_after) is int else None,
                    "elapsed_seconds": round(time.monotonic() - start, 6),
                    "token_usage": base._usage(result.get("llm_verification", {})), "raw_result": result}
                base._write(result_path, row)
                rows.append(row)
                print(json.dumps({"event": "CHECKLIST_COMPLETE", "case_id": current,
                    "method": method, "checklist_id": key, "accepted_label": row["accepted_label"]}), flush=True)
            metadata = base._read_json(method_dir / "verification-metadata.json")
            report = base._contract_report(compiled, items, rows, metadata, resolved)
            report.update(pipeline="p2-retrieval-development-comparison-v1", limitations=[
                "Different retrieval packs, same model/verifier/scorer; previously inspected DEV, not a held-out evaluation.",
                "LOCAL uses BM25 only; semantic GRAPH is unavailable and has no fabricated result row.",
                "Source-bound citations do not prove semantic support; proposal scores are not teacher-score agreement."])
            validate_assessment_report(report)
            validate_json_schema(report, kind="assessment")
            _save_or_verify(method_dir / "assessment-report.json", report)
    predictions = {method: [] for method in METHODS}
    complete_cases = []
    for case in manifest["cases"]:
        current = case["case_id"]
        case_complete = True
        for method in METHODS:
            items = base._read_json(prepared / "cases" / current / (method + ".json"))["items"]
            for item in items:
                path = out / current / method / (item["checklist"]["checklist_id"] + "-result.json")
                if path.exists():
                    predictions[method].append(base._read_json(path))
                else:
                    case_complete = False
        if case_complete:
            complete_cases.append(current)
    complete = len(complete_cases) == len(manifest["cases"])
    summary = {"schema_version": 1, "design": DESIGN,
        "status": "COMPLETE_DEV_COMPARISON" if complete else "PARTIAL_DEV_COMPARISON",
        "complete_reports": len(complete_cases), "reports": len(manifest["cases"]),
        "unavailable_methods": manifest["unavailable_methods"],
        "approved_gold_claim": False, "independent_holdout_claim": False,
        "methods": {m: {"records": len(rows), "technical_abstentions": sum(r["accepted_label"] is None for r in rows),
            "accepted_labels": dict(Counter(r["accepted_label"] for r in rows if r["accepted_label"] is not None))}
            for m, rows in predictions.items()}}
    if complete:
        _save_or_verify(out / "all-methods-predictions.json", {"design": DESIGN, "methods": predictions,
            "unavailable_methods": manifest["unavailable_methods"]})
        scores = metrics.summarize(reference["rows"], predictions,
            reference_sha256=base._sha(prepared / "reference.json"), expected_items=manifest["items_per_method"])
        scores.update(design=DESIGN, independent_holdout_claim=False,
            unavailable_methods=manifest["unavailable_methods"], teacher_score_agreement_evaluated=False)
        _save_or_verify(out / "metrics.json", scores)
        _save_or_verify(out / "run-summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--source-prepared-dir", type=Path, required=True)
    prepare.add_argument("--config", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--cohort", choices=COHORTS, required=True)
    prepare.add_argument("--case-id", action="append", dest="case_ids")
    run = commands.add_parser("run")
    run.add_argument("--prepared-dir", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--case-id")
    run.add_argument("--allow-real-model", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_retrieval_study(source_prepared_dir=args.source_prepared_dir,
            config_path=args.config, output_dir=args.output_dir, cohort=args.cohort, case_ids=args.case_ids)
    else:
        result = run_retrieval_study(prepared_dir=args.prepared_dir, output_dir=args.output_dir,
            case_id=args.case_id, allow_real_model=args.allow_real_model)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
