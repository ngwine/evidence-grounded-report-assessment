"""Focused tests for the locked Cross-Encoder adapter."""

from __future__ import annotations

import sys
import time
import types

import pytest

from research.offline_retrieval.cross_encoder import (
    MemoizedPairScorer,
    SentenceTransformersCrossEncoder,
    locked_model_revision,
    score_pairs,
)
from research.offline_retrieval.dense import local_model_revision


class _InjectedScorer:
    metadata = {
        "backend": "injected_test",
        "revision": "locked-fixture-v1",
        "scientific_result": False,
    }

    def score_pairs(self, pairs):
        return [-0.0, 0.75][: len(pairs)]


def test_injected_pair_scorer_returns_canonical_python_floats():
    values = score_pairs(
        [("query one", "passage one"), ("query two", "passage two")],
        scorer=_InjectedScorer(),
    )

    assert values == [0.0, 0.75]
    assert all(type(value) is float for value in values)


def test_memoized_pair_scorer_reuses_exact_pairs_and_records_counts():
    class CountingScorer:
        metadata = {"backend": "counting-test"}

        def __init__(self):
            self.calls = []

        def score_pairs(self, pairs):
            self.calls.append(list(pairs))
            return [float(len(query) + len(passage)) for query, passage in pairs]

    underlying = CountingScorer()
    scorer = MemoizedPairScorer(underlying)

    assert scorer.score_pairs([("a", "b"), ("a", "b"), ("xx", "y")]) == [
        2.0,
        2.0,
        3.0,
    ]
    assert scorer.score_pairs([("xx", "y"), ("z", "q")]) == [3.0, 2.0]
    assert underlying.calls == [[("a", "b"), ("xx", "y")], [("z", "q")]]
    assert scorer.metadata["exact_pair_memoization"] == {
        "enabled": True,
        "requests": 5,
        "cache_hits": 2,
        "unique_pairs_scored": 3,
    }


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), [0.1, 0.2]])
def test_injected_pair_scorer_rejects_invalid_scalar_outputs(bad_score):
    class BadScorer:
        metadata = {"backend": "bad-test"}

        def score_pairs(self, _pairs):
            return [bad_score]

    with pytest.raises(ValueError):
        score_pairs([("query", "passage")], scorer=BadScorer())


def test_locked_local_model_requires_exact_directory_checksum(tmp_path):
    model_dir = tmp_path / "cross-encoder"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}\n", encoding="utf-8")
    revision = local_model_revision(model_dir)

    model_reference, resolved_revision = locked_model_revision(model_dir, revision)

    assert model_reference == str(model_dir.resolve())
    assert resolved_revision == revision
    with pytest.raises(ValueError, match="checksum mismatch"):
        locked_model_revision(model_dir, "sha256:" + "0" * 64)


def test_cached_model_requires_immutable_commit_revision():
    with pytest.raises(ValueError, match="immutable"):
        locked_model_revision("org/model", "main")

    revision = "a" * 40
    assert locked_model_revision("org/model", revision) == ("org/model", revision)


def test_sentence_transformers_adapter_is_offline_batched_and_deterministic(
    tmp_path, monkeypatch
):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}\n", encoding="utf-8")
    revision = local_model_revision(model_dir)
    calls = {"init": None, "predict": [], "eval": 0}

    class FakeUnderlyingModel:
        def eval(self):
            calls["eval"] += 1

    class FakeTokenizer:
        def __call__(self, query, passage, *, truncation, max_length=None, **_kwargs):
            token_count = len(query.split()) + len(passage.split()) + 3
            if truncation:
                token_count = min(token_count, max_length)
            return {"input_ids": list(range(token_count))}

    class FakeCrossEncoder:
        def __init__(self, model, **kwargs):
            calls["init"] = (model, kwargs)
            self.model = FakeUnderlyingModel()
            self.tokenizer = FakeTokenizer()

        def predict(self, pairs, **kwargs):
            calls["predict"].append((list(pairs), kwargs))
            return [[len(query) / 10] for query, _passage in pairs]

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    scorer = SentenceTransformersCrossEncoder(
        model=model_dir,
        revision=revision,
        device="mps",
        batch_size=2,
        max_length=256,
    )
    pairs = [("a", "x"), ("bb", "y"), ("ccc", "z")]

    first = scorer.score_pairs(pairs)
    second = scorer.score_pairs(pairs)

    assert first == second == [0.1, 0.2, 0.3]
    loaded_model, init_kwargs = calls["init"]
    assert loaded_model == str(model_dir.resolve())
    assert init_kwargs["device"] == "mps"
    assert init_kwargs["local_files_only"] is True
    assert init_kwargs["max_length"] == 256
    assert init_kwargs["activation_fn"].__class__.__name__ == "Identity"
    assert calls["eval"] == 1
    assert [len(batch) for batch, _kwargs in calls["predict"]] == [2, 1, 2, 1]
    assert all(
        kwargs
        == {
            "batch_size": 2,
            "show_progress_bar": False,
            "activation_fn": init_kwargs["activation_fn"],
            "apply_softmax": False,
            "convert_to_numpy": True,
        }
        for _batch, kwargs in calls["predict"]
    )
    assert scorer.metadata == {
        "backend": "sentence_transformers_cross_encoder",
        "model": str(model_dir),
        "resolved_model": str(model_dir.resolve()),
        "revision": revision,
        "device": "mps",
        "batch_size": 2,
        "max_length": 256,
        "local_files_only": True,
        "output": "scalar_float",
        "score_output": "raw_logit",
        "activation": "torch.nn.Identity",
        "apply_softmax": False,
        "cooperative_deadline_enabled": False,
        "tokenization": {
            "available": True,
            "truncation_strategy": "longest_first",
            "max_length": 256,
            "unique_pairs_inspected": 3,
            "pairs_truncated": 0,
            "max_tokens_before_truncation": 5,
            "max_tokens_model_input": 5,
        },
    }


def test_cached_model_passes_exact_revision_without_network(monkeypatch):
    captured = {}

    class FakeCrossEncoder:
        model = None

        def __init__(self, model, **kwargs):
            captured.update(model=model, kwargs=kwargs)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    revision = "b" * 64

    scorer = SentenceTransformersCrossEncoder(
        model="org/locked-model",
        revision=revision,
        device="cpu",
    )

    assert captured["model"] == "org/locked-model"
    assert captured["kwargs"]["device"] == "cpu"
    assert captured["kwargs"]["local_files_only"] is True
    assert captured["kwargs"]["revision"] == revision
    assert captured["kwargs"]["activation_fn"].__class__.__name__ == "Identity"
    assert scorer.metadata["revision"] == revision
    assert scorer.metadata["local_files_only"] is True


def test_adapter_validates_batch_device_and_pair_shape_before_inference(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    revision = local_model_revision(model_dir)

    with pytest.raises(ValueError, match="batch_size"):
        SentenceTransformersCrossEncoder(
            model=model_dir,
            revision=revision,
            batch_size=0,
        )
    with pytest.raises(ValueError, match="device"):
        SentenceTransformersCrossEncoder(
            model=model_dir,
            revision=revision,
            device="auto",
        )
    with pytest.raises(ValueError, match="score_output"):
        SentenceTransformersCrossEncoder(
            model=model_dir,
            revision=revision,
            score_output="sigmoid_probability",
        )
    with pytest.raises(ValueError, match="two texts"):
        score_pairs([("only one",)], scorer=_InjectedScorer())


def test_adapter_records_pair_level_truncation_without_relabeling_source_span(
    tmp_path, monkeypatch
):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}\n", encoding="utf-8")
    revision = local_model_revision(model_dir)

    class FakeTokenizer:
        def __call__(self, query, passage, *, truncation, max_length=None, **_kwargs):
            token_count = len(query.split()) + len(passage.split()) + 3
            if truncation:
                token_count = min(token_count, max_length)
            return {"input_ids": list(range(token_count))}

    class FakeCrossEncoder:
        model = None
        tokenizer = FakeTokenizer()

        def __init__(self, _model, **_kwargs):
            pass

        def predict(self, pairs, **_kwargs):
            return [0.5 for _pair in pairs]

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    scorer = SentenceTransformersCrossEncoder(
        model=model_dir,
        revision=revision,
        max_length=6,
    )
    pair = ("one two three", "four five six seven")

    assert scorer.score_pairs([pair]) == [0.5]
    [diagnostic] = scorer.pair_diagnostics([pair])
    assert diagnostic == {
        "available": True,
        "truncated": True,
        "tokens_before_truncation": 10,
        "tokens_model_input": 6,
        "max_length": 6,
        "truncation_strategy": "longest_first",
        "source_span_scope": "candidate_passage_before_model_tokenization",
    }
    assert scorer.metadata["tokenization"]["pairs_truncated"] == 1

    scorer.set_deadline(time.perf_counter() - 1.0)
    with pytest.raises(TimeoutError, match="between batches"):
        scorer.score_pairs([pair])
    assert scorer.metadata["cooperative_deadline_enabled"] is True
