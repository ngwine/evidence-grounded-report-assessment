"""Conservative citation/reference candidates from provenance-v2 chunks.

This adapter recognises a deliberately small grammar.  A candidate link means
only that a marker and a bibliography entry have matching *printed keys*;
neither the cited work nor the academic use of the citation is verified.
Offsets are zero-based, half-open Unicode code-point offsets into the exact
chunk and parser-element strings, not byte offsets or inferred PDF coordinates.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
EXTRACTOR_VERSION = "citation-marker-candidates-v1"
_REFERENCE_HEADINGS = ("references", "bibliography", "works cited", "tai lieu tham khao")
_NUMERIC_CANDIDATE = re.compile(r"\[(?P<body>\d[^\[\]\n]{0,50})\]", re.UNICODE)
_NUMERIC_SYNTAX = re.compile(r"\d+(?:\s*(?:[,;]|[-–])\s*\d+)*\Z", re.UNICODE)
_NUMERIC_ENTRY = re.compile(r"^\s*(?:\[(?P<bracket>\d+)\]|(?P<period>\d+)\.)\s+", re.UNICODE)
_AUTHOR_TOKEN = r"[^\W\d_][\w'’\-]*"
_YEAR = r"(?:19|20)\d{2}[a-z]?"
_PAREN_AUTHOR_YEAR = re.compile(
    rf"\((?P<author>{_AUTHOR_TOKEN}(?:\s+(?:et\s+al\.?|&\s+{_AUTHOR_TOKEN}|and\s+{_AUTHOR_TOKEN}))?),\s*(?P<year>{_YEAR})\)",
    re.IGNORECASE | re.UNICODE,
)
_NARRATIVE_AUTHOR_YEAR = re.compile(
    rf"(?<![\w])(?P<author>{_AUTHOR_TOKEN}(?:\s+et\s+al\.?)?)\s+\((?P<year>{_YEAR})\)",
    re.IGNORECASE | re.UNICODE,
)
_AUTHOR_YEAR_ENTRY = re.compile(
    rf"^\s*(?P<author>{_AUTHOR_TOKEN})\b[^\n]{{0,100}}?\((?P<year>{_YEAR})\)",
    re.IGNORECASE | re.UNICODE,
)


def _stable_id(prefix: str, value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reference_section(path: Any) -> bool:
    if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
        return False
    for heading in path:
        folded = unicodedata.normalize("NFD", heading.casefold())
        folded = "".join(char for char in folded if unicodedata.category(char) != "Mn")
        folded = re.sub(r"[^\w]+", " ", folded).strip()
        if any(folded == name or folded.endswith(" " + name) for name in _REFERENCE_HEADINGS):
            return True
    return False


def _bounds(value: Mapping[str, Any], prefix: str, limit: int) -> tuple[int, int]:
    start, end = value.get(prefix + "_start"), value.get(prefix + "_end")
    if (
        isinstance(start, bool) or isinstance(end, bool)
        or not isinstance(start, int) or not isinstance(end, int)
        or not 0 <= start < end <= limit
    ):
        raise ValueError(f"Invalid {prefix} half-open source span")
    return start, end


def _validated_chunks(chunks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(chunks, (str, bytes, Mapping)):
        raise ValueError("chunks must be iterable provenance-v2 chunk mappings")
    result: list[dict[str, Any]] = []
    keys: set[str] = set()
    versions: set[str] = set()
    for chunk in chunks:
        if not isinstance(chunk, Mapping) or chunk.get("schema_version") != 2:
            raise ValueError("citation extraction requires provenance-v2 chunks")
        key = chunk.get("chunk_key")
        version = chunk.get("document_version_id")
        raw, normalized = chunk.get("raw_text"), chunk.get("normalized_text")
        spans = chunk.get("source_spans")
        normalization_map = chunk.get("normalization_map")
        char_map = (
            normalization_map.get("normalized_char_to_raw_span")
            if isinstance(normalization_map, Mapping) else None
        )
        if (
            not isinstance(key, str) or not key or key in keys
            or not isinstance(version, str) or not version
            or not isinstance(raw, str) or not isinstance(normalized, str)
            or not isinstance(spans, list) or not spans
            or not isinstance(char_map, list) or len(char_map) != len(normalized)
        ):
            raise ValueError("Chunk lacks unique key, version, text, source spans or normalization map")
        keys.add(key)
        versions.add(version)
        previous_map_start = previous_map_end = 0
        for offset, pair in enumerate(char_map):
            if (
                not isinstance(pair, (list, tuple)) or len(pair) != 2
                or any(isinstance(n, bool) or not isinstance(n, int) for n in pair)
                or not 0 <= pair[0] <= pair[1] <= len(raw)
                or (offset > 0 and (pair[0] < previous_map_start or pair[1] < previous_map_end))
            ):
                raise ValueError("Chunk normalized-to-raw map is invalid or nonmonotonic")
            previous_map_start, previous_map_end = pair
        previous_normalized_end = -1
        for span in spans:
            if (
                not isinstance(span, Mapping)
                or not isinstance(span.get("element_key"), str)
                or not isinstance(span.get("element_type"), str)
            ):
                raise ValueError("Chunk source span lacks an element key")
            ns, ne = _bounds(span, "chunk_normalized_char", len(normalized))
            rs, re_ = _bounds(span, "chunk_raw_char", len(raw))
            ens, ene = _bounds(span, "element_normalized_char", 10**12)
            ers, ere = _bounds(span, "element_raw_char", 10**12)
            if (
                ns < previous_normalized_end or ne - ns != ene - ens
                or re_ - rs != ere - ers
                or any(not rs <= char_map[index][0] <= char_map[index][1] <= re_ for index in range(ns, ne))
                or not isinstance(span.get("locator"), Mapping)
            ):
                raise ValueError("Chunk source span does not agree with text/map/locator")
            previous_normalized_end = ne
        result.append(dict(chunk))
    if len(versions) > 1:
        raise ValueError("Citation extraction accepts one immutable document version at a time")
    return sorted(result, key=lambda item: item["chunk_key"])


def _provenance(
    chunk: Mapping[str, Any], source: Mapping[str, Any], start: int, end: int
) -> dict[str, Any]:
    ns, ne = _bounds(source, "chunk_normalized_char", len(chunk["normalized_text"]))
    if not ns <= start < end <= ne:
        raise ValueError("Candidate crosses parser element boundaries")
    char_map = chunk["normalization_map"]["normalized_char_to_raw_span"]
    raw_start, raw_end = char_map[start][0], char_map[end - 1][1]
    span_raw_start = source["chunk_raw_char_start"]
    span_norm_start = source["chunk_normalized_char_start"]
    return {
        "document_version_id": chunk["document_version_id"],
        "chunk_key": chunk["chunk_key"],
        "element_key": source["element_key"],
        "chunk_normalized_char_start": start,
        "chunk_normalized_char_end": end,
        "chunk_raw_char_start": raw_start,
        "chunk_raw_char_end": raw_end,
        "element_normalized_char_start": source["element_normalized_char_start"] + start - span_norm_start,
        "element_normalized_char_end": source["element_normalized_char_start"] + end - span_norm_start,
        "element_raw_char_start": source["element_raw_char_start"] + raw_start - span_raw_start,
        "element_raw_char_end": source["element_raw_char_start"] + raw_end - span_raw_start,
        "locator": deepcopy(dict(source["locator"])),
    }


def _candidate(
    chunk: Mapping[str, Any], source: Mapping[str, Any], start: int, end: int,
    *, prefix: str, kind: str, keys: list[str], parse_confidence: float,
) -> dict[str, Any]:
    span = _provenance(chunk, source, start, end)
    raw_start, raw_end = span["chunk_raw_char_start"], span["chunk_raw_char_end"]
    source_start, source_end = source["chunk_normalized_char_start"], source["chunk_normalized_char_end"]
    context_start = max(source_start, start - 80)
    context_end = min(source_end, end + 80)
    identity = {
        "extractor_version": EXTRACTOR_VERSION,
        "chunk_key": chunk["chunk_key"],
        "element_key": source["element_key"],
        "kind": kind,
        "start": start,
        "end": end,
        "normalized_text": chunk["normalized_text"][start:end],
    }
    return {
        "id": _stable_id(prefix, identity),
        "kind": kind,
        "keys": keys,
        "raw_text": chunk["raw_text"][raw_start:raw_end],
        "normalized_text": chunk["normalized_text"][start:end],
        "context_normalized_text": chunk["normalized_text"][context_start:context_end],
        "span": span,
        "parse_confidence": parse_confidence,
        "confidence_calibrated": False,
    }


def _numeric_keys(body: str) -> list[str] | None:
    if not _NUMERIC_SYNTAX.fullmatch(body):
        return None
    keys: list[str] = []
    tokens = re.split(r"\s*[,;]\s*", body)
    for token in tokens:
        pair = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", token)
        if pair:
            first, last = int(pair.group(1)), int(pair.group(2))
            if last < first or last - first > 20:
                return None
            keys.extend(f"numeric:{number}" for number in range(first, last + 1))
        else:
            keys.append(f"numeric:{int(token)}")
    return list(dict.fromkeys(keys))


def _author_year_key(author: str, year: str) -> str:
    first_name = author.strip().split()[0]
    return "author-year:" + unicodedata.normalize("NFKC", first_name).casefold() + ":" + year.casefold()


def _entry_keys(text: str) -> list[str]:
    keys: list[str] = []
    numeric = _NUMERIC_ENTRY.match(text)
    if numeric:
        keys.append(f"numeric:{int(numeric.group('bracket') or numeric.group('period'))}")
        text = text[numeric.end():]
    author_year = _AUTHOR_YEAR_ENTRY.match(text)
    if author_year:
        keys.append(_author_year_key(author_year.group("author"), author_year.group("year")))
    return keys


def extract_citation_candidates(chunks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return traceable candidates, never a citation-validity/plagiarism verdict.

    Only paragraphs under an explicit References/Bibliography heading (or v2
    ``reference`` elements) can become bibliography entries.  A unique printed
    key creates a ``CANDIDATE_LINK``, not a verified reference.  Missing,
    duplicate and unsupported keys stay unresolved for human review.
    """

    validated = _validated_chunks(chunks)
    entries: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []
    for chunk in validated:
        for source in chunk["source_spans"]:
            if source["element_type"] not in {"paragraph", "text", "list", "reference"}:
                continue
            start, end = source["chunk_normalized_char_start"], source["chunk_normalized_char_end"]
            piece = chunk["normalized_text"][start:end]
            section_path = source["locator"].get("section_path", chunk.get("structure_path"))
            in_references = source["element_type"] == "reference" or _reference_section(section_path)
            if in_references:
                stripped_start = len(piece) - len(piece.lstrip())
                stripped_end = len(piece.rstrip())
                if stripped_start >= stripped_end:
                    continue
                keys = _entry_keys(piece[stripped_start:stripped_end])
                item = _candidate(
                    chunk, source, start + stripped_start, start + stripped_end,
                    prefix="ref-", kind="BIBLIOGRAPHY_ENTRY_CANDIDATE",
                    keys=keys,
                    parse_confidence=1.0 if keys else 0.0,
                )
                item["parse_status"] = "PARSED" if item["keys"] else "UNRESOLVED_UNSUPPORTED_FORMAT"
                item["verification_status"] = "UNKNOWN"
                entries.append(item)
                continue

            matches: list[tuple[int, int, str, list[str], float]] = []
            for match in _NUMERIC_CANDIDATE.finditer(piece):
                keys = _numeric_keys(match.group("body"))
                matches.append((match.start(), match.end(), "NUMERIC", keys or [], 1.0 if keys else 0.0))
            for regex, kind in ((_PAREN_AUTHOR_YEAR, "AUTHOR_YEAR"), (_NARRATIVE_AUTHOR_YEAR, "AUTHOR_YEAR")):
                for match in regex.finditer(piece):
                    matches.append((
                        match.start(), match.end(), kind,
                        [_author_year_key(match.group("author"), match.group("year"))], 0.7,
                    ))
            consumed_end = -1
            for local_start, local_end, kind, keys, confidence in sorted(matches, key=lambda row: (row[0], -row[1])):
                if local_start < consumed_end:
                    continue
                consumed_end = local_end
                item = _candidate(
                    chunk, source, start + local_start, start + local_end,
                    prefix="citm-", kind=kind, keys=keys, parse_confidence=confidence,
                )
                markers.append(item)

    entries.sort(key=lambda item: item["id"])
    markers.sort(key=lambda item: item["id"])
    entry_index: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        for key in entry["keys"]:
            entry_index[key].append(entry["id"])
    for marker in markers:
        unique: list[str] = []
        ambiguous: list[str] = []
        missing: list[str] = []
        for key in marker["keys"]:
            candidates = entry_index.get(key, [])
            if len(candidates) == 1:
                unique.append(candidates[0])
            elif len(candidates) > 1:
                ambiguous.extend(candidates)
            else:
                missing.append(key)
        marker["candidate_entry_ids"] = sorted(set(unique))
        marker["ambiguous_entry_ids"] = sorted(set(ambiguous))
        marker["unresolved_keys"] = missing
        if not marker["keys"]:
            marker["link_status"] = "UNRESOLVED_UNSUPPORTED_FORMAT"
        elif ambiguous:
            marker["link_status"] = "UNRESOLVED_AMBIGUOUS"
        elif missing:
            marker["link_status"] = "UNRESOLVED_NOT_FOUND" if entries else "UNRESOLVED_NO_BIBLIOGRAPHY"
        else:
            marker["link_status"] = "CANDIDATE_LINK"
        marker["link_confidence"] = 0.5 if marker["link_status"] == "CANDIDATE_LINK" else 0.0
        marker["verification_status"] = "UNKNOWN"

    return {
        "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "document_version_id": validated[0]["document_version_id"] if validated else None,
        "markers": markers,
        "bibliography_entries": entries,
        "policy": "candidate_keys_only; citation_validity_and_plagiarism_unknown",
    }
