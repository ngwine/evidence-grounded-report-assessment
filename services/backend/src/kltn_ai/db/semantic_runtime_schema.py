"""Additive migration 007: separately locked NLI runtime-budget v2 profiles.

V4 and V6 already have persisted records and immutable migration identities.
Only the two new profile identifiers are added; no record is rewritten.
"""

from __future__ import annotations

from copy import deepcopy

from .migrations import apply_migration
from .schema import _enum
from .semantic_analysis_schema import INDEXES_V6, VALIDATORS_V6


MIGRATION_ID_V7 = "007-semantic-profile-runtime-budget-v2"
VALIDATORS_V7 = deepcopy(VALIDATORS_V6)
INDEXES_V7 = deepcopy(INDEXES_V6)
for _name in VALIDATORS_V7:
    VALIDATORS_V7[_name]["$jsonSchema"]["properties"]["config_id"] = _enum(
        "bm25-smoke", "research-v0", "bm25-nli-v1", "rrf-nli-v1",
        "bm25-nli-v2", "rrf-nli-v2",
    )


def apply_schema_v7(database, *, code_commit: str, applied_by: str):
    return apply_migration(
        database, code_commit=code_commit, applied_by=applied_by,
        migration_id=MIGRATION_ID_V7, validators=VALIDATORS_V7, indexes=INDEXES_V7,
        description="Add separately locked NLI v2 runtime profiles without altering existing config identities",
    )
