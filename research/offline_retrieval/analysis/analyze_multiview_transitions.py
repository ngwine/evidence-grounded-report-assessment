#!/usr/bin/env python3
"""Audit Top-K transitions between Dense retrieval and multi-view RRF.

The script deliberately analyses immutable prediction artifacts instead of
re-running retrieval.  It is intended for diagnostic sets with exactly one
relevant source document per query, such as the bounded PAN-PC-11 pilot.

Example:

    python3 research/offline_retrieval/analysis/analyze_multiview_transitions.py \
      --predictions research/results/rq1-pan-pc-11/\
multiview-hybrid-pilot-v1-02a3c4b/predictions.jsonl \
      --run-manifest research/results/rq1-pan-pc-11/\
multiview-hybrid-pilot-v1-02a3c4b/run_manifest.json \
      --dataset-dir var/datasets/derived/similarity/pan-pc-11-pilot-v1 \
      --cutoff 10
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import statistics
from typing import Any, Iterable


BM25_METHOD = "fixed_window_bm25"
DENSE_METHOD = "structure_dense"
RRF_METHOD = "multiview_hybrid_rrf"
TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


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


def unique_by(records: Iterable[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        value = record.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Record requires non-empty {key}")
        if value in indexed:
            raise ValueError(f"Duplicate {key}: {value}")
        indexed[value] = record
    return indexed


def token_set(text: str) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(text)}


def lexical_features(query_text: str, source_text: str) -> dict[str, float | int]:
    query_tokens = token_set(query_text)
    source_tokens = token_set(source_text)
    shared = query_tokens & source_tokens
    union = query_tokens | source_tokens
    return {
        "query_unique_tokens": len(query_tokens),
        "source_unique_tokens": len(source_tokens),
        "shared_unique_tokens": len(shared),
        "token_jaccard": len(shared) / len(union) if union else 0.0,
        "query_token_coverage": len(shared) / len(query_tokens) if query_tokens else 0.0,
    }


def rank_for(
    rankings: dict[str, dict[str, list[dict[str, Any]]]],
    method: str,
    query_id: str,
    document_id: str,
) -> int | None:
    for candidate in rankings[method][query_id]:
        if candidate.get("document_id") == document_id:
            return int(candidate["rank"])
    return None


def rrf_candidate_for(
    rankings: dict[str, dict[str, list[dict[str, Any]]]],
    query_id: str,
    document_id: str,
) -> dict[str, Any] | None:
    return next(
        (
            candidate
            for candidate in rankings[RRF_METHOD][query_id]
            if candidate.get("document_id") == document_id
        ),
        None,
    )


def validate_prediction_artifact(predictions_path: Path, run_manifest_path: Path) -> str:
    run_manifest = read_json(run_manifest_path)
    expected = (
        run_manifest.get("artifacts", {})
        .get("predictions", {})
        .get("sha256")
    )
    actual = sha256_file(predictions_path)
    if not isinstance(expected, str) or expected != actual:
        raise ValueError(
            "Prediction checksum does not match run manifest: "
            f"expected={expected!r}, actual={actual}"
        )
    return actual


def load_rankings(
    predictions_path: Path,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    rankings: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    for record in read_jsonl(predictions_path):
        method = record.get("method")
        query_id = record.get("query_id")
        candidates = record.get("candidates")
        if not isinstance(method, str) or not isinstance(query_id, str):
            raise ValueError("Every prediction record requires method and query_id")
        if not isinstance(candidates, list):
            raise ValueError("Every prediction record requires a candidates list")
        if query_id in rankings[method]:
            raise ValueError(f"Duplicate prediction row: {method}/{query_id}")
        rankings[method][query_id] = candidates
    missing = {BM25_METHOD, DENSE_METHOD, RRF_METHOD} - set(rankings)
    if missing:
        raise ValueError(f"Missing prediction methods: {sorted(missing)}")
    return dict(rankings)


def mechanism_bucket(transition: str, bm25_rank: int, cutoff: int) -> str:
    if transition == "DENSE_HIT_RRF_LOSS":
        if bm25_rank <= 100:
            return "BM25_DISAGREEMENT_RANK_11_100"
        return "BM25_SEVERE_DISAGREEMENT_RANK_101_PLUS"
    if bm25_rank <= cutoff:
        return "BM25_TOP_K_RESCUE"
    return "CROSS_VIEW_MODERATE_CONSENSUS_RESCUE"


def analyse(
    *,
    predictions_path: Path,
    run_manifest_path: Path,
    dataset_dir: Path,
    cutoff: int,
) -> dict[str, Any]:
    if cutoff <= 0:
        raise ValueError("cutoff must be positive")

    predictions_sha256 = validate_prediction_artifact(
        predictions_path, run_manifest_path
    )
    rankings = load_rankings(predictions_path)
    queries = unique_by(read_jsonl(dataset_dir / "queries.jsonl"), "query_id")
    documents = unique_by(
        read_jsonl(dataset_dir / "documents.jsonl"), "document_id"
    )

    qrels_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for qrel in read_jsonl(dataset_dir / "qrels.jsonl"):
        qrels_by_query[str(qrel["query_id"])].append(qrel)
    if set(qrels_by_query) != set(queries):
        raise ValueError("Query IDs and qrel query IDs differ")
    non_singletons = {
        query_id: len(qrels)
        for query_id, qrels in qrels_by_query.items()
        if len(qrels) != 1
    }
    if non_singletons:
        raise ValueError(
            "This diagnostic requires one relevant document per query: "
            f"{non_singletons}"
        )

    method_query_ids = {method: set(rows) for method, rows in rankings.items()}
    for method in (BM25_METHOD, DENSE_METHOD, RRF_METHOD):
        if method_query_ids[method] != set(queries):
            raise ValueError(f"Prediction/query mismatch for {method}")

    cases: list[dict[str, Any]] = []
    parent_effects: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "query_windows": 0,
            "dense_top_k_hits": 0,
            "rrf_top_k_hits": 0,
            "dense_hit_rrf_loss": 0,
            "rrf_rescue": 0,
        }
    )
    for query_id in sorted(queries):
        query = queries[query_id]
        parent_annotation_id = str(query["parent_annotation_id"])
        qrel = qrels_by_query[query_id][0]
        document_id = str(qrel["document_id"])
        dense_rank = rank_for(rankings, DENSE_METHOD, query_id, document_id)
        rrf_candidate = rrf_candidate_for(rankings, query_id, document_id)
        rrf_rank = int(rrf_candidate["rank"]) if rrf_candidate else None

        dense_hit = dense_rank is not None and dense_rank <= cutoff
        rrf_hit = rrf_rank is not None and rrf_rank <= cutoff
        parent_effect = parent_effects[parent_annotation_id]
        parent_effect["query_windows"] += 1
        parent_effect["dense_top_k_hits"] += int(dense_hit)
        parent_effect["rrf_top_k_hits"] += int(rrf_hit)
        if dense_hit == rrf_hit:
            continue

        transition = "DENSE_HIT_RRF_LOSS" if dense_hit else "RRF_RESCUE"
        if transition == "DENSE_HIT_RRF_LOSS":
            parent_effect["dense_hit_rrf_loss"] += 1
        else:
            parent_effect["rrf_rescue"] += 1
        if rrf_candidate is None:
            raise ValueError(
                f"Relevant RRF candidate missing for transition query {query_id}"
            )
        rrf_ranks = rrf_candidate.get("rrf_ranks")
        if not isinstance(rrf_ranks, dict):
            raise ValueError(f"Missing RRF contribution ranks for {query_id}")
        bm25_rank = rrf_ranks.get(BM25_METHOD)
        dense_input_rank = rrf_ranks.get(DENSE_METHOD)
        if not isinstance(bm25_rank, int) or not isinstance(dense_input_rank, int):
            raise ValueError(f"Incomplete RRF contribution ranks for {query_id}")
        if dense_rank != dense_input_rank:
            raise ValueError(f"Dense rank mismatch inside RRF record for {query_id}")

        source_document = documents[document_id]
        raw_start = int(qrel["raw_start"])
        raw_end = int(qrel["raw_end"])
        source_span = str(source_document["text"])[raw_start:raw_end]
        lexical = lexical_features(str(query["text"]), source_span)
        query_window = query.get("query_window", {})
        cases.append(
            {
                "transition": transition,
                "mechanism_bucket": mechanism_bucket(
                    transition, bm25_rank, cutoff
                ),
                "query_id": query_id,
                "parent_annotation_id": parent_annotation_id,
                "query_window_index": query_window.get("index"),
                "relevant_document_id": document_id,
                "bm25_rank": bm25_rank,
                "dense_rank": dense_rank,
                "rrf_rank": rrf_rank,
                "rrf_rank_minus_dense_rank": rrf_rank - dense_rank,
                **lexical,
            }
        )

    transition_counts = Counter(case["transition"] for case in cases)
    mechanism_counts = Counter(case["mechanism_bucket"] for case in cases)
    parent_counts = {
        transition: Counter(
            case["parent_annotation_id"]
            for case in cases
            if case["transition"] == transition
        )
        for transition in sorted(transition_counts)
    }

    summaries: dict[str, Any] = {}
    for transition in sorted(transition_counts):
        selected = [case for case in cases if case["transition"] == transition]
        summaries[transition] = {
            "query_windows": len(selected),
            "unique_parent_annotations": len(parent_counts[transition]),
            "bm25_rank_median": statistics.median(
                case["bm25_rank"] for case in selected
            ),
            "dense_rank_median": statistics.median(
                case["dense_rank"] for case in selected
            ),
            "rrf_rank_median": statistics.median(
                case["rrf_rank"] for case in selected
            ),
            "query_token_coverage_median": statistics.median(
                case["query_token_coverage"] for case in selected
            ),
            "parents": dict(sorted(parent_counts[transition].items())),
        }

    affected_parent_effects: dict[str, Any] = {}
    for parent_annotation_id, effect in sorted(parent_effects.items()):
        if not effect["dense_hit_rrf_loss"] and not effect["rrf_rescue"]:
            continue
        query_windows = effect["query_windows"]
        affected_parent_effects[parent_annotation_id] = {
            **effect,
            "dense_top_k_rate": effect["dense_top_k_hits"] / query_windows,
            "rrf_top_k_rate": effect["rrf_top_k_hits"] / query_windows,
            "rrf_minus_dense_rate": (
                effect["rrf_top_k_hits"] - effect["dense_top_k_hits"]
            )
            / query_windows,
        }

    return {
        "schema_version": 1,
        "analysis": "dense_vs_multiview_rrf_top_k_transition_audit",
        "cutoff": cutoff,
        "predictions_path": predictions_path.as_posix(),
        "predictions_sha256": predictions_sha256,
        "run_manifest_path": run_manifest_path.as_posix(),
        "dataset_dir": dataset_dir.as_posix(),
        "transition_counts": dict(sorted(transition_counts.items())),
        "mechanism_counts": dict(sorted(mechanism_counts.items())),
        "summaries": summaries,
        "affected_parent_effects": affected_parent_effects,
        "cases": cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--cutoff", type=int, default=10)
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON instead of canonical compact output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyse(
        predictions_path=args.predictions,
        run_manifest_path=args.run_manifest,
        dataset_dir=args.dataset_dir,
        cutoff=args.cutoff,
    )
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
