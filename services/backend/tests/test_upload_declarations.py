"""No preseeded rights: exact-file author consent through authenticated HTTP."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

from services.backend.tests.test_authenticated_documents import (
    ORIGIN,
    PAYLOAD,
    assert_error,
    component,
    headers,
    path,
    sign_in,
    upload,
)
from services.backend.tests.test_authenticated_documents import (
    context as base_context,
)


@pytest.fixture
def context(tmp_path):
    for value in base_context.__wrapped__(tmp_path):
        value["db"].governance_records.create_index([
            ("resource_type", 1), ("resource_id", 1), ("record_version", 1)],
            unique=True, name="uq_governance_version")
        yield value


def body(**changes):
    return {"kind": "REPORT", "filename": "report.txt", "content_sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "rights_basis": "SELF_AUTHORED", "attested_authority": True, "pii_reviewed": True,
        "internal_use_only": True, **changes}


def declare(context, *, key="consent-request-0001", **changes):
    return context["client"].post(path(context, "upload-declarations"),
        json=body(**changes), headers=headers(context, key))


def record(context, response):
    return context["db"].governance_records.find_one({"_id": ObjectId(response.json()["id"])})


def test_direct_author_consent_upload_is_private_scoped_audited_and_replayable(context):
    assert context["db"].governance_records.count_documents({}) == 0
    result = declare(context)
    assert result.status_code == 201, result.text
    dto = result.json()
    component("UploadAuthorDeclarationRequest", body())
    component("UploadAuthorDeclaration", dto)
    assert dto["independent_approval"] is False
    assert dto["declaration_scope"] == "INTERNAL_SELF_AUTHORED"
    assert dto["allowed_purposes"] == ["INTERNAL_TEST"]
    consent = record(context, result)
    assert consent["rights_basis"] == "CONSENT" and consent["redistribution"] == "PROHIBITED"
    assert consent["data_class"] == "RESTRICTED"
    assert consent["created_by"] == consent["approver_id"] == context["identities"]["lecturer"]
    assert consent["retention_policy"]["expires_at"] == consent["valid_until"]
    assert consent["valid_until"] - consent["approved_at"] == timedelta(days=30)
    assert consent["rights_evidence"]["sha256"] == body()["content_sha256"]
    assert declare(context).json() == dto
    assert context["db"].governance_records.count_documents({}) == 1
    assert context["db"].audit_events.count_documents({"action": "UPLOAD_AUTHOR_CONSENT_DECLARED"}) == 1
    event = context["db"].audit_events.find_one({"action": "UPLOAD_AUTHOR_CONSENT_DECLARED"})
    assert "report.txt" not in str(event) and body()["content_sha256"] not in str(event)
    created, _ = upload(context, rights=consent)
    assert created.status_code == 202, created.text
    assert context["db"].jobs.count_documents({"job_type": "PARSE"}) == 1
    assert declare(context).json() == dto


@pytest.mark.parametrize("changes", [
    {"attested_authority": False}, {"attested_authority": "true"}, {"pii_reviewed": False},
    {"pii_reviewed": 1}, {"internal_use_only": False}, {"rights_basis": "LICENSE"},
    {"rights_basis": "CONSENT"}, {"kind": "DATASET"}, {"kind": []},
    {"filename": "payload.exe"}, {"filename": "x\n.txt"}, {"filename": "a" * 256 + ".txt"},
    {"content_sha256": "a" * 63}, {"content_sha256": "A" * 64},
    {"status": "APPROVED"}, {"allowed_purposes": ["PUBLICATION"]}, {"approver_id": str(ObjectId())},
])
def test_incomplete_unknown_and_broadened_declarations_rejected(context, changes):
    assert_error(declare(context, **changes), 422, "INVALID_DECLARATION")
    assert context["db"].governance_records.count_documents({}) == 0


def test_missing_fields_and_transport_require_authentication_csrf_and_key(context):
    incomplete = body()
    incomplete.pop("pii_reviewed")
    assert_error(context["client"].post(path(context, "upload-declarations"), json=incomplete,
        headers=headers(context)), 422)
    assert_error(context["client"].post(path(context, "upload-declarations"), json=body(),
        headers={"Origin": ORIGIN}), 403)
    assert_error(context["client"].post(path(context, "upload-declarations"), json=body(),
        headers=headers(context, "bad")), 422)
    context["client"].cookies.clear()
    assert_error(declare(context), 401)


def test_current_roles_workspace_and_membership_do_not_inherit_approval(context):
    sign_in(context, "student")
    assert declare(context).status_code == 201
    assert_error(declare(context, kind="CORPUS_SOURCE"), 403)
    sign_in(context, "lecturer")
    workspace = context["workspace"]
    assert_error(context["client"].post(f"/api/v1/workspaces/{ObjectId()}/upload-declarations",
        json=body(), headers=headers(context)), 404)
    context["db"].memberships.update_one({"workspace_id": workspace,
        "user_id": context["identities"]["lecturer"]}, {"$set": {"roles": ["DATA_APPROVER", "OPERATOR"]}})
    assert_error(declare(context), 403)


def test_research_and_publication_are_not_self_approved(context):
    context["db"].workspaces.update_one({"_id": context["workspace"]},
        {"$set": {"default_purpose": "RESEARCH_EXPERIMENT"}})
    assert_error(declare(context), 409, "DECLARATION_SCOPE_NOT_ALLOWED")
    assert context["db"].governance_records.count_documents({}) == 0


def test_mismatched_file_kind_actor_and_filename_never_reach_private_storage(context):
    consent = record(context, declare(context))
    for options in ({"payload": PAYLOAD + b"changed"}, {"filename": "renamed.txt"},
                    {"target": "sources"}):
        result, _ = upload(context, rights=consent, **options)
        assert_error(result, 409, "DECLARATION_FILE_MISMATCH")
    sign_in(context, "other")
    result, _ = upload(context, rights=consent)
    assert_error(result, 409, "DECLARATION_FILE_MISMATCH")
    assert context["db"].documents.count_documents({}) == 0
    assert context["db"].jobs.count_documents({}) == 0
    assert not list((context["private"] / "document-files").iterdir())


def test_replay_conflict_revocation_expiry_and_current_purpose_rechecked(context):
    result = declare(context)
    consent = record(context, result)
    assert_error(declare(context, filename="other.txt"), 409, "IDEMPOTENCY_CONFLICT")
    context["db"].governance_records.update_one({"_id": consent["_id"]}, {"$set": {"status": "REVOKED"}})
    assert_error(declare(context), 409, "GOVERNANCE_NOT_APPROVED")
    context["db"].governance_records.update_one({"_id": consent["_id"]},
        {"$set": {"status": "APPROVED", "valid_until": datetime.now(UTC) - timedelta(seconds=1)}})
    assert_error(declare(context), 409, "GOVERNANCE_NOT_APPROVED")
    context["db"].governance_records.update_one({"_id": consent["_id"]},
        {"$set": {"valid_until": datetime.now(UTC) + timedelta(days=1),
                  "allowed_purposes": ["RESEARCH_EXPERIMENT"]}})
    context["db"].workspaces.update_one({"_id": context["workspace"]},
        {"$set": {"default_purpose": "RESEARCH_EXPERIMENT"}})
    created, _ = upload(context, rights=consent)
    assert_error(created, 409, "GOVERNANCE_NOT_APPROVED")


def test_selector_cannot_leak_other_authors_self_declarations(context):
    declare(context)
    response = context["client"].get(path(context, "upload-authorizations"), params={"kind": "CORPUS_SOURCE"})
    assert response.json()["items"] == []
    sign_in(context, "other")
    response = context["client"].get(path(context, "upload-authorizations"), params={"kind": "REPORT"})
    assert response.json()["items"] == []


def test_new_version_consent_is_bound_to_existing_document_and_owner(context):
    consent = record(context, declare(context))
    created, _ = upload(context, rights=consent)
    identifier = created.json()["document_id"]
    second = declare(context, key="consent-new-version-0001", document_id=identifier,
        content_sha256=hashlib.sha256(PAYLOAD + b"new version").hexdigest())
    assert second.status_code == 201
    rights = record(context, second)
    assert rights["record_version"] == 2
    result, _ = upload(context, target=f"reports/{identifier}/versions", create=False,
        rights=rights, payload=PAYLOAD + b"new version", revision='"rev-1"', token="synthetic-new-version-0001")
    assert result.status_code == 202, result.text
    assert context["db"].document_versions.count_documents({}) == 2
    assert declare(context, key="consent-new-version-0001", document_id=identifier,
        content_sha256=hashlib.sha256(PAYLOAD + b"new version").hexdigest()).json() == second.json()
    sign_in(context, "other")
    assert_error(declare(context, key="synthetic-test-operation-foreign-document-0001", document_id=identifier), 404)
    sign_in(context, "lecturer")
    assert_error(declare(context, key="source-kind-conflict-0001", kind="CORPUS_SOURCE", document_id=identifier), 404)
