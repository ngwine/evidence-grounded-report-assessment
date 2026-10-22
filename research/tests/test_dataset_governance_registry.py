"""Specific pack approval must not be inferred from a dataset mapping row."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from research.governance import load_registry, validate_pack_manifest


def _pack(tmp_path: Path, dataset_id: str = "pan-pc-11-source-retrieval-pilot") -> Path:
    payload = tmp_path / "documents.jsonl"
    payload.write_text('{"document_id":"doc-1"}\n', encoding="utf-8")
    manifest = {
        "dataset_id": dataset_id,
        "dataset_version": "pilot-frozen-v1",
        "governance": {
            "status": "APPROVED",
            "allowed_purposes": ["RETRIEVAL_EXPERIMENT"],
            "rights_basis": "Approved limited research use",
            "classification": "PUBLIC_RESEARCH_CORPUS",
            "contains_pii": False,
            "retention": "Delete local copies after the thesis defense",
            "approver": "Reviewer",
            "approved_at": "2026-10-01",
            "approval_evidence": "Dataset mapping row and pack review record",
        },
        "source": {
            "archives": [
                {
                    "name": "pan-plagiarism-corpus-2011.part1.rar",
                    "local_sha256": "ec92d20d29afa7503e3521249ea11421fc6a8ecfc871e0c79764646092ab9c35",
                }
            ]
        },
        "split": {"name": "frozen-dev", "unit": "source_document", "document_ids": ["doc-1"]},
        "files": {
            "documents": {
                "path": payload.name,
                "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
            }
        },
    }
    path = tmp_path / "dataset-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _edit(path: Path, change) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    change(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_registry_keeps_excel_mapping_separate_from_pack_approval():
    registry = load_registry()
    entries = {entry["id"]: entry for entry in registry["datasets"]}
    assert {entries[name]["mapping"]["decision"] for name in ("mmdocir", "hover", "harmogen-r")} == {"USE"}
    assert all(entries[name]["mapping"]["approved_at"] is None for name in ("mmdocir", "hover", "harmogen-r"))
    assert entries["pan13"]["rights"]["workbook_status"] == "RIGHTS_REVIEW_REQUIRED"
    assert entries["in-domain-report-rubric"]["mapping"]["decision"] == "PENDING"


def test_in_domain_template_exposes_every_human_approval_gate():
    template = json.loads((
        Path(__file__).resolve().parents[1]
        / "datasets/assessment/in-domain-report-rubric-pilot-v1/dataset-manifest.template.json"
    ).read_text(encoding="utf-8"))
    governance = template["governance"]
    assert governance["status"] == "PENDING"
    assert governance["consent_or_authority"]["status"] == "PENDING"
    assert governance["pii_review"]["status"] == "PENDING"
    assert "approval_evidence" in governance


def test_frozen_approved_pack_passes_with_exact_hash(tmp_path: Path):
    path = _pack(tmp_path)
    result = validate_pack_manifest(path, "RETRIEVAL_EXPERIMENT")
    assert result["registry_id"] == "pan-pc-11"
    assert result["dataset_version"] == "pilot-frozen-v1"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data["governance"].update(status="PENDING"), "APPROVED"),
        (lambda data: data["governance"].update(contains_pii="UNKNOWN"), "explicit boolean"),
        (lambda data: data["governance"].update(approval_evidence=None), "approval_evidence"),
        (lambda data: data["governance"].update(retention=None), "retention"),
        (lambda data: data["source"]["archives"][0].update(local_sha256="0" * 64), "Source checksum"),
        (lambda data: data["files"]["documents"].update(sha256="0" * 64), "does not match"),
        (lambda data: data["files"]["documents"].update(path="../private.jsonl"), "inside the pack"),
        (lambda data: data.update(dataset_version="UNFROZEN"), "not frozen"),
    ],
)
def test_pack_gate_fails_closed(tmp_path: Path, change, message: str):
    path = _pack(tmp_path)
    _edit(path, change)
    with pytest.raises(ValueError, match=message):
        validate_pack_manifest(path, "RETRIEVAL_EXPERIMENT")


def test_purpose_and_split_are_scoped(tmp_path: Path):
    path = _pack(tmp_path)
    with pytest.raises(ValueError, match="not approved"):
        validate_pack_manifest(path, "ASSESSMENT_EXPERIMENT")
    _edit(path, lambda data: data["split"].update(document_ids=[]))
    with pytest.raises(ValueError, match="frozen"):
        validate_pack_manifest(path, "RETRIEVAL_EXPERIMENT")


def test_private_report_needs_authority_even_if_status_is_approved(tmp_path: Path):
    path = _pack(tmp_path, "in-domain-report-rubric-pilot")
    _edit(path, lambda data: data.update(source={"archives": []}))
    with pytest.raises(ValueError, match="granted consent or authority"):
        validate_pack_manifest(path, "RETRIEVAL_EXPERIMENT")
    _edit(path, lambda data: data["governance"].update(
        anonymization="Names removed and manually checked",
        consent_or_authority={"status": "GRANTED", "evidence_ref": "private-consent-record-id"},
    ))
    with pytest.raises(ValueError, match="CLEARED PII review"):
        validate_pack_manifest(path, "RETRIEVAL_EXPERIMENT")
    _edit(path, lambda data: data["governance"].update(
        pii_review={
            "status": "CLEARED", "reviewer": "Second reviewer",
            "reviewed_at": "2026-10-01", "evidence_ref": "private-pii-review-id",
        },
    ))
    assert validate_pack_manifest(path, "RETRIEVAL_EXPERIMENT")["registry_id"] == "in-domain-report-rubric"
