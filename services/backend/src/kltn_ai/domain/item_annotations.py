"""Append-only human review of model-visible, version-pinned analysis items.

These records are review decisions, never independent gold, training labels,
official grades or mutations of the model's persisted results. All quotations
are resolved from authoritative parser source spans, not client-supplied text.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from .access import object_id
from .analysis import AnalysisService, _sha, evidence_sha, json_value
from .audit import append_event
from .documents import _options
from .errors import DomainError


MODE = "MODEL_VISIBLE_REVIEW"
MAX_ITEMS = 3000
MAX_SPANS_PER_ITEM = 512
MAX_TOTAL_SPANS = 20000
MAX_TEXT_PER_ITEM = 250000
MAX_TOTAL_TEXT = 2000000
MAX_SELECTED_SPANS = 100
MAX_ANNOTATIONS = 10000
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
P1_LABELS = frozenset({"VERBATIM", "PARAPHRASE", "SUMMARY", "NONE", "UNSURE"})
P2_LABELS = frozenset({"MET", "UNMET", "CANNOT_ASSESS", "UNSURE"})
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")


def annotation_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(row["_id"]), "annotator_id": str(row["created_by"]),
        **{key: json_value(row[key]) for key in ("item_id", "pipeline", "label",
            "evidence_span_ids", "rationale", "quote_or_citation", "annotation_revision",
            "created_at", "annotation_mode", "run_revision")}}


def _invalid(message: str = "Invalid item annotation") -> NoReturn:
    raise DomainError(422, "VALIDATION_FAILED", message)


def _integrity() -> NoReturn:
    raise DomainError(409, "ANNOTATION_INTEGRITY_FAILED", "Stored annotation integrity failed")


def _limit() -> NoReturn:
    raise DomainError(409, "ANNOTATION_OUTPUT_LIMIT", "Annotation scope exceeds the review budget")


def _bounded(value: Any) -> Any:
    if len(json.dumps(json_value(value), ensure_ascii=False, allow_nan=False).encode()) > MAX_RESPONSE_BYTES:
        _limit()
    return value


class ItemAnnotationService:
    def __init__(self, database: Any, private_root: Path | str, *, transactional: bool = True):
        self.db = database
        self.analysis = AnalysisService(database, private_root, transactional=transactional)

    def _scope(self, actor_id: ObjectId, workspace_id: ObjectId | str,
               run_id: ObjectId | str, *, session: Any = None):
        """Recheck current authority, governance and immutable results each time."""
        run = self.analysis.get(actor_id, workspace_id, run_id, session=session)
        self.analysis.policy.require(actor_id, run["workspace_id"], "review.create", session=session)
        results = self.analysis.get_result(actor_id, run["workspace_id"], run["_id"])
        # get_result's public adapter predates session support. Repeat its
        # integrity comparison in the transaction's snapshot before any write.
        if session is not None:
            options = _options(session)
            stored = self.db.analysis_results.find_one({"_id": run["result_id"],
                "workspace_id": run["workspace_id"], "analysis_run_id": run["_id"]}, **options)
            evidence = list(self.db.evidence_items.find({"workspace_id": run["workspace_id"],
                "analysis_run_id": run["_id"]}, **options).limit(3001))
            if (stored is None or len(evidence) > 3000
                    or _sha({key: stored[key] for key in ("similarity", "assessment", "manifest")}) != stored["result_sha256"]
                    or evidence_sha(evidence) != stored["evidence_sha256"]
                    or stored["manifest"] != run["manifest"]
                    or {key: stored[key] for key in ("similarity", "assessment", "manifest")} != results):
                raise DomainError(409, "RESULT_INTEGRITY_FAILED", "Stored result integrity failed")
        snapshot = self.analysis.snapshot(actor_id, run["workspace_id"], run, session=session)
        return run, results, snapshot

    @staticmethod
    def _span_options(run: dict[str, Any], chunks: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
        options: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            raw = chunk["raw_text"]
            for span in chunk["source_spans"]:
                start, end = span["chunk_raw_char_start"], span["chunk_raw_char_end"]
                if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw)
                        or not isinstance(span.get("locator"), dict)):
                    raise DomainError(409, "PROVENANCE_INVALID", "Stored provenance integrity failed")
                identity = {"analysis_run_id": str(run["_id"]), "side": side,
                    "document_version_id": chunk["document_version_id"], "chunk_id": chunk["chunk_id"],
                    "raw_start": start, "raw_end": end}
                span_id = _sha(identity)
                options[span_id] = {"span_id": span_id, **{key: value for key, value in identity.items()
                    if key != "analysis_run_id"}, "quote_text": raw[start:end], "locator": deepcopy(span["locator"])}
                if len(options) > MAX_SPANS_PER_ITEM:
                    _limit()
        return list(options.values())

    def _items(self, run: dict[str, Any], results: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        report_chunks = snapshot["report_chunks"]
        report_map = {row["chunk_id"]: row for row in report_chunks}
        source_map = {row["chunk_id"]: row for row in snapshot["source_chunks"]}
        items: dict[str, dict[str, Any]] = {}
        text_total = span_total = 0

        def add(pipeline: str, reports: list[dict[str, Any]], sources: list[dict[str, Any]],
                checklist_id: str | None = None, statement: str | None = None) -> None:
            nonlocal text_total, span_total
            fields = {"pipeline": pipeline, "report_version_id": str(run["document_version_id"]),
                "report_chunk_id": reports[0]["chunk_id"] if len(reports) == 1 else None,
                "source_version_id": sources[0]["document_version_id"] if sources else None,
                "source_chunk_id": sources[0]["chunk_id"] if sources else None,
                "checklist_id": checklist_id}
            # A checklist identity does not depend on its retrieved evidence.
            identity = {**fields, "report_chunk_id": fields["report_chunk_id"] if pipeline == "SIMILARITY" else None}
            item_id = _sha({"analysis_run_id": str(run["_id"]), **identity})
            if item_id in items:
                return
            report_text = "\n\n".join(row["raw_text"] for row in reports)
            source_text = sources[0]["raw_text"] if sources else None
            size = len(report_text) + len(source_text or "")
            if size > MAX_TEXT_PER_ITEM or text_total + size > MAX_TOTAL_TEXT:
                _limit()
            spans = self._span_options(run, reports, "REPORT") + self._span_options(run, sources, "SOURCE")
            if len(spans) > MAX_SPANS_PER_ITEM or span_total + len(spans) > MAX_TOTAL_SPANS:
                _limit()
            text_total += size
            span_total += len(spans)
            items[item_id] = {"item_id": item_id, **fields, "statement": statement,
                "report_text": report_text, "source_text": source_text, "span_options": spans,
                "latest_annotation": None}
            if len(items) > MAX_ITEMS:
                _limit()

        similarity = results.get("similarity")
        if similarity:
            for match in similarity["matches"]:
                report, source = report_map.get(match["report_chunk_id"]), source_map.get(match["source_chunk_id"])
                if (report is None or source is None
                        or source["document_id"] != match["source_document_id"]):
                    raise DomainError(409, "PROVENANCE_INVALID", "Stored match scope is invalid")
                add("SIMILARITY", [report], [source])
        assessment = results.get("assessment")
        if assessment:
            seen = set()
            for checklist in assessment["checklist_results"]:
                checklist_id, statement = checklist["checklist_id"], checklist["statement"]
                if checklist_id in seen or not isinstance(checklist_id, str) or not isinstance(statement, str):
                    raise DomainError(409, "RESULT_INTEGRITY_FAILED", "Stored checklist scope is invalid")
                seen.add(checklist_id)
                add("ASSESSMENT", report_chunks, [], checklist_id, statement)
        return [items[key] for key in sorted(items)]

    @staticmethod
    def _payload(body: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        allowed = {"item_id", "label", "evidence_span_ids", "rationale", "quote_or_citation"}
        if (not isinstance(body, dict) or set(body) - allowed
                or not {"item_id", "label", "evidence_span_ids", "rationale"} <= set(body)
                or body.get("item_id") != item["item_id"]
                or not isinstance(body.get("label"), str)
                or not isinstance(body.get("rationale"), str)
                or not 1 <= len(body["rationale"].strip()) <= 4000
                or len(body["rationale"]) > 4000
                or not isinstance(body.get("evidence_span_ids"), list)
                or len(body["evidence_span_ids"]) > MAX_SELECTED_SPANS
                or any(not isinstance(value, str) or not HASH_PATTERN.fullmatch(value)
                       for value in body["evidence_span_ids"])):
            _invalid()
        spans = body["evidence_span_ids"]
        if len(set(spans)) != len(spans):
            _invalid("Evidence span IDs must be unique")
        available = {span["span_id"]: span for span in item["span_options"]}
        if not set(spans) <= set(available):
            _invalid("Evidence spans must belong to this pinned item")
        sides = {available[value]["side"] for value in spans}
        quote = body.get("quote_or_citation")
        label = body["label"]
        if item["pipeline"] == "SIMILARITY":
            if label not in P1_LABELS or not isinstance(quote, str) or quote not in {"YES", "NO", "UNSURE"}:
                _invalid("Similarity review requires a valid relation and quotation/citation choice")
            if label in {"VERBATIM", "PARAPHRASE", "SUMMARY"} and sides != {"REPORT", "SOURCE"}:
                _invalid("Positive similarity review requires report and source evidence")
        else:
            if label not in P2_LABELS or quote is not None:
                _invalid("Assessment review requires a checklist outcome and no quotation/citation choice")
            if label in {"MET", "UNMET"} and "REPORT" not in sides:
                _invalid("MET and UNMET require report evidence")
        return {"item_id": item["item_id"], "label": label, "evidence_span_ids": sorted(spans),
            "rationale": body["rationale"], "quote_or_citation": quote}

    def _records(self, run: dict[str, Any], items: list[dict[str, Any]],
                 *, session: Any = None) -> list[dict[str, Any]]:
        rows = list(self.db.item_annotations.find({"workspace_id": run["workspace_id"],
            "analysis_run_id": run["_id"]}, **_options(session)).sort("_id", 1).limit(MAX_ANNOTATIONS + 1))
        if len(rows) > MAX_ANNOTATIONS:
            _limit()
        item_map = {item["item_id"]: item for item in items}
        revisions: dict[tuple[Any, str], list[int]] = {}
        for row in rows:
            try:
                if (row["annotation_sha256"] != _sha({key: value for key, value in row.items() if key != "annotation_sha256"})
                        or row["annotation_mode"] != MODE or row["item_id"] not in item_map
                        or row["pipeline"] != item_map[row["item_id"]]["pipeline"]
                        or row["run_revision"] > run["revision"]
                        or row["run_revision"] != row["based_on_revision"] + 1
                        or not isinstance(row["created_by"], ObjectId)):
                    _integrity()
                body = {key: row[key] for key in ("item_id", "label", "evidence_span_ids", "rationale", "quote_or_citation")}
                canonical = self._payload(body, item_map[row["item_id"]])
                if row["request_sha256"] != _sha(canonical):
                    _integrity()
                key = (row["created_by"], row["item_id"])
                revisions.setdefault(key, []).append(row["annotation_revision"])
            except (KeyError, TypeError, ValueError):
                _integrity()
            except DomainError as error:
                if error.status == 422:
                    _integrity()
                raise
        for values in revisions.values():
            if sorted(values) != list(range(1, len(values) + 1)):
                _integrity()
        return rows

    @staticmethod
    def _page_limit(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= 100:
            _invalid("Page limit must be between 1 and 100")

    def list_items(self, actor_id: ObjectId, workspace_id: ObjectId | str, run_id: ObjectId | str,
                   *, limit: int = 25, cursor: str | None = None) -> dict[str, Any]:
        self._page_limit(limit)
        if cursor is not None and (not isinstance(cursor, str) or not HASH_PATTERN.fullmatch(cursor)):
            _invalid("Invalid annotation item cursor")
        run, results, snapshot = self._scope(actor_id, workspace_id, run_id)
        items = self._items(run, results, snapshot)
        annotations = self._records(run, items)
        latest: dict[tuple[ObjectId, str], dict[str, Any]] = {}
        for row in annotations:
            key = (row["created_by"], row["item_id"])
            if key not in latest or row["annotation_revision"] > latest[key]["annotation_revision"]:
                latest[key] = row
        selected = [item for item in items if cursor is None or item["item_id"] > cursor]
        more, selected = len(selected) > limit, selected[:limit]
        for item in selected:
            own = latest.get((actor_id, item["item_id"]))
            item["latest_annotation"] = annotation_dto(own) if own else None
        return _bounded({"items": selected, "page": {"limit": limit, "has_more": more,
            "next_cursor": selected[-1]["item_id"] if more else None}, "run_revision": run["revision"]})

    def create(self, actor_id: ObjectId, workspace_id: ObjectId | str, run_id: ObjectId | str,
               body: dict[str, Any], *, expected_revision: int, idempotency_key: str,
               request_id: str) -> dict[str, Any]:
        if (type(expected_revision) is not int or expected_revision < 1
                or not isinstance(idempotency_key, str)
                or re.fullmatch(r"[A-Za-z0-9_.:-]{16,128}", idempotency_key) is None
                or not isinstance(body, dict) or not isinstance(body.get("item_id"), str)
                or not HASH_PATTERN.fullmatch(body["item_id"])):
            _invalid()
        workspace_id, run_id = object_id(workspace_id), object_id(run_id)
        identity = {"workspace_id": workspace_id, "analysis_run_id": run_id,
            "created_by": actor_id, "idempotency_key": idempotency_key}

        def perform(session: Any = None, *, replay_only: bool = False):
            options = _options(session)
            run, results, snapshot = self._scope(actor_id, workspace_id, run_id, session=session)
            items = self._items(run, results, snapshot)
            rows = self._records(run, items, session=session)
            item = next((item for item in items if item["item_id"] == body["item_id"]), None)
            if item is None:
                _invalid("Item must belong to this pinned run")
            payload = self._payload(body, item)
            request_sha = _sha(payload)
            previous = next((row for row in rows if all(row[key] == value for key, value in identity.items())), None)
            if previous is not None:
                if previous["request_sha256"] != request_sha:
                    raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Idempotency key used for a different annotation")
                return previous
            if replay_only:
                raise DomainError(409, "REVISION_CONFLICT", "Annotation changed; reload before reviewing")
            if run["revision"] != expected_revision:
                raise DomainError(409, "REVISION_CONFLICT", "Analysis revision has changed; reload before reviewing")
            if len(rows) >= MAX_ANNOTATIONS:
                _limit()
            own = [row for row in rows if row["created_by"] == actor_id and row["item_id"] == item["item_id"]]
            now = datetime.now(UTC)
            # BSON stores milliseconds; hash the exact persisted timestamp.
            now = now.replace(microsecond=now.microsecond // 1000 * 1000)
            row = {"_id": ObjectId(), "schema_version": 1, "created_at": now, "created_by": actor_id,
                "workspace_id": workspace_id, "analysis_run_id": run_id, **payload,
                "pipeline": item["pipeline"], "annotation_mode": MODE,
                "annotation_revision": len(own) + 1, "based_on_revision": expected_revision,
                "run_revision": expected_revision + 1, "idempotency_key": idempotency_key,
                "request_sha256": request_sha}
            row["annotation_sha256"] = _sha(row)
            changed = self.db.analysis_runs.update_one({"_id": run_id, "workspace_id": workspace_id,
                "revision": expected_revision, "state": "SUCCEEDED", "lifecycle_state": "ACTIVE"},
                {"$set": {"updated_at": now, "updated_by": actor_id}, "$inc": {"revision": 1}}, **options)
            if changed.matched_count != 1:
                raise DomainError(409, "REVISION_CONFLICT", "Analysis revision has changed; reload before reviewing")
            self.db.item_annotations.insert_one(row, **options)
            append_event(self.db, actor_id=actor_id, workspace_id=workspace_id,
                action="ITEM_ANNOTATION_CREATED", resource_type="ITEM_ANNOTATION", resource_id=row["_id"],
                request_id=request_id, session=session)
            return row

        try:
            with self.analysis.documents.transaction() as session:
                row = perform(session)
        except DuplicateKeyError:
            row = perform(replay_only=True)
        return annotation_dto(row)

    def history(self, actor_id: ObjectId, workspace_id: ObjectId | str, run_id: ObjectId | str,
                *, limit: int = 25, cursor: str | None = None) -> dict[str, Any]:
        self._page_limit(limit)
        cursor_id = object_id(cursor) if cursor is not None else None
        run, results, snapshot = self._scope(actor_id, workspace_id, run_id)
        rows = self._records(run, self._items(run, results, snapshot))
        selected = [row for row in rows if row["created_by"] == actor_id and (cursor_id is None or row["_id"] > cursor_id)]
        more, selected = len(selected) > limit, selected[:limit]
        return _bounded({"items": [annotation_dto(row) for row in selected], "page": {"limit": limit, "has_more": more,
            "next_cursor": str(selected[-1]["_id"]) if more else None}, "run_revision": run["revision"],
            "annotation_mode": MODE, "predictions_visible": True})

    def export(self, actor_id: ObjectId, workspace_id: ObjectId | str, run_id: ObjectId | str) -> dict[str, Any]:
        run, results, snapshot = self._scope(actor_id, workspace_id, run_id)
        items = self._items(run, results, snapshot)
        rows = self._records(run, items)
        own = [row for row in rows if row["created_by"] == actor_id]
        return _bounded({"schema_version": 1, "analysis_run_id": str(run["_id"]),
            "workspace_id": str(run["workspace_id"]), "run_revision": run["revision"],
            "annotator_id": str(actor_id), "annotation_mode": MODE,
            "predictions_visible": True, "independent_gold": False, "official_grade": False,
            "interpretation": "Model-visible human review only; not independent blinded gold, training data, or an official grade.",
            "items": items, "annotations": [annotation_dto(row) for row in own]})
