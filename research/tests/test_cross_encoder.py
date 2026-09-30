"""Focused tests for the locked Cross-Encoder adapter."""

from __future__ import annotations

import sys
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

    class FakeCrossEncoder:
        def __init__(self, model, **kwargs):
            calls["init"] = (model, kwargs)
            self.model = FakeUnderlyingModel()

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
    assert calls["init"] == (
        str(model_dir.resolve()),
        {
            "device": "mps",
            "local_files_only": True,
            "max_length": 256,
        },
    )
    assert calls["eval"] == 1
    assert [len(batch) for batch, _kwargs in calls["predict"]] == [2, 1, 2, 1]
    assert all(
        kwargs
        == {
            "batch_size": 2,
            "show_progress_bar": False,
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

    assert captured == {
        "model": "org/locked-model",
        "kwargs": {
            "device": "cpu",
            "local_files_only": True,
            "revision": revision,
        },
    }
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
    with pytest.raises(ValueError, match="two texts"):
        score_pairs([("only one",)], scorer=_InjectedScorer())
