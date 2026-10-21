"""Fail-closed validation of the team's frozen dataset packs.

The registry records what the Excel mapping says. A row marked "USE" is not
enough to authorize a run: the exact pack still needs a frozen manifest with
its own approval, rights basis, split, file hashes and handling decisions.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any


REGISTRY_PATH = Path(__file__).with_name("dataset_registry.json")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    registry = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        raise ValueError("Dataset registry schema_version must be 1")
    datasets = registry.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("Dataset registry needs datasets")
    seen_ids: set[str] = set()
    seen_manifest_ids: set[str] = set()
    for entry in datasets:
        if not isinstance(entry, dict):
            raise ValueError("Dataset registry entries must be objects")
        dataset_id = _text(entry.get("id"), "registry.id")
        if dataset_id in seen_ids:
            raise ValueError(f"Duplicate registry id: {dataset_id}")
        seen_ids.add(dataset_id)
        aliases = entry.get("manifest_ids")
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(f"{dataset_id}.manifest_ids must be non-empty")
        for alias in aliases:
            alias = _text(alias, f"{dataset_id}.manifest_ids")
            if alias in seen_manifest_ids:
                raise ValueError(f"Duplicate manifest id: {alias}")
            seen_manifest_ids.add(alias)
        mapping = entry.get("mapping")
        if not isinstance(mapping, dict) or mapping.get("decision") not in {
            "USE", "REVIEW_REQUIRED", "PENDING"
        }:
            raise ValueError(f"{dataset_id}.mapping.decision is invalid")
        _text(mapping.get("evidence"), f"{dataset_id}.mapping.evidence")
        rights = entry.get("rights")
        if not isinstance(rights, dict) or rights.get("workbook_status") not in {
            "APPROVED", "RIGHTS_REVIEW_REQUIRED", "NOT_REVIEWED"
        }:
            raise ValueError(f"{dataset_id}.rights.workbook_status is invalid")
        _text(rights.get("evidence"), f"{dataset_id}.rights.evidence")
        for name, digest in entry.get("source_sha256", {}).items():
            _text(name, f"{dataset_id}.source_sha256 name")
            _sha256(digest, f"{dataset_id}.source_sha256[{name}]")
    return registry


def _read_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Pack manifest must be an object")
    return manifest


def _verify_split(split: Any) -> None:
    if not isinstance(split, dict):
        raise ValueError("split is required")
    _text(split.get("name"), "split.name")
    _text(split.get("unit"), "split.unit")
    named_partitions = ("train_ids", "validation_ids", "test_ids")
    values = [split.get(name) for name in named_partitions if name in split]
    if values:
        seen: set[str] = set()
        for name in named_partitions:
            ids = split.get(name, [])
            if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids):
                raise ValueError(f"split.{name} must contain non-empty ids")
            duplicate = seen.intersection(ids)
            if duplicate or len(ids) != len(set(ids)):
                raise ValueError("split partitions overlap or contain duplicate ids")
            seen.update(ids)
        if not seen:
            raise ValueError("split partitions cannot all be empty")
    else:
        ids = split.get("document_ids") or split.get("query_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids):
            raise ValueError("split needs frozen document_ids, query_ids or named partitions")
        if len(ids) != len(set(ids)):
            raise ValueError("split ids must be unique")


def _source_digests(manifest: dict[str, Any]) -> dict[str, str]:
    source = manifest.get("source", {})
    if not isinstance(source, dict):
        raise ValueError("source must be an object")
    listed = source.get("archives", source.get("files", []))
    if not isinstance(listed, list):
        raise ValueError("source archives/files must be a list")
    digests: dict[str, str] = {}
    for item in listed:
        if not isinstance(item, dict):
            raise ValueError("source file record must be an object")
        name = _text(item.get("name"), "source file name")
        digest = _sha256(item.get("local_sha256"), f"source file {name}.local_sha256")
        if name in digests:
            raise ValueError(f"Duplicate source file: {name}")
        digests[name] = digest
    return digests


def _verify_pack_files(manifest_path: Path, files: Any, *, verify_files: bool) -> None:
    if not isinstance(files, dict) or not files:
        raise ValueError("files must declare at least one frozen input")
    root = manifest_path.parent.resolve()
    seen_paths: set[Path] = set()
    for logical_name, record in files.items():
        if not isinstance(record, dict):
            raise ValueError(f"files.{logical_name} must be an object")
        raw_path = _text(record.get("path"), f"files.{logical_name}.path")
        relative = PurePosixPath(raw_path)
        if relative.is_absolute() or ".." in relative.parts or raw_path.startswith("~"):
            raise ValueError(f"files.{logical_name}.path must stay inside the pack")
        path = (root / raw_path).resolve()
        if not path.is_relative_to(root) or path in seen_paths:
            raise ValueError(f"files.{logical_name}.path escapes or duplicates a pack file")
        seen_paths.add(path)
        expected = _sha256(record.get("sha256"), f"files.{logical_name}.sha256")
        if verify_files:
            if not path.is_file():
                raise ValueError(f"files.{logical_name}.path does not exist")
            actual_hash = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    actual_hash.update(block)
            if actual_hash.hexdigest() != expected:
                raise ValueError(f"files.{logical_name}.sha256 does not match the file")


def validate_pack_manifest(
    manifest_path: Path,
    purpose: str,
    *,
    registry: dict[str, Any] | None = None,
    verify_files: bool = True,
) -> dict[str, Any]:
    """Validate a specific frozen pack; catalog selection alone never grants access."""

    manifest_path = Path(manifest_path)
    manifest = _read_manifest(manifest_path)
    registry = registry if registry is not None else load_registry()
    manifest_id = _text(manifest.get("dataset_id"), "dataset_id")
    matches = [d for d in registry["datasets"] if manifest_id in d["manifest_ids"]]
    if len(matches) != 1:
        raise ValueError(f"dataset_id {manifest_id} is not registered exactly once")
    entry = matches[0]
    version = _text(manifest.get("dataset_version"), "dataset_version")
    if "UNFROZEN" in version.upper() or "SET_AFTER" in version.upper():
        raise ValueError("dataset_version is not frozen")
    governance = manifest.get("governance")
    if not isinstance(governance, dict) or governance.get("status") != "APPROVED":
        raise ValueError("Pack governance must be APPROVED")
    allowed_purposes = governance.get("allowed_purposes")
    if not isinstance(allowed_purposes, list) or purpose not in allowed_purposes:
        raise ValueError(f"Pack is not approved for {purpose}")
    _text(governance.get("rights_basis"), "governance.rights_basis")
    _text(governance.get("classification"), "governance.classification")
    _text(governance.get("retention"), "governance.retention")
    _text(governance.get("approver"), "governance.approver")
    approved_at = _text(governance.get("approved_at"), "governance.approved_at")
    try:
        date.fromisoformat(approved_at)
    except ValueError as error:
        raise ValueError("governance.approved_at must be an ISO date") from error
    if not isinstance(governance.get("contains_pii"), bool):
        raise ValueError("governance.contains_pii must be an explicit boolean")
    if governance["contains_pii"]:
        _text(governance.get("anonymization"), "governance.anonymization")
    if governance.get("classification") != "SYNTHETIC_PUBLIC":
        _text(governance.get("approval_evidence"), "governance.approval_evidence")
    if entry["id"] == "in-domain-report-rubric":
        authority = governance.get("consent_or_authority")
        if not isinstance(authority, dict) or authority.get("status") != "GRANTED":
            raise ValueError("Private reports require granted consent or authority")
        _text(authority.get("evidence_ref"), "governance.consent_or_authority.evidence_ref")
        _text(governance.get("anonymization"), "governance.anonymization")
    _verify_split(manifest.get("split"))
    _verify_pack_files(manifest_path, manifest.get("files"), verify_files=verify_files)

    expected_source = entry["source_sha256"]
    if expected_source:
        declared_source = _source_digests(manifest)
        if not declared_source:
            raise ValueError("Pack must record the source files it used")
        unknown = set(declared_source) - set(expected_source)
        if unknown:
            raise ValueError(f"Pack declares unregistered source files: {sorted(unknown)}")
        for name, actual in declared_source.items():
            if actual != expected_source[name]:
                raise ValueError(f"Source checksum differs from registry: {name}")

    return {
        "dataset_id": manifest_id,
        "registry_id": entry["id"],
        "dataset_version": version,
        "purpose": purpose,
        "mapping_evidence": entry["mapping"]["evidence"],
        "approval_evidence": governance.get("approval_evidence"),
    }
