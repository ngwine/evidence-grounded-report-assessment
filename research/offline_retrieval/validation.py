"""Governance and semantic-provenance gates for research dataset packs."""

from __future__ import annotations

import re
from typing import Any

from .common import sha256_text


SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def validate_approved_governance(manifest: dict[str, Any]) -> None:
    """Require explicit data-handling decisions for every approved pack."""

    governance = manifest.get("governance")
    if not isinstance(governance, dict) or governance.get("status") != "APPROVED":
        raise ValueError("Dataset governance must be APPROVED")

    classification = _required_text(
        governance.get("classification"), "governance.classification"
    )
    _required_text(governance.get("retention"), "governance.retention")
    if not isinstance(governance.get("contains_pii"), bool):
        raise ValueError("governance.contains_pii must be an explicit boolean")

    transformation = manifest.get("transformation")
    is_pan_pack = (
        isinstance(transformation, dict)
        and transformation.get("converter") == "research.pan_pilot"
    )
    if not is_pan_pack or classification == "SYNTHETIC_PUBLIC":
        return

    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ValueError("Approved PAN pack requires source provenance")
    archives = source.get("archives")
    if not isinstance(archives, list) or not archives:
        raise ValueError("Approved PAN pack requires source.archives")
    for index, archive in enumerate(archives):
        if not isinstance(archive, dict):
            raise ValueError(f"source.archives[{index}] must be an object")
        _required_text(archive.get("name"), f"source.archives[{index}].name")
        local_sha256 = _required_text(
            archive.get("local_sha256"),
            f"source.archives[{index}].local_sha256",
        )
        if not SHA256_RE.fullmatch(local_sha256):
            raise ValueError(
                f"source.archives[{index}].local_sha256 must be 64 lowercase hex"
            )
        size_bytes = archive.get("size_bytes")
        if (
            isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes <= 0
        ):
            raise ValueError(f"source.archives[{index}].size_bytes must be positive")
        if archive.get("provider_checksum_verified") is not True:
            raise ValueError(
                f"source.archives[{index}] provider checksum must be verified"
            )

    provenance = transformation.get("converter_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Approved PAN pack requires converter provenance")
    code_sha256 = _required_text(
        provenance.get("code_sha256"),
        "transformation.converter_provenance.code_sha256",
    )
    if not SHA256_RE.fullmatch(code_sha256):
        raise ValueError("converter provenance code_sha256 must be 64 lowercase hex")


def validate_pan_semantic_provenance(
    manifest: dict[str, Any],
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    qrels: list[dict[str, Any]],
) -> None:
    """Cross-check hashes and raw spans emitted by ``research.pan_pilot``."""

    transformation = manifest.get("transformation")
    if not isinstance(transformation, dict) or transformation.get(
        "converter"
    ) != "research.pan_pilot":
        return

    documents_by_id = {record["document_id"]: record for record in documents}
    for document in documents:
        digest = sha256_text(document["text"])
        if document.get("raw_sha256") != digest:
            raise ValueError(
                f"Document {document['document_id']} raw_sha256 does not match text"
            )
        if document.get("version") != f"sha256:{digest}":
            raise ValueError(
                f"Document {document['document_id']} version does not match text"
            )

    for chunk in chunks:
        document = documents_by_id[chunk["document_id"]]
        if chunk.get("document_version") != document["version"]:
            raise ValueError(
                f"Chunk {chunk['chunk_id']} document_version does not match document"
            )
        spans = chunk["source_spans"]
        if len(spans) != 1:
            raise ValueError(
                f"PAN chunk {chunk['chunk_id']} must have exactly one raw source span"
            )
        span = spans[0]
        expected = document["text"][span["raw_start"] : span["raw_end"]]
        if chunk["text"] != expected:
            raise ValueError(
                f"Chunk {chunk['chunk_id']} text does not match its raw source span"
            )

    for query in queries:
        provenance = query.get("annotation_provenance")
        if not isinstance(provenance, dict):
            raise ValueError(f"Query {query['query_id']} lacks annotation provenance")
        if provenance.get("text_sha256") != sha256_text(query["text"]):
            raise ValueError(f"Query {query['query_id']} text hash does not match")

    for qrel in qrels:
        document = documents_by_id[qrel["document_id"]]
        annotated = qrel.get("annotated_source_span")
        if not isinstance(annotated, dict):
            raise ValueError(f"Qrel {qrel['qrel_id']} lacks annotated_source_span")
        if (
            annotated.get("raw_start") != qrel["raw_start"]
            or annotated.get("raw_end") != qrel["raw_end"]
        ):
            raise ValueError(f"Qrel {qrel['qrel_id']} source spans disagree")
        expected = document["text"][qrel["raw_start"] : qrel["raw_end"]]
        if annotated.get("text_sha256") != sha256_text(expected):
            raise ValueError(f"Qrel {qrel['qrel_id']} source text hash does not match")

    files = manifest.get("files", {})
    for name, records in (
        ("documents", documents),
        ("chunks", chunks),
        ("queries", queries),
        ("qrels", qrels),
    ):
        declared = files.get(name, {}).get("records")
        if declared != len(records):
            raise ValueError(
                f"Manifest files.{name}.records={declared} does not match {len(records)}"
            )
