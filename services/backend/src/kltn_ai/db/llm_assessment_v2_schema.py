"""Additive migration 009: bounded-context local LLM assessment profile.

Applied catalogs 001–008 remain immutable. The new profile is opt-in and
only expands existing config enums; source documents and indexes are unchanged.
"""

from __future__ import annotations

from copy import deepcopy

from .llm_assessment_schema import INDEXES_V8, VALIDATORS_V8
from .migrations import apply_migration
from .schema import _enum


MIGRATION_ID_V9 = "009-local-llm-assessment-profile-v2"
VALIDATORS_V9 = deepcopy(VALIDATORS_V8)
INDEXES_V9 = deepcopy(INDEXES_V8)
for _name in VALIDATORS_V9:
    _previous = VALIDATORS_V8[_name]["$jsonSchema"]["properties"]["config_id"]["enum"]
    VALIDATORS_V9[_name]["$jsonSchema"]["properties"]["config_id"] = _enum(
        *_previous, "bm25-p2-llm-v2",
    )


def apply_schema_v9(database, *, code_commit: str, applied_by: str):
    return apply_migration(
        database, code_commit=code_commit, applied_by=applied_by,
        migration_id=MIGRATION_ID_V9, validators=VALIDATORS_V9, indexes=INDEXES_V9,
        description="Add an opt-in bounded-context local LLM assessment profile",
    )
