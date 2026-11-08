"""Deterministic offline contract checks; live enforcement is tested separately."""

from copy import deepcopy

import pytest

from services.backend.src.kltn_ai.db.migrations import schema_checksum
from services.backend.src.kltn_ai.db.roles import role_specifications
from services.backend.src.kltn_ai.db.schema import INDEXES, VALIDATORS


def test_schema_plan_is_explicit_and_deterministic() -> None:
    assert set(VALIDATORS) == {"users", "workspaces", "memberships", "jobs"}
    assert set(INDEXES) == set(VALIDATORS)
    before = deepcopy(VALIDATORS)
    assert len(schema_checksum()) == 64
    assert schema_checksum() == schema_checksum()
    assert VALIDATORS == before
    for validator in VALIDATORS.values():
        shape = validator["$jsonSchema"]
        assert shape["additionalProperties"] is False
        assert shape["properties"]["_id"]["bsonType"] == "objectId"
        assert {"schema_version", "created_by", "revision"} <= set(shape["required"])


def test_runtime_roles_never_gain_migration_or_result_ownership() -> None:
    roles = role_specifications("dedicated_test")
    privileges = {
        name: {item["resource"]["collection"]: set(item["actions"]) for item in spec}
        for name, spec in roles.items()
    }
    for role in ("kltn_api", "kltn_worker"):
        assert "schema_migrations" not in privileges[role]
        assert all(actions <= {"find", "insert", "update"} for actions in privileges[role].values())
        assert privileges[role]["audit_events"] == ({"find", "insert"} if role == "kltn_api" else {"insert"})
    assert privileges["kltn_api"]["evidence_items"] == {"find"}
    assert privileges["kltn_api"]["assessment_proposals"] == {"find"}
    assert privileges["kltn_worker"]["users"] == {"find"}
    assert privileges["kltn_worker"]["memberships"] == {"find"}
    assert "publications" not in privileges["kltn_worker"]
    assert "reviews" not in privileges["kltn_worker"]
    assert "remove" not in privileges["kltn_migration"][""]
    for value in ("", "admin", "config", "local"):
        with pytest.raises(ValueError):
            role_specifications(value)
