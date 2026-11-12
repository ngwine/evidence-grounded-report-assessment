from research.offline_retrieval.analysis.analyze_cross_encoder_ablation import (
    group_summary,
    span_overlaps_gold,
    transition_summary,
)


def _row(query_id: str, parent_id: str, **ranks: int | None) -> dict:
    return {
        "query_id": query_id,
        "parent_annotation_id": parent_id,
        "relevant_document_id": "doc-gold",
        **ranks,
    }


def test_transition_summary_counts_gains_and_losses() -> None:
    rows = [
        _row("q1", "p1", A2=1, A4=2),
        _row("q2", "p1", A2=3, A4=12),
        _row("q3", "p2", A2=20, A4=4),
        _row("q4", "p3", A2=30, A4=40),
    ]

    result = transition_summary(rows, "A2", "A4", 10)

    assert result["counts"] == {
        "hit_to_hit": 1,
        "hit_to_miss": 1,
        "miss_to_hit": 1,
        "miss_to_miss": 1,
    }
    assert result["net_top_k_hits"] == 0


def test_group_summary_keeps_parent_count_and_median_rank() -> None:
    rows = [
        _row("q1", "p1", A1=30, A2=1, A3=15, A4=2, A5=20),
        _row("q2", "p1", A1=40, A2=3, A3=25, A4=4, A5=10),
        _row("q3", "p2", A1=None, A2=5, A3=35, A4=6, A5=None),
    ]

    result = group_summary(rows, 10)

    assert result["query_windows"] == 3
    assert result["unique_parent_annotations"] == 2
    assert result["top_k_hits"] == {
        "A1": 0,
        "A2": 3,
        "A3": 0,
        "A4": 3,
        "A5": 1,
    }
    assert result["retrieved_in_output"] == {
        "A1": 2,
        "A2": 3,
        "A3": 3,
        "A4": 3,
        "A5": 2,
    }
    assert result["missing_from_output"] == {
        "A1": 1,
        "A2": 0,
        "A3": 0,
        "A4": 0,
        "A5": 1,
    }
    assert result["median_rank"]["A2"] == 3
    assert result["median_rank"]["A3"] == 25


def test_span_overlap_requires_same_document_and_positive_intersection() -> None:
    spans = [
        {"document_id": "doc-other", "raw_start": 100, "raw_end": 200},
        {"document_id": "doc-gold", "raw_start": 200, "raw_end": 300},
    ]

    assert span_overlaps_gold(
        spans, document_id="doc-gold", raw_start=250, raw_end=400
    )
    assert not span_overlaps_gold(
        spans, document_id="doc-gold", raw_start=300, raw_end=400
    )
