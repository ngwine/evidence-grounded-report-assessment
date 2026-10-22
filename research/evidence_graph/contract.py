"""Evidence Graph v1 contract; no semantic relation is inferred here.

The parser's ``source_spans`` are authoritative. A graph span copies one
source span exactly, including element-local raw/normalized offsets and its
PDF/DOCX locator. The graph never invents a page or converts normalized
offsets to raw offsets itself.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import math
from typing import Any, Mapping


SCHEMA_VERSION = "evidence-graph-v1"
SCOPE_FIELDS = (
    "workspace_id", "report_id", "report_version_id", "graph_version", "analysis_run_id"
)
NODE_TYPES = frozenset({
    "CLAIM", "CONCEPT", "METHOD", "RESULT", "CONCLUSION", "SOURCE", "EVIDENCE_SPAN"
})
RELATION_DOMAINS = {
    "MENTIONS": ({"SOURCE", "EVIDENCE_SPAN"}, NODE_TYPES - {"SOURCE", "EVIDENCE_SPAN"}),
    "USES_METHOD": ({"CLAIM", "RESULT"}, {"METHOD"}),
    "EVALUATED_ON": ({"METHOD", "RESULT"}, {"SOURCE", "CONCEPT"}),
    "SUPPORTS": ({"EVIDENCE_SPAN", "RESULT"}, {"CLAIM", "CONCLUSION"}),
    "CONTRADICTS": ({"EVIDENCE_SPAN", "CLAIM"}, {"CLAIM", "CONCLUSION"}),
    "REPORTS_RESULT": ({"METHOD", "SOURCE"}, {"RESULT"}),
    "DRAWS_CONCLUSION": ({"RESULT", "CLAIM"}, {"CONCLUSION"}),
    "REFERS_TO": (NODE_TYPES, NODE_TYPES),
}
REVIEW_STATES = frozenset({"UNREVIEWED", "ACCEPTED", "REJECTED"})
ATTRIBUTE_ALLOWLIST = {
    "CLAIM": {"claim_kind", "polarity", "subject", "time", "condition"},
    "CONCEPT": {"aliases"},
    "METHOD": {"version", "config"},
    "RESULT": {"metric", "value", "unit", "dataset", "split", "context"},
    "CONCLUSION": {"scope"},
    "SOURCE": {"document_id", "document_version_id", "rights_state"},
    "EVIDENCE_SPAN": set(),
}
SPAN_FIELDS = (
    "element_key", "element_type", "element_raw_char_start", "element_raw_char_end",
    "element_normalized_char_start", "element_normalized_char_end",
    "chunk_raw_char_start", "chunk_raw_char_end", "chunk_normalized_char_start",
    "chunk_normalized_char_end", "locator",
)


class GraphValidationError(ValueError):
    """An untraceable or inconsistent graph must fail closed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _id(prefix: str, value: Any) -> str:
    return f"{prefix}-{digest(value)}"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GraphValidationError(f"{name} must be a nonempty string")
    return value


def _scope(value: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(SCOPE_FIELDS):
        raise GraphValidationError(f"scope must contain exactly {', '.join(SCOPE_FIELDS)}")
    return {key: _nonempty(value[key], f"scope.{key}") for key in SCOPE_FIELDS}


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GraphValidationError("confidence must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise GraphValidationError("confidence must be in [0, 1]")
    return result


def _utc_timestamp(value: Any, name: str) -> str:
    _nonempty(value, name)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise GraphValidationError(f"{name} must be ISO 8601 UTC") from error
    if parsed.utcoffset() != timedelta(0):
        raise GraphValidationError(f"{name} must be ISO 8601 UTC")
    return value


def _unique_ids(values: Any, name: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise GraphValidationError(f"{name} must be a nonempty list")
    ids = [_nonempty(value, name) for value in values]
    if len(ids) != len(set(ids)):
        raise GraphValidationError(f"{name} contains duplicates")
    return ids


def _source_span(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not set(SPAN_FIELDS).issubset(value):
        raise GraphValidationError("source span lacks parser v2 coordinates/locator")
    span = {key: deepcopy(value[key]) for key in SPAN_FIELDS}
    _nonempty(span["element_key"], "source_span.element_key")
    _nonempty(span["element_type"], "source_span.element_type")
    if not isinstance(span["locator"], Mapping) or not span["locator"]:
        raise GraphValidationError("source_span.locator is required")
    for prefix in ("element_raw_char", "element_normalized_char", "chunk_raw_char", "chunk_normalized_char"):
        start, end = span[f"{prefix}_start"], span[f"{prefix}_end"]
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (start, end)) or not 0 <= start < end:
            raise GraphValidationError(f"{prefix} must be a nonempty half-open range")
    return span


def make_chunk_reference(chunk: Mapping[str, Any], *, document_id: str) -> dict[str, Any]:
    """Project one validated parser v2 chunk without storing report text."""
    if chunk.get("schema_version") != 2:
        raise GraphValidationError("Evidence Graph requires parser chunk schema v2")
    if chunk.get("chunk_key") != chunk.get("chunk_id"):
        raise GraphValidationError("parser chunk_key/chunk_id stable identity mismatch")
    source_spans = chunk.get("source_spans")
    if not isinstance(source_spans, list) or not source_spans:
        raise GraphValidationError("chunk source_spans are required")
    content_hash = chunk.get("content_sha256")
    normalized_text = chunk.get("normalized_text")
    raw_text = chunk.get("raw_text")
    if not isinstance(normalized_text, str) or not isinstance(raw_text, str):
        raise GraphValidationError("parser chunk raw/normalized text is required")
    if content_hash != hashlib.sha256(normalized_text.encode("utf-8")).hexdigest():
        raise GraphValidationError("parser chunk content_sha256 does not match normalized text")
    canonical_spans = [_source_span(value) for value in source_spans]
    for span in canonical_spans:
        if (
            span["chunk_raw_char_end"] > len(raw_text)
            or span["chunk_normalized_char_end"] > len(normalized_text)
        ):
            raise GraphValidationError("parser source span exceeds chunk text length")
    return {
        "chunk_id": _nonempty(chunk.get("chunk_id"), "chunk_id"),
        "document_id": _nonempty(document_id, "document_id"),
        "document_version_id": _nonempty(chunk.get("document_version_id"), "document_version_id"),
        "content_sha256": content_hash,
        "source_spans": canonical_spans,
    }


def make_span(scope: Mapping[str, Any], chunk: Mapping[str, Any], source_span_index: int) -> dict[str, Any]:
    normalized_scope = _scope(scope)
    if isinstance(source_span_index, bool) or not isinstance(source_span_index, int):
        raise GraphValidationError("source_span_index must be an integer")
    spans = chunk.get("source_spans")
    if not isinstance(spans, list) or not 0 <= source_span_index < len(spans):
        raise GraphValidationError("source_span_index is outside the chunk")
    source_span = _source_span(spans[source_span_index])
    record = {
        "scope": normalized_scope,
        "chunk_id": _nonempty(chunk.get("chunk_id"), "chunk_id"),
        "document_id": _nonempty(chunk.get("document_id"), "document_id"),
        "document_version_id": _nonempty(chunk.get("document_version_id"), "document_version_id"),
        "source_span_index": source_span_index,
        "source_span": source_span,
    }
    record["span_id"] = _id("gsp", record)
    return record


def make_node(
    scope: Mapping[str, Any], *, node_type: str, label: str,
    evidence_span_ids: list[str], extractor: str, model_or_rule_version: str,
    confidence: float, created_at: str, attributes: Mapping[str, Any] | None = None,
    prompt_sha256: str | None = None,
) -> dict[str, Any]:
    identity = {
        "scope": _scope(scope), "node_type": node_type,
        "label": _nonempty(label, "node.label"),
        "attributes": deepcopy(dict(attributes or {})),
        "evidence_span_ids": _unique_ids(evidence_span_ids, "node.evidence_span_ids"),
        "extractor": _nonempty(extractor, "node.extractor"),
        "model_or_rule_version": _nonempty(model_or_rule_version, "node.model_or_rule_version"),
    }
    record = {
        **identity, "prompt_sha256": prompt_sha256,
        "confidence": _confidence(confidence),
        "created_at": _utc_timestamp(created_at, "node.created_at"),
    }
    record["node_id"] = _id("gn", identity)
    return record


def make_edge(
    scope: Mapping[str, Any], *, relation_type: str, from_node_id: str,
    to_node_id: str, evidence_span_ids: list[str], extractor: str,
    model_or_rule_version: str, confidence: float,
    review_state: str = "UNREVIEWED", prompt_sha256: str | None = None,
    reviewer_id: str | None = None, reviewed_at: str | None = None,
) -> dict[str, Any]:
    identity = {
        "scope": _scope(scope), "relation_type": relation_type,
        "from_node_id": _nonempty(from_node_id, "edge.from_node_id"),
        "to_node_id": _nonempty(to_node_id, "edge.to_node_id"),
        "evidence_span_ids": _unique_ids(evidence_span_ids, "edge.evidence_span_ids"),
        "extractor": _nonempty(extractor, "edge.extractor"),
        "model_or_rule_version": _nonempty(model_or_rule_version, "edge.model_or_rule_version"),
    }
    if review_state not in REVIEW_STATES:
        raise GraphValidationError("unknown edge review_state")
    if review_state == "UNREVIEWED":
        if reviewer_id is not None or reviewed_at is not None:
            raise GraphValidationError("UNREVIEWED edge cannot carry a reviewer")
    else:
        _nonempty(reviewer_id, "edge.reviewer_id")
        _utc_timestamp(reviewed_at, "edge.reviewed_at")
    record = {
        **identity, "prompt_sha256": prompt_sha256,
        "confidence": _confidence(confidence), "review_state": review_state,
        "reviewer_id": reviewer_id, "reviewed_at": reviewed_at,
    }
    record["edge_id"] = _id("ge", identity)
    return record


def _validate_prompt(value: Any) -> None:
    if value is not None and (
        not isinstance(value, str) or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise GraphValidationError("prompt_sha256 must be null or lowercase SHA-256")


def validate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one immutable graph generation and return canonical records."""
    if not isinstance(snapshot, Mapping) or snapshot.get("schema_version") != SCHEMA_VERSION:
        raise GraphValidationError("unsupported Evidence Graph schema_version")
    scope = _scope(snapshot.get("scope"))
    versions = snapshot.get("input_versions")
    if not isinstance(versions, list) or not versions:
        raise GraphValidationError("input_versions are required")
    version_map: dict[str, dict[str, str]] = {}
    report_count = 0
    for item in versions:
        if not isinstance(item, Mapping):
            raise GraphValidationError("input version must be an object")
        version = _nonempty(item.get("document_version_id"), "input_version.document_version_id")
        document_id = _nonempty(item.get("document_id"), "input_version.document_id")
        kind = item.get("kind")
        if kind not in {"REPORT", "SOURCE"} or item.get("rights_state") != "APPROVED":
            raise GraphValidationError("input version kind and APPROVED rights_state are required")
        if version in version_map:
            raise GraphValidationError("duplicate document_version_id")
        if kind == "REPORT":
            report_count += 1
            if document_id != scope["report_id"] or version != scope["report_version_id"]:
                raise GraphValidationError("REPORT input must match scope report/version")
        version_map[version] = {
            "document_id": document_id, "document_version_id": version,
            "kind": kind, "rights_state": "APPROVED",
        }
    if report_count != 1:
        raise GraphValidationError("exactly one scoped REPORT input is required")

    chunks = snapshot.get("chunks")
    if not isinstance(chunks, list):
        raise GraphValidationError("chunks must be a list")
    chunk_map: dict[str, dict[str, Any]] = {}
    for item in chunks:
        if not isinstance(item, Mapping):
            raise GraphValidationError("chunk reference must be an object")
        content_hash = item.get("content_sha256")
        if not isinstance(content_hash, str) or len(content_hash) != 64 or any(c not in "0123456789abcdef" for c in content_hash):
            raise GraphValidationError("chunk content_sha256 must be lowercase SHA-256")
        chunk = {
            "chunk_id": _nonempty(item.get("chunk_id"), "chunk_id"),
            "document_id": _nonempty(item.get("document_id"), "chunk.document_id"),
            "document_version_id": _nonempty(item.get("document_version_id"), "chunk.document_version_id"),
            "content_sha256": content_hash,
            "source_spans": [_source_span(value) for value in item.get("source_spans", [])],
        }
        if not chunk["source_spans"]:
            raise GraphValidationError("chunk source_spans are required")
        source_version = version_map.get(chunk["document_version_id"])
        if source_version is None or source_version["document_id"] != chunk["document_id"]:
            raise GraphValidationError("chunk document/version is outside approved input scope")
        if chunk["chunk_id"] in chunk_map:
            raise GraphValidationError("duplicate chunk_id")
        chunk_map[chunk["chunk_id"]] = chunk

    spans = snapshot.get("spans")
    if not isinstance(spans, list):
        raise GraphValidationError("spans must be a list")
    span_map: dict[str, dict[str, Any]] = {}
    for item in spans:
        if not isinstance(item, Mapping) or item.get("scope") != scope:
            raise GraphValidationError("span has cross-report/version scope")
        chunk = chunk_map.get(item.get("chunk_id"))
        if chunk is None:
            raise GraphValidationError("dangling span chunk_id")
        index = item.get("source_span_index")
        expected = make_span(scope, chunk, index)
        if dict(item) != expected:
            raise GraphValidationError("span differs from parser source span or stable identity")
        if expected["span_id"] in span_map:
            raise GraphValidationError("duplicate span_id")
        span_map[expected["span_id"]] = expected

    nodes = snapshot.get("nodes")
    if not isinstance(nodes, list):
        raise GraphValidationError("nodes must be a list")
    node_map: dict[str, dict[str, Any]] = {}
    for item in nodes:
        if not isinstance(item, Mapping) or item.get("scope") != scope:
            raise GraphValidationError("node has cross-report/version scope")
        if item.get("node_type") not in NODE_TYPES:
            raise GraphValidationError("unknown node_type")
        attributes = item.get("attributes")
        if not isinstance(attributes, Mapping):
            raise GraphValidationError("node.attributes must be an object")
        node_type = item["node_type"]
        if not set(attributes).issubset(ATTRIBUTE_ALLOWLIST[node_type]):
            raise GraphValidationError("node.attributes contains fields outside type allowlist")
        if node_type == "CLAIM" and (
            not isinstance(attributes.get("claim_kind"), str)
            or not attributes["claim_kind"].strip()
            or attributes.get("polarity") not in {"POSITIVE", "NEGATIVE", "NEUTRAL"}
        ):
            raise GraphValidationError("CLAIM requires claim_kind and polarity")
        if node_type == "RESULT" and not any(key in attributes for key in ("dataset", "split", "context")):
            raise GraphValidationError("RESULT requires dataset, split or context")
        for span_id in _unique_ids(item.get("evidence_span_ids"), "node.evidence_span_ids"):
            if span_id not in span_map:
                raise GraphValidationError("dangling node evidence_span_id")
        _validate_prompt(item.get("prompt_sha256"))
        expected = make_node(
            scope, node_type=item["node_type"], label=item.get("label"),
            evidence_span_ids=item["evidence_span_ids"], extractor=item.get("extractor"),
            model_or_rule_version=item.get("model_or_rule_version"),
            confidence=item.get("confidence"), attributes=item.get("attributes"),
            prompt_sha256=item.get("prompt_sha256"),
            created_at=item.get("created_at"),
        )
        if dict(item) != expected:
            raise GraphValidationError("node differs from stable identity or contract")
        if item["node_type"] == "EVIDENCE_SPAN" and len(item["evidence_span_ids"]) != 1:
            raise GraphValidationError("EVIDENCE_SPAN node must point to one source span")
        if expected["node_id"] in node_map:
            raise GraphValidationError("duplicate node_id")
        node_map[expected["node_id"]] = expected

    edges = snapshot.get("edges")
    if not isinstance(edges, list):
        raise GraphValidationError("edges must be a list")
    edge_map: dict[str, dict[str, Any]] = {}
    for item in edges:
        if not isinstance(item, Mapping) or item.get("scope") != scope:
            raise GraphValidationError("edge has cross-report/version scope")
        relation = item.get("relation_type")
        if relation not in RELATION_DOMAINS:
            raise GraphValidationError("unknown relation_type")
        source = node_map.get(item.get("from_node_id"))
        target = node_map.get(item.get("to_node_id"))
        if source is None or target is None:
            raise GraphValidationError("dangling or cross-generation edge endpoint")
        source_types, target_types = RELATION_DOMAINS[relation]
        if source["node_type"] not in source_types or target["node_type"] not in target_types:
            raise GraphValidationError("relation_type has invalid endpoint types")
        for span_id in _unique_ids(item.get("evidence_span_ids"), "edge.evidence_span_ids"):
            if span_id not in span_map:
                raise GraphValidationError("dangling edge evidence_span_id")
        _validate_prompt(item.get("prompt_sha256"))
        if item.get("review_state") not in REVIEW_STATES:
            raise GraphValidationError("unknown edge review_state")
        expected = make_edge(
            scope, relation_type=relation, from_node_id=item["from_node_id"],
            to_node_id=item["to_node_id"], evidence_span_ids=item["evidence_span_ids"],
            extractor=item.get("extractor"), model_or_rule_version=item.get("model_or_rule_version"),
            confidence=item.get("confidence"), review_state=item["review_state"],
            prompt_sha256=item.get("prompt_sha256"),
            reviewer_id=item.get("reviewer_id"), reviewed_at=item.get("reviewed_at"),
        )
        if dict(item) != expected:
            raise GraphValidationError("edge differs from stable identity or contract")
        if expected["edge_id"] in edge_map:
            raise GraphValidationError("duplicate edge_id")
        edge_map[expected["edge_id"]] = expected

    return {
        "schema_version": SCHEMA_VERSION, "scope": scope,
        "input_versions": [version_map[key] for key in sorted(version_map)],
        "chunks": [chunk_map[key] for key in sorted(chunk_map)],
        "spans": [span_map[key] for key in sorted(span_map)],
        "nodes": [node_map[key] for key in sorted(node_map)],
        "edges": [edge_map[key] for key in sorted(edge_map)],
    }
