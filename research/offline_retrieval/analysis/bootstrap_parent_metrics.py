#!/usr/bin/env python3
"""Parent-cluster paired bootstrap for the frozen PAN-PC-11 DEV0 run.

The 320 query windows in DEV0 are not independent: overlapping windows were
derived from 30 plagiarism annotations.  This module first averages each
metric within a parent annotation, then resamples the parent annotations with
replacement.  A single resample is shared by every method, so method deltas
remain paired.

Only Python's standard library is used.  The implementation is intentionally
separate from model execution: it consumes an existing ``metrics.json`` and
the dataset ``queries.jsonl`` and cannot tune or rerun a retrieval method.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Mapping, Sequence


METHODS: dict[str, str] = {
    "A1": "fixed_window_bm25",
    "A2": "structure_dense",
    "A3": "multiview_hybrid_rrf",
    "A4": "dense_cross_encoder",
    "A5": "multiview_hybrid_cross_encoder",
}

CONTRASTS: tuple[tuple[str, str], ...] = (
    ("A2", "A1"),
    ("A3", "A2"),
    ("A4", "A2"),
    ("A5", "A3"),
)

METRICS: dict[str, str] = {
    "recall_at_10": "recall",
    "mrr_at_10": "reciprocal_rank",
    "ndcg_at_10": "ndcg",
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile_type7(values: Sequence[float], probability: float) -> float:
    """Return the linearly interpolated (Hyndman--Fan type 7) percentile."""

    if not values:
        raise ValueError("At least one value is required")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def load_query_parents(queries_path: Path) -> dict[str, str]:
    """Load and validate the query-to-parent mapping used for clustering."""

    parents: dict[str, str] = {}
    for record in _read_jsonl(queries_path):
        query_id = record.get("query_id")
        parent_id = record.get("parent_annotation_id")
        if not isinstance(query_id, str) or not query_id:
            raise ValueError("Each query requires a non-empty query_id")
        if not isinstance(parent_id, str) or not parent_id:
            raise ValueError(
                f"Query {query_id!r} requires a non-empty parent_annotation_id"
            )
        if query_id in parents:
            raise ValueError(f"Duplicate query_id in queries file: {query_id}")
        parents[query_id] = parent_id
    if not parents:
        raise ValueError("At least one query is required")
    return parents


def _validate_metric_value(
    *, method: str, query_id: str, metric: str, value: Any
) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Non-numeric {metric} for {method}/{query_id}")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(
            f"Expected {metric} in [0, 1] for {method}/{query_id}; got {value!r}"
        )
    return numeric


def build_parent_vectors(
    metrics: Mapping[str, Any], query_parents: Mapping[str, str]
) -> tuple[list[str], dict[str, dict[str, list[float]]]]:
    """Build aligned per-parent means for every method and metric.

    Parent IDs are sorted once.  All returned vectors therefore share exactly
    the same coordinate system, which is required for paired resampling.
    """

    parent_ids = sorted(set(query_parents.values()))
    queries_by_parent: dict[str, list[str]] = defaultdict(list)
    for query_id, parent_id in query_parents.items():
        queries_by_parent[parent_id].append(query_id)

    vectors: dict[str, dict[str, list[float]]] = {}
    expected_queries = set(query_parents)
    for label, method_name in METHODS.items():
        method_metrics = metrics.get(method_name)
        if not isinstance(method_metrics, Mapping):
            raise ValueError(f"Missing method in metrics.json: {method_name}")
        per_query = method_metrics.get("per_query")
        if not isinstance(per_query, Mapping):
            raise ValueError(f"Missing per_query metrics for {method_name}")
        actual_queries = set(per_query)
        if actual_queries != expected_queries:
            missing = sorted(expected_queries - actual_queries)
            extra = sorted(actual_queries - expected_queries)
            raise ValueError(
                f"Query mismatch for {method_name}: missing={missing[:5]}, "
                f"extra={extra[:5]}"
            )

        by_metric: dict[str, list[float]] = {}
        for metric_label, metric_key in METRICS.items():
            parent_means: list[float] = []
            for parent_id in parent_ids:
                query_values: list[float] = []
                for query_id in queries_by_parent[parent_id]:
                    query_metrics = per_query[query_id]
                    if not isinstance(query_metrics, Mapping):
                        raise ValueError(
                            f"Invalid per_query record for {method_name}/{query_id}"
                        )
                    cutoff_metrics = query_metrics.get("10")
                    if not isinstance(cutoff_metrics, Mapping):
                        raise ValueError(
                            f"Missing cutoff 10 for {method_name}/{query_id}"
                        )
                    query_values.append(
                        _validate_metric_value(
                            method=method_name,
                            query_id=query_id,
                            metric=metric_key,
                            value=cutoff_metrics.get(metric_key),
                        )
                    )
                parent_means.append(math.fsum(query_values) / len(query_values))
            by_metric[metric_label] = parent_means

            stored_parent_macro = method_metrics.get("parent_macro")
            if isinstance(stored_parent_macro, Mapping):
                stored_at_10 = stored_parent_macro.get("10")
                if isinstance(stored_at_10, Mapping):
                    stored_key = "mrr" if metric_key == "reciprocal_rank" else metric_key
                    stored = stored_at_10.get(stored_key)
                    recomputed = math.fsum(parent_means) / len(parent_means)
                    if (
                        not isinstance(stored, (int, float))
                        or isinstance(stored, bool)
                        or not math.isclose(
                            recomputed, float(stored), rel_tol=0.0, abs_tol=1e-12
                        )
                    ):
                        raise ValueError(
                            f"Stored parent_macro mismatch for {method_name}/"
                            f"{metric_label}: stored={stored!r}, "
                            f"recomputed={recomputed}"
                        )
        vectors[label] = by_metric
    return parent_ids, vectors


def bootstrap_parent_vectors(
    parent_ids: Sequence[str],
    vectors: Mapping[str, Mapping[str, Sequence[float]]],
    *,
    repetitions: int,
    seed: int,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Compute percentile intervals with one shared parent resample per draw."""

    if repetitions <= 0:
        raise ValueError("repetitions must be positive")
    if not parent_ids:
        raise ValueError("At least one parent is required")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")

    parent_count = len(parent_ids)
    for label in METHODS:
        if label not in vectors:
            raise ValueError(f"Missing parent vectors for {label}")
        for metric_label in METRICS:
            values = vectors[label].get(metric_label)
            if values is None or len(values) != parent_count:
                raise ValueError(
                    f"Expected {parent_count} values for {label}/{metric_label}"
                )

    method_draws = {
        label: {metric: [] for metric in METRICS} for label in METHODS
    }
    delta_draws = {
        f"{left}-{right}": {metric: [] for metric in METRICS}
        for left, right in CONTRASTS
    }
    rng = random.Random(seed)
    for _ in range(repetitions):
        sampled = [rng.randrange(parent_count) for _ in range(parent_count)]
        for label in METHODS:
            for metric_label in METRICS:
                values = vectors[label][metric_label]
                method_draws[label][metric_label].append(
                    math.fsum(values[index] for index in sampled) / parent_count
                )
        for left, right in CONTRASTS:
            contrast = f"{left}-{right}"
            for metric_label in METRICS:
                left_values = vectors[left][metric_label]
                right_values = vectors[right][metric_label]
                # Compute the paired difference within each sampled parent.
                delta_draws[contrast][metric_label].append(
                    math.fsum(
                        left_values[index] - right_values[index]
                        for index in sampled
                    )
                    / parent_count
                )

    tail = (1.0 - confidence_level) / 2.0

    def summarize(point: float, draws: Sequence[float]) -> dict[str, float]:
        return {
            "estimate": point,
            "ci_lower": percentile_type7(draws, tail),
            "ci_upper": percentile_type7(draws, 1.0 - tail),
        }

    estimates: dict[str, Any] = {}
    for label, method_name in METHODS.items():
        estimates[label] = {
            "method": method_name,
            "metrics": {
                metric_label: summarize(
                    math.fsum(vectors[label][metric_label]) / parent_count,
                    method_draws[label][metric_label],
                )
                for metric_label in METRICS
            },
        }

    deltas: dict[str, Any] = {}
    for left, right in CONTRASTS:
        contrast = f"{left}-{right}"
        deltas[contrast] = {
            "left": left,
            "right": right,
            "metrics": {},
        }
        for metric_label in METRICS:
            paired_parent_differences = [
                left_value - right_value
                for left_value, right_value in zip(
                    vectors[left][metric_label], vectors[right][metric_label]
                )
            ]
            deltas[contrast]["metrics"][metric_label] = summarize(
                math.fsum(paired_parent_differences) / parent_count,
                delta_draws[contrast][metric_label],
            )

    return {
        "confidence_level": confidence_level,
        "repetitions": repetitions,
        "seed": seed,
        "resampling_unit": "parent_annotation",
        "parent_count": parent_count,
        "estimates": estimates,
        "paired_deltas": deltas,
    }


def analyse(
    *,
    metrics_path: Path,
    queries_path: Path,
    repetitions: int,
    seed: int,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    metrics = _read_json(metrics_path)
    query_parents = load_query_parents(queries_path)
    parent_ids, vectors = build_parent_vectors(metrics, query_parents)
    result = bootstrap_parent_vectors(
        parent_ids,
        vectors,
        repetitions=repetitions,
        seed=seed,
        confidence_level=confidence_level,
    )
    query_counts: dict[str, int] = defaultdict(int)
    for parent_id in query_parents.values():
        query_counts[parent_id] += 1
    result.update(
        {
            "schema_version": 1,
            "method_mapping": dict(METHODS),
            "query_count": len(query_parents),
            "queries_per_parent": {
                "min": min(query_counts.values()),
                "max": max(query_counts.values()),
            },
            "inputs": {
                "metrics": {
                    "path": str(metrics_path),
                    "sha256": _sha256(metrics_path),
                },
                "queries": {
                    "path": str(queries_path),
                    "sha256": _sha256(queries_path),
                },
            },
            "interval": {
                "method": "nonparametric_parent_cluster_bootstrap_percentile",
                "quantile": "Hyndman-Fan type 7 linear interpolation",
                "lower_probability": (1.0 - confidence_level) / 2.0,
                "upper_probability": 1.0 - (1.0 - confidence_level) / 2.0,
                "paired_resamples": True,
            },
        }
    )
    return result


def _format_interval(summary: Mapping[str, float]) -> str:
    return (
        f'{summary["estimate"]:.6f} '
        f'[{summary["ci_lower"]:.6f}, {summary["ci_upper"]:.6f}]'
    )


def render_markdown(result: Mapping[str, Any], *, command: str) -> str:
    """Render a deterministic, paper-auditable benchmark note."""

    inputs = result["inputs"]
    repetitions = int(result["repetitions"])
    seed = int(result["seed"])
    lines = [
        "# PAN-PC-11 DEV0 parent-cluster paired bootstrap",
        "",
        "## Scope",
        "",
        "This analysis adds uncertainty intervals to the **frozen DEV0** A1--A5 "
        "retrieval/reranking results. The 320 overlapping query windows are not "
        "treated as independent observations. Each metric is first averaged "
        "within its originating plagiarism annotation, and the 30 parent "
        "annotations are then sampled with replacement. The same parent draw is "
        "used for all methods and paired deltas.",
        "",
        "This is a descriptive diagnostic on a development set, not a final "
        "holdout evaluation or a confirmatory significance test.",
        "",
        "## Reproduction",
        "",
        "```bash",
        command,
        "```",
        "",
        f"- Bootstrap repetitions: `{repetitions:,}`",
        f"- Seed: `{seed}`",
        f'- Confidence interval: `{result["confidence_level"] * 100:.1f}%` '
        "percentile interval (Hyndman--Fan type 7 interpolation)",
        f'- Resampling unit: `{result["resampling_unit"]}`; '
        f'parents: `{result["parent_count"]}`; query windows: '
        f'`{result["query_count"]}`',
        f'- Query windows per parent: `{result["queries_per_parent"]["min"]}`--'
        f'`{result["queries_per_parent"]["max"]}`',
        f'- `metrics.json` SHA-256: `{inputs["metrics"]["sha256"]}`',
        f'- `queries.jsonl` SHA-256: `{inputs["queries"]["sha256"]}`',
        "",
        "## Parent-balanced estimates",
        "",
        "Each cell is `estimate [95% CI]`.",
        "",
        "| ID | Method | Recall@10 | MRR@10 | nDCG@10 |",
        "|---|---|---:|---:|---:|",
    ]
    for label in METHODS:
        entry = result["estimates"][label]
        values = entry["metrics"]
        lines.append(
            f'| {label} | `{entry["method"]}` | '
            f'{_format_interval(values["recall_at_10"])} | '
            f'{_format_interval(values["mrr_at_10"])} | '
            f'{_format_interval(values["ndcg_at_10"])} |'
        )

    lines.extend(
        [
            "",
            "## Paired deltas",
            "",
            "A positive value favors the method on the left. Each bootstrap draw "
            "uses the same sampled parent annotations for both methods.",
            "",
            "| Contrast | Recall@10 | MRR@10 | nDCG@10 |",
            "|---|---:|---:|---:|",
        ]
    )
    for left, right in CONTRASTS:
        contrast = f"{left}-{right}"
        values = result["paired_deltas"][contrast]["metrics"]
        lines.append(
            f'| {contrast} | {_format_interval(values["recall_at_10"])} | '
            f'{_format_interval(values["mrr_at_10"])} | '
            f'{_format_interval(values["ndcg_at_10"])} |'
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- A1 has the highest point estimate on all three parent-balanced "
            "Top-10 metrics in this DEV0 sample.",
            "- A3 versus A2 has a small positive point delta, while A4 versus A2 "
            "and A5 versus A3 are negative. These intervals quantify the "
            "uncertainty among the 30 observed parent annotations; they do not "
            "turn the diagnostic into a final model-selection result.",
            "- The paired construction preserves each parent annotation's "
            "method-by-method comparison. Resampling 320 windows independently "
            "would give long annotations excessive weight and understate "
            "dependence caused by overlap.",
            "",
            "## Caveats",
            "",
            "- DEV0 was used for diagnosis and must not be reused indefinitely "
            "for parameter tuning. An independently frozen DEV1/holdout is still "
            "required for confirmatory comparison.",
            "- A percentile interval that excludes zero is **not reported as a "
            "significance claim** here. The experiment was not preregistered for "
            "hypothesis testing, no multiple-comparison correction is applied, "
            "and only 30 parent annotations are observed.",
            "- Bootstrap uncertainty is conditional on this derived, "
            "resource-bounded positive-query sample. It does not capture corpus "
            "construction, model selection, or annotation uncertainty.",
            "- The pilot contains queries with a known relevant source. It does "
            "not measure false positives, no-source cases, plagiarism-type "
            "classification, final span alignment, or document-level similarity "
            "percentages.",
            "- A1 and A2 differ in both retrieval algorithm and chunk view, so "
            "their delta is not a single-factor causal estimate.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20261012)
    parser.add_argument("--confidence-level", type=float, default=0.95)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write a Markdown report; otherwise print result JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyse(
        metrics_path=args.metrics,
        queries_path=args.queries,
        repetitions=args.repetitions,
        seed=args.seed,
        confidence_level=args.confidence_level,
    )
    if args.output is None:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    command = " \\\n".join(
        [
            "python3 -m research.offline_retrieval.analysis.bootstrap_parent_metrics",
            f"  --metrics {args.metrics}",
            f"  --queries {args.queries}",
            f"  --repetitions {args.repetitions} --seed {args.seed}",
            f"  --output {args.output}",
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        render_markdown(result, command=command), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
