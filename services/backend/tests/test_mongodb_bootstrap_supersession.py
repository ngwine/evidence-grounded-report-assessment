"""Bootstrap supersession orchestration without connecting to a real database.

The fake models config-enum preflight, validator read-back and index options;
Mongo's BSON-schema enforcement itself belongs to the live migration suite.
"""

from copy import deepcopy

import pytest

from scripts import setup_mongodb_local as bootstrap
from services.backend.src.kltn_ai.db.migrations import MigrationError, schema_checksum


class _Ledger:
    def __init__(self):
        self.entries = {}

    def find_one(self, query):
        return deepcopy(self.entries.get(query["_id"]))


class _Collection:
    def __init__(self, validator, indexes):
        self.settings = {"validator": deepcopy(validator), "validationLevel": "strict", "validationAction": "error"}
        self.indexes = deepcopy(indexes)
        self.documents = []
        self.preflights = []

    def find_one(self, query, **options):
        validator = query["$nor"][0]
        self.preflights.append(deepcopy(validator))
        enum = validator["$jsonSchema"]["properties"].get("config_id", {}).get("enum")
        return next(({"_id": row["_id"]} for row in self.documents
                     if row.get("invalid") or enum and row.get("config_id") not in enum), None)

    def options(self):
        return deepcopy(self.settings)

    def list_indexes(self):
        return deepcopy(self.indexes)


class _Database:
    def __init__(self):
        self.schema_migrations = _Ledger()
        self.collections = {}

    def __getitem__(self, name):
        return self.collections[name]

    def list_collection_names(self):
        return list(self.collections)


def _install(database, migration_id, validators, indexes):
    for name, validator in validators.items():
        if name in database.collections:
            collection = database[name]
            if collection.find_one({"$nor": [validator]}) is not None:
                raise MigrationError("Existing documents fail old validator")
            collection.settings["validator"] = deepcopy(validator)
            collection.indexes = deepcopy(indexes[name])
        else:
            database.collections[name] = _Collection(validator, indexes[name])
    database.schema_migrations.entries.setdefault(migration_id, {
        "_id": migration_id, "kind": "ENTRY", "status": "APPLIED",
        "checksum": schema_checksum(validators, indexes),
    })
    return {"migration_id": migration_id, "status": "APPLIED"}


@pytest.fixture
def migrations(monkeypatch):
    calls = []
    for number in (1, 2, 3, 5):
        def apply(database, *, code_commit, applied_by, number=number):
            calls.append(number)
            return {"migration_id": str(number), "status": "APPLIED"}
        monkeypatch.setattr(bootstrap, f"apply_schema_v{number}", apply)
    for number, migration_id, validators, indexes in (
        (4, bootstrap._V4_MIGRATION_ID, bootstrap.VALIDATORS_V4, bootstrap.INDEXES_V4),
        (6, bootstrap.MIGRATION_ID_V6, bootstrap.VALIDATORS_V6, bootstrap.INDEXES_V6),
        (7, bootstrap.MIGRATION_ID_V7, bootstrap.VALIDATORS_V7, bootstrap.INDEXES_V7),
        (8, bootstrap.MIGRATION_ID_V8, bootstrap.VALIDATORS_V8, bootstrap.INDEXES_V8),
        (9, bootstrap.MIGRATION_ID_V9, bootstrap.VALIDATORS_V9, bootstrap.INDEXES_V9),
    ):
        def apply(database, *, code_commit, applied_by, number=number,
                  migration_id=migration_id, validators=validators, indexes=indexes):
            calls.append(number)
            return _install(database, migration_id, validators, indexes)
        monkeypatch.setattr(bootstrap, f"apply_schema_v{number}", apply)
    return calls


def _existing(*, version=7):
    database = _Database()
    _install(database, bootstrap._V4_MIGRATION_ID, bootstrap.VALIDATORS_V4, bootstrap.INDEXES_V4)
    _install(database, bootstrap.MIGRATION_ID_V6, bootstrap.VALIDATORS_V6, bootstrap.INDEXES_V6)
    if version >= 7:
        _install(database, bootstrap.MIGRATION_ID_V7, bootstrap.VALIDATORS_V7, bootstrap.INDEXES_V7)
    if version >= 8:
        _install(database, bootstrap.MIGRATION_ID_V8, bootstrap.VALIDATORS_V8, bootstrap.INDEXES_V8)
    if version >= 9:
        _install(database, bootstrap.MIGRATION_ID_V9, bootstrap.VALIDATORS_V9, bootstrap.INDEXES_V9)
    for name in bootstrap.VALIDATORS_V6:
        database[name].documents.extend([
            {"_id": "synthetic-nli", "config_id": f"bm25-nli-v{2 if version >= 7 else 1}"},
            {"_id": "synthetic-rrf", "config_id": f"rrf-nli-v{2 if version >= 7 else 1}"},
        ])
    for collection in database.collections.values():
        collection.preflights.clear()
    return database


def _apply(database):
    return bootstrap.apply_schema_chain(database, code_commit="a" * 40, applied_by="test-bootstrap")


def test_fresh_bootstrap_applies_the_original_chain_in_order(migrations):
    database = _Database()
    first, last = _apply(database)
    assert migrations == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert first["migration_id"] == "1" and last["migration_id"] == bootstrap.MIGRATION_ID_V9
    for name, validator in {**bootstrap.VALIDATORS_V4, **bootstrap.VALIDATORS_V9}.items():
        assert database[name].options()["validator"] == validator


def test_idempotent_reapply_preserves_expanded_validators_and_new_profile_documents(migrations):
    database = _existing()
    old_entry = deepcopy(database.schema_migrations.entries[bootstrap._V4_MIGRATION_ID])
    for _ in range(2):
        _apply(database)
    assert migrations == [1, 2, 3, 5, 7, 8, 9, 1, 2, 3, 5, 9]
    assert database.schema_migrations.entries[bootstrap._V4_MIGRATION_ID] == old_entry
    for name, validator in bootstrap.VALIDATORS_V9.items():
        assert database[name].options()["validator"] == validator
        assert len(database[name].documents) == 2
        assert database[name].preflights
        # The first upgrade verifies its already-applied V7 predecessor;
        # every later reapply uses V9 directly without narrowing it again.
        assert all(row in (bootstrap.VALIDATORS_V7[name], bootstrap.VALIDATORS_V8[name], validator) for row in database[name].preflights)
        assert database[name].preflights[-1] == validator


@pytest.mark.parametrize("migration_id", [bootstrap._V4_MIGRATION_ID, bootstrap.MIGRATION_ID_V6, bootstrap.MIGRATION_ID_V7, bootstrap.MIGRATION_ID_V8, bootstrap.MIGRATION_ID_V9])
@pytest.mark.parametrize("field,value", [("checksum", "0" * 64), ("status", "PENDING"), ("kind", "LOCK")])
def test_drifted_predecessor_or_successor_ledger_rejects_before_any_ddl(migrations, migration_id, field, value):
    database = _existing(version=9)
    database.schema_migrations.entries[migration_id][field] = value
    with pytest.raises(MigrationError, match="ledger identity/checksum"):
        _apply(database)
    assert migrations == []


def test_successor_without_predecessor_ledger_does_not_authorize_skip(migrations):
    database = _existing()
    database.schema_migrations.entries.pop(bootstrap._V4_MIGRATION_ID)
    with pytest.raises(MigrationError, match="ledger identity/checksum"):
        _apply(database)
    assert migrations == []


def test_v7_requires_its_v6_predecessor_identity(migrations):
    database = _existing()
    database.schema_migrations.entries.pop(bootstrap.MIGRATION_ID_V6)
    with pytest.raises(MigrationError, match="ledger identity/checksum"):
        _apply(database)
    assert migrations == []


def test_v8_requires_its_v7_predecessor_identity(migrations):
    database = _existing(version=8)
    database.schema_migrations.entries.pop(bootstrap.MIGRATION_ID_V7)
    with pytest.raises(MigrationError, match="ledger identity/checksum"):
        _apply(database)
    assert migrations == []


def test_v9_requires_its_v8_predecessor_identity(migrations):
    database = _existing(version=9)
    database.schema_migrations.entries.pop(bootstrap.MIGRATION_ID_V8)
    with pytest.raises(MigrationError, match="ledger identity/checksum"):
        _apply(database)
    assert migrations == []


def test_existing_v9_profile_documents_are_never_narrowed_to_v8(migrations):
    database = _existing(version=9)
    old_v8 = deepcopy(database.schema_migrations.entries[bootstrap.MIGRATION_ID_V8])
    for name in bootstrap.VALIDATORS_V9:
        database[name].documents.append({"_id": "synthetic-llm-v2", "config_id": "bm25-p2-llm-v2"})
    for _ in range(2):
        _apply(database)
    assert migrations == [1, 2, 3, 5, 9] * 2
    assert database.schema_migrations.entries[bootstrap.MIGRATION_ID_V8] == old_v8
    for name, validator in bootstrap.VALIDATORS_V9.items():
        assert database[name].options()["validator"] == validator
        assert len(database[name].documents) == 3
        assert all(row == validator for row in database[name].preflights)


def test_existing_v8_profile_documents_are_never_narrowed_to_v7(migrations):
    database = _existing(version=8)
    old_v7 = deepcopy(database.schema_migrations.entries[bootstrap.MIGRATION_ID_V7])
    for name in bootstrap.VALIDATORS_V8:
        database[name].documents.append({"_id": "synthetic-llm", "config_id": "bm25-p2-llm-v1"})
    for _ in range(2):
        _apply(database)
    assert migrations == [1, 2, 3, 5, 8, 9, 1, 2, 3, 5, 9]
    assert database.schema_migrations.entries[bootstrap.MIGRATION_ID_V7] == old_v7
    for name, validator in bootstrap.VALIDATORS_V9.items():
        assert database[name].options()["validator"] == validator
        assert len(database[name].documents) == 3
        assert all(row in (bootstrap.VALIDATORS_V8[name], validator) for row in database[name].preflights)


def test_v6_upgrade_adds_v7_then_reapply_never_narrows_its_validator(migrations):
    database = _existing(version=6)
    old_v6 = deepcopy(database.schema_migrations.entries[bootstrap.MIGRATION_ID_V6])
    _apply(database)
    assert migrations == [1, 2, 3, 5, 6, 7, 8, 9]
    database["analysis_runs"].documents.append({"_id": "synthetic-v2", "config_id": "rrf-nli-v2"})
    _apply(database)
    assert migrations == [1, 2, 3, 5, 6, 7, 8, 9, 1, 2, 3, 5, 9]
    assert database.schema_migrations.entries[bootstrap.MIGRATION_ID_V6] == old_v6


@pytest.mark.parametrize("change", ["validator", "validation_level", "validation_action", "index", "document", "missing"])
def test_unchanged_v4_collections_still_receive_strict_verification(migrations, change):
    database = _existing()
    name = "analysis_results"
    if change == "validator":
        database[name].settings["validator"] = {}
    elif change == "validation_level":
        database[name].settings["validationLevel"] = "moderate"
    elif change == "validation_action":
        database[name].settings["validationAction"] = "warn"
    elif change == "index":
        database[name].indexes[0]["unique"] = False
    elif change == "document":
        database[name].documents.append({"_id": "synthetic-invalid", "invalid": True})
    else:
        database.collections.pop(name)
    with pytest.raises(MigrationError):
        _apply(database)
    assert migrations == [1, 2, 3]


def test_successor_validator_readback_is_checked_after_apply(migrations, monkeypatch):
    database = _existing()
    apply = bootstrap.apply_schema_v9
    def drifted_readback(*args, **kwargs):
        result = apply(*args, **kwargs)
        database["analysis_runs"].settings["validationAction"] = "warn"
        return result
    monkeypatch.setattr(bootstrap, "apply_schema_v9", drifted_readback)
    with pytest.raises(MigrationError, match="Validator read-back"):
        _apply(database)
    assert migrations == [1, 2, 3, 5, 7, 8, 9]


def test_new_profile_documents_do_not_allow_unknown_profiles(migrations):
    database = _existing()
    database["analysis_runs"].documents.append({"_id": "synthetic-unknown", "config_id": "not-registered"})
    with pytest.raises(MigrationError, match="Existing documents"):
        _apply(database)
