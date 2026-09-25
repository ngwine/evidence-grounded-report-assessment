"""Unit and end-to-end tests for the offline retrieval runner."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from research.offline_retrieval.aggregation import collapse_to_documents
from research.offline_retrieval.bm25 import rank_bm25
from research.offline_retrieval.common import read_json, read_jsonl, sha256_file
from research.offline_retrieval.dense import local_model_revision
from research.offline_retrieval.fixed_window import build_fixed_windows
from research.offline_retrieval.metrics import evaluate_rankings
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

    assert metrics["macro"]["1"] == {"recall": 1.0, "mrr": 1.0, "ndcg": 1.0}


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
