"""Audit a completed A5/A6 run and report a paired parent-level comparison."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .bootstrap_parent_metrics import analyse
from ..common import read_json, read_jsonl, sha256_file, write_json


METHODS = {
    "A5": "multiview_hybrid_cross_encoder",
    "A6": "multiview_hybrid_cross_encoder_short_evidence",
}


def verify_candidates(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Reject changed candidate/support budgets before interpreting metrics."""
    records: dict[str, dict[str, list[dict[str, Any]]]] = {label: {} for label in METHODS}
    for record in predictions:
        for label, name in METHODS.items():
            if record["method"] == name:
                query = record["query_id"]
                if query in records[label]:
                    raise ValueError("Duplicate comparison prediction")
                records[label][query] = record["candidates"]
    if not records["A5"] or set(records["A5"]) != set(records["A6"]):
        raise ValueError("A5/A6 must contain identical nonempty query sets")

    counts = {label: {"scored_support_requests": 0, "truncated_support_requests": 0,
                      "query_cropped_requests": 0, "passage_cropped_requests": 0,
                      "budget_repaired_requests": 0, "max_visible_pair_tokens": 0}
              for label in METHODS}
    for query, before in records["A5"].items():
        after = records["A6"][query]
        if len(before) != len(after) or {item["document_id"] for item in before} != {item["document_id"] for item in after}:
            raise ValueError("A5/A6 candidate pools differ")
        old = {item["document_id"]: item for item in before}
        new = {item["document_id"]: item for item in after}
        for identifier, baseline in old.items():
            changed = new[identifier]
            if baseline["pre_rerank_rank"] != changed["pre_rerank_rank"] or baseline["reranked"] != changed["reranked"]:
                raise ValueError("A5/A6 reranking head or upstream ranks differ")
            if not baseline["reranked"]:
                if baseline != changed:
                    raise ValueError("A5/A6 unscored tails differ")
                continue
            def supports(item):
                return [(support["method"], support["support_id"], support["source_spans"])
                        for support in item["cross_encoder_scores_by_support"]]
            if supports(baseline) != supports(changed):
                raise ValueError("A5/A6 selected support passages differ")
            for label, candidate in (("A5", baseline), ("A6", changed)):
                for support in candidate["cross_encoder_scores_by_support"]:
                    diagnostic = support["cross_encoder_input"]
                    if diagnostic.get("available") is not True or not isinstance(diagnostic.get("truncated"), bool):
                        raise ValueError("Actual tokenizer diagnostics required for comparison")
                    stats = counts[label]
                    stats["scored_support_requests"] += 1
                    stats["truncated_support_requests"] += int(diagnostic["truncated"])
                    stats["max_visible_pair_tokens"] = max(stats["max_visible_pair_tokens"], diagnostic["tokens_model_input"])
                    if label == "A6":
                        window = diagnostic.get("evidence_window", {})
                        if diagnostic.get("source_span_scope") != "CROPPED_PAIR_OFFSETS_ONLY" or window.get("gold_used") is not False:
                            raise ValueError("A6 needs inference-only crop provenance")
                        if diagnostic["truncated"] or window.get("prepared_pair_tokens") != diagnostic["tokens_model_input"]:
                            raise ValueError("A6 visible input exceeds or disagrees with tokenizer diagnostics")
                        if support.get("model_visible_source_spans") is not None:
                            raise ValueError("Cropped input cannot claim full original raw spans as visible")
                        stats["query_cropped_requests"] += int(window["query_cropped"])
                        stats["passage_cropped_requests"] += int(window["passage_cropped"])
                        stats["budget_repaired_requests"] += int(bool(window.get("query_budget_repair_steps", 0) or window.get("passage_budget_repair_steps", 0)))
    return {"query_count": len(records["A5"]), "candidate_pool_and_supports_equal": True,
            "tokenization": counts, "counting_unit": "support requests, including exact-pair cache reuse"}


def compare(run_dir: Path, queries_path: Path, *, repetitions: int = 10000, seed: int = 20261028) -> dict[str, Any]:
    manifest = read_json(run_dir / "run_manifest.json")
    for name, filename in (("predictions", "predictions.jsonl"), ("metrics", "metrics.json")):
        if sha256_file(run_dir / filename) != manifest["artifacts"][name]["sha256"]:
            raise ValueError("Comparison artifact checksum mismatch")
    if sha256_file(queries_path) != manifest["dataset"]["files"]["queries"]["sha256"]:
        raise ValueError("Query-to-parent mapping does not match the frozen run")
    audit = verify_candidates(read_jsonl(run_dir / "predictions.jsonl"))
    metrics = read_json(run_dir / "metrics.json")
    for label in METHODS:
        if "100" not in metrics[METHODS[label]]["parent_macro"]:
            raise ValueError("Comparison requires parent-balanced candidate Recall@100")
    candidate_recall = {label: metrics[name]["parent_macro"]["100"]["recall"] for label, name in METHODS.items()}
    if candidate_recall["A5"] != candidate_recall["A6"]:
        raise ValueError("Candidate Recall@100 changed despite fixed pool")
    bootstrap = analyse(metrics_path=run_dir / "metrics.json", queries_path=queries_path,
                        repetitions=repetitions, seed=seed, methods=METHODS, contrasts=(("A6", "A5"),))
    return {"schema_version": 1, "run_id": manifest["run_id"],
            "result_classification": manifest["result_classification"],
            "dataset_role": manifest["config"]["resolved"]["protocol"]["dataset_role"],
            "audit": audit, "parent_recall_at_100": candidate_recall, "bootstrap": bootstrap,
            "inference_timing_note": "Shared model and exact-pair cache: sequential method times are not independent cold latency.",
            "claim_limit": "Input-construction comparison; cannot isolate truncation alone or establish end-to-end plagiarism/assessment accuracy."}


def render(result: dict[str, Any]) -> str:
    def interval(value):
        return f"{value['estimate']:.6f} [{value['ci_lower']:.6f}, {value['ci_upper']:.6f}]"
    lines = ["# Controlled A5/A6 short-evidence comparison", "",
             f"Run: `{result['run_id']}`; classification: `{result['result_classification']}`; role: `{result['dataset_role']}`.", "",
             "| Method | Parent Recall@10 [95% CI] | MRR@10 [95% CI] | nDCG@10 [95% CI] | Candidate R@100 |",
             "|---|---|---|---|---|"]
    for label in METHODS:
        metrics = result["bootstrap"]["estimates"][label]["metrics"]
        lines.append(f"| {label} | {interval(metrics['recall_at_10'])} | {interval(metrics['mrr_at_10'])} | {interval(metrics['ndcg_at_10'])} | {result['parent_recall_at_100'][label]:.6f} |")
    lines += ["", "A6 minus A5 (paired parent resampling):"]
    for metric, value in result["bootstrap"]["paired_deltas"]["A6-A5"]["metrics"].items():
        lines.append(f"- {metric}: {interval(value)}")
    lines += ["", "| Method | Scored support requests | Truncated | Query cropped | Passage cropped | Budget repaired | Max visible tokens |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for label, values in result["audit"]["tokenization"].items():
        lines.append("| " + label + " | " + " | ".join(str(value) for value in values.values()) + " |")
    lines += ["", result["audit"]["counting_unit"] + ".", "", result["inference_timing_note"], "", result["claim_limit"], ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.run_dir, args.queries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(result), encoding="utf-8")
    write_json(args.output.with_suffix(".json"), result)
    print(args.output)


if __name__ == "__main__":
    main()
