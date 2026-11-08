"""Supplemental typed evidence for assessment annotation and diagnostics.

This module does not approve a dataset, freeze gold, certify an annotator, or
decide whether a passage semantically satisfies a rubric.  Existing gold-v1
span contracts are unchanged.  A document-absence record is an explicit claim
about the entire *captured text*, not an invented quotation or an assertion
about a PDF's unparsed text/images.  Its structural validity does not establish
that the claimed absence is true.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


EVIDENCE_SCHEMA_VERSION = 1
EVIDENCE_KINDS = frozenset({"SPAN_SET", "DOCUMENT_ABSENCE", "INSUFFICIENT_INPUT", "UNRESOLVED"})
_IDENTITY = ("report_id", "report_version", "body_sha256")
_MAX_TEXT_CHARS = 2_000_000
_MAX_PARAGRAPHS = 100_000
_MAX_SPANS = 10_000


def _invalid(reason: str) -> ValueError:
    # Error messages do not contain report text, quotations or user values.
    return ValueError("Invalid assessment evidence: " + reason)


def _string(value: Any, field: str, *, limit: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise _invalid(field)
    return value.strip()


def _integer(value: Any) -> int:
    if type(value) is not int:
        raise _invalid("range coordinates must be integers")
    return value


def _sha(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise _invalid("body_sha256")
    return value


@dataclass(frozen=True)
class _Scope:
    identity: dict[str, str]
    text: str
    paragraphs: tuple[dict[str, Any], ...]


def _scope(context: Mapping[str, Any]) -> _Scope:
    if not isinstance(context, Mapping):
        raise _invalid("context")
    identity = {
        "report_id": _string(context.get("report_id"), "report_id"),
        "report_version": _string(context.get("report_version"), "report_version"),
        "body_sha256": _sha(context.get("body_sha256")),
    }
    text = context.get("report_text")
    if not isinstance(text, str) or len(text) > _MAX_TEXT_CHARS:
        raise _invalid("report_text")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != identity["body_sha256"]:
        raise _invalid("context text/hash conflict")
    paragraphs = context.get("paragraphs")
    if not isinstance(paragraphs, list) or len(paragraphs) > _MAX_PARAGRAPHS:
        raise _invalid("paragraphs")
    canonical = []
    seen = set()
    for paragraph in paragraphs:
        if not isinstance(paragraph, Mapping):
            raise _invalid("paragraph")
        identifier = _string(paragraph.get("paragraph_id"), "paragraph_id")
        start, end = _integer(paragraph.get("start")), _integer(paragraph.get("end"))
        if identifier in seen or not 0 <= start <= end <= len(text):
            raise _invalid("duplicate paragraph or out-of-range paragraph")
        if paragraph.get("text", text[start:end]) != text[start:end]:
            raise _invalid("paragraph text/range conflict")
        seen.add(identifier)
        canonical.append({"paragraph_id": identifier, "start": start, "end": end})
    canonical.sort(key=lambda p: (p["start"], p["end"], p["paragraph_id"]))
    previous = 0
    for paragraph in canonical:
        if paragraph["start"] < previous or text[previous:paragraph["start"]].strip():
            raise _invalid("paragraphs overlap or omit captured text")
        previous = paragraph["end"]
    if text[previous:].strip():
        raise _invalid("paragraphs omit captured text")
    return _Scope(identity, text, tuple(canonical))


def _span_identifier(scope: _Scope, start: int, end: int) -> str:
    data = {**scope.identity, "start": start, "end": end}
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "span-" + hashlib.sha256(payload).hexdigest()[:24]


def span_identifier(context: Mapping[str, Any], start: int, end: int) -> str:
    """Return a source-bound ID; repeated quotations at different ranges differ."""
    scope = _scope(context)
    start, end = _integer(start), _integer(end)
    if not 0 <= start < end <= len(scope.text):
        raise _invalid("span range")
    return _span_identifier(scope, start, end)


def validate_evidence_record(record: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    """Validate geometry/coverage and return a new canonical typed record.

    Required shared fields are schema_version, kind, report_id, report_version,
    body_sha256. SPAN_SET carries exact nonempty spans. DOCUMENT_ABSENCE
    carries scope=ENTIRE_CAPTURED_TEXT, reviewed_whole_text=True, every paragraph
    ID exactly once and a rationale. INSUFFICIENT_INPUT and UNRESOLVED carry a
    rationale. Unknown fields and implicit conversion between kinds are rejected.
    """
    scope = _scope(context)
    if not isinstance(record, Mapping) or type(record.get("schema_version")) is not int:
        raise _invalid("record schema_version")
    if (record["schema_version"] != EVIDENCE_SCHEMA_VERSION or not isinstance(record.get("kind"), str)
            or record["kind"] not in EVIDENCE_KINDS):
        raise _invalid("record schema_version or kind")
    for key in _IDENTITY:
        if record.get(key) != scope.identity[key]:
            raise _invalid("record/context identity conflict")
    kind = record["kind"]
    common = {"schema_version", "kind", *_IDENTITY}
    allowed = common | ({"spans"} if kind == "SPAN_SET" else
                        {"scope", "reviewed_whole_text", "paragraph_ids", "rationale"} if kind == "DOCUMENT_ABSENCE" else
                        {"rationale"})
    if set(record) != allowed:
        raise _invalid("missing or unexpected record fields")
    canonical: dict[str, Any] = {"schema_version": EVIDENCE_SCHEMA_VERSION, "kind": kind, **scope.identity}
    if kind == "SPAN_SET":
        spans = record["spans"]
        if not isinstance(spans, list) or not 0 < len(spans) <= _MAX_SPANS:
            raise _invalid("SPAN_SET requires nonempty spans")
        result, seen = [], set()
        paragraph_starts = [p["start"] for p in scope.paragraphs]
        for span in spans:
            if not isinstance(span, Mapping) or not {"start", "end", "quote"} <= set(span):
                raise _invalid("span fields")
            if set(span) - {"start", "end", "quote", "paragraph_id", "span_id"}:
                raise _invalid("unexpected span fields")
            start, end = _integer(span["start"]), _integer(span["end"])
            quote = span["quote"]
            if (not 0 <= start < end <= len(scope.text) or not isinstance(quote, str)
                    or not quote.strip() or scope.text[start:end] != quote):
                raise _invalid("span quote/range conflict")
            index = bisect_right(paragraph_starts, start) - 1
            owner = scope.paragraphs[index] if index >= 0 else None
            if (owner is None or end > owner["end"]
                    or span.get("paragraph_id", owner["paragraph_id"]) != owner["paragraph_id"]):
                raise _invalid("span does not belong to the declared paragraph")
            identifier = _span_identifier(scope, start, end)
            if identifier in seen or span.get("span_id", identifier) != identifier:
                raise _invalid("duplicate or forged span_id")
            seen.add(identifier)
            result.append({"span_id": identifier, "start": start, "end": end,
                           "quote": quote, "paragraph_id": owner["paragraph_id"]})
        canonical["spans"] = sorted(result, key=lambda s: (s["start"], s["end"]))
    elif kind == "DOCUMENT_ABSENCE":
        supplied = record["paragraph_ids"]
        expected = [p["paragraph_id"] for p in scope.paragraphs]
        if (record["scope"] != "ENTIRE_CAPTURED_TEXT" or record["reviewed_whole_text"] is not True
                or not scope.text.strip() or not expected or not isinstance(supplied, list)
                or any(not isinstance(identifier, str) for identifier in supplied)
                or len(supplied) != len(set(supplied)) or set(supplied) != set(expected)):
            raise _invalid("absence needs explicit review of every captured paragraph")
        canonical.update(scope="ENTIRE_CAPTURED_TEXT", reviewed_whole_text=True,
                         paragraph_ids=expected, rationale=_string(record["rationale"], "rationale", limit=20000))
    else:
        canonical["rationale"] = _string(record["rationale"], "rationale", limit=20000)
    return canonical


def _union(spans: Sequence[Mapping[str, Any]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for start, end in sorted((span["start"], span["end"]) for span in spans):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def _overlap(first: Sequence[tuple[int, int]], second: Sequence[tuple[int, int]]) -> int:
    total, a, b = 0, 0, 0
    while a < len(first) and b < len(second):
        left, right = first[a], second[b]
        total += max(0, min(left[1], right[1]) - max(left[0], right[0]))
        if left[1] <= right[1]:
            a += 1
        else:
            b += 1
    return total


def _rates(reference: int, predicted: int, overlap: int) -> dict[str, Any]:
    return {"reference_chars": reference, "predicted_chars": predicted, "overlap_chars": overlap,
            "precision": overlap / predicted if predicted else None,
            "recall": overlap / reference if reference else None,
            "f1": 2 * overlap / (reference + predicted) if reference + predicted else None}


def compare_evidence(predicted: Mapping[str, Any] | None, reference: Mapping[str, Any],
                     context: Mapping[str, Any]) -> dict[str, Any]:
    """Compare source geometry and absence records separately, not semantic truth.

    None denotes missing prediction evidence, not automatically a technical
    abstention or CANNOT_ASSESS label. Callers retain run/label status separately.
    An unresolved reference cannot contribute to final evidence metrics.
    """
    actual = validate_evidence_record(predicted, context) if predicted is not None else None
    expected = validate_evidence_record(reference, context)
    unresolved = expected["kind"] == "UNRESOLVED"
    actual_spans = _union(actual.get("spans", [])) if actual else []
    expected_spans = _union(expected.get("spans", []))
    a_size = sum(end - start for start, end in actual_spans)
    e_size = sum(end - start for start, end in expected_spans)
    absence = expected["kind"] == "DOCUMENT_ABSENCE"
    applicable = not unresolved and not absence
    rates = _rates(e_size, a_size, _overlap(expected_spans, actual_spans)) if applicable else None
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "status": "REFERENCE_UNRESOLVED" if unresolved else "COMPARED",
        "reference_kind": expected["kind"], "predicted_kind": actual["kind"] if actual else None,
        "prediction_evidence_missing": actual is None,
        "kind_match": actual is not None and actual["kind"] == expected["kind"],
        "span_evidence": {"applicable": applicable, "metrics": rates},
        "document_absence": {
            "applicable": absence,
            "matching_complete_scope_record": bool(absence and actual and actual["kind"] == "DOCUMENT_ABSENCE"),
            "unexpected_span_chars": a_size if absence else 0,
            "semantic_absence_verified": False,
        },
        "semantic_support_verified": False,
    }


def summarize_comparisons(comparisons: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Micro-average span geometry; retain absence and unresolved counts separately."""
    counts = Counter(item["status"] for item in comparisons)
    span_rows = [item["span_evidence"]["metrics"] for item in comparisons
                 if item["span_evidence"]["applicable"]]
    reference = sum(row["reference_chars"] for row in span_rows)
    predicted = sum(row["predicted_chars"] for row in span_rows)
    overlap = sum(row["overlap_chars"] for row in span_rows)
    absence = [item["document_absence"] for item in comparisons if item["document_absence"]["applicable"]]
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION, "items": len(comparisons),
        "compared_items": counts["COMPARED"], "unresolved_reference_items": counts["REFERENCE_UNRESOLVED"],
        "span_geometry": {"items": len(span_rows), **_rates(reference, predicted, overlap)},
        "document_absence": {
            "reference_items": len(absence),
            "matching_complete_scope_records": sum(row["matching_complete_scope_record"] for row in absence),
            "unexpected_span_chars": sum(row["unexpected_span_chars"] for row in absence),
            "semantic_absence_verified": False,
        },
        "semantic_support_verified": False,
        "limitations": [
            "Span overlap is coordinate agreement, not proof that evidence satisfies the rubric.",
            "Document-absence matches verify complete captured-text scope records, not the truth of the absence claim or a reviewer identity.",
            "Absence and unresolved references are excluded from span micro denominators and counted separately; empty evidence never yields a perfect score.",
            "No label accuracy, technical-abstention status, approval or gold readiness is inferred from evidence alone.",
        ],
    }
