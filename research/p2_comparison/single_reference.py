"""Explicit, locked exploratory evaluation against one AI-assisted reference.

This separate entry point never changes the protected DEV comparator or the
two-annotator gold-v1 gate. Reference labels are archived, not given to models.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import time
from typing import Any, Callable
import json

from research.core_mvp import assessment
from research.core_mvp.bounded_documents import ParseLimits, parse_document_bounded
from research.core_mvp.llm_assessment import LlmAssessmentVerifier, _source_unit_catalog
from research.core_mvp.rubric import compile_rubric
from research.gold_annotation.p2_workbook_intake import _packet, parse_workbook
from research.p2_comparison import runner as base

DESIGN = "SINGLE_ANNOTATOR_AI_ASSISTED_EXPLORATORY"
SCOPE = "RUN_LOCAL_SINGLE_REFERENCE_EXPLORATORY_P2"


def _scope(protocol, authorization):
    if (protocol.get("schema_version") != 1 or protocol.get("design") != DESIGN
            or protocol.get("allow_actual_cohort") is not True
            or protocol.get("methods") != list(base.METHODS)
            or protocol.get("no_tuning_after_first_prediction") is not True
            or protocol.get("approved_gold_claim") is not False
            or protocol.get("independent_holdout_claim") is not False
            or protocol.get("label_classes") != ["MET", "UNMET", "CANNOT_ASSESS"]):
        raise ValueError("An explicit single-reference exploratory protocol is required")
    if (authorization.get("schema_version") != 1 or authorization.get("scope") != SCOPE
            or authorization.get("allow_actual_cohort") is not True
            or authorization.get("approved_gold_claim") is not False
            or not authorization.get("user_instruction")
            or not authorization.get("prior_single_annotator_instruction")):
        raise ValueError("Explicit actual-cohort execution authorization is required")


def _save_or_verify(path, value):
    data = base._canonical(value)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("A previously recorded execution output differs")
    else:
        base._write(path, value)


def _case_pack(body_path, context, compiled, config):
    documents = config.get("documents", {})
    parsed = parse_document_bounded(body_path, role="student-report",
        max_tokens=documents.get("max_tokens", 220), min_tokens=documents.get("min_tokens", 30),
        limits=ParseLimits.from_config(documents.get("resource_limits")))
    chunks = list(parsed.chunks)
    if not chunks:
        raise ValueError("Evaluation needs nonempty parsed report chunks")
    report_map, report_id, report_version = assessment._report_scope(chunks)
    resolved = assessment.validate_assessment_config(config["pipeline2"])
    items = []
    for criterion in compiled["criteria"]:
        for checklist in criterion["checklists"]:
            candidates, retrieval = assessment._rank_local(checklist, chunks,
                config=resolved, encoder=None, reranker=None)
            if "evidence_context" in resolved:
                candidates, retrieval = assessment._bounded_report_context(candidates, retrieval,
                    chunks, resolved["evidence_context"])
            pack = assessment._validated_evidence_pack(candidates, report_map,
                report_id=report_id, report_version=report_version)
            units, catalog = _source_unit_catalog(LlmAssessmentVerifier._scope(pack))
            serialized = base._serialized_pack(pack)
            items.append({"criterion_id": criterion["criterion_id"], "checklist": checklist,
                "retrieval": retrieval, "evidence_pack": serialized,
                "evidence_pack_sha256": base._digest(serialized), "source_units": units,
                "source_units_sha256": base._digest(units), "unit_count": len(catalog)})
    return {"schema_version": 1, "case_id": context["case_id"], "items": items,
        "reference_identity": {key: context[key] for key in ("report_id", "report_version", "body_sha256")},
        "runtime_identity": {"report_id": report_id, "report_version": report_version},
        "identity_alias_is_explicit": True, "parsed_chunks": chunks,
        "parsed_elements": list(parsed.elements), "parsed_document": parsed.document,
        "original_document_completeness_asserted": False}


def prepare_single_reference(*, packet_dir: Path, workbook_path: Path, canonical_reference: Path,
    rubric_path: Path, protocol_path: Path, authorization_path: Path, output_dir: Path,
    one_step_config: Path = base.ROOT / "research/configs/p2-comparison/one-step.json",
    two_step_config: Path = base.ROOT / "research/configs/p2-comparison/two-step.json") -> dict[str, Any]:
    """Validate the actual returned sheet, then lock every input before inference."""
    protocol, authorization = base._read_json(protocol_path), base._read_json(authorization_path)
    _scope(protocol, authorization)
    packet = _packet(Path(packet_dir), "YEN")
    reference = parse_workbook(Path(packet_dir), Path(workbook_path), "YEN")
    if base._read_json(canonical_reference) != reference:
        raise ValueError("Canonical reference does not match the supplied returned workbook")
    if (reference["provenance_issues"] or any(row["state"] != "VALID" for row in reference["rows"])
            or reference["provenance_review_flags"] != ["AI_ASSISTANCE_DECLARED"]):
        raise ValueError("Reference must have resolved records and disclosed AI assistance only")
    pair = base.configuration_pair(Path(one_step_config), Path(two_step_config))
    compiled = compile_rubric(base._read_json(rubric_path))
    checklists = [c for criterion in compiled["criteria"] for c in criterion["checklists"]]
    if any(c["mode"] != "LOCAL" for c in checklists):
        raise ValueError("Only the locked LOCAL assessment comparison is supported")
    checklist_ids = {c["checklist_id"] for c in checklists}
    if len(checklist_ids) != len(checklists):
        raise ValueError("Duplicate compiled checklist IDs")
    reference_by_case = {}
    for row in reference["rows"]:
        reference_by_case.setdefault(row["case_id"], {})[row["metadata"]["checklist_id"]] = row
    for rows in reference_by_case.values():
        if set(rows) != checklist_ids:
            raise ValueError("Compiled and reference checklist scopes differ")
    expected_cases = protocol.get("expected_reports", len(reference_by_case))
    expected_items = protocol.get("expected_items", len(reference["rows"]))
    if len(reference_by_case) != expected_cases or len(reference["rows"]) != expected_items:
        raise ValueError("Protocol and reference cohort sizes differ")
    out = base._private_output(Path(output_dir))
    inputs = out / "inputs"
    inputs.mkdir(mode=0o700)
    originals = {"reference-workbook.xlsx": Path(workbook_path),
        "canonical-reference-original.json": Path(canonical_reference),
        "authored-rubric.json": Path(rubric_path), "protocol.json": Path(protocol_path),
        "authorization.json": Path(authorization_path)}
    for name, source in originals.items():
        shutil.copyfile(source, inputs / name)
    base._write(out / "reference.json", reference)
    base._write(inputs / "compiled-rubric.json", compiled)
    methods_dir = out / "methods"
    methods_dir.mkdir(mode=0o700)
    for name, config in pair.items():
        base._write(methods_dir / (name + ".json"), config)
    cases = []
    cases_dir = out / "cases"
    cases_dir.mkdir(mode=0o700)
    config = pair["one-step"]
    for case_id in sorted(reference_by_case):
        context = packet["contexts"][case_id]
        source_body = packet["bundle"] / "BAI_VIET" / case_id / "body.txt"
        destination = cases_dir / case_id
        destination.mkdir(mode=0o700)
        shutil.copyfile(source_body, destination / "body.txt")
        if base._sha(destination / "body.txt") != context["body_sha256"]:
            raise ValueError("Report body no longer matches returned annotation identity")
        base._write(destination / "reference-context.json", context)
        common = _case_pack(destination / "body.txt", context, compiled, config)
        base._write(destination / "common-evidence.json", common)
        order = sorted(base.METHODS, key=lambda name: hashlib.sha256(
            (str(config.get("seed", 0)) + ":" + context["body_sha256"] + ":" + name).encode()).hexdigest())
        cases.append({"case_id": case_id, "execution_order": order,
                      "reference_item_ids": [reference_by_case[case_id][key]["item_id"] for key in sorted(checklist_ids)],
                      "body_sha256": context["body_sha256"], "parsed_chunks": len(common["parsed_chunks"]),
                      "evidence_context": [item["retrieval"] for item in common["items"]]})
    code_paths = [Path(__file__), Path(base.__file__),
        *sorted((base.ROOT / "research/core_mvp").glob("*.py")),
        base.ROOT / "research/offline_retrieval/bm25.py", base.ROOT / "research/offline_retrieval/common.py",
        base.ROOT / "services/backend/src/kltn_ai/integrations/indexing/chunking.py",
        base.ROOT / "services/backend/src/kltn_ai/integrations/parsing/text_normalization.py"]
    code_hashes = {str(path.relative_to(base.ROOT)): base._sha(path) for path in code_paths}
    for source in code_paths:
        destination = out / "code-snapshot" / source.relative_to(base.ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    locked_files = {str(path.relative_to(out)): base._sha(path) for path in sorted(out.rglob("*")) if path.is_file()}
    receipt = {"schema_version": 1, "design": DESIGN,
        "status": "PREPARED_SINGLE_REFERENCE_EXPLORATORY_NO_MODEL_CALLS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "approved_gold_claim": False, "independent_holdout_claim": False,
        "inter_annotator_agreement_applicable": False, "model_called": False,
        "reference_not_given_to_verifier": True, "same_citation_cap": 3,
        "budget_regime": "SAME_PER_CALL_BUDGET_NOT_TOTAL_COMPUTE_MATCHED",
        "no_tuning_after_first_prediction": True, "packet_manifest_sha256": packet["manifest_sha256"],
        "cases": cases, "items": len(reference["rows"]),
        "locked_files": locked_files, "code_hashes": code_hashes,
        "source_input_hashes": {str(path): base._sha(path) for path in originals.values()}}
    base._write(out / "preparation-manifest.json", receipt)
    for path in out.rglob("*"):
        if path.is_file():
            path.chmod(0o400)
    return {"status": receipt["status"], "reports": len(cases), "items": receipt["items"],
            "output_dir": str(out), "preparation_manifest_sha256": base._sha(out / "preparation-manifest.json")}


def _validated_preparation(prepared):
    manifest = base._read_json(prepared / "preparation-manifest.json")
    if manifest.get("design") != DESIGN or manifest.get("model_called") is not False:
        raise ValueError("Only locked single-reference preparations can be executed")
    for relative, checksum in manifest["locked_files"].items():
        path = prepared / relative
        if not path.resolve().is_relative_to(prepared) or base._sha(path) != checksum:
            raise ValueError("A frozen evaluation input changed")
    for relative, checksum in manifest["code_hashes"].items():
        if base._sha(base.ROOT / relative) != checksum:
            raise ValueError("Evaluation implementation changed after locking")
    _scope(base._read_json(prepared / "inputs/protocol.json"),
           base._read_json(prepared / "inputs/authorization.json"))
    return manifest


def run_single_reference(*, prepared_dir: Path, output_dir: Path, allow_real_model: bool = False,
    case_id: str | None = None, verifier_factory: Callable | None = None) -> dict[str, Any]:
    """Run frozen methods once; never retry an uncertain interrupted model call."""
    if verifier_factory is None and not allow_real_model:
        raise ValueError("Actual local execution requires explicit --allow-real-model")
    prepared = Path(prepared_dir).resolve(strict=True)
    manifest = _validated_preparation(prepared)
    configs = base.configuration_pair(prepared / "methods/one-step.json", prepared / "methods/two-step.json")
    compiled = base._read_json(prepared / "inputs/compiled-rubric.json")
    reference = base._read_json(prepared / "reference.json")
    references = {(r["case_id"], r["metadata"]["checklist_id"]): r for r in reference["rows"]}
    out = Path(output_dir).absolute()
    identity = {"schema_version": 1, "design": DESIGN, "real_model_execution": verifier_factory is None,
        "prepared_dir": str(prepared), "preparation_manifest_sha256": base._sha(prepared / "preparation-manifest.json")}
    if out.exists():
        if (not out.is_relative_to(base.VAR_ROOT.absolute())
                or any(p.is_symlink() for p in (out, *out.parents))
                or base._read_json(out / "execution-identity.json") != identity):
            raise ValueError("Existing output is not this locked execution")
    else:
        out = base._private_output(out)
        base._write(out / "execution-identity.json", identity)
    cases = [case for case in manifest["cases"] if case_id is None or case["case_id"] == case_id]
    if not cases:
        raise ValueError("Unknown evaluation case")
    for case in cases:
        current = case["case_id"]
        common = base._read_json(prepared / "cases" / current / "common-evidence.json")
        items = common["items"]
        for item in items:
            if base._digest(item["evidence_pack"]) != item["evidence_pack_sha256"]:
                raise ValueError("Frozen evidence pack changed")
            units, _ = _source_unit_catalog(LlmAssessmentVerifier._scope(base._rehydrate_pack(item["evidence_pack"])))
            if units != item["source_units"] or base._digest(units) != item["source_units_sha256"]:
                raise ValueError("Frozen source-unit catalog changed")
        for method in case["execution_order"]:
            method_dir = out / current / method
            method_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            config = configs[method]
            verifier = None
            method_rows = []
            for item in items:
                checklist = deepcopy(item["checklist"])
                key = checklist["checklist_id"]
                result_path = method_dir / (key + "-result.json")
                ref = references[(current, key)]
                if result_path.exists():
                    row = base._read_json(result_path)
                    if (row["item_id"] != ref["item_id"] or row["metadata"] != ref["metadata"]
                            or row["common_pack_sha256"] != item["evidence_pack_sha256"]
                            or row["common_catalog_sha256"] != item["source_units_sha256"]):
                        raise ValueError("Recorded result differs from the frozen evaluation identity")
                    method_rows.append(row)
                    continue
                started_path = method_dir / (key + "-started.json")
                if started_path.exists():
                    raise ValueError("Interrupted call has no result; refusing automatic duplicate request")
                if verifier is None:
                    model, policy = config["models"]["assessment_verifier"], config["pipeline2"]["llm_verification"]
                    verifier = (verifier_factory(method, deepcopy(model), deepcopy(policy)) if verifier_factory else
                                LlmAssessmentVerifier(model, policy))
                    if verifier.metadata.get("source_unit_policy", {}).get("max_citations_per_requirement") != 3:
                        raise ValueError("Runtime citation cap differs from locked comparison")
                    _save_or_verify(method_dir / "verification-metadata.json", deepcopy(verifier.metadata))
                base._write(started_path, {"item_id": ref["item_id"], "method": method,
                    "started_at_utc": datetime.now(timezone.utc).isoformat(), "retry_allowed": False})
                print(json.dumps({"event": "CHECKLIST_STARTED", "case_id": current,
                                  "method": method, "checklist_id": key}), flush=True)
                pack = base._rehydrate_pack(item["evidence_pack"])
                calls_before = getattr(verifier, "_model_calls", None)
                started = time.monotonic()
                result = verifier.verify(checklist, pack)
                calls_after = getattr(verifier, "_model_calls", None)
                if (base._digest(base._serialized_pack(pack)) != item["evidence_pack_sha256"]
                        or checklist != item["checklist"]):
                    raise ValueError("Verifier mutated frozen evidence")
                status, label = result.get("llm_verification", {}).get("status"), result.get("checklist_outcome")
                if status not in {"VALIDATED", "WITHHELD"} or label not in base.LABELS:
                    raise ValueError("Unexpected verifier decision")
                row = {"item_id": ref["item_id"], "case_id": current, "metadata": deepcopy(ref["metadata"]),
                    "checklist_id": key, "criterion_id": item["criterion_id"],
                    "common_pack_sha256": item["evidence_pack_sha256"],
                    "common_catalog_sha256": item["source_units_sha256"],
                    "accepted_label": label if status == "VALIDATED" else None,
                    "decision_status": "SEMANTIC_DECISION" if status == "VALIDATED" else "TECHNICAL_ABSTENTION",
                    "model_calls_observed": calls_after - calls_before if type(calls_after) is int and type(calls_before) is int else None,
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                    "token_usage": base._usage(result.get("llm_verification", {})), "raw_result": result}
                base._write(result_path, row)
                method_rows.append(row)
                print(json.dumps({"event": "CHECKLIST_COMPLETE", "case_id": current, "method": method,
                    "checklist_id": key, "accepted_label": row["accepted_label"],
                    "decision_status": row["decision_status"]}), flush=True)
            metadata = base._read_json(method_dir / "verification-metadata.json")
            report = base._contract_report(compiled, items, method_rows, metadata,
                assessment.validate_assessment_config(config["pipeline2"]))
            report["pipeline"] = "single-reference-exploratory-comparison-v1"
            report["research_status"] = DESIGN
            _save_or_verify(method_dir / "assessment-report.json", report)
            _save_or_verify(method_dir / "results.json", {"method": method, "case_id": current,
                "items": method_rows, "verification_metadata": metadata})
    _validated_preparation(prepared)
    all_results = {method: [] for method in base.METHODS}
    complete = True
    for case in manifest["cases"]:
        for method in base.METHODS:
            path = out / case["case_id"] / method / "results.json"
            if not path.exists():
                complete = False
                continue
            all_results[method].extend(base._read_json(path)["items"])
    summary = {"schema_version": 1, "design": DESIGN,
        "status": "COMPLETE_EXPLORATORY_PREDICTIONS_NOT_APPROVED_GOLD" if complete else "PARTIAL_EXPLORATORY_PREDICTIONS",
        "approved_gold_claim": False, "independent_holdout_claim": False,
        "same_upstream_evidence_verified": True, "reference_labels_given_to_verifier": False,
        "accuracy_computed": False, "real_model_execution": verifier_factory is None,
        "preparation_manifest_sha256": identity["preparation_manifest_sha256"],
        "budget_regime": manifest["budget_regime"],
        "methods": {method: {"items": len(rows),
            "accepted_labels": dict(Counter(r["accepted_label"] for r in rows if r["accepted_label"] is not None)),
            "technical_abstentions": sum(r["accepted_label"] is None for r in rows)} for method, rows in all_results.items()}}
    if complete:
        _save_or_verify(out / "all-methods-predictions.json", {"schema_version": 1, "methods": all_results})
        _save_or_verify(out / "run-summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    prepare = subs.add_parser("prepare")
    for flag in ("packet-dir", "workbook", "canonical-reference", "rubric", "protocol", "authorization", "output-dir"):
        prepare.add_argument("--" + flag, type=Path, required=True)
    prepare.add_argument("--one-step-config", type=Path, default=base.ROOT / "research/configs/p2-comparison/one-step.json")
    prepare.add_argument("--two-step-config", type=Path, default=base.ROOT / "research/configs/p2-comparison/two-step.json")
    run = subs.add_parser("run")
    run.add_argument("--prepared-dir", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--case-id")
    run.add_argument("--allow-real-model", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_single_reference(packet_dir=args.packet_dir, workbook_path=args.workbook,
            canonical_reference=args.canonical_reference, rubric_path=args.rubric,
            protocol_path=args.protocol, authorization_path=args.authorization, output_dir=args.output_dir,
            one_step_config=args.one_step_config, two_step_config=args.two_step_config)
    else:
        result = run_single_reference(prepared_dir=args.prepared_dir, output_dir=args.output_dir,
            case_id=args.case_id, allow_real_model=args.allow_real_model)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
