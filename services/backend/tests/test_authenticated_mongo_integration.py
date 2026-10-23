"""Optional real MongoDB auth/rubric transaction and migration regression tests.

Set KLTN_MONGO_TEST_URI to the dedicated replica-set test server. Only this
module's uniquely named databases and their own users/roles are cleaned up.
The URI and generated passwords are never printed or written to artifacts.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
import secrets
from uuid import uuid4

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import WriteError
from pymongo.write_concern import WriteConcern

from services.backend.src.kltn_ai.api.app import COOKIE, PREFIX, create_app
from services.backend.src.kltn_ai.auth.service import AuthService, create_local_user
from services.backend.src.kltn_ai.db.application_schema import (
    INDEXES_V2, VALIDATORS_V2, apply_schema_v2,
)
from services.backend.src.kltn_ai.db.migrations import (
    MIGRATION_ID, MigrationError, apply_schema_v1, schema_checksum,
)
from services.backend.src.kltn_ai.db.roles import provision_roles
from services.backend.src.kltn_ai.domain.errors import DomainError
from services.backend.src.kltn_ai.domain.rubrics import RubricService


COMMIT = "0" * 40
ORIGIN = "http://127.0.0.1:5173"
MIGRATION_V2 = "002-local-auth-and-rubric-lifecycle-v1"
LOCKED_V1_CHECKSUM = "5e904b12bb07dcd39f69649c6f70c0fc1709de65c119a32265b9b2e6aee601f1"


@pytest.fixture
def live_database():
    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Set KLTN_MONGO_TEST_URI for authenticated real-Mongo tests")
    with MongoClient(uri, serverSelectionTimeoutMS=3000, timeoutMS=30000, tz_aware=True) as client:
        name = "kltn_authenticated_test_" + uuid4().hex
        database = client[name]
        client.admin.command("ping")
        try:
            yield database
        finally:
            # Database name is locally generated, never supplied by a caller.
            for user in database.command("usersInfo")["users"]:
                database.command("dropUser", user["user"])
            for role in database.command("rolesInfo")["roles"]:
                database.command("dropRole", role["role"])
            client.drop_database(name)


def apply_all(database):
    first = apply_schema_v1(database, code_commit=COMMIT, applied_by="synthetic-auth-test")
    second = apply_schema_v2(database, code_commit=COMMIT, applied_by="synthetic-auth-test")
    return first, second


def common(actor_id=None):
    now = datetime.now(timezone.utc)
    return {"schema_version": 1, "created_at": now, "created_by": actor_id,
            "updated_at": now, "updated_by": actor_id, "revision": 1}


def seed_identity(database):
    password = secrets.token_urlsafe(24)
    with database.client.start_session() as session:
        with session.start_transaction(write_concern=WriteConcern("majority", wtimeout=10000)):
            actor = create_local_user(database, "real-fixture@example.invalid", "Synthetic real-Mongo lecturer",
                                      password, session=session)
            actor_id, workspace_id, membership_id = ObjectId(actor["id"]), ObjectId(), ObjectId()
            database.workspaces.insert_one({
                "_id": workspace_id, **common(actor_id), "workspace_key": "synthetic-real-mongo",
                "name": "Synthetic real-Mongo workspace", "kind": "RESEARCH",
                "status": "ACTIVE", "default_purpose": "RESEARCH",
            }, session=session)
            database.memberships.insert_one({
                "_id": membership_id, **common(actor_id), "workspace_id": workspace_id,
                "user_id": actor_id, "roles": ["LECTURER"], "status": "ACTIVE",
                "valid_from": None, "valid_until": None,
            }, session=session)
    return actor_id, workspace_id, membership_id, password


def definition():
    return {"max_score": 10, "criteria": [{
        "criterion_key": "C1", "title": "Measured implementation", "weight": 10,
        "scoring_mode": "PROPORTIONAL_CHECKLIST_V0", "checklists": [{
            "checklist_key": "C1.1", "statement": "Has a measured implementation",
            "evidence_mode": "LOCAL", "importance": "REQUIRED",
            "requirements": [{"requirement_id": "R1", "any_of": ["benchmark", "latency"]}],
            "contradiction_patterns": ["not implemented"],
        }],
    }]}


def test_migration_001_checksum_remains_unchanged_after_generic_refactor():
    assert schema_checksum() == LOCKED_V1_CHECKSUM
    assert schema_checksum(VALIDATORS_V2, INDEXES_V2) != LOCKED_V1_CHECKSUM


@pytest.mark.parametrize("format_name", ["txt", "pdf", "docx"])
def test_real_mongo_http_upload_worker_and_exact_provenance(live_database, tmp_path, format_name):
    """Real API and worker identities, strict catalog, actual bounded parser.

    Rights here describe generated test bytes only; no student/dataset approval
    is inferred from this synthetic fixture.
    """
    from io import BytesIO

    from services.backend.src.kltn_ai.db.document_schema import apply_schema_v3
    from services.backend.src.kltn_ai.worker.mongo_worker import MongoParseWorker

    database = live_database
    apply_all(database)
    migrated = apply_schema_v3(database, code_commit=COMMIT, applied_by="synthetic-auth-test")
    assert apply_schema_v3(database, code_commit=COMMIT, applied_by="synthetic-auth-test") == migrated
    actor_id, workspace_id, _, password = seed_identity(database)
    provision_roles(database)
    text = "Synthetic report preserves exact evidence spans and source versions."
    if format_name == "pdf":
        import fitz
        with fitz.open() as pdf:
            pdf.new_page().insert_text((72, 72), text)
            pdf.new_page().insert_text((72, 72), "A separate page contains benchmark evidence.")
            payload = pdf.tobytes()
    elif format_name == "docx":
        from docx import Document
        document = Document()
        document.add_heading("Measured implementation", level=1)
        document.add_paragraph(text)
        table = document.add_table(rows=2, cols=2)
        for index, cell in enumerate(table._cells):
            cell.text = "Synthetic measured value " + str(index)
        stream = BytesIO()
        document.save(stream)
        payload = stream.getvalue()
    else:
        payload = (text + "\n\nA separate paragraph contains benchmark evidence.").encode()
    governance_id, document_id = ObjectId(), ObjectId()
    now = datetime.now(timezone.utc)
    database.governance_records.insert_one({"_id": governance_id, **common(actor_id),
        "workspace_id": workspace_id, "resource_type": "DOCUMENT", "resource_id": document_id,
        "record_version": 1, "data_owner": {"kind": "SYNTHETIC_TEST"},
        "rights_basis": "INTERNAL_APPROVAL", "license_id": None,
        "rights_evidence": {"kind": "GENERATED_TEST_BYTES"}, "allowed_purposes": ["RESEARCH"],
        "redistribution": "ALLOWED", "data_class": "INTERNAL", "anonymization": {"required": False},
        "retention_policy": {"expires_at": None}, "approver_id": actor_id, "approved_at": now,
        "valid_from": None, "valid_until": None, "status": "APPROVED"})
    host, port = database.client.address
    connections = []
    try:
        for role in ("api", "worker"):
            secret = secrets.token_urlsafe(24)
            user = "synthetic_document_" + role
            database.command("createUser", user, pwd=secret, roles=[{"role": "kltn_" + role, "db": database.name}])
            connections.append(MongoClient(host=host, port=port, username=user, password=secret,
                authSource=database.name, directConnection=True, serverSelectionTimeoutMS=3000,
                timeoutMS=30000, tz_aware=True))
        private = tmp_path / "private-runtime"
        app = create_app(connections[0][database.name], private_root=private, allow_test_client=True)
        with TestClient(app) as client:
            session = client.post(PREFIX + "/auth/sessions", json={
                "email": "real-fixture@example.invalid", "password": password}, headers={"Origin": ORIGIN})
            assert session.status_code == 200
            headers = {"Origin": ORIGIN, "X-CSRF-Token": session.json()["csrf_token"],
                       "Idempotency-Key": "synthetic-real-upload-0001"}
            scope = f"{PREFIX}/workspaces/{workspace_id}"
            uploaded = client.post(scope + "/reports", data={"document_key": "generated-" + format_name,
                "title": "Generated format fixture", "governance_record_id": str(governance_id)},
                files={"file": ("generated." + format_name, payload)}, headers=headers)
            assert uploaded.status_code == 202, uploaded.text
            result = uploaded.json()
            assert result["document_id"] == str(document_id)
            worker = MongoParseWorker(connections[1][database.name], private)
            assert worker.process_one()
            job = client.get(scope + "/jobs/" + result["job_id"])
            assert job.status_code == 200 and job.json()["state"] == "SUCCEEDED", job.text
            version = client.get(scope + "/document-versions/" + result["document_version_id"])
            assert version.status_code == 200 and version.json()["processing_state"] == "PARSED", version.text
            chunks = client.get(scope + "/document-versions/" + result["document_version_id"] + "/chunks")
            assert chunks.status_code == 200 and chunks.json()["items"], chunks.text
            for chunk in chunks.json()["items"]:
                for span in chunk["source_spans"]:
                    element = database.document_elements.find_one({"_id": ObjectId(span["element_id"])})
                    assert element is not None
                    assert element["document_version_id"] == ObjectId(result["document_version_id"])
                    assert element["raw_text"][span["element_raw_char_start"]:span["element_raw_char_end"]]
            assert worker.process_one() is False
            assert database.audit_events.count_documents({"action": "DOCUMENT_PARSED"}) == 1
    finally:
        for connection in connections:
            connection.close()


def test_real_mongo_auth_http_rubric_lifecycle_uses_scoped_runtime_role(live_database):
    database = live_database
    first, _ = apply_all(database)
    assert first["checksum"] == LOCKED_V1_CHECKSUM
    actor_id, workspace_id, membership_id, password = seed_identity(database)
    provision_roles(database)
    runtime_password = secrets.token_urlsafe(24)
    database.command("createUser", "synthetic_auth_api", pwd=runtime_password,
                     roles=[{"role": "kltn_api", "db": database.name}])
    host, port = database.client.address
    with MongoClient(host=host, port=port, username="synthetic_auth_api", password=runtime_password,
                     authSource=database.name, directConnection=True, serverSelectionTimeoutMS=3000,
                     timeoutMS=30000, tz_aware=True) as runtime_client:
        runtime_db = runtime_client[database.name]
        # Only TestClient peer/Host differs; transaction_mode remains default True.
        app = create_app(runtime_db, allow_test_client=True)
        with TestClient(app) as client:
            signed_in = client.post(f"{PREFIX}/auth/sessions", json={
                "email": "real-fixture@example.invalid", "password": password,
            }, headers={"Origin": ORIGIN})
            assert signed_in.status_code == 200
            csrf = signed_in.json()["csrf_token"]
            token = client.cookies[COOKIE]
            assert signed_in.json()["actor"]["id"] == str(actor_id)
            assert client.get(f"{PREFIX}/auth/me").status_code == 200
            refreshed = client.get(f"{PREFIX}/auth/csrf", headers={"X-CSRF-Refresh": "1", "Origin": ORIGIN})
            assert refreshed.status_code == 200
            assert refreshed.json()["csrf_token"] != csrf
            csrf = refreshed.json()["csrf_token"]

            def headers(key, revision=None):
                values = {"Origin": ORIGIN, "X-CSRF-Token": csrf, "Idempotency-Key": key}
                if revision:
                    values["If-Match"] = revision
                return values

            path = f"{PREFIX}/workspaces/{workspace_id}/rubrics"
            body = {"rubric_key": "synthetic-real-mongo", "title": "Synthetic real-Mongo rubric",
                    "definition": definition()}
            created = client.post(path, json=body, headers=headers("create-rubric-0001"))
            assert created.status_code == 201, created.json().get("error", {}).get("code")
            rubric = created.json()
            replay = client.post(path, json=body, headers=headers("create-rubric-0001"))
            assert replay.status_code == 201 and replay.json() == rubric
            assert database.rubrics.count_documents({}) == 1
            version_path = f"{PREFIX}/workspaces/{workspace_id}/rubric-versions/{rubric['current_version_id']}"
            changed = deepcopy(definition())
            changed["criteria"][0]["title"] = "Updated measured implementation"
            update = client.put(version_path, json=changed, headers=headers("update-rubric-0001", '"rev-1"'))
            assert update.status_code == 200 and update.headers["etag"] == '"rev-2"'
            published = client.post(version_path + ":publish", headers=headers("publish-rubric-0001", '"rev-2"'))
            assert published.status_code == 200 and published.json()["status"] == "PUBLISHED"
            immutable = client.put(version_path, json=changed, headers=headers("update-rubric-0002", '"rev-3"'))
            assert immutable.status_code == 409 and immutable.json()["error"]["code"] == "RUBRIC_IMMUTABLE"
            parent = client.get(path + "/" + rubric["id"])
            clone = client.post(path + "/" + rubric["id"] + "/versions",
                                json={"clone_from_version_id": rubric["current_version_id"]},
                                headers=headers("clone-rubric-0001", parent.headers["etag"]))
            assert clone.status_code == 201 and clone.json()["version_no"] == 2
            assert clone.json()["status"] == "DRAFT"
            assert database.rubric_versions.count_documents({}) == 2
            stored_version = database.rubric_versions.find_one({"_id": ObjectId(rubric["current_version_id"])})
            assert stored_version["compiled_id"] and stored_version["compiled_sha256"]
            service = RubricService(runtime_db)
            compiled = service.get_compiled_published(actor_id, workspace_id, rubric["current_version_id"])
            assert compiled["compiled_sha256"] == stored_version["compiled_sha256"]
            # Shape validation cannot prevent an administrator tampering with
            # published content; runtime integrity checks must still stop use.
            database.rubric_versions.update_one({"_id": stored_version["_id"]}, {"$set": {"definition.max_score": 9}})
            with pytest.raises(DomainError) as integrity:
                service.get_compiled_published(actor_id, workspace_id, rubric["current_version_id"])
            assert integrity.value.code == "RUBRIC_INTEGRITY_FAILED"
            database.rubric_versions.update_one({"_id": stored_version["_id"]}, {"$set": {"definition": stored_version["definition"]}})
            sessions = list(database.auth_sessions.find())
            assert len(sessions) == 1
            assert sessions[0]["token_sha256"] != token
            assert sessions[0]["csrf_sha256"] != csrf
            assert password not in repr(sessions)
            assert token not in repr(list(database.audit_events.find()))

            # Revoke an authoritative membership after login and publication.
            database.memberships.update_one({"_id": membership_id}, {"$set": {"status": "REVOKED"}, "$inc": {"revision": 1}})
            denied = client.get(path)
            assert denied.status_code == 404
            assert client.get(f"{PREFIX}/auth/me").json()["memberships"] == []
            database.users.update_one({"_id": actor_id}, {"$set": {"status": "DISABLED"}, "$inc": {"revision": 1}})
            assert client.get(f"{PREFIX}/auth/me").status_code == 401
            database.users.update_one({"_id": actor_id}, {"$set": {"status": "ACTIVE"}, "$inc": {"revision": 1}})
            database.auth_credentials.update_one({"user_id": actor_id}, {"$inc": {"revision": 1}})
            assert client.get(f"{PREFIX}/auth/me").status_code == 401
            assert client.get(f"{PREFIX}/workspaces/{ObjectId()}/rubrics").status_code == 401


def test_real_mongo_session_validator_uniqueness_revocation_and_metadata(live_database):
    database = live_database
    apply_all(database)
    actor_id, _, _, password = seed_identity(database)
    auth = AuthService(database)
    response = auth.login("real-fixture@example.invalid", password, "synthetic-peer")
    token = response["token"]
    session = auth.authenticate(token)
    auth.check_csrf(session, response["csrf_token"])
    assert session["credential_revision"] == 1
    assert session["user_id"] == actor_id
    with pytest.raises(WriteError) as rejected:
        database.auth_sessions.update_one({"_id": session["_id"]}, {"$set": {"raw_token": token}})
    assert rejected.value.code == 121
    with pytest.raises(WriteError) as rejected:
        database.auth_credentials.update_one({"user_id": actor_id}, {"$set": {"plaintext_password": "synthetic-not-a-secret"}})
    assert rejected.value.code == 121
    auth.revoke(token)
    with pytest.raises(DomainError) as rejected:
        auth.authenticate(token)
    assert rejected.value.status == 401
    assert database.auth_sessions.find_one({"_id": session["_id"]})["revoked_at"] is not None
    assert database.audit_events.count_documents({"action": "AUTH_LOGOUT"}) == 1


def test_real_mongo_migration_002_idempotent_and_drift_is_fail_closed(live_database):
    database = live_database
    first, second = apply_all(database)
    old_v1 = database.schema_migrations.find_one({"_id": MIGRATION_ID})
    old_v2 = database.schema_migrations.find_one({"_id": MIGRATION_V2})
    assert apply_schema_v2(database, code_commit=COMMIT, applied_by="synthetic-auth-test") == second
    new_v2 = database.schema_migrations.find_one({"_id": MIGRATION_V2})
    assert new_v2["applied_at"] == old_v2["applied_at"]
    assert new_v2["last_verified_at"] >= old_v2["last_verified_at"]
    assert database.schema_migrations.find_one({"_id": MIGRATION_ID}) == old_v1
    assert database.schema_migrations.count_documents({"kind": "ENTRY"}) == 2
    for name, validator in VALIDATORS_V2.items():
        options = database[name].options()
        assert options["validator"] == validator
        assert options["validationLevel"] == "strict" and options["validationAction"] == "error"
    # Modify only our freshly created test TTL index. Migrator must reject it,
    # not silently rebuild, delete records or claim a successful verification.
    database.command({"collMod": "auth_sessions", "index": {
        "name": "ttl_auth_session", "expireAfterSeconds": 123,
    }})
    with pytest.raises(MigrationError, match="Index options drift"):
        apply_schema_v2(database, code_commit=COMMIT, applied_by="synthetic-auth-test")
    assert database.schema_migrations.find_one({"_id": MIGRATION_V2})["last_verified_at"] == new_v2["last_verified_at"]
    database.schema_migrations.update_one({"_id": MIGRATION_V2}, {"$set": {"checksum": "0" * 64}})
    with pytest.raises(MigrationError, match="checksum mismatch"):
        apply_schema_v2(database, code_commit=COMMIT, applied_by="synthetic-auth-test")
    assert first["checksum"] == LOCKED_V1_CHECKSUM
