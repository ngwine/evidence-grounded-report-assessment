#!/usr/bin/env python3
"""Audit the locked A1--A5 DEV0 retrieval/reranking ablation.

The analysis consumes immutable run artifacts; it does not run retrieval,
reranking, or tune a parameter.  The current PAN pilot has one relevant
source document per query, which makes exact Top-K transition counts possible.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any


METHODS = {
    "A1": "fixed_window_bm25",
    "A2": "structure_dense",
    "A3": "multiview_hybrid_rrf",
    "A4": "dense_cross_encoder",
    "A5": "multiview_hybrid_cross_encoder",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object at {path}:{line_number}")
            records.append(value)
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_artifacts(
    predictions_path: Path, metrics_path: Path, manifest_path: Path
) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    expected = manifest.get("artifacts", {})
    for name, path in (("predictions", predictions_path), ("metrics", metrics_path)):
        expected_hash = expected.get(name, {}).get("sha256")
        actual_hash = sha256_file(path)
        if expected_hash != actual_hash:
            raise ValueError(
                f"{name} checksum mismatch: expected={expected_hash!r}, "
                f"actual={actual_hash}"
            )
    return manifest


def load_rankings(
    predictions_path: Path,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    rankings: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    for record in read_jsonl(predictions_path):
        method = record.get("method")
        query_id = record.get("query_id")
        candidates = record.get("candidates")
        if not isinstance(method, str) or not isinstance(query_id, str):
            raise ValueError("Prediction requires method and query_id")
        if not isinstance(candidates, list):
            raise ValueError("Prediction requires candidates")
        if query_id in rankings[method]:
            raise ValueError(f"Duplicate prediction: {method}/{query_id}")
        rankings[method][query_id] = candidates
    missing = set(METHODS.values()) - set(rankings)
    if missing:
        raise ValueError(f"Missing methods: {sorted(missing)}")
    return dict(rankings)


def load_gold(
    dataset_dir: Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, Any]]]:
    queries = read_jsonl(dataset_dir / "queries.jsonl")
    parents: dict[str, str] = {}
    for query in queries:
        query_id = str(query["query_id"])
        if query_id in parents:
            raise ValueError(f"Duplicate query: {query_id}")
        parents[query_id] = str(query["parent_annotation_id"])

    relevant: dict[str, str] = {}
    qrels: dict[str, dict[str, Any]] = {}
    for qrel in read_jsonl(dataset_dir / "qrels.jsonl"):
        query_id = str(qrel["query_id"])
        if query_id in relevant:
            raise ValueError(
                "This audit requires exactly one relevant document per query: "
                f"{query_id}"
            )
        relevant[query_id] = str(qrel["document_id"])
        qrels[query_id] = qrel
    if set(parents) != set(relevant):
        raise ValueError("Query and qrel IDs differ")
    return parents, relevant, qrels


def rank_of(candidates: list[dict[str, Any]], document_id: str) -> int | None:
    for candidate in candidates:
        if candidate.get("document_id") == document_id:
            return int(candidate["rank"])
    return None


def candidate_of(
    candidates: list[dict[str, Any]], document_id: str
) -> dict[str, Any] | None:
    return next(
        (
            candidate
            for candidate in candidates
            if candidate.get("document_id") == document_id
        ),
        None,
    )


def span_overlaps_gold(
    spans: Any, *, document_id: str, raw_start: int, raw_end: int
) -> bool:
    if not isinstance(spans, list):
        return False
    for span in spans:
        if not isinstance(span, dict) or span.get("document_id") != document_id:
            continue
        start = span.get("raw_start")
        end = span.get("raw_end")
        if isinstance(start, int) and isinstance(end, int):
            if max(start, raw_start) < min(end, raw_end):
                return True
    return False


def median_or_none(values: list[int]) -> float | None:
    return statistics.median(values) if values else None


def transition_summary(
    rows: list[dict[str, Any]], before: str, after: str, cutoff: int
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    changed_parents: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        before_hit = row[before] is not None and row[before] <= cutoff
        after_hit = row[after] is not None and row[after] <= cutoff
        label = {
            (True, True): "hit_to_hit",
            (True, False): "hit_to_miss",
            (False, True): "miss_to_hit",
            (False, False): "miss_to_miss",
        }[(before_hit, after_hit)]
        counts[label] += 1
        changed_parents[label].add(row["parent_annotation_id"])
    return {
        "before": before,
        "after": after,
        "cutoff": cutoff,
        "counts": dict(sorted(counts.items())),
        "unique_parents": {
            label: len(parents) for label, parents in sorted(changed_parents.items())
        },
        "net_top_k_hits": counts["miss_to_hit"] - counts["hit_to_miss"],
    }


def group_summary(
    selected: list[dict[str, Any]], cutoff: int
) -> dict[str, Any]:
    rank_fields = tuple(METHODS)
    return {
        "query_windows": len(selected),
        "unique_parent_annotations": len(
            {row["parent_annotation_id"] for row in selected}
        ),
        "top_k_hits": {
            method: sum(
                row[method] is not None and row[method] <= cutoff for row in selected
            )
            for method in rank_fields
        },
        "retrieved_in_output": {
            method: sum(row[method] is not None for row in selected)
            for method in rank_fields
        },
        "missing_from_output": {
            method: sum(row[method] is None for row in selected)
            for method in rank_fields
        },
        # This median is intentionally labelled "observed": missing candidates
        # are right-censored by the output depth and must not be silently
        # treated as if they had a known rank.
        "median_rank": {
            method: median_or_none(
                [int(row[method]) for row in selected if row[method] is not None]
            )
            for method in rank_fields
        },
        "cases": selected,
    }


def analyse(
    *,
    predictions_path: Path,
    metrics_path: Path,
    manifest_path: Path,
    dataset_dir: Path,
    cutoff: int,
) -> dict[str, Any]:
    if cutoff <= 0:
        raise ValueError("cutoff must be positive")
    manifest = validate_artifacts(predictions_path, metrics_path, manifest_path)
    rankings = load_rankings(predictions_path)
    parents, relevant, qrels = load_gold(dataset_dir)
    query_ids = set(relevant)
    for method in METHODS.values():
        if set(rankings[method]) != query_ids:
            raise ValueError(f"Prediction/query mismatch for {method}")

    rows: list[dict[str, Any]] = []
    for query_id in sorted(query_ids):
        relevant_document = relevant[query_id]
        ranks = {
            label: rank_of(rankings[method][query_id], relevant_document)
            for label, method in METHODS.items()
        }
        rows.append(
            {
                "query_id": query_id,
                "parent_annotation_id": parents[query_id],
                "relevant_document_id": relevant_document,
                **ranks,
            }
        )

    dense_rrf_losses = [
        row
        for row in rows
        if row["A2"] is not None
        and row["A2"] <= cutoff
        and (row["A3"] is None or row["A3"] > cutoff)
    ]
    rrf_rescues = [
        row
        for row in rows
        if (row["A2"] is None or row["A2"] > cutoff)
        and row["A3"] is not None
        and row["A3"] <= cutoff
    ]

    rerank_head_diagnostics: dict[str, Any] = {}
    for baseline, reranked in (("A2", "A4"), ("A3", "A5")):
        eligible = [
            row
            for row in rows
            if row[baseline] is not None and row[baseline] <= 50
        ]
        rerank_head_diagnostics[f"{baseline}_to_{reranked}"] = {
            "relevant_in_top_50_before": len(eligible),
            "still_in_top_10_after": sum(
                row[reranked] is not None and row[reranked] <= cutoff
                for row in eligible
            ),
            "not_in_top_10_after": sum(
                row[reranked] is None or row[reranked] > cutoff for row in eligible
            ),
            "median_rank_before": median_or_none(
                [int(row[baseline]) for row in eligible if row[baseline] is not None]
            ),
            "median_rank_after": median_or_none(
                [int(row[reranked]) for row in eligible if row[reranked] is not None]
            ),
        }

    evidence_support_diagnostics: dict[str, Any] = {}
    for label in ("A4", "A5"):
        method = METHODS[label]
        counts: Counter[str] = Counter()
        for row in rows:
            query_id = str(row["query_id"])
            document_id = str(row["relevant_document_id"])
            candidate = candidate_of(rankings[method][query_id], document_id)
            if candidate is None or not candidate.get("reranked"):
                continue
            qrel = qrels[query_id]
            raw_start = int(qrel["raw_start"])
            raw_end = int(qrel["raw_end"])
            support_rows = candidate.get("cross_encoder_scores_by_support", [])
            any_overlap = any(
                isinstance(support, dict)
                and span_overlaps_gold(
                    support.get("source_spans"),
                    document_id=document_id,
                    raw_start=raw_start,
                    raw_end=raw_end,
                )
                for support in support_rows
            )
            winning_overlap = span_overlaps_gold(
                candidate.get("source_spans"),
                document_id=document_id,
                raw_start=raw_start,
                raw_end=raw_end,
            )
            support_truncation = [
                support.get("cross_encoder_input", {}).get("truncated")
                for support in support_rows
                if isinstance(support, dict)
                and isinstance(support.get("cross_encoder_input"), dict)
            ]
            available_truncation = [
                value for value in support_truncation if isinstance(value, bool)
            ]
            any_support_truncated = any(available_truncation)
            all_supports_truncated = bool(available_truncation) and all(
                available_truncation
            )
            winner_truncated = candidate.get("cross_encoder_input", {}).get(
                "truncated"
            )
            top_k_hit = int(candidate["rank"]) <= cutoff
            counts["relevant_documents_reranked"] += 1
            counts["any_support_overlaps_gold"] += int(any_overlap)
            counts["no_support_overlaps_gold"] += int(not any_overlap)
            counts["winning_support_overlaps_gold"] += int(winning_overlap)
            counts["top_k_hit_with_any_overlap"] += int(top_k_hit and any_overlap)
            counts["top_k_miss_with_any_overlap"] += int(not top_k_hit and any_overlap)
            counts["top_k_hit_without_overlap"] += int(top_k_hit and not any_overlap)
            counts["top_k_miss_without_overlap"] += int(not top_k_hit and not any_overlap)
            counts["truncation_available"] += int(bool(available_truncation))
            counts["any_support_truncated"] += int(any_support_truncated)
            counts["all_supports_truncated"] += int(all_supports_truncated)
            counts["winning_support_truncated"] += int(winner_truncated is True)
            counts["top_k_hit_with_truncated_winner"] += int(
                top_k_hit and winner_truncated is True
            )
            counts["top_k_miss_with_truncated_winner"] += int(
                not top_k_hit and winner_truncated is True
            )
        evidence_support_diagnostics[label] = dict(sorted(counts.items()))

    metrics = read_json(metrics_path)
    metric_summary: dict[str, Any] = {}
    for label, method in METHODS.items():
        result = metrics[method]
        metric_summary[label] = {
            "method": method,
            "query_macro": {
                "recall_at_1": result["macro"]["1"]["recall"],
                "recall_at_5": result["macro"]["5"]["recall"],
                "recall_at_10": result["macro"]["10"]["recall"],
                "recall_at_20": result["macro"]["20"]["recall"],
                "recall_at_100": result["macro"]["100"]["recall"],
                "mrr_at_10": result["macro"]["10"]["mrr"],
                "ndcg_at_10": result["macro"]["10"]["ndcg"],
            },
            "parent_macro": {
                "recall_at_1": result["parent_macro"]["1"]["recall"],
                "recall_at_5": result["parent_macro"]["5"]["recall"],
                "recall_at_10": result["parent_macro"]["10"]["recall"],
                "recall_at_20": result["parent_macro"]["20"]["recall"],
                "recall_at_100": result["parent_macro"]["100"]["recall"],
                "mrr_at_10": result["parent_macro"]["10"]["mrr"],
                "ndcg_at_10": result["parent_macro"]["10"]["ndcg"],
            },
        }

    return {
        "schema_version": 1,
        "analysis": "locked_A1_A5_DEV0_cross_encoder_ablation_audit",
        "cutoff": cutoff,
        "query_windows": len(rows),
        "parent_annotations": len(set(parents.values())),
        "artifact_checksums": {
            "predictions": sha256_file(predictions_path),
            "metrics": sha256_file(metrics_path),
        },
        "run_commit": manifest.get("git", {}).get("commit"),
        "cross_encoder_tokenization": manifest.get("cross_encoder", {}).get(
            "tokenization"
        ),
        "timing_seconds": manifest.get("timing_seconds"),
        "timing_context": manifest.get("timing_context"),
        "methods": METHODS,
        "metrics": metric_summary,
        "top_k_transitions": {
            "A2_to_A4": transition_summary(rows, "A2", "A4", cutoff),
            "A3_to_A5": transition_summary(rows, "A3", "A5", cutoff),
        },
        "rerank_head_diagnostics": rerank_head_diagnostics,
        "evidence_support_diagnostics": evidence_support_diagnostics,
        "dense_hit_rrf_loss_group": group_summary(dense_rrf_losses, cutoff),
        "rrf_rescue_group": group_summary(rrf_rescues, cutoff),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--cutoff", type=int, default=10)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyse(
        predictions_path=args.predictions,
        metrics_path=args.metrics,
        manifest_path=args.run_manifest,
        dataset_dir=args.dataset_dir,
        cutoff=args.cutoff,
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
            separators=None if args.pretty else (",", ":"),
        )
    )


if __name__ == "__main__":
    main()
