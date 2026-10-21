import copy
import hashlib
import json

import pytest

from research.governance import load_registry
from research.mmdocir_pilot import (
    CachedEncoder,
    main,
    retrieved_pages,
    validate_mmdocir_manifest,
)


def test_page_coverage_deduplicates_zero_based_multi_page_evidence():
    candidates = [{"source_spans": [
        {"locator": {"page_index": 0}},
        {"locator": {"page_index": 2}},
        {"locator": {"page_index": 2}},
        {"locator": {"page_index": None}},
    ]}]
    assert retrieved_pages(candidates) == {0, 2}


def test_dense_cache_keeps_query_and_passage_prefixes_separate():
    class Encoder:
        metadata = {}
        mode = "document"
        calls = []

        def set_mode(self, mode):
            self.mode = mode

        def encode(self, texts):
            self.calls.append((self.mode, list(texts)))
            return [[1.0 if self.mode == "query" else 2.0] for _ in texts]

    base = Encoder()
    cache = CachedEncoder(base)
    assert cache.encode(["identical", "identical"]) == [[2.0], [2.0]]
    assert cache.encode(["identical"]) == [[2.0]]
    cache.set_mode("query")
    assert cache.encode(["identical"]) == [[1.0]]
    cache.set_mode("document")
    assert cache.encode(["identical"]) == [[2.0]]
    assert base.calls == [("document", ["identical"]), ("query", ["identical"])]


def _approved_mmdocir_pack(tmp_path):
    annotation = tmp_path / "MMDocIR_annotations.jsonl"
    archive = tmp_path / "doc_pdfs.rar"
    annotation.write_bytes(b'{"doc_name":"example.pdf"}\n')
    archive.write_bytes(b"synthetic test archive")
    digests = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (annotation, archive)}
    registry = copy.deepcopy(load_registry())
    entry = next(item for item in registry["datasets"] if item["id"] == "mmdocir")
    entry["source_sha256"] = digests
    manifest = {
        "dataset_id": "mmdocir-local-evidence-pilot",
        "dataset_version": "test-frozen-v1",
        "governance": {
            "status": "APPROVED",
            "rights_basis": "Apache-2.0 test fixture",
            "allowed_purposes": ["EVIDENCE_RETRIEVAL_EXPERIMENT"],
            "classification": "PUBLIC_RESEARCH_CORPUS",
            "contains_pii": False,
            "retention": "Delete fixture after test",
            "approver": "Test reviewer",
            "approved_at": "2026-10-01",
            "approval_evidence": "synthetic-fixture-only",
        },
        "source": {"files": [{"name": name, "local_sha256": digest} for name, digest in digests.items()]},
        "split": {
            "name": "test-p5",
            "unit": "pdf_document",
            "seed": 20261018,
            "document_ids": [f"synthetic-{i}.pdf" for i in range(5)],
        },
        "files": {
            "annotations": {"path": annotation.name, "sha256": digests[annotation.name]},
            "pdf_archive": {"path": archive.name, "sha256": digests[archive.name]},
        },
    }
    path = tmp_path / "dataset-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, registry, manifest


def test_mmdocir_requires_manifest_argument_before_data_access():
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2


def test_mmdocir_pack_gate_binds_exact_files_and_split(tmp_path):
    path, registry, manifest = _approved_mmdocir_pack(tmp_path)
    assert validate_mmdocir_manifest(path, raw_dir=tmp_path, registry=registry)["dataset_version"] == "test-frozen-v1"

    manifest["governance"]["status"] = "PENDING"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="APPROVED"):
        validate_mmdocir_manifest(path, raw_dir=tmp_path, registry=registry)

    manifest["governance"]["status"] = "APPROVED"
    manifest["split"]["document_ids"] = ["synthetic-0.pdf"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="five selected PDFs"):
        validate_mmdocir_manifest(path, raw_dir=tmp_path, registry=registry)


def test_mmdocir_pack_gate_rejects_wrong_raw_location(tmp_path):
    path, registry, _ = _approved_mmdocir_pack(tmp_path)
    with pytest.raises(ValueError, match="beside the raw files"):
        validate_mmdocir_manifest(path, raw_dir=tmp_path / "other", registry=registry)
