"""Deterministic, provenance-preserving document chunking.

The parsers emit document elements.  This module turns those elements into
retrieval chunks without losing the offsets needed to resolve an evidence span
back to the parser output.  Version-2 parser elements are preferred, while the
legacy ``text/page/para_index`` shape remains accepted during the migration.

Offsets in this module are zero-based, half-open character offsets.  A chunk's
``source_spans`` is authoritative; the top-level ``locator`` is only a compact
summary for filtering and display.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence


CHUNK_SCHEMA_VERSION = 2
CHUNKER_NAME = "structure-aware-provenance-chunker"
CHUNKER_VERSION = "2.0.0"
NORMALIZATION_MAP_VERSION = 1
_TEXT_ELEMENT_TYPES = {"paragraph", "caption", "reference", "list", "text"}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_object(value: Any) -> str:
    return _sha256_text(_canonical_json(value))


def approx_token_count(text: str) -> int:
    """Return the deterministic tokenizer-independent estimate used by v2.

    It is intentionally only a planning estimate.  Once an embedding model is
    selected, its locked tokenizer can be supplied by a later chunker version;
    changing that policy must also change ``CHUNKER_VERSION``.
    """

    words = len(text.split())
    return max(1, int(words * 1.3))


def _format_table_text(rows: Sequence[Sequence[Any]]) -> str:
    """Render legacy table rows deterministically without dropping columns."""

    lines: list[str] = []
    for raw_row in rows:
        row = ["" if cell is None else str(cell) for cell in raw_row]
        if not any(cell for cell in row):
            continue
        if len(row) == 2:
            lines.append(f"{row[0]}: {row[1]}")
        else:
            lines.append(" - ".join(row))
    return "\n".join(lines)


def _breadcrumb(section_path: Sequence[str]) -> str:
    return " > ".join(section_path) if section_path else ""


def _identity_map(text: str) -> list[list[int]]:
    return [[index, index + 1] for index in range(len(text))]


def _legacy_locator(element: Mapping[str, Any]) -> dict[str, Any]:
    """Create a non-deceptive locator for old parser output.

    Old PDF pages were not explicitly documented as zero- or one-based, so the
    original value is retained as ``legacy_page`` instead of being relabelled as
    a precise v2 ``page_index``.
    """

    paragraph_index = element.get("para_index")
    table_index = element.get("table_index")
    block_id = None
    if paragraph_index is not None:
        block_id = f"legacy-paragraph:{paragraph_index}"
    elif table_index is not None:
        block_id = f"legacy-table:{table_index}"

    return {
        "locator_version": 0,
        "page_index": None,
        "page_label": None,
        "bbox": None,
        "block_id": block_id,
        "legacy_page": element.get("page"),
    }


def _validate_section_path(value: Any, *, element_index: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(
            f"elements[{element_index}] section_path/structure_path must be a list of strings"
        )
    result = list(value)
    if not all(isinstance(item, str) for item in result):
        raise ValueError(
            f"elements[{element_index}] section_path/structure_path must contain only strings"
        )
    return result


def _validate_normalization_map(
    raw_text: str,
    normalized_text: str,
    normalization_map: Any,
    *,
    element_index: int,
    require_explicit: bool,
) -> list[list[int]]:
    if isinstance(normalization_map, Mapping):
        char_map = normalization_map.get("normalized_char_to_raw_span")
        if char_map is None and normalization_map.get("segments") is not None:
            segments = normalization_map["segments"]
            if isinstance(segments, (str, bytes)) or not isinstance(segments, Sequence):
                raise ValueError(
                    f"elements[{element_index}] normalization_map.segments must be a list"
                )
            expanded: list[list[int] | None] = [None] * len(normalized_text)
            for segment_index, segment in enumerate(segments):
                if not isinstance(segment, Mapping):
                    raise ValueError(
                        f"elements[{element_index}] normalization segment {segment_index} "
                        "must be an object"
                    )
                values = (
                    segment.get("normalized_start"),
                    segment.get("normalized_end"),
                    segment.get("raw_start"),
                    segment.get("raw_end"),
                )
                if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
                    raise ValueError(
                        f"elements[{element_index}] normalization segment {segment_index} "
                        "must contain integer normalized/raw boundaries"
                    )
                normalized_start, normalized_end, raw_start, raw_end = values
                if not (0 <= normalized_start < normalized_end <= len(normalized_text)):
                    raise ValueError(
                        f"elements[{element_index}] normalization segment {segment_index} "
                        "has invalid normalized bounds"
                    )
                if not (0 <= raw_start <= raw_end <= len(raw_text)):
                    raise ValueError(
                        f"elements[{element_index}] normalization segment {segment_index} "
                        "has invalid raw bounds"
                    )
                for normalized_index in range(normalized_start, normalized_end):
                    if expanded[normalized_index] is not None:
                        raise ValueError(
                            f"elements[{element_index}] normalization segments overlap at "
                            f"normalized offset {normalized_index}"
                        )
                    expanded[normalized_index] = [raw_start, raw_end]
            if any(span is None for span in expanded):
                raise ValueError(
                    f"elements[{element_index}] normalization segments do not cover every "
                    "normalized character"
                )
            char_map = expanded
    else:
        char_map = normalization_map

    if char_map is None:
        if raw_text == normalized_text:
            return _identity_map(raw_text)
        if require_explicit:
            raise ValueError(
                f"elements[{element_index}] changes raw_text during normalization but has no "
                "normalized_char_to_raw_span mapping"
            )
        # Legacy elements do not declare separate raw/normalized forms.  This
        # branch is defensive for transitional callers.
        raw_text = normalized_text
        return _identity_map(raw_text)

    if isinstance(char_map, (str, bytes)) or not isinstance(char_map, Sequence):
        raise ValueError(
            f"elements[{element_index}] normalized_char_to_raw_span must be a list"
        )
    if len(char_map) != len(normalized_text):
        raise ValueError(
            f"elements[{element_index}] normalization map length {len(char_map)} does not "
            f"match normalized_text length {len(normalized_text)}"
        )

    validated: list[list[int]] = []
    previous_start = 0
    previous_end = 0
    for char_index, span in enumerate(char_map):
        if (
            isinstance(span, (str, bytes))
            or not isinstance(span, Sequence)
            or len(span) != 2
            or isinstance(span[0], bool)
            or isinstance(span[1], bool)
            or not isinstance(span[0], int)
            or not isinstance(span[1], int)
        ):
            raise ValueError(
                f"elements[{element_index}] normalization map entry {char_index} "
                "must be [raw_start, raw_end] integers"
            )
        start, end = span
        if not (0 <= start <= end <= len(raw_text)):
            raise ValueError(
                f"elements[{element_index}] normalization map entry {char_index} "
                f"is outside raw_text: [{start}, {end})"
            )
        if char_index and (start < previous_start or end < previous_end):
            raise ValueError(
                f"elements[{element_index}] normalization map must be monotonic; "
                f"entry {char_index} moves backwards"
            )
        validated.append([start, end])
        previous_start, previous_end = start, end
    return validated


@dataclass(frozen=True)
class _PreparedElement:
    element_key: str
    document_version_id: str | None
    source_generation_key: str | None
    element_type: str
    raw_text: str
    normalized_text: str
    normalized_char_to_raw_span: list[list[int]]
    section_path: list[str]
    locator: dict[str, Any]
    source_ref: Any


@dataclass(frozen=True)
class _Piece:
    element_key: str
    element_type: str
    raw_text: str
    normalized_text: str
    normalized_char_to_raw_span: list[list[int]]
    element_raw_start: int
    element_raw_end: int
    element_normalized_start: int
    element_normalized_end: int
    section_path: list[str]
    locator: dict[str, Any]
    source_ref: Any


def _prepare_element(element: Mapping[str, Any], element_index: int) -> _PreparedElement:
    if not isinstance(element, Mapping):
        raise ValueError(f"elements[{element_index}] must be a mapping")

    raw_type = element.get("type", element.get("element_type"))
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise ValueError(f"elements[{element_index}] has no valid type/element_type")
    element_type = raw_type.strip().lower()

    if element_type == "table" and not any(
        key in element for key in ("normalized_text", "text", "raw_text")
    ):
        rows = element.get("rows")
        if not isinstance(rows, Sequence):
            raise ValueError(f"elements[{element_index}] table has no text or rows")
        normalized_text = _format_table_text(rows)
    else:
        normalized_value = element.get("normalized_text", element.get("text", ""))
        if not isinstance(normalized_value, str):
            raise ValueError(f"elements[{element_index}] normalized_text/text must be a string")
        normalized_text = normalized_value

    raw_value = element.get("raw_text", normalized_text)
    if not isinstance(raw_value, str):
        raise ValueError(f"elements[{element_index}] raw_text must be a string")
    raw_text = raw_value

    schema_version = element.get("schema_version", 1)
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise ValueError(f"elements[{element_index}] schema_version must be an integer")
    char_map = _validate_normalization_map(
        raw_text,
        normalized_text,
        element.get("normalization_map"),
        element_index=element_index,
        require_explicit=schema_version >= 2,
    )

    section_path = _validate_section_path(
        element.get("structure_path", element.get("section_path", [])),
        element_index=element_index,
    )
    locator_value = element.get("locator")
    if locator_value is None:
        locator = _legacy_locator(element)
    elif not isinstance(locator_value, Mapping):
        raise ValueError(f"elements[{element_index}] locator must be an object")
    else:
        locator = deepcopy(dict(locator_value))

    element_key_value = element.get("element_key")
    if element_key_value is None:
        element_key = "legacy-el-" + _sha256_object(
            {
                "type": element_type,
                "locator": locator,
                "raw_text_sha256": _sha256_text(raw_text),
            }
        )
    elif not isinstance(element_key_value, str) or not element_key_value:
        raise ValueError(f"elements[{element_index}] element_key must be a non-empty string")
    else:
        element_key = element_key_value

    document_version_value = element.get("document_version_id")
    if document_version_value is not None and not isinstance(document_version_value, str):
        # Mongo ObjectId-like values are deliberately converted only at the API
        # boundary.  This pure-Python prototype expects its serialized form.
        document_version_value = str(document_version_value)

    source_generation = element.get("generation_key")
    if source_generation is not None and not isinstance(source_generation, str):
        source_generation = str(source_generation)

    if "source_ref" in element:
        source_ref = deepcopy(element["source_ref"])
    elif "para_index" in element:
        source_ref = element["para_index"]
    elif "page" in element:
        source_ref = element["page"]
    elif "table_index" in element:
        source_ref = element["table_index"]
    else:
        source_ref = deepcopy(locator) if locator else element_key

    return _PreparedElement(
        element_key=element_key,
        document_version_id=document_version_value,
        source_generation_key=source_generation,
        element_type=element_type,
        raw_text=raw_text,
        normalized_text=normalized_text,
        normalized_char_to_raw_span=char_map,
        section_path=section_path,
        locator=locator,
        source_ref=source_ref,
    )


def _split_normalized_ranges(text: str, max_tokens: int) -> list[tuple[int, int]]:
    """Split on word boundaries while covering the input exactly once."""

    if not text:
        return []
    if approx_token_count(text) <= max_tokens:
        return [(0, len(text))]

    words = list(re.finditer(r"\S+", text, flags=re.UNICODE))
    if not words:
        return [(0, len(text))]

    ranges: list[tuple[int, int]] = []
    start = 0
    for match in words:
        if approx_token_count(text[start : match.end()]) <= max_tokens:
            continue

        split_at = match.start()
        if split_at <= start:
            # Under the current estimator one non-whitespace run is one token,
            # so this can only be reached if that policy changes without also
            # changing this function.
            raise ValueError(
                "A single token exceeds max_tokens under the configured token estimator"
            )
        ranges.append((start, split_at))
        start = split_at

    if start < len(text):
        ranges.append((start, len(text)))

    if any(approx_token_count(text[start:end]) > max_tokens for start, end in ranges):
        raise AssertionError("Internal error: normalized split exceeds max_tokens")
    return ranges


def _adjust_ranges_for_raw_mapping(
    ranges: list[tuple[int, int]], char_map: Sequence[Sequence[int]]
) -> list[tuple[int, int]]:
    """Avoid a split inside a raw span expanded to multiple normalized chars."""

    if len(ranges) < 2:
        return ranges

    boundaries = [ranges[0][0]]
    proposed = [end for _, end in ranges[:-1]]
    for boundary in proposed:
        while (
            0 < boundary < len(char_map)
            and char_map[boundary - 1][1] > char_map[boundary][0]
        ):
            boundary += 1
        if boundary > boundaries[-1] and boundary < len(char_map):
            boundaries.append(boundary)
    boundaries.append(ranges[-1][1])
    return [
        (start, end)
        for start, end in zip(boundaries, boundaries[1:])
        if start < end
    ]


def _piece_raw_boundary(element: _PreparedElement, normalized_offset: int) -> int:
    if normalized_offset <= 0:
        return 0
    if normalized_offset >= len(element.normalized_text):
        return len(element.raw_text)
    return element.normalized_char_to_raw_span[normalized_offset][0]


def _pieces_for_element(element: _PreparedElement, max_tokens: int) -> list[_Piece]:
    if not element.normalized_text.strip():
        return []

    normalized_ranges = _split_normalized_ranges(element.normalized_text, max_tokens)
    normalized_ranges = _adjust_ranges_for_raw_mapping(
        normalized_ranges, element.normalized_char_to_raw_span
    )

    pieces: list[_Piece] = []
    for normalized_start, normalized_end in normalized_ranges:
        raw_start = _piece_raw_boundary(element, normalized_start)
        raw_end = _piece_raw_boundary(element, normalized_end)
        raw_text = element.raw_text[raw_start:raw_end]
        normalized_text = element.normalized_text[normalized_start:normalized_end]
        relative_map = [
            [start - raw_start, end - raw_start]
            for start, end in element.normalized_char_to_raw_span[
                normalized_start:normalized_end
            ]
        ]
        pieces.append(
            _Piece(
                element_key=element.element_key,
                element_type=element.element_type,
                raw_text=raw_text,
                normalized_text=normalized_text,
                normalized_char_to_raw_span=relative_map,
                element_raw_start=raw_start,
                element_raw_end=raw_end,
                element_normalized_start=normalized_start,
                element_normalized_end=normalized_end,
                section_path=list(element.section_path),
                locator=deepcopy(element.locator),
                source_ref=deepcopy(element.source_ref),
            )
        )
    return pieces


def _combined_normalized_text(pieces: Sequence[_Piece]) -> str:
    return " ".join(piece.normalized_text for piece in pieces)


def _unique_in_order(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        identity = _canonical_json(value)
        if identity not in seen:
            seen.add(identity)
            result.append(deepcopy(value))
    return result


def _deepest_section_path(pieces: Sequence[_Piece]) -> list[str]:
    # ``max`` keeps the first path on equal lengths, giving deterministic ties.
    return list(max((piece.section_path for piece in pieces), key=len, default=[]))


def _locator_summary(
    source_spans: Sequence[Mapping[str, Any]],
    section_path: Sequence[str],
    raw_text_length: int,
) -> dict[str, Any]:
    locators = [span["locator"] for span in source_spans]
    page_indices = [locator.get("page_index") for locator in locators]
    page_index = (
        page_indices[0]
        if page_indices and page_indices[0] is not None and len(set(page_indices)) == 1
        else None
    )
    page_labels = [locator.get("page_label") for locator in locators]
    page_label = (
        page_labels[0]
        if page_labels and page_labels[0] is not None and len(set(page_labels)) == 1
        else None
    )
    block_ids = [locator.get("block_id") for locator in locators]
    block_id = (
        block_ids[0]
        if len(block_ids) == 1 and block_ids[0] is not None
        else None
    )
    bbox = deepcopy(locators[0].get("bbox")) if len(locators) == 1 else None
    element_keys = _unique_in_order(span["element_key"] for span in source_spans)

    return {
        "locator_version": 2,
        "page_index": page_index,
        "page_label": page_label,
        "bbox": bbox,
        "section_path": list(section_path),
        "block_id": block_id,
        "raw_char_start": 0,
        "raw_char_end": raw_text_length,
        "source_element_ids": element_keys,
        "source_spans_authoritative": True,
    }


def _build_chunk(
    pieces: Sequence[_Piece],
    *,
    chunk_type: str,
    document_version_id: str,
    generation_key: str,
    chunker_spec: Mapping[str, str],
) -> dict[str, Any]:
    if not pieces:
        raise ValueError("Cannot build a chunk without source pieces")

    raw_parts: list[str] = []
    normalized_parts: list[str] = []
    chunk_char_map: list[list[int]] = []
    source_spans: list[dict[str, Any]] = []
    raw_cursor = 0
    normalized_cursor = 0

    for piece_index, piece in enumerate(pieces):
        if piece_index:
            raw_parts.append(" ")
            normalized_parts.append(" ")
            chunk_char_map.append([raw_cursor, raw_cursor + 1])
            raw_cursor += 1
            normalized_cursor += 1

        chunk_raw_start = raw_cursor
        chunk_normalized_start = normalized_cursor
        raw_parts.append(piece.raw_text)
        normalized_parts.append(piece.normalized_text)
        chunk_char_map.extend(
            [start + raw_cursor, end + raw_cursor]
            for start, end in piece.normalized_char_to_raw_span
        )
        raw_cursor += len(piece.raw_text)
        normalized_cursor += len(piece.normalized_text)

        source_spans.append(
            {
                "element_key": piece.element_key,
                "element_type": piece.element_type,
                "element_raw_char_start": piece.element_raw_start,
                "element_raw_char_end": piece.element_raw_end,
                "element_normalized_char_start": piece.element_normalized_start,
                "element_normalized_char_end": piece.element_normalized_end,
                "chunk_raw_char_start": chunk_raw_start,
                "chunk_raw_char_end": raw_cursor,
                "chunk_normalized_char_start": chunk_normalized_start,
                "chunk_normalized_char_end": normalized_cursor,
                "locator": deepcopy(piece.locator),
            }
        )

    raw_text = "".join(raw_parts)
    normalized_text = "".join(normalized_parts)
    content_sha256 = _sha256_text(normalized_text)
    raw_text_sha256 = _sha256_text(raw_text)
    section_path = _deepest_section_path(pieces)
    section_paths = _unique_in_order(piece.section_path for piece in pieces)
    element_ids = _unique_in_order(piece.element_key for piece in pieces)
    source_refs = [deepcopy(piece.source_ref) for piece in pieces]

    chunk_identity_spans = [
        {
            "element_key": span["element_key"],
            "element_raw_char_start": span["element_raw_char_start"],
            "element_raw_char_end": span["element_raw_char_end"],
            "element_normalized_char_start": span["element_normalized_char_start"],
            "element_normalized_char_end": span["element_normalized_char_end"],
        }
        for span in source_spans
    ]
    chunk_key = "chk-" + _sha256_object(
        {
            "document_version_id": document_version_id,
            "generation_key": generation_key,
            "chunker_spec": dict(chunker_spec),
            "ordered_source_spans": chunk_identity_spans,
            "content_sha256": content_sha256,
        }
    )
    locator = _locator_summary(source_spans, section_path, len(raw_text))

    return {
        "schema_version": CHUNK_SCHEMA_VERSION,
        "document_version_id": document_version_id,
        "chunk_key": chunk_key,
        "chunk_id": chunk_key,  # compatibility alias; display ordering is separate
        "generation_key": generation_key,
        "type": chunk_type,
        "element_ids": element_ids,
        "source_element_ids": list(element_ids),
        "raw_text": raw_text,
        "normalized_text": normalized_text,
        "text": normalized_text,  # legacy retrieval/demo alias
        "raw_text_sha256": raw_text_sha256,
        "normalized_text_sha256": content_sha256,
        "content_sha256": content_sha256,
        "language": None,
        "structure_path": section_path,
        "section_path": list(section_path),  # legacy alias
        "section_paths": section_paths,
        "locator": locator,
        "source_spans": source_spans,
        "source_refs": source_refs,
        "normalization_map": {
            "normalization_map_version": NORMALIZATION_MAP_VERSION,
            "algorithm": "compose-element-normalization-maps",
            "normalized_char_to_raw_span": chunk_char_map,
        },
        "chunker_spec": dict(chunker_spec),
        "token_count": approx_token_count(normalized_text),
        "text_with_context": (
            f"[{_breadcrumb(section_path)}] " if section_path else ""
        )
        + normalized_text,
    }


def chunk_elements(
    elements: Iterable[Mapping[str, Any]],
    max_tokens: int = 400,
    min_tokens: int = 40,
) -> list[dict[str, Any]]:
    """Create deterministic chunks and exact element-to-chunk source spans.

    Text elements may be combined only when their normalized text remains at or
    below ``max_tokens``.  Tables are never combined with text and an oversized
    element (including one oversized table row) is split before grouping.

    The returned ``order`` is for display only.  It is deliberately excluded
    from ``chunk_key`` so a harmless order-field edit cannot invalidate stored
    evidence.  Any change to content, source span, document version, or chunker
    configuration does produce a new key.
    """

    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    if isinstance(min_tokens, bool) or not isinstance(min_tokens, int) or min_tokens < 0:
        raise ValueError("min_tokens must be a non-negative integer")
    if isinstance(elements, (str, bytes, Mapping)):
        raise ValueError("elements must be an iterable of element mappings")

    prepared = [_prepare_element(element, index) for index, element in enumerate(elements)]
    explicit_document_versions = {
        element.document_version_id
        for element in prepared
        if element.document_version_id is not None
    }
    if len(explicit_document_versions) > 1:
        versions = ", ".join(sorted(explicit_document_versions))
        raise ValueError(
            "chunk_elements received mixed document_version_id values; chunk one immutable "
            f"document version at a time (received: {versions})"
        )
    document_version_id = (
        next(iter(explicit_document_versions))
        if explicit_document_versions
        else "legacy:sha256:" + _sha256_object(
            {
                "schema_version": 1,
                "ordered_element_keys": [element.element_key for element in prepared],
            }
        )
    )

    element_keys = [element.element_key for element in prepared]
    if len(element_keys) != len(set(element_keys)):
        raise ValueError("element_key values must be unique within one document version")

    config = {
        "max_tokens": max_tokens,
        "min_tokens": min_tokens,
        "token_estimator": "whitespace-word-count-times-1.3-floor-min-1",
        "text_joiner": "single-space",
        "table_policy": "separate-and-split",
    }
    config_sha256 = _sha256_object(config)
    chunker_spec = {
        "name": CHUNKER_NAME,
        "version": CHUNKER_VERSION,
        "config_sha256": config_sha256,
    }
    source_generation_keys = sorted(
        {
            element.source_generation_key
            for element in prepared
            if element.source_generation_key is not None
        }
    )
    generation_key = "cgen-" + _sha256_object(
        {
            "document_version_id": document_version_id,
            "source_generation_keys": source_generation_keys,
            "chunker_spec": chunker_spec,
        }
    )

    # Each tuple is (chunk type, ordered source pieces).  IDs are assigned only
    # after all safe grouping decisions have been made.
    raw_groups: list[tuple[str, list[_Piece]]] = []
    text_buffer: list[_Piece] = []
    buffer_section: tuple[str, ...] | None = None

    def flush_text_buffer() -> None:
        nonlocal text_buffer, buffer_section
        if text_buffer:
            raw_groups.append(("text", text_buffer))
        text_buffer = []
        buffer_section = None

    for element in prepared:
        if element.element_type == "heading":
            continue
        pieces = _pieces_for_element(element, max_tokens)
        if not pieces:
            continue

        if element.element_type == "table":
            flush_text_buffer()
            # A table remains isolated from prose.  Long tables/rows become
            # multiple independently traceable table chunks.
            raw_groups.extend(("table", [piece]) for piece in pieces)
            continue

        # Unknown textual element kinds are treated as prose rather than being
        # silently discarded; their original type remains in source_spans.
        element_section = tuple(element.section_path)
        if buffer_section is not None and element_section != buffer_section:
            flush_text_buffer()
        buffer_section = element_section

        for piece in pieces:
            trial = text_buffer + [piece]
            if text_buffer and approx_token_count(_combined_normalized_text(trial)) > max_tokens:
                flush_text_buffer()
                buffer_section = element_section
            text_buffer.append(piece)
    flush_text_buffer()

    # Preserve the legacy small-chunk merge policy, but reconstruct provenance
    # from source pieces instead of mutating text and losing offsets.
    merged_groups: list[tuple[str, list[_Piece]]] = []
    for chunk_type, pieces in raw_groups:
        current_tokens = approx_token_count(_combined_normalized_text(pieces))
        if (
            merged_groups
            and chunk_type == "text"
            and merged_groups[-1][0] == "text"
            and current_tokens < min_tokens
            and merged_groups[-1][1][0].section_path[:1] == pieces[0].section_path[:1]
        ):
            previous_type, previous_pieces = merged_groups[-1]
            trial_pieces = previous_pieces + pieces
            if approx_token_count(_combined_normalized_text(trial_pieces)) <= max_tokens:
                merged_groups[-1] = (previous_type, trial_pieces)
                continue
        merged_groups.append((chunk_type, list(pieces)))

    chunks: list[dict[str, Any]] = []
    for order, (chunk_type, pieces) in enumerate(merged_groups):
        chunk = _build_chunk(
            pieces,
            chunk_type=chunk_type,
            document_version_id=document_version_id,
            generation_key=generation_key,
            chunker_spec=chunker_spec,
        )
        if chunk["token_count"] > max_tokens:
            raise AssertionError(
                f"Internal error: chunk {chunk['chunk_key']} exceeds max_tokens"
            )
        chunk["order"] = order
        chunks.append(chunk)
    return chunks
