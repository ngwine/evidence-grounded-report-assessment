"""Additive migration 004: derived index generations and version-locked results.

The first three catalogs remain locked. Application services enforce references,
authority, immutable payloads and activation fences; shape validation alone
cannot establish those invariants.
"""

from __future__ import annotations

from .application_schema import HASH, NULL_ID, OID, record
from .migrations import apply_migration
from .schema import _enum, _text


OBJECT = {"bsonType": "object"}
NULL_OBJECT = {"bsonType": ["object", "null"]}
NULL_TEXT = {"bsonType": ["string", "null"]}
NULL_DATE = {"bsonType": ["date", "null"]}
CONFIG_ID = _enum("bm25-smoke", "research-v0")
IDS = {"bsonType": "array", "items": OID, "maxItems": 100, "uniqueItems": True}
POSITIVE = {"bsonType": "int", "minimum": 1}


VALIDATORS_V4 = {
    "index_generations": record({
        "workspace_id": OID, "document_id": OID, "document_version_id": OID,
        "governance_record_id": OID, "purpose": _text(), "parser_generation_key": _text(),
        "config_id": CONFIG_ID, "config_sha256": HASH, "config": OBJECT,
        "request_sha256": HASH, "generation_no": POSITIVE,
        "state": _enum("QUEUED", "BUILDING", "ACTIVE", "SUPERSEDED", "FAILED", "REVOKED"),
        "artifact_sha256": {**HASH, "bsonType": ["string", "null"]}, "artifact_key": NULL_TEXT,
        "chunk_count": {"bsonType": "int", "minimum": 0},
        "dense_dimension": {"bsonType": ["int", "null"], "minimum": 1},
        "model": NULL_OBJECT, "failure_code": NULL_TEXT, "activated_at": NULL_DATE,
        "job_id": OID, "supersedes_generation_id": NULL_ID,
    }),
    "index_heads": record({
        "workspace_id": OID, "document_version_id": OID, "config_id": CONFIG_ID,
        "generation_no": POSITIVE, "requested_generation_id": OID,
        "active_generation_id": NULL_ID,
    }),
    "index_operations": record({
        "actor_id": OID, "workspace_id": OID, "generation_id": OID, "job_id": OID,
        "idempotency_key": {**_text(), "maxLength": 128}, "request_sha256": HASH,
        "operation": _enum("INDEX_REQUEST"),
    }, immutable=True),
    "analysis_runs": record({
        "workspace_id": OID, "document_id": OID, "document_version_id": OID,
        "run_type": _enum("SIMILARITY", "ASSESSMENT", "BOTH"),
        "config_id": CONFIG_ID, "config_sha256": HASH,
        "source_version_ids": IDS, "index_generation_ids": IDS,
        "rubric_version_id": NULL_ID,
        "rubric_compiled_sha256": {**HASH, "bsonType": ["string", "null"]},
        "frozen_inputs": OBJECT, "manifest": NULL_OBJECT,
        "state": _enum("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", "INVALIDATED"),
        "lifecycle_state": _enum("ACTIVE", "TOMBSTONED"), "job_id": OID,
        "failure_code": NULL_TEXT, "result_id": NULL_ID,
        "review_state": _enum("UNREVIEWED", "REVIEWED"), "completed_at": NULL_DATE,
    }),
    "analysis_operations": record({
        "actor_id": OID, "workspace_id": OID, "operation": _enum("ANALYSIS_CREATE"),
        "idempotency_key": {**_text(), "maxLength": 128}, "request_sha256": HASH,
        "analysis_run_id": OID, "job_id": OID,
    }),
    "analysis_results": record({
        "workspace_id": OID, "analysis_run_id": OID, "document_version_id": OID,
        "similarity": NULL_OBJECT, "assessment": NULL_OBJECT,
        "result_sha256": HASH, "evidence_sha256": HASH, "manifest": OBJECT,
    }),
    "evidence_items": record({
        "workspace_id": OID, "analysis_run_id": OID, "document_version_id": OID,
        "pipeline": _enum("SIMILARITY", "ASSESSMENT"), "report_chunk_id": _text(),
        "source_chunk_id": NULL_TEXT, "source_version_id": NULL_ID,
        "checklist_id": NULL_TEXT, "evidence": OBJECT,
    }),
    "reviews": record({
        "workspace_id": OID, "analysis_run_id": OID,
        "decision": _enum("ACCEPT", "REJECT"), "reason_code": _text(),
        "reason_text": {"bsonType": ["string", "null"], "maxLength": 4000},
        "based_on_revision": POSITIVE,
    }),
}

INDEXES_V4 = {
    "index_generations": [
        {"key": {"workspace_id": 1, "document_version_id": 1, "config_id": 1, "generation_no": 1},
         "unique": True, "name": "uq_index_generation"},
        {"key": {"workspace_id": 1, "state": 1, "_id": 1}, "name": "ix_index_state"},
    ],
    "index_heads": [{"key": {"workspace_id": 1, "document_version_id": 1, "config_id": 1},
                     "unique": True, "name": "uq_index_head"}],
    "index_operations": [{"key": {"actor_id": 1, "workspace_id": 1, "operation": 1, "idempotency_key": 1},
                          "unique": True, "name": "uq_index_operation"}],
    "analysis_runs": [
        {"key": {"workspace_id": 1, "document_id": 1, "created_at": -1, "_id": 1}, "name": "ix_analysis_document"},
        {"key": {"workspace_id": 1, "state": 1, "_id": 1}, "name": "ix_analysis_state"},
    ],
    "analysis_operations": [{"key": {"actor_id": 1, "workspace_id": 1, "operation": 1, "idempotency_key": 1},
                             "unique": True, "name": "uq_analysis_operation"}],
    "analysis_results": [{"key": {"analysis_run_id": 1}, "unique": True, "name": "uq_analysis_result"}],
    "evidence_items": [{"key": {"workspace_id": 1, "analysis_run_id": 1, "_id": 1}, "name": "ix_evidence_page"}],
    "reviews": [
        {"key": {"analysis_run_id": 1, "based_on_revision": 1}, "unique": True, "name": "uq_run_review_revision"},
        {"key": {"workspace_id": 1, "analysis_run_id": 1, "_id": 1}, "name": "ix_review_page"},
    ],
}


def apply_schema_v4(database, *, code_commit: str, applied_by: str):
    return apply_migration(database, code_commit=code_commit, applied_by=applied_by,
        migration_id="004-index-and-analysis-results-v1", validators=VALIDATORS_V4,
        indexes=INDEXES_V4, description="Immutable index generations and fenced version-locked two-pipeline results")
