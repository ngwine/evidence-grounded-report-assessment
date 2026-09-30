"""Runner-level checks for the locked A1--A5 ablation path."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil

from research.offline_retrieval.common import read_json, read_jsonl, sha256_file
from research.offline_retrieval.runner import run_experiment


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "retrieval_pilot_v1"
TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class KeywordEncoder:
    metadata = {"backend": "injected_test", "revision": "fixture-dense-v1"}

    def __init__(self):
        self.mode = "document"

    def set_mode(self, mode):
        self.mode = mode

    def encode(self, texts):
        vectors = []
        for text in texts:
            lowered = text.casefold()
            vectors.append(
                [
                    float("nhãn" in lowered),
                    float("phân cụm" in lowered or "không nhãn" in lowered),
                    float("cây" in lowered or "thuộc tính" in lowered),
                ]
            )
        return vectors


class LexicalPairScorer:
    metadata = {
        "backend": "injected_test",
        "model": "lexical-pair-fixture",
        "revision": "fixture-cross-encoder-v1",
    }

    def score_pairs(self, pairs):
        values = []
        for query, passage in pairs:
            query_tokens = set(TOKEN_RE.findall(query.casefold()))
            passage_tokens = set(TOKEN_RE.findall(passage.casefold()))
            values.append(float(len(query_tokens & passage_tokens)))
        return values


def test_runner_executes_all_five_ablation_methods_with_grounded_reranking(tmp_path):
    copied = tmp_path / "fixture"
    shutil.copytree(FIXTURE_DIR, copied)

    qrels_path = copied / "qrels.jsonl"
    qrels = read_jsonl(qrels_path)
    for qrel in qrels:
        qrel["target_scope"] = "document"
    qrels_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in qrels
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
    config.update(
        {
            "methods": [
                "fixed_window_bm25",
                "structure_dense",
                "multiview_hybrid_rrf",
                "dense_cross_encoder",
                "multiview_hybrid_cross_encoder",
            ],
            "candidate_retrieval_depth": 3,
            "retrieval_depth": 3,
            "metric_cutoffs": [1, 3],
            "cross_encoder": {
                "backend": "injected_test",
                "model": "lexical-pair-fixture",
                "revision": "a" * 40,
                "device": "cpu",
                "batch_size": 4,
                "max_length": 128,
                "rerank_depth": 2,
                "support_aggregation": "max",
            },
        }
    )
    config["metrics"]["target_scope"] = "document"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )

    result = run_experiment(
        manifest_path,
        config_path,
        tmp_path / "run",
        encoder=KeywordEncoder(),
        reranker=LexicalPairScorer(),
        allow_test_encoder=True,
        allow_test_reranker=True,
    )

    predictions = read_jsonl(result["predictions_path"])
    assert {record["method"] for record in predictions} == {
        "fixed_window_bm25",
        "structure_dense",
        "multiview_hybrid_rrf",
        "dense_cross_encoder",
        "multiview_hybrid_cross_encoder",
    }
    reranked = [
        record
        for record in predictions
        if record["method"]
        in {"dense_cross_encoder", "multiview_hybrid_cross_encoder"}
    ]
    assert reranked
    for record in reranked:
        assert len(record["candidates"]) == 3
        assert all(
            candidate["reranked"] for candidate in record["candidates"][:2]
        )
        assert record["candidates"][2]["reranked"] is False
        assert record["candidates"][2]["cross_encoder_score"] is None
    multiview = next(
        record
        for record in reranked
        if record["method"] == "multiview_hybrid_cross_encoder"
    )
    assert all(
        candidate["cross_encoder_support_method"]
        in {"fixed_window_bm25", "structure_dense"}
        for candidate in multiview["candidates"][:2]
    )

    run_manifest = result["run_manifest"]
    assert run_manifest["result_classification"] == "TEST_ONLY"
    assert run_manifest["cross_encoder"]["revision"] == "fixture-cross-encoder-v1"
    assert {
        "fixed_window_bm25",
        "structure_dense",
        "multiview_hybrid_rrf",
        "dense_cross_encoder",
        "multiview_hybrid_cross_encoder",
        "evaluation",
    } <= set(run_manifest["timing_seconds"])
