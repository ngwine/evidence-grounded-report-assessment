"""Evaluate frozen, synthetic report/source cases without tuning their labels.

Retrieval success and relation decisions are reported separately. Missing or
abstained predictions are never silently counted as a correct NONE label.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


_ROOT = Path(__file__).resolve().parents[2]
_RELATIONS = {"VERBATIM", "PARAPHRASE", "NONE"}
_OUTCOMES = {"MET", "UNMET", "CANNOT_ASSESS"}
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_pack(pack: Mapping[str, Any]) -> None:
    """Validate labels and exact Unicode half-open evidence ranges."""
    if pack.get("schema_version") != 1:
        raise ValueError("Unsupported output-quality pack schema")
    provenance = pack.get("provenance", {})
    if provenance.get("label_status") != "ASSISTANT_AUTHORED_EXPECTATIONS":
        raise ValueError("This diagnostic accepts authored expectations only")
    if provenance.get("independent_human_gold") is not False:
        raise ValueError("Authored diagnostics must not claim human gold")
    if not pack.get("pack_id") or pack.get("split") not in {"DEV", "CHALLENGE"}:
        raise ValueError("Pack identity and development split are required")
    cases = pack.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("A nonempty case list is required")
    seen: set[str] = set()
    for case in cases:
        identifier = case.get("case_id")
        if not isinstance(identifier, str) or _SAFE_ID.fullmatch(identifier) is None or identifier in seen:
            raise ValueError("Case IDs must be nonempty and unique")
        seen.add(identifier)
        report = case.get("report_text")
        if not isinstance(report, str) or not report.strip():
            raise ValueError(f"Invalid report text: {identifier}")
        expected = case.get("expected", {})
        if case.get("task") == "SIMILARITY":
            sources = case.get("sources", [])
            if any(not isinstance(source.get("source_id"), str)
                   or _SAFE_ID.fullmatch(source["source_id"]) is None
                   or not isinstance(source.get("text"), str) or not source["text"].strip()
                   for source in sources):
                raise ValueError(f"Invalid source identity/text: {identifier}")
            source_map = {source["source_id"]: source["text"] for source in sources}
            if len(source_map) != len(sources) or len(sources) < 2:
                raise ValueError(f"Distinct target and distractor sources required: {identifier}")
            target = expected.get("target_source_id")
            if target not in source_map or expected.get("relation") not in _RELATIONS:
                raise ValueError(f"Invalid relation target: {identifier}")
            texts = {"report": report, "source": source_map[target]}
        elif case.get("task") == "ASSESSMENT":
            if expected.get("outcome") not in _OUTCOMES or not case.get("rubric"):
                raise ValueError(f"Invalid assessment expectation: {identifier}")
            texts = {"report": report}
        else:
            raise ValueError(f"Unsupported task: {identifier}")
        for evidence in expected.get("evidence", []):
            leg, start, end = evidence.get("leg"), evidence.get("start"), evidence.get("end")
            if leg not in texts or isinstance(start, bool) or isinstance(end, bool):
                raise ValueError(f"Invalid evidence leg/range: {identifier}")
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(texts[leg]):
                raise ValueError(f"Out-of-range evidence: {identifier}")
            if texts[leg][start:end] != evidence.get("quote"):
                raise ValueError(f"Evidence quote does not match range: {identifier}")


def load_frozen_core(snapshot_root: Path) -> dict[str, str]:
    """Load preserved modules in a separate evaluation process.

    This replaces module entries and therefore belongs in a fresh process,
    never in a running API/worker or mixed baseline/candidate Python session.
    """
    directory = snapshot_root / "research" / "core_mvp"
    hashes: dict[str, str] = {}
    for name in ("similarity", "assessment"):
        path = directory / f"{name}.py"
        module_name = f"research.core_mvp.{name}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ValueError("Cannot load frozen core snapshot")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        hashes[name] = _sha(path)
    return hashes


def _contains_range(span: Mapping[str, Any], anchor: Mapping[str, Any]) -> bool:
    return (isinstance(span.get("normalized_start"), int)
            and isinstance(span.get("normalized_end"), int)
            and span["normalized_start"] <= anchor["start"]
            and anchor["end"] <= span["normalized_end"])


def summarize_cases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    p1 = [row for row in rows if row["task"] == "SIMILARITY"]
    positives = [row for row in p1 if row["expected_relation"] != "NONE"]
    negatives = [row for row in p1 if row["expected_relation"] == "NONE"]
    p2 = [row for row in rows if row["task"] == "ASSESSMENT"]
    decisions = [row for row in p1 if row["predicted_relation"] is not None]
    confusion = Counter(f"{row['expected_relation']}->{row['predicted_relation'] or 'ABSTAIN_OR_MISSING'}" for row in p1)
    return {
        "similarity": {
            "cases": len(p1), "positive_cases": len(positives), "negative_cases": len(negatives),
            "positive_target_retrieved_at_1": sum(row["target_rank"] == 1 for row in positives),
            "positive_target_retrieved_at_3": sum(row["target_rank"] is not None and row["target_rank"] <= 3 for row in positives),
            "positive_full_anchor_in_alignment": sum(row["expected_anchor_contained"] for row in positives),
            "relation_correct": sum(row["relation_correct"] for row in p1),
            "decided_cases": len(decisions), "abstained_or_missing": len(p1) - len(decisions),
            "negative_false_reuse_labels": sum(row["predicted_relation"] in {"VERBATIM", "PARAPHRASE"} for row in negatives),
            "negative_cases_any_source_false_reuse": sum(row["any_retrieved_reuse"] for row in negatives),
            "non_target_false_reuse_labels": sum(row["non_target_reuse_count"] for row in p1),
            "cases_with_non_target_false_reuse": sum(row["non_target_reuse_count"] > 0 for row in p1),
            "predicted_reuse_labels_all_sources": sum(row["retrieved_reuse_count"] for row in p1),
            "negative_false_exact_document_coverage": sum(row["exact_document_coverage"] > 0 for row in negatives),
            "confusion": dict(sorted(confusion.items())),
        },
        "assessment": {
            "cases": len(p2), "outcome_correct": sum(row["outcome_correct"] for row in p2),
            "predicted_outcomes": dict(sorted(Counter(row["predicted_outcome"] for row in p2).items())),
            "false_met": sum(row["predicted_outcome"] == "MET" and row["expected_outcome"] != "MET" for row in p2),
            "unknown_kept_unknown": sum(row["predicted_outcome"] == "CANNOT_ASSESS" and row["expected_outcome"] == "CANNOT_ASSESS" for row in p2),
        },
    }


def evaluate_pack(
    pack_path: Path, output_dir: Path, *, profile: str = "bm25", encoder: Any = None,
    reranker: Any = None, semantic_verifier: Any = None,
    core_hashes: Mapping[str, str] | None = None, expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Run actual parsing/retrieval/output logic; model adapters are explicit."""
    from research.core_mvp.documents import parse_document
    from research.core_mvp.similarity import run_similarity_pipeline
    from research.core_mvp.assessment import run_assessment_pipeline

    if core_hashes is None:
        core_hashes = {
            name: _sha(Path(sys.modules[f"research.core_mvp.{name}"].__file__))
            for name in ("similarity", "assessment")
        }
        if semantic_verifier is not None:
            module = sys.modules.get(type(semantic_verifier).__module__)
            if module is not None and getattr(module, "__file__", None):
                core_hashes["semantic_verification"] = _sha(Path(module.__file__))
    if expected_sha256 is not None and _sha(pack_path) != expected_sha256:
        raise ValueError("Frozen pack checksum mismatch")
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    validate_pack(pack)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Use a new empty output directory for each attempt")
    if profile not in {"bm25", "rrf", "rrf-rerank"}:
        raise ValueError("Unsupported retrieval profile")
    if profile != "bm25" and encoder is None:
        raise ValueError("Dense profiles require an actual or explicitly injected encoder")
    if profile == "rrf-rerank" and reranker is None:
        raise ValueError("Reranking profile requires an actual or explicitly injected reranker")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = {"candidate_depth": 3, "rerank_depth": 3, "top_k": 3,
              "dense_enabled": profile != "bm25", "reranker_enabled": profile == "rrf-rerank"}
    if semantic_verifier is not None:
        config["semantic_verification"] = {"enabled": True}
    rows: list[dict[str, Any]] = []
    for case in pack["cases"]:
        identifier = case["case_id"]
        case_dir = output_dir / "cases" / identifier
        case_dir.mkdir(parents=True)
        report_path = case_dir / "report.txt"
        report_path.write_text(case["report_text"], encoding="utf-8")
        report = parse_document(report_path, role="student-report", min_tokens=1, max_tokens=256)
        expected = case["expected"]
        if case["task"] == "SIMILARITY":
            sources = []
            source_ids: dict[str, str] = {}
            for source in case["sources"]:
                path = case_dir / f"{source['source_id']}.txt"
                path.write_text(source["text"], encoding="utf-8")
                parsed = parse_document(path, role="comparison-source", min_tokens=1, max_tokens=256)
                sources.extend(parsed.chunks)
                source_ids[source["source_id"]] = parsed.document["document_id"]
            kwargs = {"config": config, "encoder": encoder, "reranker": reranker}
            if semantic_verifier is not None:
                kwargs["semantic_verifier"] = semantic_verifier
            result = run_similarity_pipeline(report.chunks, sources, **kwargs)
            target = source_ids[expected["target_source_id"]]
            matches = [match for match in result["matches"] if match["source_document_id"] == target]
            match = min(matches, key=lambda item: item["rank"]) if matches else None
            reuse_matches = [item for item in result["matches"]
                             if item.get("similarity_type") in {"VERBATIM", "PARAPHRASE"}]
            non_target_reuse = [item for item in reuse_matches if item["source_document_id"] != target]
            predicted = match.get("similarity_type") if match else None
            anchors = expected.get("evidence", [])
            contained = bool(match) and bool(anchors) and all(
                _contains_range(match["alignment"][anchor["leg"]], anchor) for anchor in anchors)
            row = {"case_id": identifier, "task": case["task"], "language": case["language"],
                   "category": case["category"], "expected_relation": expected["relation"],
                   "predicted_relation": predicted, "relation_correct": predicted == expected["relation"],
                   "target_rank": match["rank"] if match else None,
                   "expected_anchor_contained": contained,
                   "classification_status": match.get("classification_status") if match else "MISSING",
                   "semantic_verification_status": match.get("semantic_verification_status") if match else "NOT_RUN",
                   "any_retrieved_reuse": bool(reuse_matches),
                   "retrieved_reuse_count": len(reuse_matches),
                   "non_target_reuse_count": len(non_target_reuse),
                   "non_target_reuse_decisions": [
                       {"source_name": item.get("source_name"), "rank": item["rank"],
                        "similarity_type": item["similarity_type"]}
                       for item in non_target_reuse],
                   "exact_document_coverage": result["exact_match_coverage_percentage"]}
            row["diagnostic_stage"] = (
                "NO_TARGET_PAIR" if match is None else
                "ALIGNMENT_ANCHOR_MISS" if expected["relation"] != "NONE" and not contained else
                "RELATION_ABSTAIN" if predicted is None else
                "RELATION_MISMATCH" if predicted != expected["relation"] else "EXPECTED_DECISION")
        else:
            result = run_assessment_pipeline(report.chunks, case["rubric"], config=config,
                                             encoder=encoder, reranker=reranker)
            item = result["checklist_results"][0]
            row = {"case_id": identifier, "task": case["task"], "language": case["language"],
                   "category": case["category"], "expected_outcome": expected["outcome"],
                   "predicted_outcome": item["checklist_outcome"],
                   "outcome_correct": item["checklist_outcome"] == expected["outcome"],
                   "verification_reason": item.get("reason_code"),
                   "proposed_total_score": result["proposed_total_score"]}
        (case_dir / "pipeline-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rows.append(row)
    summary = {"schema_version": 2, "pack_id": pack["pack_id"], "split": pack["split"],
               "label_status": pack["provenance"]["label_status"], "independent_human_gold": False,
               "pack_sha256": _sha(pack_path), "created_at": datetime.now(timezone.utc).isoformat(),
               "evaluator_sha256": _sha(Path(__file__)),
               "profile": profile, "configuration": config, "core_hashes": dict(core_hashes),
               "models": {"encoder": getattr(encoder, "metadata", None), "reranker": getattr(reranker, "metadata", None),
                          "semantic_verifier": getattr(semantic_verifier, "metadata", None)},
               "summary": summarize_cases(rows), "cases": rows,
               "claim_limit": "Assistant-authored development diagnostics; not independent human gold, holdout evidence, or plagiarism accuracy."}
    (output_dir / "evaluation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--core-snapshot", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    hashes = load_frozen_core(args.core_snapshot) if args.core_snapshot else {
        name: _sha(_ROOT / "research/core_mvp" / f"{name}.py") for name in ("similarity", "assessment")}
    result = evaluate_pack(args.pack, args.output_dir, core_hashes=hashes,
                           expected_sha256=args.expected_sha256)
    print(json.dumps({key: result[key] for key in ("pack_id", "split", "summary")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
