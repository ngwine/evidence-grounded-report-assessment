"""Contract tests for the private, exact-vector W5.2 adapter."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.kltn_ai.integrations.indexing import vector_index as module  # noqa: E402
from src.kltn_ai.integrations.indexing.vector_index import (  # noqa: E402
    LocalExactVectorIndex,
)


PURPOSE = "RETRIEVAL_EXPERIMENT"
CONFIG = {"parser_version": "2.0", "chunker_version": "2.0", "code_version": "abc123"}
MODEL = {"name": "fixture-encoder", "revision": "sha256:" + "f" * 64}


def _version(document: str, *, workspace: str = "ws-1", digest: str = "a") -> dict:
    return {
        "workspace_id": workspace,
        "document_id": document,
        "document_version_id": document + ":v1",
        "content_sha256": digest * 64,
        "lifecycle_state": "ACTIVE",
        "processing_state": "READY",
        "governance_state": "APPROVED",
        "allowed_purposes": [PURPOSE],
        "tombstoned": False,
        "rights_basis": "synthetic software fixture",
        "approver": "test-owner",
        "approved_at": "2026-10-22T00:00:00Z",
    }


def _chunk(document: str, chunk_id: str, vector: list[float]) -> dict:
    return {
        "document_id": document,
        "document_version_id": document + ":v1",
        "chunk_id": chunk_id,
        "content_sha256": "b" * 64,
        "vector": vector,
        "source_spans": [{
            "element_key": "element-" + chunk_id,
            "element_raw_char_start": 2,
            "element_raw_char_end": 12,
            "locator": {"page_index": 0, "page_label": "1"},
        }],
    }


def _build(index: LocalExactVectorIndex, *, versions=None, chunks=None, model=None, config=None) -> str:
    return index.build(
        workspace_id="ws-1", purpose=PURPOSE,
        corpus_versions=versions if versions is not None else [_version("a"), _version("b")],
        model=model if model is not None else MODEL,
        config=config if config is not None else CONFIG,
        chunks=chunks if chunks is not None else [
            _chunk("a", "a-2", [2.0, 0.0]),
            _chunk("b", "b-1", [0.0, 1.0]),
            _chunk("a", "a-1", [1.0, 0.0]),
        ],
    )


def test_private_deterministic_generation_and_scoped_exact_top_k(tmp_path, monkeypatch):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    generation_id = _build(index)
    assert generation_id.startswith("vec-")
    generation = index.load(generation_id)
    assert generation["manifest"]["chunk_count"] == 3
    assert generation["manifest"]["dimension"] == 2
    assert generation["manifest"]["local_state"] == "READY_NOT_ACTIVE"
    assert (index.root.stat().st_mode & 0o777) == 0o700
    assert ((index.root / generation_id).stat().st_mode & 0o777) == 0o700
    for name in ("vectors.json", "manifest.json"):
        assert ((index.root / generation_id / name).stat().st_mode & 0o777) == 0o600

    hypot_calls: list[tuple[float, ...]] = []
    real_hypot = math.hypot

    def counting_hypot(*values: float) -> float:
        hypot_calls.append(values)
        return real_hypot(*values)

    monkeypatch.setattr(module.math, "hypot", counting_hypot)
    selected = index.search(
        generation_id, [1, 0], workspace_id="ws-1", purpose=PURPOSE,
        allowed_document_version_ids=["a:v1"], top_k=3,
    )
    assert [item["chunk_id"] for item in selected] == ["a-1", "a-2"]
    assert [item["score"] for item in selected] == [1.0, 1.0]
    assert [item["rank"] for item in selected] == [1, 2]
    assert len(hypot_calls) == 3  # query + two allowed rows; excluded b is never scored
    assert selected[0]["document_version_id"] == "a:v1"
    assert selected[0]["generation_id"] == generation_id
    assert selected[0]["source_spans"][0]["locator"]["page_label"] == "1"
    assert index.search(
        generation_id, [1, 0], workspace_id="ws-1", purpose=PURPOSE,
        allowed_document_version_ids=[], top_k=1,
    ) == []


def test_identical_rebuild_is_idempotent_and_input_order_independent(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    first = _build(index)
    payload_before = (index.root / first / "vectors.json").read_bytes()
    second = _build(
        index,
        versions=[_version("b"), _version("a")],
        chunks=[_chunk("a", "a-1", [1, 0]), _chunk("a", "a-2", [2, 0]), _chunk("b", "b-1", [0, 1])],
    )
    assert second == first
    assert (index.root / first / "vectors.json").read_bytes() == payload_before
    assert len(list(index.root.glob("vec-*"))) == 1


def test_new_model_or_config_makes_new_generation_without_reusing_version(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    first = _build(index)
    other_model = _build(index, model={**MODEL, "revision": "sha256:" + "e" * 64})
    other_config = _build(index, config={**CONFIG, "chunker_version": "2.1"})
    assert len({first, other_model, other_config}) == 3


def test_parser_chunk_without_document_id_can_use_version_lineage(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    chunk = _chunk("a", "parser-chunk", [1, 0])
    chunk.pop("document_id")  # chunker v2 currently emits version ID, not document ID
    generation_id = _build(index, versions=[_version("a")], chunks=[chunk])
    found = index.search(
        generation_id, [1, 0], workspace_id="ws-1", purpose=PURPOSE,
        allowed_document_version_ids=["a:v1"], top_k=1,
    )
    assert found[0]["document_id"] == "a"


def test_extreme_finite_vectors_do_not_overflow_cosine(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    generation_id = _build(
        index, versions=[_version("a")],
        chunks=[_chunk("a", "huge", [1.7e308, 1.7e308])],
    )
    found = index.search(
        generation_id, [1.7e308, 1.7e308], workspace_id="ws-1", purpose=PURPOSE,
        allowed_document_version_ids=["a:v1"], top_k=1,
    )
    assert found[0]["score"] == pytest.approx(1.0)


def test_model_revision_must_be_immutable(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    with pytest.raises(ValueError, match="immutable"):
        _build(index, model={"name": "fixture-encoder", "revision": "main"})


def test_reject_immutable_version_reuse_and_nondeterministic_vectors(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    _build(index)
    with pytest.raises(ValueError, match="Immutable document version reused"):
        _build(index, versions=[_version("a", digest="c"), _version("b")])
    with pytest.raises(ValueError, match="different vector generation"):
        _build(index, chunks=[
            _chunk("a", "a-2", [3, 1]), _chunk("b", "b-1", [0, 1]),
            _chunk("a", "a-1", [1, 0]),
        ])


@pytest.mark.parametrize("bad", [
    [_chunk("a", "dup", [1, 0]), _chunk("b", "dup", [0, 1])],
    [_chunk("a", "a", [1, 0]), _chunk("b", "b", [1, 0, 0])],
    [_chunk("a", "a", [float("nan"), 0])],
    [_chunk("a", "a", [float("inf"), 0])],
    [_chunk("a", "a", [0, 0])],
    [_chunk("a", "a", [True, 1])],
])
def test_reject_duplicate_nonfinite_zero_or_dimension_mismatch(tmp_path, bad):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    with pytest.raises(ValueError):
        _build(index, chunks=bad)


def test_reject_duplicate_versions_wrong_scope_and_unapproved_source(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    with pytest.raises(ValueError, match="Duplicate"):
        _build(index, versions=[_version("a"), _version("a")], chunks=[_chunk("a", "a", [1])])
    with pytest.raises(ValueError, match="different workspace"):
        _build(index, versions=[_version("a", workspace="ws-2")], chunks=[_chunk("a", "a", [1])])
    pending = _version("a")
    pending["governance_state"] = "PENDING"
    with pytest.raises(ValueError, match="not indexable"):
        _build(index, versions=[pending], chunks=[_chunk("a", "a", [1])])
    revoked = _version("a")
    revoked["tombstoned"] = True
    with pytest.raises(ValueError, match="not indexable"):
        _build(index, versions=[revoked], chunks=[_chunk("a", "a", [1])])


def test_search_rejects_cross_workspace_purpose_and_malformed_query(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    generation_id = _build(index)
    kwargs = dict(
        generation_id=generation_id, query_vector=[1, 0],
        workspace_id="ws-1", purpose=PURPOSE,
        allowed_document_version_ids=["a:v1"], top_k=1,
    )
    with pytest.raises(PermissionError):
        index.search(**{**kwargs, "workspace_id": "ws-2"})
    with pytest.raises(PermissionError):
        index.search(**{**kwargs, "purpose": "OTHER"})
    for query in ([1], [float("nan"), 0], [0, 0]):
        with pytest.raises(ValueError):
            index.search(**{**kwargs, "query_vector": query})
    with pytest.raises(ValueError, match="Explicit allowed"):
        index.search(**{**kwargs, "allowed_document_version_ids": None})
    with pytest.raises(ValueError, match="Invalid vector generation ID"):
        index.load("../manifest.json")


def test_tamper_or_public_permissions_fail_closed(tmp_path):
    index = LocalExactVectorIndex(tmp_path / "vectors")
    generation_id = _build(index)
    generation_path = index.root / generation_id
    vectors = generation_path / "vectors.json"
    vectors.write_bytes(vectors.read_bytes().replace(b'"a-1"', b'"a-x"'))
    with pytest.raises(ValueError, match="checksum mismatch"):
        index.load(generation_id)
    with pytest.raises(ValueError, match="checksum mismatch"):
        _build(index)

    other = LocalExactVectorIndex(tmp_path / "other")
    other_id = _build(other)
    manifest = other.root / other_id / "manifest.json"
    manifest_data = json.loads(manifest.read_text())
    manifest_data["chunk_count"] = 999
    manifest.write_text(json.dumps(manifest_data))
    with pytest.raises(ValueError, match="manifest/checksum mismatch"):
        other.load(other_id)

    public = LocalExactVectorIndex(tmp_path / "public")
    public_id = _build(public)
    (public.root / public_id / "vectors.json").chmod(0o644)
    with pytest.raises(PermissionError, match="not private"):
        public.load(public_id)


def test_symlinked_index_path_and_generation_are_rejected(tmp_path):
    real = tmp_path / "real"
    index = LocalExactVectorIndex(real)
    generation_id = _build(index)
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        LocalExactVectorIndex(alias)
    link = index.root / ("vec-" + "0" * 64)
    link.symlink_to(index.root / generation_id, target_is_directory=True)
    with pytest.raises(ValueError, match="does not exist"):
        index.load(link.name)
