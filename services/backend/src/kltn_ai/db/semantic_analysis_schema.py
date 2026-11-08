"""Additive migration 006: opt-in lexical/RRF plus segment-level NLI profiles.

Earlier migration catalogs remain byte-for-byte unchanged. Only the config
enum in the three affected existing collections expands; data is not rewritten.
"""

from __future__ import annotations

from copy import deepcopy

from .analysis_schema import INDEXES_V4, VALIDATORS_V4
from .migrations import apply_migration
from .schema import _enum


MIGRATION_ID_V6 = "006-bm25-semantic-verification-profile-v1"
_COLLECTIONS = ("index_generations", "index_heads", "analysis_runs")
VALIDATORS_V6 = {name: deepcopy(VALIDATORS_V4[name]) for name in _COLLECTIONS}
INDEXES_V6 = {name: deepcopy(INDEXES_V4[name]) for name in _COLLECTIONS}
for _name in _COLLECTIONS:
    VALIDATORS_V6[_name]["$jsonSchema"]["properties"]["config_id"] = _enum(
        "bm25-smoke", "research-v0", "bm25-nli-v1", "rrf-nli-v1",
    )


def apply_schema_v6(database, *, code_commit: str, applied_by: str):
    return apply_migration(
        database, code_commit=code_commit, applied_by=applied_by,
        migration_id=MIGRATION_ID_V6, validators=VALIDATORS_V6, indexes=INDEXES_V6,
        description="Expand locked analysis/index config enum for opt-in BM25/RRF plus bidirectional NLI",
    )
