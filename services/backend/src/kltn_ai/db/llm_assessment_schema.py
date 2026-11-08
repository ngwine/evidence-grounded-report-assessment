"""Additive migration 008: opt-in local LLM assessment profile.

The already-applied V4/V6/V7 catalogs remain immutable. Only the new profile
identifier is added; document contents, indexes and previous identities stay
unchanged.
"""

from __future__ import annotations

from copy import deepcopy

from .migrations import apply_migration
from .schema import _enum
from .semantic_runtime_schema import INDEXES_V7, VALIDATORS_V7


MIGRATION_ID_V8 = "008-local-llm-assessment-profile-v1"
VALIDATORS_V8 = deepcopy(VALIDATORS_V7)
INDEXES_V8 = deepcopy(INDEXES_V7)
for _name in VALIDATORS_V8:
    _previous = VALIDATORS_V7[_name]["$jsonSchema"]["properties"]["config_id"]["enum"]
    VALIDATORS_V8[_name]["$jsonSchema"]["properties"]["config_id"] = _enum(
        *_previous, "bm25-p2-llm-v1",
    )


def apply_schema_v8(database, *, code_commit: str, applied_by: str):
    return apply_migration(
        database, code_commit=code_commit, applied_by=applied_by,
        migration_id=MIGRATION_ID_V8, validators=VALIDATORS_V8, indexes=INDEXES_V8,
        description="Add an opt-in digest-locked local LLM assessment profile",
    )
