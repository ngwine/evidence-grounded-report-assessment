"""Controlled short-evidence runner checks on public synthetic fixtures only."""

from __future__ import annotations

from copy import deepcopy
import json
import re

import pytest

from research.offline_retrieval.common import read_json, read_jsonl, sha256_file
from research.offline_retrieval.runner import run_experiment, validate_inputs
from research.tests.test_cross_encoder_runner import (
    KeywordEncoder,
    _prepare_cross_encoder_fixture,
)


A5 = "multiview_hybrid_cross_encoder"
A6 = "multiview_hybrid_cross_encoder_short_evidence"


class OffsetTokenizer:
    """Small deterministic tokenizer with character offsets, not a model mock."""

    is_fast = True
    model_max_length = 128

    def num_special_tokens_to_add(self, pair=False):
        return 3 if pair else 2

    def __call__(self, text, text_pair=None, **kwargs):
        matches = list(re.finditer(r"\S+", text))
        ids = list(range(10, 10 + len(matches)))
        offsets = [match.span() for match in matches]
        if text_pair is not None:
            second = list(re.finditer(r"\S+", text_pair))
            if kwargs.get("add_special_tokens", True):
                ids = [0, *ids, 1, *range(100, 100 + len(second)), 2]
            else:
                ids += list(range(100, 100 + len(second)))
            offsets += [match.span() for match in second]
        elif kwargs.get("add_special_tokens", True):
            ids = [0, *ids, 1]
        if kwargs.get("truncation"):
            ids = ids[: kwargs.get("max_length", self.model_max_length)]
        result = {"input_ids": ids}
        if kwargs.get("return_offsets_mapping"):
            result["offset_mapping"] = offsets
        return result


class RecordingScorer:
    metadata = {
        "backend": "injected_test",
        "model": "synthetic-offset-scorer",
        "revision": "synthetic-short-evidence-v1",
        "max_length": 128,
    }

    def __init__(self):
        self.tokenizer = OffsetTokenizer()
        self.pairs = []

    def score_pairs(self, pairs):
        self.pairs.extend(pairs)
        return [float(len(set(re.findall(r"\w+", query.casefold()))
                          & set(re.findall(r"\w+", passage.casefold()))))
                for query, passage in pairs]

    def pair_diagnostics(self, pairs):
        results = []
        for query, passage in pairs:
            count = len(self.tokenizer(query, passage)["input_ids"])
            results.append({"available": True, "truncated": count > 128,
                            "tokens_before_truncation": count,
                            "tokens_model_input": min(count, 128),
                            "max_length": 128})
        return results


def _prepare(root, *, with_short=True):
    root.mkdir(parents=True)
    manifest, path, config = _prepare_cross_encoder_fixture(root)
    if with_short:
        config["methods"].append(A6)
        config["cross_encoder"]["evidence_input_policy"] = {
            "strategy": "lexical_window_v1",
            "query_token_budget": 3,
            "passage_token_budget": 4,
        }
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return manifest, path, config


def _run(manifest, config, output):
    return run_experiment(
        manifest, config, output, encoder=KeywordEncoder(),
        reranker=RecordingScorer(), allow_test_encoder=True,
        allow_test_reranker=True,
    )


def _predictions(result):
    return {(item["method"], item["query_id"]): item["candidates"]
            for item in read_jsonl(result["predictions_path"])}


def test_short_variant_preserves_original_methods_pool_supports_and_input_files(tmp_path):
    original_manifest, original_config, _ = _prepare(tmp_path / "original", with_short=False)
    short_manifest, short_config, _ = _prepare(tmp_path / "short")
    paths = [short_manifest, short_config]
    paths += [short_manifest.parent / item["path"]
              for item in read_json(short_manifest)["files"].values()]
    before = {path: path.read_bytes() for path in paths}

    original = _predictions(_run(original_manifest, original_config, tmp_path / "baseline-run"))
    short = _predictions(_run(short_manifest, short_config, tmp_path / "comparison-run"))

    for key, candidates in original.items():
        assert short[key] == candidates, f"Adding A6 changed original method {key}"
    for method, query_id in short:
        if method != A6:
            continue
        before_candidates = short[A5, query_id]
        after_candidates = short[A6, query_id]
        assert len(after_candidates) == len(before_candidates) == 3
        assert {item["document_id"] for item in after_candidates} == {
            item["document_id"] for item in before_candidates
        }
        assert after_candidates[2:] == before_candidates[2:]
        by_document = {item["document_id"]: item for item in before_candidates[:2]}
        assert set(by_document) == {item["document_id"] for item in after_candidates[:2]}
        for item in after_candidates[:2]:
            previous = by_document[item["document_id"]]
            assert item["pre_rerank_rank"] == previous["pre_rerank_rank"]
            assert [(support["method"], support["support_id"])
                    for support in item["cross_encoder_scores_by_support"]] == [
                (support["method"], support["support_id"])
                for support in previous["cross_encoder_scores_by_support"]
            ]
            assert item["cross_encoder_input"]["truncated"] is False
            # Full candidate spans remain origins, not asserted cropped views.
            assert item["model_visible_source_spans"] is None
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("mutation", [
    lambda policy: policy.update(strategy="gold_span_window"),
    lambda policy: policy.update(query_token_budget=0),
    lambda policy: policy.update(passage_token_budget=-1),
    lambda policy: policy.update(query_token_budget=True),
    lambda policy: policy.update(passage_token_budget="4"),
    lambda policy: policy.update(query_token_budget=128, passage_token_budget=128),
    lambda policy: policy.pop("query_token_budget"),
])
def test_short_variant_rejects_invalid_or_unlocked_policy(tmp_path, mutation):
    manifest, config_path, config = _prepare(tmp_path / "input")
    mutation(config["cross_encoder"]["evidence_input_policy"])
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_inputs(manifest, config_path,
                        allow_test_encoder=True, allow_test_reranker=True)


def test_short_variant_requires_explicit_input_policy(tmp_path):
    manifest, config_path, config = _prepare(tmp_path / "input")
    config["cross_encoder"].pop("evidence_input_policy")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence_input_policy"):
        validate_inputs(manifest, config_path,
                        allow_test_encoder=True, allow_test_reranker=True)


def test_short_variant_can_build_its_own_fixed_dense_and_fused_dependencies(tmp_path):
    manifest, config_path, config = _prepare(tmp_path / "input")
    config["methods"] = [A6]
    config_path.write_text(json.dumps(config), encoding="utf-8")
    result = _run(manifest, config_path, tmp_path / "run")
    predictions = read_jsonl(result["predictions_path"])
    assert {item["method"] for item in predictions} == {A6}
    assert len(predictions) == 3
    assert all(len(item["candidates"]) == 3 for item in predictions)


def test_qrel_span_changes_cannot_change_inference_predictions(tmp_path):
    manifest, config_path, _ = _prepare(tmp_path / "input")
    initial = _predictions(_run(manifest, config_path, tmp_path / "run-before"))
    manifest_record = read_json(manifest)
    path = manifest.parent / manifest_record["files"]["qrels"]["path"]
    qrels = deepcopy(read_jsonl(path))
    for qrel in qrels:
        # Still valid within the same document, but a different arbitrary
        # labelled span. Inference must not inspect these annotation offsets.
        qrel["raw_end"] = qrel["raw_start"] + 1
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                            for item in qrels), encoding="utf-8")
    manifest_record["files"]["qrels"]["sha256"] = sha256_file(path)
    manifest.write_text(json.dumps(manifest_record), encoding="utf-8")
    changed = _predictions(_run(manifest, config_path, tmp_path / "run-after"))
    assert changed == initial


def test_existing_attempt_is_preserved_before_inputs_or_models_are_loaded(tmp_path, monkeypatch):
    import research.offline_retrieval.runner as runner_module

    output = tmp_path / "prior-attempt"
    output.mkdir()
    marker = output / "previous-result.json"
    marker.write_bytes(b'{"preserve": true}\n')

    def unexpected_validation(*_args, **_kwargs):
        pytest.fail("Existing output must be rejected before reading inputs or loading models")

    monkeypatch.setattr(runner_module, "validate_inputs", unexpected_validation)
    with pytest.raises(FileExistsError, match="preserve earlier attempts"):
        run_experiment(tmp_path / "missing-manifest.json",
                       tmp_path / "missing-config.json", output)
    assert marker.read_bytes() == b'{"preserve": true}\n'
    assert list(output.iterdir()) == [marker]
