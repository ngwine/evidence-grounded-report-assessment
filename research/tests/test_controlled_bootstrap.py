"""Paired parent uncertainty for a fixed A5/A6 comparison, using synthetic data."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from research.offline_retrieval.analysis.bootstrap_parent_metrics import (
    CONTRASTS,
    METHODS,
    METRICS,
    analyse,
    bootstrap_parent_vectors,
    build_parent_vectors,
)


CONTROLLED_METHODS = {
    "A5": "multiview_hybrid_cross_encoder",
    "A6": "multiview_hybrid_cross_encoder_short_evidence",
}
CONTROLLED_CONTRASTS = (("A6", "A5"),)


def _vectors():
    return {
        "A5": {metric: [0.1, 0.4, 0.7] for metric in METRICS},
        "A6": {metric: [0.3, 0.6, 0.9] for metric in METRICS},
    }


def _metric_records(values):
    return {"per_query": {
        query: {"10": {"recall": value, "reciprocal_rank": value, "ndcg": value}}
        for query, value in values.items()
    }}


def test_custom_pair_is_deterministic_and_preserves_constant_within_parent_delta():
    default_methods, default_contrasts = deepcopy(METHODS), deepcopy(CONTRASTS)
    vectors = _vectors()
    before = deepcopy(vectors)
    kwargs = {
        "repetitions": 500, "seed": 20261028,
        "methods": CONTROLLED_METHODS, "contrasts": CONTROLLED_CONTRASTS,
    }
    first = bootstrap_parent_vectors(["p1", "p2", "p3"], vectors, **kwargs)
    second = bootstrap_parent_vectors(["p1", "p2", "p3"], vectors, **kwargs)

    assert first == second
    assert vectors == before
    assert METHODS == default_methods
    assert CONTRASTS == default_contrasts
    assert set(first["estimates"]) == {"A5", "A6"}
    assert set(first["paired_deltas"]) == {"A6-A5"}
    for metric in METRICS:
        delta = first["paired_deltas"]["A6-A5"]["metrics"][metric]
        # Resampling both arms with the same parent indices is essential:
        # every parent improves by .2, so paired uncertainty is exactly .2.
        assert delta["estimate"] == pytest.approx(0.2)
        assert delta["ci_lower"] == pytest.approx(0.2)
        assert delta["ci_upper"] == pytest.approx(0.2)
    interval = first["estimates"]["A5"]["metrics"]["recall_at_10"]
    assert interval["ci_lower"] < interval["ci_upper"]


def test_custom_methods_keep_parent_balance_with_unequal_window_counts():
    metrics = {
        CONTROLLED_METHODS["A5"]: _metric_records(
            {"q1": 0.0, "q2": 1.0, "q3": 0.25, "q4": 0.75}),
        CONTROLLED_METHODS["A6"]: _metric_records(
            {"q1": 0.2, "q2": 0.6, "q3": 0.55, "q4": 0.95}),
    }
    # Intentionally shuffled: p1 owns two correlated windows, others one.
    parents, vectors = build_parent_vectors(
        metrics, {"q4": "p3", "q2": "p1", "q3": "p2", "q1": "p1"},
        methods=CONTROLLED_METHODS,
    )
    assert parents == ["p1", "p2", "p3"]
    assert vectors["A5"]["recall_at_10"] == [0.5, 0.25, 0.75]
    assert vectors["A6"]["recall_at_10"] == pytest.approx([0.4, 0.55, 0.95])
    result = bootstrap_parent_vectors(
        parents, vectors, repetitions=100, seed=7,
        methods=CONTROLLED_METHODS, contrasts=CONTROLLED_CONTRASTS,
    )
    delta = result["paired_deltas"]["A6-A5"]["metrics"]["recall_at_10"]
    assert delta["estimate"] == pytest.approx((0.4 + 0.55 + 0.95) / 3 - 0.5)


@pytest.mark.parametrize("contrasts", [(("A7", "A5"),), (("A6", "missing"),)])
def test_custom_contrasts_must_reference_configured_arms(contrasts):
    with pytest.raises(ValueError, match="contrasts must reference"):
        bootstrap_parent_vectors(
            ["p1", "p2", "p3"], _vectors(), repetitions=10, seed=7,
            methods=CONTROLLED_METHODS, contrasts=contrasts,
        )


def test_empty_custom_method_mapping_is_rejected():
    with pytest.raises(ValueError, match="configured methods"):
        bootstrap_parent_vectors(
            ["p1", "p2", "p3"], _vectors(), repetitions=10, seed=7,
            methods={}, contrasts=(),
        )


def test_custom_method_vectors_must_cover_identical_parents():
    vectors = _vectors()
    vectors["A6"]["ndcg_at_10"] = [0.3, 0.6]
    with pytest.raises(ValueError, match="Expected 3 values for A6/ndcg_at_10"):
        bootstrap_parent_vectors(
            ["p1", "p2", "p3"], vectors, repetitions=10, seed=7,
            methods=CONTROLLED_METHODS, contrasts=CONTROLLED_CONTRASTS,
        )


def test_analyse_accepts_only_the_controlled_arms_and_records_input_hashes(tmp_path):
    metrics = {
        CONTROLLED_METHODS["A5"]: _metric_records({"q1": 0.1, "q2": 0.1, "q3": 0.7}),
        CONTROLLED_METHODS["A6"]: _metric_records({"q1": 0.3, "q2": 0.3, "q3": 0.9}),
    }
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    queries_path = tmp_path / "queries.jsonl"
    queries_path.write_text("".join(json.dumps({"query_id": query, "parent_annotation_id": parent}) + "\n"
                                    for query, parent in [("q1", "p1"), ("q2", "p1"), ("q3", "p2")]),
                            encoding="utf-8")
    kwargs = {
        "metrics_path": metrics_path, "queries_path": queries_path,
        "repetitions": 200, "seed": 19,
        "methods": CONTROLLED_METHODS, "contrasts": CONTROLLED_CONTRASTS,
    }
    result = analyse(**kwargs)
    assert analyse(**kwargs) == result
    assert result["method_mapping"] == CONTROLLED_METHODS
    assert result["parent_count"] == 2
    assert result["query_count"] == 3
    assert result["queries_per_parent"] == {"min": 1, "max": 2}
    assert result["interval"]["paired_resamples"] is True
    assert result["inputs"]["metrics"]["sha256"] == hashlib.sha256(metrics_path.read_bytes()).hexdigest()
    assert result["inputs"]["queries"]["sha256"] == hashlib.sha256(queries_path.read_bytes()).hexdigest()
    for metric in METRICS:
        summary = result["paired_deltas"]["A6-A5"]["metrics"][metric]
        assert summary["estimate"] == pytest.approx(0.2)
        assert summary["ci_lower"] == pytest.approx(0.2)
        assert summary["ci_upper"] == pytest.approx(0.2)
