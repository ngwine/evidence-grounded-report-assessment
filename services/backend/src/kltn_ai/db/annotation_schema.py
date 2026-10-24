"""Migration 005: append-only, model-visible human item review records.

Migrations 001–004 are locked. Model results and all prior validators retain
their original shape and checksums; review appends only advance run revision.
"""

from __future__ import annotations

from .application_schema import HASH, OID, record
from .migrations import apply_migration
from .schema import _enum


POSITIVE = {"bsonType": "int", "minimum": 1}
VALIDATORS_V5 = {
    "item_annotations": record({
        "workspace_id": OID, "analysis_run_id": OID, "item_id": HASH, "created_by": OID,
        "pipeline": _enum("SIMILARITY", "ASSESSMENT"),
        "label": _enum("VERBATIM", "PARAPHRASE", "SUMMARY", "NONE", "UNSURE", "MET", "UNMET", "CANNOT_ASSESS"),
        "evidence_span_ids": {"bsonType": "array", "items": HASH, "maxItems": 100, "uniqueItems": True},
        "rationale": {"bsonType": "string", "minLength": 1, "maxLength": 4000, "pattern": r"\S"},
        "quote_or_citation": {"bsonType": ["string", "null"], "enum": ["YES", "NO", "UNSURE", None]},
        "annotation_mode": _enum("MODEL_VISIBLE_REVIEW"),
        "annotation_revision": POSITIVE, "based_on_revision": POSITIVE, "run_revision": POSITIVE,
        "idempotency_key": {"bsonType": "string", "pattern": r"^[A-Za-z0-9_.:-]{16,128}$"},
        "request_sha256": HASH, "annotation_sha256": HASH,
    }, immutable=True),
}

# BSON shape additionally keeps each pipeline's relation vocabulary separate.
VALIDATORS_V5["item_annotations"]["$jsonSchema"]["oneOf"] = [
    {"properties": {"pipeline": {"enum": ["SIMILARITY"]},
        "label": {"enum": ["VERBATIM", "PARAPHRASE", "SUMMARY", "NONE", "UNSURE"]},
        "quote_or_citation": {"enum": ["YES", "NO", "UNSURE"]}}},
    {"properties": {"pipeline": {"enum": ["ASSESSMENT"]},
        "label": {"enum": ["MET", "UNMET", "CANNOT_ASSESS", "UNSURE"]},
        "quote_or_citation": {"bsonType": "null"}}},
]

INDEXES_V5 = {
    "item_annotations": [
        {"key": {"workspace_id": 1, "analysis_run_id": 1, "created_by": 1, "item_id": 1, "annotation_revision": 1},
            "unique": True, "name": "uq_item_annotation_revision"},
        {"key": {"workspace_id": 1, "analysis_run_id": 1, "created_by": 1, "idempotency_key": 1},
            "unique": True, "name": "uq_item_annotation_idempotency"},
        {"key": {"workspace_id": 1, "analysis_run_id": 1, "created_by": 1, "_id": 1}, "name": "ix_item_annotation_history"},
    ],
}


def apply_schema_v5(database, *, code_commit: str, applied_by: str):
    return apply_migration(database, code_commit=code_commit, applied_by=applied_by,
        migration_id="005-model-visible-item-annotations-v1", validators=VALIDATORS_V5,
        indexes=INDEXES_V5, description="Append-only human item review with model-visible provenance and per-actor corrections")
