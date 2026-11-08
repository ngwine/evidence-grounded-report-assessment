"""Validate stored chunk-to-element references before retrieval/inference."""

from __future__ import annotations

import hashlib
from typing import Any

from bson import ObjectId

from .documents import _options
from .errors import DomainError


def validate_chunk_generation(database: Any, version: dict[str, Any], chunks: list[dict[str, Any]],
                              *, session: Any = None) -> None:
    def reject() -> None:
        raise DomainError(409, "PROVENANCE_INVALID", "Stored provenance integrity failed")

    if not chunks or len(chunks) != version["chunk_count"] or len(chunks) > 5000:
        reject()
    identifiers = set()
    for chunk in chunks:
        if (chunk.get("workspace_id") != version["workspace_id"]
                or chunk.get("document_id") != version["document_id"]
                or chunk.get("document_version_id") != version["_id"]
                or chunk.get("generation_key") != version["generation_key"]
                or not isinstance(chunk.get("source_spans"), list) or not chunk["source_spans"]):
            reject()
        for span in chunk["source_spans"]:
            if not isinstance(span.get("element_id"), ObjectId):
                reject()
            identifiers.add(span["element_id"])
    if len(identifiers) > 20000:
        reject()
    elements = {row["_id"]: row for row in database.document_elements.find({
        "_id": {"$in": list(identifiers)}, "workspace_id": version["workspace_id"],
        "document_version_id": version["_id"], "generation_key": version["generation_key"]}, **_options(session))}
    if set(elements) != identifiers:
        reject()
    tombstones = database.tombstones.find_one({"resource_type": {"$in": ["CHUNK", "DOCUMENT_ELEMENT"]},
        "resource_id": {"$in": [*identifiers, *(row["_id"] for row in chunks)]}}, **_options(session))
    if tombstones:
        reject()
    for row in [*chunks, *elements.values()]:
        for name in ("raw_text", "normalized_text"):
            value = row.get(name)
            if not isinstance(value, str) or hashlib.sha256(value.encode()).hexdigest() != row.get(name + "_sha256"):
                reject()
    for chunk in chunks:
        references = []
        for span in chunk["source_spans"]:
            element = elements[span["element_id"]]
            if (span.get("document_version_id") != version["_id"] or span.get("document_id") != version["document_id"]
                    or span.get("stable_element_key") != element["element_key"]):
                reject()
            offsets = [span.get(key) for key in ("element_raw_char_start", "element_raw_char_end",
                                                  "chunk_raw_char_start", "chunk_raw_char_end")]
            if any(type(value) is not int for value in offsets):
                reject()
            start, end, chunk_start, chunk_end = offsets
            if (not 0 <= start < end <= len(element["raw_text"])
                    or not 0 <= chunk_start < chunk_end <= len(chunk["raw_text"])
                    or element["raw_text"][start:end] != chunk["raw_text"][chunk_start:chunk_end]):
                reject()
            references.append(element["_id"])
        if list(dict.fromkeys(references)) != chunk["element_ids"]:
            reject()
