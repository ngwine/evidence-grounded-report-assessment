"""Unit and end-to-end tests for the offline retrieval runner."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

import research.offline_retrieval.dense as dense_module
import research.offline_retrieval.runner as runner_module
from research.offline_retrieval.aggregation import collapse_to_documents
from research.offline_retrieval.bm25 import rank_bm25
from research.offline_retrieval.common import read_json, read_jsonl, sha256_file
from research.offline_retrieval.dense import local_model_revision, rank_dense
from research.offline_retrieval.fixed_window import build_fixed_windows
from research.offline_retrieval.metrics import (
    evaluate_document_rankings,
    evaluate_rankings,
)
from research.offline_retrieval.rrf import fuse_rrf
from research.offline_retrieval.runner import run_experiment, validate_inputs


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "retrieval_pilot_v1"


class KeywordFixtureEncoder:
    """Test-only semantic encoder; never exposed as a scientific Dense model."""

    metadata = {
        "backend": "injected_test",
        "model": "keyword-fixture-encoder",
        "revision": "synthetic-fixture-v1",
        "scientific_result": False,
    }

    def __init__(self) -> None:
        self.mode = "document"

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def encode(self, texts):
        vectors = []
        for text in texts:
            lowered = text.casefold()
            if "phân cụm" in lowered or "không nhãn" in lowered or "chưa gán nhãn" in lowered:
                vector = [0.0, 1.0, 0.0]
            elif "cây" in lowered or "thuộc tính" in lowered or "chia dữ liệu" in lowered:
                vector = [0.0, 0.0, 1.0]
            elif "gán nhãn" in lowered or "có nhãn" in lowered or "đầu vào và nhãn" in lowered:
                vector = [1.0, 0.0, 0.0]
            else:
                vector = [0.1, 0.1, 0.1]
            vectors.append(vector)
        return vectors


class LockedVectorEncoder:
    """Return locked vectors for direct Dense ranking tests."""

    metadata = {"backend": "test", "revision": "locked-vectors-v1"}

    def __init__(self, document_vectors, query_vectors) -> None:
        self.mode = "document"
        self.document_vectors = document_vectors
        self.query_vectors = query_vectors

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def encode(self, _texts):
        if self.mode == "document":
            return self.document_vectors
        return self.query_vectors


def test_local_model_revision_hashes_paths_and_content_deterministically(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}\n", encoding="utf-8")
    weights = model_dir / "weights"
    weights.mkdir()
    (weights / "part.bin").write_bytes(b"weights")

    first = local_model_revision(model_dir)
    second = local_model_revision(model_dir)

    assert first == second
    assert first.startswith("sha256:")
    (weights / "part.bin").write_bytes(b"changed")
    assert local_model_revision(model_dir) != first


def test_fixed_windows_have_stable_ids_and_exact_raw_spans():
    documents = read_jsonl(FIXTURE_DIR / "documents.jsonl")

    first = build_fixed_windows(documents, size_tokens=8, stride_tokens=4)
    second = build_fixed_windows(documents, size_tokens=8, stride_tokens=4)

    assert first == second
    assert len({item["chunk_id"] for item in first}) == len(first)
    source_by_id = {document["document_id"]: document["text"] for document in documents}
    for item in first:
        [span] = item["source_spans"]
        assert item["text"] == source_by_id[item["document_id"]][
            span["raw_start"] : span["raw_end"]
        ]


def test_bm25_and_rrf_use_deterministic_chunk_id_tie_breaking():
    corpus = [
        {"chunk_id": "b", "document_id": "d", "text": "same", "source_spans": []},
        {"chunk_id": "a", "document_id": "d", "text": "same", "source_spans": []},
    ]
    queries = [{"query_id": "q", "text": "same"}]
    bm25 = rank_bm25(corpus, queries, top_k=2)
    assert [candidate["chunk_id"] for candidate in bm25["q"]] == ["a", "b"]

    fused = fuse_rrf(
        {
            "one": {"q": [{**bm25["q"][0], "rank": 1}, {**bm25["q"][1], "rank": 2}]},
            "two": {"q": [{**bm25["q"][1], "rank": 1}, {**bm25["q"][0], "rank": 2}]},
        },
        rrf_k=60,
        top_k=2,
    )
    assert [candidate["chunk_id"] for candidate in fused["q"]] == ["a", "b"]


@pytest.mark.parametrize("group_by_document", [False, True])
def test_numpy_dense_matches_reference_with_ties_zeroes_and_document_grouping(
    monkeypatch, group_by_document
):
    if dense_module._np is None:
        pytest.skip("NumPy is installed only in the optional research environment")

    corpus = [
        {"chunk_id": "c-b", "document_id": "z", "text": "one", "source_spans": []},
        {"chunk_id": "c-a", "document_id": "z", "text": "two", "source_spans": []},
        {"chunk_id": "c-c", "document_id": "a", "text": "three", "source_spans": []},
        {"chunk_id": "c-d", "document_id": "b", "text": "four", "source_spans": []},
        {"chunk_id": "c-0", "document_id": "c", "text": "zero", "source_spans": []},
    ]
    queries = [
        {"query_id": "q-x", "text": "x"},
        {"query_id": "q-y", "text": "y"},
        {"query_id": "q-0", "text": "zero"},
    ]
    document_vectors = [
        [1.0, 0.0],
        [1.0, 0.0],
        [1.0, 0.0],
        [0.0, 1.0],
        [0.0, 0.0],
    ]
    query_vectors = [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]

    vectorized = rank_dense(
        corpus,
        queries,
        encoder=LockedVectorEncoder(document_vectors, query_vectors),
        top_k=4,
        group_by_document=group_by_document,
    )
    monkeypatch.setattr(dense_module, "_np", None)
    reference = rank_dense(
        corpus,
        queries,
        encoder=LockedVectorEncoder(document_vectors, query_vectors),
        top_k=4,
        group_by_document=group_by_document,
    )

    assert vectorized == reference
    if group_by_document:
        assert vectorized["q-x"][0]["document_id"] == "a"
        assert next(
            item for item in vectorized["q-x"] if item["document_id"] == "z"
        )["supporting_chunk_id"] == "c-a"
    else:
        assert [item["chunk_id"] for item in vectorized["q-x"][:3]] == [
            "c-a",
            "c-b",
            "c-c",
        ]


def test_rrf_keeps_method_specific_support_provenance():
    bm25_span = {"document_id": "d", "raw_start": 0, "raw_end": 10}
    dense_span = {"document_id": "d", "raw_start": 20, "raw_end": 30}

    [candidate] = fuse_rrf(
        {
            "bm25": {
                "q": [
                    {
                        "document_id": "d",
                        "supporting_chunk_id": "bm25-chunk",
                        "rank": 1,
                        "score": 4.5,
                        "source_spans": [bm25_span],
                    }
                ]
            },
            "dense": {
                "q": [
                    {
                        "document_id": "d",
                        "supporting_chunk_id": "dense-chunk",
                        "rank": 2,
                        "score": 0.75,
                        "source_spans": [dense_span],
                    }
                ]
            },
        },
        rrf_k=60,
        top_k=1,
        key_field="document_id",
    )["q"]

    assert candidate["rrf_ranks"] == {"bm25": 1, "dense": 2}
    assert candidate["rrf_supporting_ids"] == {
        "bm25": "bm25-chunk",
        "dense": "dense-chunk",
    }
    assert candidate["supports_by_method"] == {
        "bm25": {
            "support_id": "bm25-chunk",
            "supporting_chunk_id": "bm25-chunk",
            "rank": 1,
            "score": 4.5,
            "source_spans": [bm25_span],
        },
        "dense": {
            "support_id": "dense-chunk",
            "supporting_chunk_id": "dense-chunk",
            "rank": 2,
            "score": 0.75,
            "source_spans": [dense_span],
        },
    }
    assert candidate["representative_support_method"] == "bm25"
    assert candidate["supporting_chunk_id"] == "bm25-chunk"
    assert candidate["source_spans"] == [bm25_span, dense_span]


def test_span_grounded_metrics_use_gold_span_not_chunk_id():
    rankings = {
        "q": [
            {
                "chunk_id": "arbitrary-window-id",
                "document_id": "d",
                "rank": 1,
                "score": 1.0,
                "source_spans": [{"document_id": "d", "raw_start": 5, "raw_end": 15}],
            }
        ]
    }
    qrels = [
        {"qrel_id": "g", "query_id": "q", "document_id": "d", "raw_start": 7, "raw_end": 13}
    ]
    metrics = evaluate_rankings(rankings, qrels, cutoffs=[1], overlap_threshold=0.5)

    assert metrics["coverage_mode"] == "cumulative_union"
    assert metrics["macro"]["1"] == {"recall": 1.0, "mrr": 1.0, "ndcg": 1.0}


def test_span_metrics_accumulate_union_coverage_without_double_counting():
    rankings = {
        "q": [
            {
                "chunk_id": "c1",
                "document_id": "d",
                "rank": 1,
                "score": 2.0,
                "source_spans": [
                    {"document_id": "d", "raw_start": 0, "raw_end": 40}
                ],
            },
            {
                "chunk_id": "c2",
                "document_id": "d",
                "rank": 2,
                "score": 1.0,
                "source_spans": [
                    {"document_id": "d", "raw_start": 20, "raw_end": 60}
                ],
            },
        ]
    }
    qrels = [
        {
            "qrel_id": "g",
            "query_id": "q",
            "document_id": "d",
            "raw_start": 0,
            "raw_end": 100,
        }
    ]

    metrics = evaluate_rankings(
        rankings, qrels, cutoffs=[1, 2], overlap_threshold=0.6
    )

    assert metrics["coverage_mode"] == "cumulative_union"
    assert metrics["macro"]["1"]["recall"] == 0.0
    assert metrics["macro"]["2"]["recall"] == 1.0
    assert metrics["macro"]["2"]["mrr"] == 0.5


def test_document_metrics_report_parent_balanced_macro_for_uneven_windows():
    rankings = {
        "q-a1": [{"document_id": "wrong"}],
        "q-a2": [{"document_id": "wrong"}],
        "q-a3": [{"document_id": "wrong"}],
        "q-b1": [{"document_id": "gold-b"}],
    }
    qrels = [
        {
            "query_id": "q-a1",
            "document_id": "gold-a",
            "parent_annotation_id": "parent-a",
        },
        {
            "query_id": "q-a2",
            "document_id": "gold-a",
            "parent_annotation_id": "parent-a",
        },
        {
            "query_id": "q-a3",
            "document_id": "gold-a",
            "parent_annotation_id": "parent-a",
        },
        {
            "query_id": "q-b1",
            "document_id": "gold-b",
            "parent_annotation_id": "parent-b",
        },
    ]

    metrics = evaluate_document_rankings(rankings, qrels, cutoffs=[1])

    assert metrics["macro"]["1"] == {"recall": 0.25, "mrr": 0.25, "ndcg": 0.25}
    assert metrics["parent_annotation_count"] == 2
    assert metrics["queries_per_parent"] == {"parent-a": 3, "parent-b": 1}
    assert metrics["parent_macro"]["1"] == {
        "recall": 0.5,
        "mrr": 0.5,
        "ndcg": 0.5,
    }


def test_document_aggregation_keeps_one_best_chunk_per_source():
    collapsed = collapse_to_documents(
        {
            "q": [
                {
                    "chunk_id": "d1-c1",
                    "document_id": "d1",
                    "rank": 1,
                    "score": 4.0,
                    "source_spans": [],
                },
                {
                    "chunk_id": "d1-c2",
                    "document_id": "d1",
                    "rank": 2,
                    "score": 3.0,
                    "source_spans": [],
                },
                {
                    "chunk_id": "d2-c1",
                    "document_id": "d2",
                    "rank": 3,
                    "score": 2.0,
                    "source_spans": [],
                },
            ]
        },
        top_k=2,
    )

    assert [item["document_id"] for item in collapsed["q"]] == ["d1", "d2"]
    assert [item["supporting_chunk_id"] for item in collapsed["q"]] == [
        "d1-c1",
        "d2-c1",
    ]
    assert [item["rank"] for item in collapsed["q"]] == [1, 2]


def test_bm25_groups_documents_before_top_k_truncation():
    corpus = [
        {
            "chunk_id": "d1-c1",
            "document_id": "d1",
            "text": "target target target",
            "source_spans": [],
        },
        {
            "chunk_id": "d1-c2",
            "document_id": "d1",
            "text": "target target",
            "source_spans": [],
        },
        {
            "chunk_id": "d2-c1",
            "document_id": "d2",
            "text": "target",
            "source_spans": [],
        },
    ]

    ranking = rank_bm25(
        corpus,
        [{"query_id": "q", "text": "target"}],
        top_k=2,
        group_by_document=True,
    )["q"]

    assert {candidate["document_id"] for candidate in ranking} == {"d1", "d2"}
    assert all("supporting_chunk_id" in candidate for candidate in ranking)


def test_dataset_gate_rejects_unapproved_manifest(tmp_path):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)
    manifest_path = copied / "dataset-manifest.json"
    manifest = read_json(manifest_path)
    manifest["governance"]["status"] = "PENDING"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="not APPROVED"):
        validate_inputs(
            manifest_path,
            copied / "config.json",
            allow_test_encoder=True,
        )


def test_dataset_gate_rejects_query_qrel_parent_mismatch(tmp_path):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)
    queries_path = copied / "queries.jsonl"
    qrels_path = copied / "qrels.jsonl"
    queries = read_jsonl(queries_path)
    qrels = read_jsonl(qrels_path)
    queries[0]["parent_annotation_id"] = "parent-query"
    qrels[0]["parent_annotation_id"] = "parent-qrel"
    queries_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in queries
        ),
        encoding="utf-8",
    )
    qrels_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in qrels
        ),
        encoding="utf-8",
    )
    manifest_path = copied / "dataset-manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"]["queries"]["sha256"] = sha256_file(queries_path)
    manifest["files"]["qrels"]["sha256"] = sha256_file(qrels_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="does not match query"):
        validate_inputs(
            manifest_path,
            copied / "config.json",
            allow_test_encoder=True,
        )


def test_runner_cannot_misclassify_an_injected_encoder_as_scientific(tmp_path):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)
    config_path = copied / "config.json"
    config = read_json(config_path)
    config["dense"]["backend"] = "sentence_transformers"
    config["dense"]["model"] = "cached/model"
    config["dense"]["revision"] = "a" * 40
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="injected encoder is allowed only"):
        run_experiment(
            copied / "dataset-manifest.json",
            config_path,
            tmp_path / "run",
            encoder=KeywordFixtureEncoder(),
        )


def test_document_scope_runner_collapses_before_metrics_and_rrf(tmp_path):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)
    qrels_path = copied / "qrels.jsonl"
    qrels = read_jsonl(qrels_path)
    for qrel in qrels:
        qrel["target_scope"] = "document"
    qrels_path.write_text(
        "".join(
            json.dumps(qrel, ensure_ascii=False, sort_keys=True) + "\n"
            for qrel in qrels
        ),
        encoding="utf-8",
    )
    manifest_path = copied / "dataset-manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"]["qrels"]["sha256"] = sha256_file(qrels_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    config_path = copied / "config.json"
    config = read_json(config_path)
    config["metrics"]["target_scope"] = "document"
    config["candidate_retrieval_depth"] = 20
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    result = run_experiment(
        manifest_path,
        config_path,
        tmp_path / "run",
        encoder=KeywordFixtureEncoder(),
        allow_test_encoder=True,
    )

    predictions = read_jsonl(result["predictions_path"])
    for record in predictions:
        document_ids = [
            candidate["document_id"] for candidate in record["candidates"]
        ]
        assert len(document_ids) == len(set(document_ids))
        assert all("supporting_chunk_id" in candidate for candidate in record["candidates"])
    metrics = read_json(result["metrics_path"])
    assert metrics["structure_hybrid_rrf"]["target_scope"] == "document"
    assert metrics["structure_hybrid_rrf"]["macro"]["3"]["recall"] == 1.0


def test_multiview_rrf_requires_document_target_scope(tmp_path):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)
    config_path = copied / "config.json"
    config = read_json(config_path)
    config["methods"] = ["multiview_hybrid_rrf"]
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="multiview_hybrid_rrf requires metrics.target_scope=document",
    ):
        validate_inputs(
            copied / "dataset-manifest.json",
            config_path,
            allow_test_encoder=True,
        )


def test_multiview_rrf_fuses_fixed_bm25_and_structure_dense_at_document_scope(
    tmp_path, monkeypatch
):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)

    qrels_path = copied / "qrels.jsonl"
    qrels = read_jsonl(qrels_path)
    for qrel in qrels:
        qrel["target_scope"] = "document"
    qrels_path.write_text(
        "".join(
            json.dumps(qrel, ensure_ascii=False, sort_keys=True) + "\n"
            for qrel in qrels
        ),
        encoding="utf-8",
    )
    manifest_path = copied / "dataset-manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"]["qrels"]["sha256"] = sha256_file(qrels_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    config_path = copied / "config.json"
    config = read_json(config_path)
    config["methods"] = ["multiview_hybrid_rrf"]
    config["retrieval_depth"] = 1
    config["candidate_retrieval_depth"] = 2
    config["metric_cutoffs"] = [1]
    config["metrics"]["target_scope"] = "document"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    calls = {"bm25": 0, "dense": 0}

    def ranked_candidate(item, rank, score):
        return {
            "document_id": item["document_id"],
            "supporting_chunk_id": item["chunk_id"],
            "rank": rank,
            "score": score,
            "source_spans": item["source_spans"],
        }

    def fake_bm25(corpus, queries, *, top_k, group_by_document, **_kwargs):
        calls["bm25"] += 1
        items = list(corpus)
        assert top_k == 2
        assert group_by_document is True
        assert items and all(item["chunk_id"].startswith("fw-") for item in items)
        by_document = {item["document_id"]: item for item in items}
        ordered = [
            ranked_candidate(by_document["doc-supervised"], 1, 2.0),
            ranked_candidate(by_document["doc-tree"], 2, 1.0),
        ]
        return {
            str(query["query_id"]): [dict(candidate) for candidate in ordered]
            for query in queries
        }

    def fake_dense(corpus, queries, *, top_k, group_by_document, **_kwargs):
        calls["dense"] += 1
        items = list(corpus)
        assert top_k == 2
        assert group_by_document is True
        assert items and all(not item["chunk_id"].startswith("fw-") for item in items)
        by_document = {item["document_id"]: item for item in items}
        ordered = [
            ranked_candidate(by_document["doc-unsupervised"], 1, 0.9),
            ranked_candidate(by_document["doc-tree"], 2, 0.8),
        ]
        return {
            str(query["query_id"]): [dict(candidate) for candidate in ordered]
            for query in queries
        }

    monkeypatch.setattr(runner_module, "rank_bm25", fake_bm25)
    monkeypatch.setattr(runner_module, "rank_dense", fake_dense)

    result = run_experiment(
        manifest_path,
        config_path,
        tmp_path / "run",
        encoder=KeywordFixtureEncoder(),
        allow_test_encoder=True,
    )

    assert calls == {"bm25": 1, "dense": 1}
    predictions = read_jsonl(result["predictions_path"])
    assert {record["method"] for record in predictions} == {
        "multiview_hybrid_rrf"
    }
    for record in predictions:
        [winner] = record["candidates"]
        assert winner["document_id"] == "doc-tree"
        assert winner["rrf_ranks"] == {
            "fixed_window_bm25": 2,
            "structure_dense": 2,
        }
        assert set(winner["supports_by_method"]) == {
            "fixed_window_bm25",
            "structure_dense",
        }
        assert set(winner["rrf_supporting_ids"]) == {
            "fixed_window_bm25",
            "structure_dense",
        }

    assert set(result["run_manifest"]["timing_seconds"]) == {
        "fixed_window_build",
        "fixed_window_bm25",
        "structure_dense",
        "multiview_hybrid_rrf",
        "evaluation",
    }


def test_span_runner_fuses_candidate_depth_before_final_truncation(
    tmp_path, monkeypatch
):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)

    def candidate(item, rank, score):
        return {
            "chunk_id": item["chunk_id"],
            "document_id": item["document_id"],
            "rank": rank,
            "score": score,
            "source_spans": item["source_spans"],
        }

    def fake_bm25(corpus, queries, *, top_k, **_kwargs):
        items = list(corpus)
        by_id = {item["chunk_id"]: item for item in items}
        if "doc-supervised-c1" in by_id:
            ordered = [
                candidate(by_id["doc-supervised-c1"], 1, 2.0),
                candidate(by_id["doc-tree-c1"], 2, 1.0),
            ]
        else:
            ordered = [
                candidate(item, rank, 3.0 - rank)
                for rank, item in enumerate(items[:2], 1)
            ]
        return {
            str(query["query_id"]): [dict(value) for value in ordered[:top_k]]
            for query in queries
        }

    def fake_dense(corpus, queries, *, top_k, **_kwargs):
        by_id = {item["chunk_id"]: item for item in corpus}
        ordered = [
            candidate(by_id["doc-unsupervised-c1"], 1, 0.9),
            candidate(by_id["doc-tree-c1"], 2, 0.8),
        ]
        return {
            str(query["query_id"]): [dict(value) for value in ordered[:top_k]]
            for query in queries
        }

    monkeypatch.setattr(runner_module, "rank_bm25", fake_bm25)
    monkeypatch.setattr(runner_module, "rank_dense", fake_dense)

    def run_with_candidate_depth(value):
        config_path = copied / f"config-{value}.json"
        config = read_json(copied / "config.json")
        config["retrieval_depth"] = 1
        config["candidate_retrieval_depth"] = value
        config["metric_cutoffs"] = [1]
        config_path.write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8"
        )
        result = run_experiment(
            copied / "dataset-manifest.json",
            config_path,
            tmp_path / f"run-{value}",
            encoder=KeywordFixtureEncoder(),
            allow_test_encoder=True,
        )
        predictions = read_jsonl(result["predictions_path"])
        return next(
            record["candidates"][0]["chunk_id"]
            for record in predictions
            if record["method"] == "structure_hybrid_rrf"
            and record["query_id"] == "q-supervised"
        )

    assert run_with_candidate_depth(1) == "doc-supervised-c1"
    # The shared rank-2 candidate wins only if both two-deep lists reach RRF.
    assert run_with_candidate_depth(2) == "doc-tree-c1"


def test_bm25_only_run_does_not_load_or_execute_dense_model(tmp_path, monkeypatch):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)
    config_path = copied / "config.json"
    config = read_json(config_path)
    config["methods"] = ["fixed_window_bm25", "structure_bm25"]
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    def unexpected_dense(*_args, **_kwargs):
        raise AssertionError("Dense path must not run in a BM25-only experiment")

    monkeypatch.setattr(runner_module, "_make_encoder", unexpected_dense)
    monkeypatch.setattr(runner_module, "rank_dense", unexpected_dense)

    result = run_experiment(
        copied / "dataset-manifest.json",
        config_path,
        tmp_path / "run",
        allow_test_encoder=True,
    )

    metrics = read_json(result["metrics_path"])
    assert set(metrics) == {"fixed_window_bm25", "structure_bm25"}
    timings = result["run_manifest"]["timing_seconds"]
    assert set(timings) == {
        "fixed_window_build",
        "fixed_window_bm25",
        "structure_bm25",
        "evaluation",
    }


def test_full_runner_writes_reproducibility_manifest_and_stable_artifacts(tmp_path):
    encoder = KeywordFixtureEncoder()
    first_dir = tmp_path / "run-one"
    second_dir = tmp_path / "run-two"

    first = run_experiment(
        FIXTURE_DIR / "dataset-manifest.json",
        FIXTURE_DIR / "config.json",
        first_dir,
        encoder=encoder,
        allow_test_encoder=True,
    )
    second = run_experiment(
        FIXTURE_DIR / "dataset-manifest.json",
        FIXTURE_DIR / "config.json",
        second_dir,
        encoder=KeywordFixtureEncoder(),
        allow_test_encoder=True,
    )

    assert first["predictions_path"].read_bytes() == second["predictions_path"].read_bytes()
    assert first["metrics_path"].read_bytes() == second["metrics_path"].read_bytes()
    manifest = read_json(first["run_manifest_path"])
    assert manifest["result_classification"] == "TEST_ONLY"
    assert manifest["seed"] == 20260923
    assert manifest["git"]["commit"]
    assert manifest["dataset"]["dataset_version"] == "1.0.0"
    assert manifest["config"]["sha256"]
    assert manifest["dense_encoder"]["revision"] == "synthetic-fixture-v1"
    assert manifest["hardware"]["machine"]
    assert set(manifest["timing_seconds"]) == {
        "fixed_window_build",
        "fixed_window_bm25",
        "structure_bm25",
        "structure_dense",
        "structure_hybrid_rrf",
        "evaluation",
    }
    assert set(manifest["artifacts"]) == {"predictions", "metrics"}
    assert "/Users/" not in first["run_manifest_path"].read_text(encoding="utf-8")

    metrics = read_json(first["metrics_path"])
    assert set(metrics) == {
        "fixed_window_bm25",
        "structure_bm25",
        "structure_dense",
        "structure_hybrid_rrf",
    }
    assert metrics["structure_dense"]["macro"]["3"]["recall"] == 1.0
