"""The upload selector shares the upload gate without exposing approval metadata."""

from datetime import UTC, datetime, timedelta

from bson import ObjectId
import pytest

from services.backend.tests.test_authenticated_documents import (
    approval, assert_error, context as base_context, path, sign_in, upload,
)


@pytest.fixture
def context(tmp_path):
    yield from base_context.__wrapped__(tmp_path)


def options(context, **params):
    return context["client"].get(path(context, "upload-authorizations"),
        params={"kind": "REPORT", **params})


def test_safe_choices_are_usable_and_consumed_choices_disappear(context):
    rights = approval(context, data_owner={"email": "private-person@example.invalid"},
        rights_evidence={"secret": "PRIVATE-EVIDENCE-REFERENCE"}, license_id="PRIVATE-LICENSE")
    response = options(context)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == {"id", "name", "rights_basis", "allowed_purposes", "valid_until",
                         "resource_id", "classification"}
    assert item["id"] == str(rights["_id"]) and item["resource_id"] == str(rights["resource_id"])
    assert item["classification"] == "INTERNAL"
    assert "private-person" not in response.text and "PRIVATE-" not in response.text
    created, _ = upload(context, rights=rights)
    assert created.status_code == 202
    assert options(context).json()["items"] == []


@pytest.mark.parametrize("changes", [
    {"status": "REVOKED"}, {"status": "PENDING"}, {"rights_basis": "UNKNOWN"},
    {"approver_id": None}, {"approved_at": None}, {"schema_version": 99},
    {"allowed_purposes": ["OTHER_PURPOSE"]},
    {"allowed_purposes": ["INTERNAL_TEST", "private-person@example.invalid"]},
    {"anonymization": {"required": True, "status": "PENDING"}},
    {"valid_from": datetime.now(UTC) + timedelta(days=1)},
    {"valid_until": datetime.now(UTC) - timedelta(seconds=1)},
    {"retention_policy": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
    {"retention_policy": {"expires_at": "invalid"}},
    {"resource_type": "DATASET"}, {"workspace_id": ObjectId()},
    {"rights_evidence": None}, {"rights_evidence": []},
])
def test_ineligible_governance_never_becomes_a_choice(context, changes):
    approval(context, **changes)
    assert options(context).json()["items"] == []


def test_tombstones_and_any_existing_document_binding_are_excluded(context):
    first = approval(context)
    second = approval(context)
    context["db"].tombstones.insert_one({"resource_type": "DOCUMENT", "resource_id": first["resource_id"]})
    context["db"].documents.insert_one({"_id": second["resource_id"], "workspace_id": ObjectId(),
        "kind": "CORPUS_SOURCE", "document_key": "foreign", "lifecycle_state": "ARCHIVED"})
    assert options(context).json()["items"] == []


def test_current_identity_workspace_membership_and_source_roles(context):
    approval(context)
    sign_in(context, "student")
    assert len(options(context).json()["items"]) == 1
    assert_error(options(context, kind="CORPUS_SOURCE"), 403)
    sign_in(context, "lecturer")
    assert len(options(context, kind="CORPUS_SOURCE").json()["items"]) == 1
    foreign = context["client"].get(f"/api/v1/workspaces/{ObjectId()}/upload-authorizations?kind=REPORT")
    assert_error(foreign, 404)
    context["db"].memberships.update_one({"user_id": context["identities"]["lecturer"]},
        {"$set": {"valid_until": datetime.now(UTC) - timedelta(seconds=1)}})
    assert_error(options(context), 404)
    context["client"].cookies.clear()
    assert_error(options(context), 401)


def test_operator_cannot_discover_academic_approvals(context):
    context["db"].memberships.update_one({"user_id": context["identities"]["lecturer"]},
        {"$set": {"roles": ["OPERATOR", "DATA_APPROVER"]}})
    assert_error(options(context), 403)


def test_bounded_pagination_advances_over_invalid_records(context):
    for _ in range(101):
        approval(context, allowed_purposes=["OTHER_PURPOSE"])
    wanted = approval(context)
    first = options(context, limit=1).json()
    assert first["items"] == [] and first["page"]["has_more"]
    second = options(context, limit=1, cursor=first["page"]["next_cursor"]).json()
    assert [item["id"] for item in second["items"]] == [str(wanted["_id"])]
    assert second["page"]["next_cursor"] is None


def test_pagination_and_kind_validation_and_upload_revalidation(context):
    rights = [approval(context) for _ in range(3)]
    first = options(context, limit=2).json()
    assert len(first["items"]) == 2 and first["page"]["has_more"]
    second = options(context, limit=2, cursor=first["page"]["next_cursor"]).json()
    assert len(second["items"]) == 1 and not second["page"]["has_more"]
    assert_error(options(context, limit=101), 400)
    assert_error(options(context, cursor="bad-cursor"), 400)
    assert_error(options(context, kind="OTHER"), 422)
    context["db"].governance_records.update_one({"_id": rights[0]["_id"]}, {"$set": {"status": "REVOKED"}})
    response, _ = upload(context, rights=rights[0])
    assert_error(response, 409, "GOVERNANCE_NOT_APPROVED")
