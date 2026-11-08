"""Audit citation coordinates against frozen P2 inputs, without semantic judging.

The caller verifies artifact hashes/freezes. This pure adapter checks the frozen
chunk-to-original-body mapping and optionally compares locations with one human
reference. A source-bound quotation is not proof that its conclusion is true.
"""
from __future__ import annotations

from bisect import bisect_right
import hashlib
import json
from typing import Any, Mapping
import unicodedata

from research.core_mvp.similarity import _resolve_normalized_range
from research.gold_annotation.assessment_evidence import compare_evidence, validate_evidence_record


_IDENTITY = ("report_id", "report_version", "body_sha256")


def _normalized(text: str) -> str:
    text = "".join(char for char in text if char not in "\u200b\u200c\u200d\u2060\ufeff")
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _digest(value: Any) -> str:
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _integer(value: Any) -> int:
    _require(type(value) is int, "NON_INTEGER_COORDINATE")
    return value


def _version(value: Mapping[str, Any]) -> str:
    version = value.get("document_version_id", value.get("document_version"))
    _require(isinstance(version, str) and bool(version), "MISSING_RUNTIME_VERSION")
    _require(value.get("document_version", version) == version, "RUNTIME_VERSION_ALIAS_MISMATCH")
    return version


def _catalog(common_item: Mapping[str, Any]) -> dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]]:
    pack = common_item.get("evidence_pack")
    _require(isinstance(pack, list) and 0 < len(pack) <= 10000, "INVALID_FROZEN_PACK")
    if "evidence_pack_sha256" in common_item:
        _require(_digest(pack) == common_item["evidence_pack_sha256"], "FROZEN_PACK_HASH_MISMATCH")
    entries = {}
    documents = set()
    for entry in pack:
        record, chunk = entry["record"], entry["chunk"]
        version = _version(chunk)
        identifier = record.get("evidence_id")
        _require(isinstance(identifier, str) and bool(identifier) and identifier not in entries,
                 "INVALID_FROZEN_EVIDENCE_ID")
        _require(all(record.get(key) == chunk.get(key) for key in ("chunk_id", "document_id"))
                 and record.get("document_version_id") == version, "FROZEN_RUNTIME_ID_MISMATCH")
        _require(record.get("source_spans") == chunk.get("source_spans"), "FROZEN_SOURCE_MAP_MISMATCH")
        text, raw = chunk.get("normalized_text"), chunk.get("raw_text")
        _require(isinstance(text, str) and bool(text.strip()) and isinstance(raw, str), "INVALID_FROZEN_TEXT")
        mapping = chunk.get("normalization_map", {}).get("normalized_char_to_raw_span")
        _require(isinstance(mapping, list) and len(mapping) == len(text), "INVALID_FROZEN_NORMALIZATION_MAP")
        for pair in mapping:
            _require(isinstance(pair, list) and len(pair) == 2, "INVALID_FROZEN_NORMALIZATION_MAP")
            a, b = _integer(pair[0]), _integer(pair[1])
            _require(0 <= a < b <= len(raw), "INVALID_FROZEN_NORMALIZATION_MAP")
        documents.add((chunk["document_id"], version))
        entries[identifier] = (record, chunk)
    _require(len(documents) == 1, "MULTIPLE_FROZEN_RUNTIME_DOCUMENTS")
    return entries


def _proof_geometry(proof: Mapping[str, Any], relation: str, entries, context, paragraph_starts, paragraphs):
    _require(isinstance(proof, Mapping) and proof.get("relation") == relation, "PROOF_RELATION_MISMATCH")
    identifier = proof.get("evidence_id")
    _require(isinstance(identifier, str) and identifier in entries, "UNKNOWN_EVIDENCE_ID")
    _, chunk = entries[identifier]
    span = proof.get("span")
    _require(isinstance(span, Mapping), "MISSING_PROOF_SPAN")
    _require(span.get("chunk_id") == chunk["chunk_id"] and span.get("document_id") == chunk["document_id"]
             and span.get("document_version_id") == _version(chunk), "PROOF_RUNTIME_ID_MISMATCH")
    start, end = _integer(span.get("normalized_start")), _integer(span.get("normalized_end"))
    text = chunk["normalized_text"]
    _require(0 <= start < end <= len(text), "PROOF_NORMALIZED_RANGE_OUTSIDE_CHUNK")
    _require(isinstance(span.get("text"), str) and bool(span["text"].strip())
             and span["text"] == text[start:end], "PROOF_TEXT_RANGE_MISMATCH")
    resolved = _resolve_normalized_range(chunk, start, end)
    _require(all(span.get(key) == resolved[key] for key in ("raw_start", "raw_end", "source_spans")),
             "PROOF_SOURCE_MAP_MISMATCH")
    segments = span["source_spans"]
    _require(isinstance(segments, list) and bool(segments), "EMPTY_PROOF_SOURCE_MAP")
    mapped, fragments = [], []
    covered = start
    for segment in segments:
        _require(segment.get("document_id") == chunk["document_id"]
                 and _version(segment) == _version(chunk), "PROOF_SEGMENT_RUNTIME_ID_MISMATCH")
        left = _integer(segment.get("matched_chunk_normalized_start"))
        right = _integer(segment.get("matched_chunk_normalized_end"))
        _require(start <= left < right <= end and left >= covered, "PROOF_SEGMENT_NORMALIZED_RANGE_INVALID")
        _require(not text[covered:left].strip(), "PROOF_SOURCE_MAP_OMITS_TEXT")
        covered = right
        locator = segment.get("locator")
        _require(isinstance(locator, Mapping), "MISSING_RAW_BODY_LOCATOR")
        base = _integer(locator.get("document_raw_char_start"))
        raw_left = _integer(segment.get("matched_element_raw_start"))
        raw_right = _integer(segment.get("matched_element_raw_end"))
        _require(base >= 0 and 0 <= raw_left < raw_right, "INVALID_ELEMENT_RAW_RANGE")
        body_start, body_end = base + raw_left, base + raw_right
        _require(0 <= body_start < body_end <= len(context["report_text"]), "PROOF_BODY_RANGE_OUTSIDE_TEXT")
        index = bisect_right(paragraph_starts, body_start) - 1
        paragraph = paragraphs[index] if index >= 0 else None
        _require(paragraph is not None and body_end <= paragraph["end"], "PROOF_OUTSIDE_SINGLE_PARAGRAPH")
        quote = context["report_text"][body_start:body_end]
        _require(bool(quote.strip()), "EMPTY_RAW_SOURCE_QUOTE")
        fragments.append(quote)
        mapped.append({"paragraph_id": paragraph["paragraph_id"], "start": body_start,
                       "end": body_end, "quote": quote})
    _require(not text[covered:end].strip(), "PROOF_SOURCE_MAP_OMITS_TEXT")
    _require(_normalized(" ".join(fragments)) == _normalized(span["text"]), "RAW_SOURCE_NORMALIZATION_MISMATCH")
    return {"evidence_id": identifier, "chunk_id": chunk["chunk_id"], "relation": relation,
            "normalized_start": start, "normalized_end": end, "mapped_segments": mapped}


def audit_item(prediction: Mapping[str, Any], reference: Mapping[str, Any],
               context: Mapping[str, Any], common_item: Mapping[str, Any]) -> dict[str, Any]:
    """Check one result row against its frozen pack and exact original context.

    ``reference`` is a canonical intake row (``evidence`` field), or a typed
    evidence record itself. ``common_item`` is the corresponding entry from
    common-evidence.json's items. Corrupt reference/context/frozen pack raises;
    invalid prediction citations are reported, and their overlap is withheld.
    Absence scope and span-location overlap are always separate diagnostics.
    """
    evidence = reference.get("evidence", reference)
    expected = validate_evidence_record(evidence, context)
    entries = _catalog(common_item)
    checklist_id = common_item["checklist"]["checklist_id"]
    for row in (prediction, reference):
        metadata = row.get("metadata", {})
        for key in _IDENTITY:
            if key in metadata:
                _require(metadata[key] == context[key], "REFERENCE_IDENTITY_MISMATCH")
        _require(metadata.get("checklist_id", row.get("checklist_id", checklist_id)) == checklist_id,
                 "CHECKLIST_IDENTITY_MISMATCH")
    if "common_pack_sha256" in prediction:
        _require(prediction["common_pack_sha256"] == _digest(common_item["evidence_pack"]), "PREDICTION_PACK_HASH_MISMATCH")
    raw = prediction.get("raw_result")
    _require(isinstance(raw, Mapping), "MISSING_RAW_RESULT")
    paragraphs = sorted(context["paragraphs"], key=lambda p: (p["start"], p["end"], p["paragraph_id"]))
    paragraph_starts = [p["start"] for p in paragraphs]
    records, issues, proof_count = [], [], 0
    for field, relation in (("matched_evidence_spans", "SUPPORTED"), ("contradiction_hits", "CONTRADICTED")):
        proofs = raw.get(field)
        if not isinstance(proofs, list) or len(proofs) > 10000:
            issues.append({"field": field, "code": "INVALID_PROOF_ARRAY"})
            continue
        for index, proof in enumerate(proofs):
            proof_count += 1
            try:
                records.append(_proof_geometry(proof, relation, entries, context, paragraph_starts, paragraphs))
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                code = str(exc) if type(exc) is ValueError else "MALFORMED_PROOF"
                issues.append({"field": field, "index": index, "code": code})
    accepted_label = prediction.get("accepted_label")
    if accepted_label in {"MET", "UNMET"} and not proof_count:
        issues.append({"code": "MISSING_CONCLUSIVE_PROOF"})
    if prediction.get("decision_status") == "TECHNICAL_ABSTENTION" and proof_count:
        issues.append({"code": "TECHNICAL_ABSTENTION_HAS_PROOF"})
    actual = None
    if records and not issues:
        unique = {(part["start"], part["end"]): part for record in records for part in record["mapped_segments"]}
        actual = validate_evidence_record({"schema_version": 1, "kind": "SPAN_SET",
                    **{key: context[key] for key in _IDENTITY}, "spans": list(unique.values())}, context)
    comparison = compare_evidence(actual, expected, context) if not issues else None
    return {"schema_version": 1, "checklist_id": checklist_id,
            "audit_status": "INVALID" if issues else "PASSED" if proof_count else "NO_CITATIONS",
            "proof_count": proof_count, "source_bound_proof_count": len(records),
            "all_present_proofs_source_bound": bool(proof_count and not issues),
            "issues": issues, "proof_records": records,
            "location_overlap": comparison["span_evidence"] if comparison else None,
            "document_absence": comparison["document_absence"] if comparison else {
                "applicable": expected["kind"] == "DOCUMENT_ABSENCE",
                "matching_complete_scope_record": False, "semantic_absence_verified": False},
            "reference_evidence_kind": expected["kind"],
            "model_absence_detection_validated": False, "semantic_support_verified": False,
            "interpretation": "Source traceability and selected-location overlap only; alternate valid evidence can differ from the human selection."}
