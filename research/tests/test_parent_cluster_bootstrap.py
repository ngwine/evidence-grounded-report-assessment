import json
import math

import pytest

from research.offline_retrieval.analysis.bootstrap_parent_metrics import (
    METHODS,
    analyse,
    bootstrap_parent_vectors,
    build_parent_vectors,
    percentile_type7,
)


def _method_metrics(values: dict[str, tuple[float, float, float]]) -> dict:
    per_query = {
        query_id: {
            "10": {
                "recall": recall,
                "reciprocal_rank": mrr,
                "ndcg": ndcg,
            }
        }
        for query_id, (recall, mrr, ndcg) in values.items()
    }
    # p1 owns q1/q2, while p2 owns q3 in these fixtures.
    parent_metrics = {}
    for output_key, value_index in (("recall", 0), ("mrr", 1), ("ndcg", 2)):
        p1 = (values["q1"][value_index] + values["q2"][value_index]) / 2
        p2 = values["q3"][value_index]
        parent_metrics[output_key] = (p1 + p2) / 2
    return {"per_query": per_query, "parent_macro": {"10": parent_metrics}}


def _all_methods(values: dict[str, tuple[float, float, float]]) -> dict:
    return {method_name: _method_metrics(values) for method_name in METHODS.values()}


def test_percentile_type7_interpolates() -> None:
    assert percentile_type7([0.0, 10.0, 20.0, 30.0], 0.25) == 7.5
    assert percentile_type7([0.0, 10.0, 20.0, 30.0], 0.975) == 29.25


def test_parent_vectors_balance_parents_not_query_windows() -> None:
    metrics = _all_methods(
        {
            "q1": (1.0, 1.0, 1.0),
            "q2": (1.0, 1.0, 1.0),
            "q3": (0.0, 0.0, 0.0),
        }
    )
    parents, vectors = build_parent_vectors(
        metrics, {"q1": "p1", "q2": "p1", "q3": "p2"}
    )

    assert parents == ["p1", "p2"]
    assert vectors["A1"]["recall_at_10"] == [1.0, 0.0]
    # Parent-balanced estimate is .5; a query-window average would be 2/3.
    assert math.fsum(vectors["A1"]["recall_at_10"]) / 2 == 0.5


def test_paired_bootstrap_preserves_constant_parent_delta() -> None:
    parents = ["p1", "p2", "p3"]
    vectors = {
        label: {
            metric: [0.1, 0.4, 0.7]
            for metric in ("recall_at_10", "mrr_at_10", "ndcg_at_10")
        }
        for label in METHODS
    }
    for metric in vectors["A2"]:
        vectors["A2"][metric] = [0.3, 0.6, 0.9]

    first = bootstrap_parent_vectors(
        parents, vectors, repetitions=500, seed=17
    )
    second = bootstrap_parent_vectors(
        parents, vectors, repetitions=500, seed=17
    )

    assert first == second
    delta = first["paired_deltas"]["A2-A1"]["metrics"]["recall_at_10"]
    assert delta["estimate"] == pytest.approx(0.2)
    assert delta["ci_lower"] == pytest.approx(0.2)
    assert delta["ci_upper"] == pytest.approx(0.2)


def test_build_parent_vectors_rejects_query_mismatch() -> None:
    metrics = _all_methods(
        {
            "q1": (1.0, 1.0, 1.0),
            "q2": (1.0, 1.0, 1.0),
            "q3": (0.0, 0.0, 0.0),
        }
    )
    del metrics["fixed_window_bm25"]["per_query"]["q3"]

    with pytest.raises(ValueError, match="Query mismatch"):
        build_parent_vectors(
            metrics, {"q1": "p1", "q2": "p1", "q3": "p2"}
        )


def test_analyse_reads_files_and_records_hashes(tmp_path) -> None:
    values = {
        "q1": (1.0, 1.0, 1.0),
        "q2": (1.0, 0.5, 0.6),
        "q3": (0.0, 0.0, 0.0),
    }
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(_all_methods(values)), encoding="utf-8")
    queries_path = tmp_path / "queries.jsonl"
    queries_path.write_text(
        "\n".join(
            json.dumps({"query_id": query, "parent_annotation_id": parent})
            for query, parent in (("q1", "p1"), ("q2", "p1"), ("q3", "p2"))
        )
        + "\n",
        encoding="utf-8",
    )

    result = analyse(
        metrics_path=metrics_path,
        queries_path=queries_path,
        repetitions=100,
        seed=3,
    )

    assert result["parent_count"] == 2
    assert result["query_count"] == 3
    assert result["queries_per_parent"] == {"min": 1, "max": 2}
    assert len(result["inputs"]["metrics"]["sha256"]) == 64
    assert result["estimates"]["A1"]["metrics"]["recall_at_10"][
        "estimate"
    ] == pytest.approx(0.5)
