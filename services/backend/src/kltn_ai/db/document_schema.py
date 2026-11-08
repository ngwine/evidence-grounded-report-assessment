"""Migration 003: immutable document upload and provenance storage catalog."""

from __future__ import annotations

from typing import Any

from .application_schema import HASH, NULL_ID, OID, record
from .migrations import apply_migration
from .schema import _enum, _text

TEXT = {"bsonType": "string", "maxLength": 2_000_000}
OBJECT = {"bsonType": "object"}
NULL_DATE = {"bsonType": ["date", "null"]}
STRING_ARRAY = {"bsonType": "array", "items": {"bsonType": "string"}, "maxItems": 20000}
ID_ARRAY = {"bsonType": "array", "items": OID, "minItems": 1, "maxItems": 20000, "uniqueItems": True}
NONNEGATIVE = {"bsonType": "int", "minimum": 0}


def _artifact(fields: dict[str, Any], *, optional: tuple[str, ...] = ()) -> dict[str, Any]:
    schema = record(fields)
    schema["$jsonSchema"]["required"] = [key for key in schema["$jsonSchema"]["required"] if key not in optional]
    return schema


_ARTIFACT = {
    "workspace_id": OID, "document_id": OID, "document_version_id": OID,
    "artifact_schema_version": {"bsonType": "int", "enum": [2]},
    "order": NONNEGATIVE, "raw_text": TEXT, "normalized_text": TEXT, "text": TEXT,
    "raw_text_sha256": HASH, "normalized_text_sha256": HASH,
    "section_path": STRING_ARRAY, "structure_path": STRING_ARRAY,
    "locator": OBJECT, "normalization_map": OBJECT,
    "generation_key": _text(), "type": _text(),
}

VALIDATORS_V3 = {
    "documents": record({
        "workspace_id": OID, "kind": _enum("REPORT", "CORPUS_SOURCE"),
        "document_key": {**_text(), "maxLength": 128}, "title": _text(),
        "owner_user_id": NULL_ID, "subject_user_ids": {"bsonType": "array", "items": OID, "maxItems": 100},
        "current_version_id": NULL_ID, "current_governance_record_id": NULL_ID,
        "lifecycle_state": _enum("ACTIVE", "ARCHIVED", "TOMBSTONED", "PURGING", "PURGED"),
    }),
    "file_objects": record({
        "workspace_id": OID, "storage_backend": _enum("LOCAL_VOLUME"),
        "storage_key": {"bsonType": "string", "pattern": r"^[0-9a-f]{24}\.(pdf|docx|txt|md)$"},
        "original_filename": {**_text(), "maxLength": 255}, "media_type": _text(),
        "size_bytes": {"bsonType": ["int", "long"], "minimum": 1, "maximum": 20 * 1024 * 1024},
        "content_sha256": HASH, "storage_state": _enum("QUARANTINED", "COMMITTED", "MISSING", "PURGED"),
        "data_class": _enum("RESTRICTED", "INTERNAL", "PUBLIC_LICENSED"),
        "verified_at": NULL_DATE, "retention_expires_at": NULL_DATE,
    }),
    "document_versions": record({
        "workspace_id": OID, "document_id": OID, "file_object_id": OID,
        "version_no": {"bsonType": "int", "minimum": 1}, "content_sha256": HASH,
        "supersedes_version_id": NULL_ID,
        "processing_state": _enum("QUARANTINED", "QUEUED", "PARSING", "PARSED", "INDEXING", "READY", "FAILED"),
        "lifecycle_state": _enum("ACTIVE", "ARCHIVED", "TOMBSTONED", "PURGING", "PURGED"),
        "governance_record_id": OID,
        "parser_spec": {"bsonType": ["object", "null"]}, "chunker_spec": {"bsonType": ["object", "null"]},
        "element_count": NONNEGATIVE, "chunk_count": NONNEGATIVE,
        "failure_code": {"bsonType": ["string", "null"], "pattern": r"^[A-Z][A-Z0-9_]{0,63}$"},
        "ready_at": NULL_DATE, "generation_key": {"bsonType": ["string", "null"]},
    }),
    "governance_records": record({
        "workspace_id": NULL_ID, "resource_type": _enum("DOCUMENT", "DATASET", "MODEL", "RUBRIC"),
        "resource_id": OID, "record_version": {"bsonType": "int", "minimum": 1},
        "data_owner": OBJECT,
        "rights_basis": _enum("LICENSE", "CONSENT", "RESEARCH_USE_STATEMENT", "INTERNAL_APPROVAL", "UNKNOWN"),
        "license_id": {"bsonType": ["string", "null"]}, "rights_evidence": OBJECT,
        "allowed_purposes": {**STRING_ARRAY, "maxItems": 100, "uniqueItems": True},
        "redistribution": _enum("ALLOWED", "PROHIBITED", "UNKNOWN"),
        "data_class": _enum("RESTRICTED", "INTERNAL", "PUBLIC_LICENSED"),
        "anonymization": OBJECT, "retention_policy": OBJECT,
        "approver_id": NULL_ID, "approved_at": NULL_DATE,
        "valid_from": NULL_DATE, "valid_until": NULL_DATE,
        "status": _enum("PENDING", "APPROVED", "REJECTED", "REVOKED", "EXPIRED"),
    }),
    "document_elements": _artifact({
        **_ARTIFACT, "element_key": _text(), "element_id": _text(),
        "element_type": _text(), "parser_spec": OBJECT, "parser_generation_key": _text(),
        "page": {"bsonType": "int", "minimum": 1}, "para_index": NONNEGATIVE,
        "level": {"bsonType": "int", "minimum": 1},
        "raw_rows": {"bsonType": "array"}, "rows": {"bsonType": "array"},
    }, optional=("page", "para_index", "level", "raw_rows", "rows")),
    "chunks": _artifact({
        **_ARTIFACT, "chunk_id": _text(), "chunk_key": _text(),
        "chunker_spec": OBJECT, "content_sha256": HASH,
        "document_role": _enum("report", "source"), "document_version": _text(),
        "source_name": _text(), "element_ids": ID_ARRAY, "source_element_ids": ID_ARRAY,
        "language": {"bsonType": ["string", "null"]}, "text_with_context": TEXT,
        "token_count": {"bsonType": "int", "minimum": 1},
        "section_paths": {"bsonType": "array", "items": STRING_ARRAY},
        "source_refs": {"bsonType": "array", "items": OBJECT, "maxItems": 20000},
        "source_spans": {"bsonType": "array", "minItems": 1, "maxItems": 20000,
                         "items": {"bsonType": "object", "required": ["element_id", "stable_element_key", "document_id", "document_version_id"],
                                   "properties": {"element_id": OID, "stable_element_key": _text(),
                                                  "document_id": OID, "document_version_id": OID}}},
    }),
    "document_operations": record({
        "workspace_id": OID, "actor_id": OID, "operation": _enum("DOCUMENT_UPLOAD"),
        "idempotency_key": {**_text(), "maxLength": 128}, "request_sha256": HASH,
        "document_id": OID, "document_version_id": OID, "job_id": OID,
    }),
}

INDEXES_V3 = {
    "documents": [
        {"key": {"workspace_id": 1, "kind": 1, "document_key": 1}, "unique": True, "name": "uq_document_key"},
        {"key": {"workspace_id": 1, "lifecycle_state": 1, "kind": 1, "_id": 1}, "name": "ix_document_scope"},
        {"key": {"workspace_id": 1, "owner_user_id": 1, "lifecycle_state": 1}, "name": "ix_document_owner"},
    ],
    "file_objects": [
        {"key": {"workspace_id": 1, "storage_key": 1}, "unique": True, "name": "uq_file_storage_key"},
        {"key": {"workspace_id": 1, "content_sha256": 1}, "name": "ix_file_content"},
        {"key": {"storage_state": 1, "created_at": 1}, "name": "ix_file_reconciliation"},
    ],
    "document_versions": [
        {"key": {"document_id": 1, "version_no": 1}, "unique": True, "name": "uq_document_version"},
        {"key": {"workspace_id": 1, "processing_state": 1, "lifecycle_state": 1, "_id": 1}, "name": "ix_document_version_state"},
    ],
    "governance_records": [
        {"key": {"resource_type": 1, "resource_id": 1, "record_version": 1}, "unique": True, "name": "uq_governance_version"},
        {"key": {"workspace_id": 1, "status": 1, "valid_until": 1}, "name": "ix_governance_scope"},
    ],
    "document_elements": [
        {"key": {"document_version_id": 1, "generation_key": 1, "element_key": 1}, "unique": True, "name": "uq_element_generation"},
        {"key": {"workspace_id": 1, "document_version_id": 1, "generation_key": 1, "order": 1}, "name": "ix_element_order"},
    ],
    "chunks": [
        {"key": {"document_version_id": 1, "generation_key": 1, "chunk_key": 1}, "unique": True, "name": "uq_chunk_generation"},
        {"key": {"workspace_id": 1, "document_version_id": 1, "generation_key": 1, "order": 1}, "name": "ix_chunk_order"},
    ],
    "document_operations": [
        {"key": {"actor_id": 1, "workspace_id": 1, "operation": 1, "idempotency_key": 1},
         "unique": True, "name": "uq_document_operation"},
    ],
}


def apply_schema_v3(database, *, code_commit: str, applied_by: str):
    return apply_migration(database, code_commit=code_commit, applied_by=applied_by,
        migration_id="003-document-ingestion-provenance-v1", validators=VALIDATORS_V3,
        indexes=INDEXES_V3, description="Immutable uploads, current rights gate and fenced parser provenance generations")
