"""Synthetic parse/index/BOTH-run tests for model-visible item review.

These fixtures verify workflow/provenance, never classifier accuracy or gold.
Real Mongo validator/privilege/transaction coverage lives with integration tests.
"""

from __future__ import annotations

from copy import deepcopy

from bson import ObjectId
import pytest

from services.backend.tests.test_authenticated_documents import (
    context as base_context, headers, path, sign_in,
)
from services.backend.tests.test_authenticated_app import definition
from services.backend.tests.test_mongo_analysis_flow import create, prepare
from services.backend.src.kltn_ai.db.annotation_schema import INDEXES_V5, VALIDATORS_V5
from services.backend.src.kltn_ai.db.roles import role_specifications
from services.backend.src.kltn_ai.domain.analysis import json_value
from services.backend.src.kltn_ai.domain.rubrics import RubricService
from services.backend.src.kltn_ai.worker.mongo_analysis_worker import MongoAnalysisWorker


@pytest.fixture
def context(tmp_path):
    yield from base_context.__wrapped__(tmp_path)


def completed(ctx, *, zero_evidence=False):
    for spec in INDEXES_V5["item_annotations"]:
        ctx["db"].item_annotations.create_index(list(spec["key"].items()),
            unique=spec.get("unique", False), name=spec["name"])
    prepared = prepare(ctx)
    if zero_evidence:
        rubric = definition()
        criterion = rubric["criteria"][0]
        criterion["title"] = "Zyxwvu"
        checklist = criterion["checklists"][0]
        checklist["statement"] = "Qqqzzzx"
        checklist["requirements"][0]["any_of"] = ["Unfindableqazwsxedc"]
        checklist["contradiction_patterns"] = ["Unfindablepoiuytrewq"]
        service = RubricService(ctx["db"], transaction_mode=False)
        changed = service.create(ctx["identities"]["lecturer"], ctx["workspace"],
            {"rubric_key": "zero-evidence", "title": "Zyxwvu", "definition": rubric},
            idempotency_key="rubric-no-evidence-0001", request_id="synthetic-request")
        service.publish_version(ctx["identities"]["lecturer"], ctx["workspace"], changed["current_version_id"],
            expected_revision=1, idempotency_key="rubric-no-evidence-publish", request_id="synthetic-request")
        prepared["body"]["rubric_version_id"] = changed["current_version_id"]
    operation = create(ctx, prepared)
    assert MongoAnalysisWorker(ctx["db"], ctx["private"], transactional=False).process_one()
    base = path(ctx, "analysis-runs/" + operation["run_id"])
    response = ctx["client"].get(base + "/annotation-items")
    assert response.status_code == 200, response.text
    return {"base": base, "prepared": prepared, "operation": operation, "page": response.json(),
        "etag": response.headers["etag"]}


def item(flow, pipeline="SIMILARITY"):
    return next(row for row in flow["page"]["items"] if row["pipeline"] == pipeline)


def payload(flow, pipeline="SIMILARITY"):
    chosen = item(flow, pipeline)
    sides = ("REPORT", "SOURCE") if pipeline == "SIMILARITY" else ("REPORT",)
    result = {"item_id": chosen["item_id"], "label": "VERBATIM" if pipeline == "SIMILARITY" else "MET",
        "evidence_span_ids": [next(span["span_id"] for span in chosen["span_options"] if span["side"] == side)
            for side in sides], "rationale": "Synthetic human decision; predictions were visible."}
    if pipeline == "SIMILARITY":
        result["quote_or_citation"] = "UNSURE"
    return result


def post(ctx, flow, body=None, *, key="item-annotation-operation-0001", revision=None):
    return ctx["client"].post(flow["base"] + "/item-annotations", json=body or payload(flow),
        headers=headers(ctx, key, revision or flow["etag"]))


def test_items_are_unique_pinned_raw_spans_and_paginated(context):
    flow = completed(context)
    rows = flow["page"]["items"]
    assert {row["pipeline"] for row in rows} == {"SIMILARITY", "ASSESSMENT"}
    assert len({row["item_id"] for row in rows}) == len(rows)
    fixed = {"item_id", "pipeline", "report_version_id", "report_chunk_id", "source_version_id",
        "source_chunk_id", "checklist_id", "statement", "report_text", "source_text", "span_options", "latest_annotation"}
    for row in rows:
        assert set(row) == fixed and row["latest_annotation"] is None
        assert row["report_version_id"] == flow["prepared"]["report"]["document_version_id"]
        for span in row["span_options"]:
            assert set(span) == {"span_id", "side", "document_version_id", "chunk_id", "raw_start", "raw_end", "quote_text", "locator"}
            chunk = context["db"].chunks.find_one({"_id": ObjectId(span["chunk_id"])})
            assert span["quote_text"] == chunk["raw_text"][span["raw_start"]:span["raw_end"]]
            assert any(raw["chunk_raw_char_start"] == span["raw_start"]
                and raw["chunk_raw_char_end"] == span["raw_end"] and json_value(raw["locator"]) == span["locator"]
                for raw in chunk["source_spans"])
            assert span["document_version_id"] == str(chunk["document_version_id"])
    first = context["client"].get(flow["base"] + "/annotation-items?limit=1").json()
    assert first["page"]["has_more"]
    second = context["client"].get(flow["base"] + "/annotation-items", params={
        "limit": 1, "cursor": first["page"]["next_cursor"]}).json()
    assert first["items"][0]["item_id"] != second["items"][0]["item_id"]
    assert context["client"].get(flow["base"] + "/annotation-items").json() == flow["page"]
    for query in ("?limit=0", "?limit=101", "?cursor=not-a-hash"):
        assert context["client"].get(flow["base"] + "/annotation-items" + query).status_code == 422


def test_append_correction_idempotence_revision_and_results_immutability(context):
    flow = completed(context)
    original_results = deepcopy(list(context["db"].analysis_results.find()))
    original_evidence = deepcopy(list(context["db"].evidence_items.find()))
    first = post(context, flow)
    assert first.status_code == 201, first.text
    first_row = first.json()
    assert first_row["annotation_revision"] == 1 and first_row["annotation_mode"] == "MODEL_VISIBLE_REVIEW"
    assert first_row["run_revision"] == flow["page"]["run_revision"] + 1
    assert first_row["annotator_id"] == str(context["identities"]["lecturer"])
    # Replay compares only the canonical payload; stale run revision is fine.
    assert post(context, flow).json() == first_row
    reordered = payload(flow)
    reordered["evidence_span_ids"].reverse()
    assert post(context, flow, reordered).json() == first_row
    conflict = post(context, flow, {**payload(flow), "label": "PARAPHRASE"})
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    stale = post(context, flow, key="item-annotation-operation-0002")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "REVISION_CONFLICT"
    corrected_body = {**payload(flow), "label": "PARAPHRASE", "rationale": "Corrected after manual inspection."}
    corrected = post(context, flow, corrected_body, key="item-annotation-operation-0002", revision=first.headers["etag"])
    assert corrected.status_code == 201, corrected.text
    assert corrected.json()["annotation_revision"] == 2
    assert context["db"].item_annotations.count_documents({}) == 2
    current = context["client"].get(flow["base"] + "/annotation-items").json()
    chosen = next(row for row in current["items"] if row["item_id"] == first_row["item_id"])
    assert chosen["latest_annotation"] == corrected.json()
    assert context["client"].get(flow["base"] + "/results").status_code == 200
    assert list(context["db"].analysis_results.find()) == original_results
    assert list(context["db"].evidence_items.find()) == original_evidence
    assert context["db"].analysis_runs.find_one()["review_state"] == "UNREVIEWED"
    history = context["client"].get(flow["base"] + "/item-annotations?limit=1").json()
    assert history["items"] == [first_row] and history["page"]["has_more"]
    last = context["client"].get(flow["base"] + "/item-annotations", params={"limit": 1,
        "cursor": history["page"]["next_cursor"]}).json()
    assert last["items"] == [corrected.json()] and not last["page"]["has_more"]
    assert history["annotation_mode"] == "MODEL_VISIBLE_REVIEW" and history["predictions_visible"] is True
    exported = context["client"].get(flow["base"] + "/item-annotations/export")
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    value = exported.json()
    assert value["predictions_visible"] is True and value["independent_gold"] is value["official_grade"] is False
    assert value["annotations"] == [first_row, corrected.json()]
    assert "blinded gold" in value["interpretation"] and "storage_key" not in exported.text
    events = list(context["db"].audit_events.find({"action": "ITEM_ANNOTATION_CREATED"}))
    assert len(events) == 2 and all(event["metadata_allowlist"] == {} for event in events)
    assert corrected_body["rationale"] not in repr(events)


def test_reject_missing_duplicate_wrong_evidence_and_client_quote(context):
    flow = completed(context)
    good = payload(flow)
    report_span = good["evidence_span_ids"][0]
    assessment = payload(flow, "ASSESSMENT")
    invalid = [
        {**good, "evidence_span_ids": []},
        {**good, "evidence_span_ids": [report_span]},
        {**good, "evidence_span_ids": [report_span, report_span]},
        {**good, "evidence_span_ids": ["0" * 64]},
        {**good, "item_id": "0" * 64},
        {**good, "quote_text": "Client text is not accepted"},
        {key: value for key, value in good.items() if key != "quote_or_citation"},
        {**good, "quote_or_citation": {}},
        {**good, "label": "MET"},
        {**good, "rationale": "  \n"},
        {**good, "rationale": "x" * 4001},
        {**good, "evidence_span_ids": [None]},
        {**assessment, "evidence_span_ids": [good["evidence_span_ids"][1]]},
        {**assessment, "evidence_span_ids": []},
        {**assessment, "quote_or_citation": "YES"},
        {**assessment, "label": "VERBATIM"},
    ]
    for body in invalid:
        rejected = post(context, flow, body)
        assert rejected.status_code == 422, (body, rejected.text)
    assert context["db"].item_annotations.count_documents({}) == 0
    assert context["client"].get(flow["base"]).headers["etag"] == flow["etag"]
    none = {**good, "label": "NONE", "evidence_span_ids": [], "quote_or_citation": "NO"}
    accepted = post(context, flow, none)
    assert accepted.status_code == 201, accepted.text


def test_zero_evidence_checklist_is_visible_and_can_be_reviewed(context):
    flow = completed(context, zero_evidence=True)
    model = context["client"].get(flow["base"] + "/results").json()
    checklist = model["assessment"]["checklist_results"][0]
    assert checklist["evidence_pack"] == []
    chosen = item(flow, "ASSESSMENT")
    assert chosen["statement"] == "Qqqzzzx" and chosen["checklist_id"] == checklist["checklist_id"]
    assert chosen["span_options"] and all(span["side"] == "REPORT" for span in chosen["span_options"])
    body = {**payload(flow, "ASSESSMENT"), "label": "CANNOT_ASSESS", "evidence_span_ids": []}
    created = post(context, flow, body)
    assert created.status_code == 201, created.text
    assert created.json()["quote_or_citation"] is None
    met = post(context, flow, payload(flow, "ASSESSMENT"), key="zero-evidence-correction-0001", revision=created.headers["etag"])
    assert met.status_code == 201, met.text
    assert context["client"].get(flow["base"] + "/results").json() == model


def test_annotation_latest_history_and_export_are_current_actor_only(context):
    flow = completed(context)
    first = post(context, flow)
    assert first.status_code == 201
    context["db"].memberships.update_one({"user_id": context["identities"]["other"]}, {"$set": {"roles": ["LECTURER"]}})
    sign_in(context, "other")
    visible = context["client"].get(flow["base"] + "/annotation-items")
    assert visible.status_code == 200 and all(row["latest_annotation"] is None for row in visible.json()["items"])
    assert context["client"].get(flow["base"] + "/item-annotations").json()["items"] == []
    assert context["client"].get(flow["base"] + "/item-annotations/export").json()["annotations"] == []
    other = post(context, flow, revision=visible.headers["etag"])
    assert other.status_code == 201 and other.json()["annotation_revision"] == 1
    assert other.json()["annotator_id"] != first.json()["annotator_id"]
    sign_in(context, "lecturer")
    history = context["client"].get(flow["base"] + "/item-annotations").json()
    assert history["items"] == [first.json()]


@pytest.mark.parametrize("change", ["source_approval", "membership", "result", "span", "annotation"])
def test_current_revocation_or_tamper_blocks_reads_export_and_replay(context, change):
    flow = completed(context)
    assert post(context, flow).status_code == 201
    db = context["db"]
    if change == "source_approval":
        db.governance_records.update_one({"_id": flow["prepared"]["source_right"]["_id"]}, {"$set": {"status": "REVOKED"}})
    elif change == "membership":
        db.memberships.update_one({"user_id": context["identities"]["lecturer"]}, {"$set": {"status": "REVOKED"}})
    elif change == "result":
        db.analysis_results.update_one({}, {"$set": {"similarity.exact_match_coverage_percentage": 99.5}})
    elif change == "span":
        db.chunks.update_one({}, {"$set": {"source_spans.0.chunk_raw_char_end": 999999}})
    else:
        db.item_annotations.update_one({}, {"$set": {"rationale": "Tampered saved rationale"}})
    for suffix in ("/annotation-items", "/item-annotations", "/item-annotations/export"):
        response = context["client"].get(flow["base"] + suffix)
        assert response.status_code == (404 if change == "membership" else 409), response.text
    assert post(context, flow).status_code == (404 if change == "membership" else 409)
    assert db.item_annotations.count_documents({}) == 1


def test_annotation_auth_csrf_workspace_preconditions_and_append_only_roles(context):
    flow = completed(context)
    url = flow["base"] + "/item-annotations"
    no_csrf = headers(context, revision=flow["etag"])
    no_csrf.pop("X-CSRF-Token")
    assert context["client"].post(url, json=payload(flow), headers=no_csrf).status_code == 403
    assert context["client"].post(url, json=payload(flow), headers=headers(context)).status_code == 428
    no_key = headers(context, revision=flow["etag"])
    no_key.pop("Idempotency-Key")
    assert context["client"].post(url, json=payload(flow), headers=no_key).status_code == 422
    wrong = flow["base"].replace(str(context["workspace"]), str(ObjectId()))
    assert context["client"].get(wrong + "/annotation-items").status_code == 404
    sign_in(context, "student")
    for suffix in ("/annotation-items", "/item-annotations", "/item-annotations/export"):
        assert context["client"].get(flow["base"] + suffix).status_code == 403
    assert post(context, flow).status_code == 403
    context["client"].cookies.clear()
    assert context["client"].get(flow["base"] + "/annotation-items").status_code == 401
    roles = role_specifications("synthetic_annotations")
    api = {entry["resource"]["collection"]: entry["actions"] for entry in roles["kltn_api"]}
    worker = {entry["resource"]["collection"]: entry["actions"] for entry in roles["kltn_worker"]}
    assert set(api["item_annotations"]) == {"find", "insert"}
    assert "item_annotations" not in worker
    shape = VALIDATORS_V5["item_annotations"]["$jsonSchema"]
    assert shape["additionalProperties"] is False and len(shape["oneOf"]) == 2
    assert not {"updated_at", "updated_by", "revision"} & set(shape["properties"])


def test_item_and_span_response_budgets_fail_closed(context, monkeypatch):
    from services.backend.src.kltn_ai.domain import item_annotations
    flow = completed(context)
    for name in ("MAX_ITEMS", "MAX_SPANS_PER_ITEM", "MAX_TOTAL_SPANS", "MAX_TEXT_PER_ITEM", "MAX_TOTAL_TEXT", "MAX_RESPONSE_BYTES"):
        with monkeypatch.context() as limits:
            limits.setattr(item_annotations, name, 0)
            response = context["client"].get(flow["base"] + "/annotation-items")
            assert response.status_code == 409 and response.json()["error"]["code"] == "ANNOTATION_OUTPUT_LIMIT"
