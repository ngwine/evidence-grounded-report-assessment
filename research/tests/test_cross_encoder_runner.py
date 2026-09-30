"""Runner-level checks for the locked A1--A5 ablation path."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil

import pytest

import research.offline_retrieval.runner as runner_module
from research.offline_retrieval.common import read_json, read_jsonl, sha256_file
from research.offline_retrieval.runner import (
    ExperimentStageError,
    run_experiment,
    validate_inputs,
)


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


class FailingPairScorer:
    metadata = {
        "backend": "injected_test",
        "model": "failing-pair-fixture",
        "revision": "fixture-cross-encoder-failure-v1",
    }

    def score_pairs(self, _pairs):
        raise RuntimeError("synthetic scoring failure")


class SecondCallFailingPairScorer:
    metadata = {
        "backend": "injected_test",
        "model": "second-call-failure-fixture",
        "revision": "fixture-cross-encoder-second-failure-v1",
    }

    def __init__(self):
        self.calls = 0

    def score_pairs(self, pairs):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("synthetic A5 scoring failure")
        return [0.0 for _pair in pairs]


def _prepare_cross_encoder_fixture(root: Path):
    copied = root / "fixture"
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
                "score_output": "raw_logit",
                "failure_policy": "write_partial_baselines_and_fail",
            },
        }
    )
    config["metrics"]["target_scope"] = "document"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    return manifest_path, config_path, config


def test_runner_executes_all_five_ablation_methods_with_grounded_reranking(tmp_path):
    manifest_path, config_path, config = _prepare_cross_encoder_fixture(tmp_path)

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
    assert run_manifest["cross_encoder"]["score_output"] == "raw_logit"
    assert {
        "transformers",
        "tokenizers",
        "safetensors",
        "huggingface-hub",
    } <= set(run_manifest["hardware"]["packages"])
    assert {
        "fixed_window_bm25",
        "structure_dense",
        "multiview_hybrid_rrf",
        "dense_cross_encoder",
        "multiview_hybrid_cross_encoder",
        "evaluation",
    } <= set(run_manifest["timing_seconds"])
    assert "cross_encoder_shared_run_total" in run_manifest["timing_seconds"]
    timing = run_manifest["timing_context"]["cross_encoder"]
    assert timing["model_load_measurement"] == "not_measured_injected_preloaded"
    assert timing["model_load_seconds"] is None
    assert timing["method_measurements"]["dense_cross_encoder"][
        "independent_cold_latency_comparable"
    ] is True
    a5_timing = timing["method_measurements"][
        "multiview_hybrid_cross_encoder"
    ]
    assert a5_timing["cache_state"] == "warm_after_dense_cross_encoder"
    assert a5_timing["independent_cold_latency_comparable"] is False

    config["cross_encoder"]["score_output"] = "sigmoid_probability"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="score_output must be raw_logit"):
        validate_inputs(
            manifest_path,
            config_path,
            allow_test_encoder=True,
            allow_test_reranker=True,
        )

    config["cross_encoder"]["score_output"] = "raw_logit"
    config["cross_encoder"].pop("failure_policy")
    config_path.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="failure_policy"):
        validate_inputs(
            manifest_path,
            config_path,
            allow_test_encoder=True,
            allow_test_reranker=True,
        )

    config["cross_encoder"]["failure_policy"] = (
        "write_partial_baselines_and_fail"
    )
    config["cross_encoder"]["stage_timeout_seconds"] = 0
    config_path.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="stage_timeout_seconds"):
        validate_inputs(
            manifest_path,
            config_path,
            allow_test_encoder=True,
            allow_test_reranker=True,
        )


def _assert_partial_baseline_checkpoint(output_dir: Path, failure_type: str):
    manifest_path = output_dir / "partial_run_manifest.json"
    manifest = read_json(manifest_path)
    assert manifest["status"] == "FAILED"
    assert manifest["result_scope"] == "PARTIAL_BASELINES_ONLY"
    assert manifest["failure"]["exception_type"] == failure_type
    assert manifest["failure"]["completed_methods"] == [
        "fixed_window_bm25",
        "multiview_hybrid_rrf",
        "structure_dense",
    ]
    assert manifest["failure"]["withheld_cross_encoder_methods"] == [
        "dense_cross_encoder",
        "multiview_hybrid_cross_encoder",
    ]
    assert manifest["failure"]["full_ablation_valid"] is False
    predictions = read_jsonl(output_dir / "partial_baseline_predictions.jsonl")
    expected_methods = {
        "fixed_window_bm25",
        "structure_dense",
        "multiview_hybrid_rrf",
    }
    assert {record["method"] for record in predictions} == expected_methods
    assert set(read_json(output_dir / "partial_baseline_metrics.json")) == (
        expected_methods
    )
    assert manifest["dense_encoder"]["revision"] == "fixture-dense-v1"
    assert not (output_dir / "predictions.jsonl").exists()
    assert not (output_dir / "metrics.json").exists()
    assert not (output_dir / "run_manifest.json").exists()


def test_scoring_failure_saves_only_partial_baselines_and_raises(tmp_path):
    manifest_path, config_path, _config = _prepare_cross_encoder_fixture(tmp_path)
    output_dir = tmp_path / "scoring-failure"

    with pytest.raises(ExperimentStageError) as captured:
        run_experiment(
            manifest_path,
            config_path,
            output_dir,
            encoder=KeywordEncoder(),
            reranker=FailingPairScorer(),
            allow_test_encoder=True,
            allow_test_reranker=True,
        )

    assert captured.value.partial_manifest_path == (
        output_dir / "partial_run_manifest.json"
    )
    _assert_partial_baseline_checkpoint(output_dir, "RuntimeError")


def test_constructor_failure_saves_only_partial_baselines_and_raises(
    tmp_path, monkeypatch
):
    manifest_path, config_path, config = _prepare_cross_encoder_fixture(tmp_path)
    config["cross_encoder"]["backend"] = "sentence_transformers_cross_encoder"
    config["cross_encoder"]["model"] = "org/locked-model"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )

    def fail_constructor(_config, _config_path):
        raise RuntimeError("synthetic constructor failure")

    monkeypatch.setattr(runner_module, "_make_reranker", fail_constructor)
    output_dir = tmp_path / "constructor-failure"
    with pytest.raises(ExperimentStageError):
        run_experiment(
            manifest_path,
            config_path,
            output_dir,
            encoder=KeywordEncoder(),
            allow_test_encoder=True,
        )

    _assert_partial_baseline_checkpoint(output_dir, "RuntimeError")
    partial = read_json(output_dir / "partial_run_manifest.json")
    assert partial["cross_encoder"]["construction_completed"] is False
    assert "cross_encoder_model_load" in partial["timing_seconds"]


def test_a5_failure_does_not_publish_completed_a4_as_a_baseline(tmp_path):
    manifest_path, config_path, _config = _prepare_cross_encoder_fixture(tmp_path)
    output_dir = tmp_path / "a5-failure"

    with pytest.raises(ExperimentStageError):
        run_experiment(
            manifest_path,
            config_path,
            output_dir,
            encoder=KeywordEncoder(),
            reranker=SecondCallFailingPairScorer(),
            allow_test_encoder=True,
            allow_test_reranker=True,
        )

    _assert_partial_baseline_checkpoint(output_dir, "RuntimeError")
    partial = read_json(output_dir / "partial_run_manifest.json")
    assert partial["failure"]["active_operation"] == (
        "multiview_hybrid_cross_encoder"
    )
