"""Deterministic text normalization with reversible provenance metadata.

The parsers keep the text returned by the source library in ``raw_text`` and
use this module to derive search-friendly text.  Every character in the
normalized string carries a half-open interval into ``raw_text`` so a UI can
highlight the source without guessing how NFKC or whitespace normalization
changed the string.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\u2060\ufeff")


@dataclass(frozen=True)
class NormalizedText:
    """A normalized string and its normalized-to-raw character map."""

    text: str
    normalization_map: dict[str, Any]


def sha256_text(text: str) -> str:
    """Return the lowercase SHA-256 hex digest of UTF-8 text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(file_path: str | Path) -> str:
    """Hash a file in bounded blocks so large reports do not fill memory."""

    digest = hashlib.sha256()
    with Path(file_path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_document_version_id(
    file_path: str | Path,
    document_version_id: str | None = None,
) -> str:
    """Use the caller's immutable version id, or derive one from file bytes."""

    if document_version_id is not None:
        value = str(document_version_id).strip()
        if not value:
            raise ValueError("document_version_id must not be empty")
        return value
    return f"sha256:{sha256_file(file_path)}"


def canonical_sha256(value: Any) -> str:
    """Hash a JSON-compatible value using a platform-independent encoding."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_element_key(
    *,
    document_version_id: str,
    element_type: str,
    raw_text_sha256: str,
    locator: dict[str, Any],
    level: int | None = None,
) -> str:
    """Build a stable, opaque element id from canonical source coordinates.

    ``order`` is intentionally absent.  It is presentation metadata and must
    not itself become an element identity.  Source coordinates remain in the
    payload to disambiguate duplicate text in the same document.
    """

    payload = {
        "schema_version": 2,
        "document_version_id": document_version_id,
        "type": element_type,
        "level": level,
        "raw_text_sha256": raw_text_sha256,
        "locator": locator,
    }
    return f"el_{canonical_sha256(payload)}"


def build_parser_spec(
    *,
    name: str,
    version: str,
    config: dict[str, Any],
) -> dict[str, str]:
    """Return the versioned parser identity persisted with every element."""

    return {
        "name": name,
        "version": version,
        "config_sha256": canonical_sha256(config),
    }


def build_generation_key(
    *,
    document_version_id: str,
    parser_spec: dict[str, str],
) -> str:
    """Identify one deterministic parse generation without database ids."""

    return "parse_" + canonical_sha256(
        {
            "schema_version": 2,
            "document_version_id": document_version_id,
            "parser_spec": parser_spec,
        }
    )


def stable_block_id(
    *,
    document_version_id: str,
    source_kind: str,
    source_coordinate: dict[str, Any],
    raw_text_sha256: str,
) -> str:
    """Build a source block key independent from element display order."""

    return "blk_" + canonical_sha256(
        {
            "document_version_id": document_version_id,
            "source_kind": source_kind,
            "source_coordinate": source_coordinate,
            "raw_text_sha256": raw_text_sha256,
        }
    )


def _union_spans(spans: Iterable[tuple[int, int]], fallback: int) -> tuple[int, int]:
    spans = tuple(spans)
    if not spans:
        return fallback, fallback
    return min(start for start, _ in spans), max(end for _, end in spans)


def _is_hangul_jamo(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x1100 <= codepoint <= 0x11FF
        or 0xA960 <= codepoint <= 0xA97F
        or 0xD7B0 <= codepoint <= 0xD7FF
    )


def _normalization_units(raw_text: str) -> list[tuple[str, int, int]]:
    """Group a starter with combining marks before applying NFKC.

    Compatibility characters (for example ``ﬃ``) stay as a one-code-point
    unit and may expand.  Hangul Jamo are grouped because NFKC composes them
    across code-point boundaries.
    """

    units: list[tuple[str, int, int]] = []
    start = 0
    current = ""
    for index, char in enumerate(raw_text):
        extends_current = bool(current) and (
            unicodedata.combining(char) != 0
            or (_is_hangul_jamo(current[-1]) and _is_hangul_jamo(char))
        )
        if current and not extends_current:
            units.append((current, start, index))
            start = index
            current = char
        else:
            if not current:
                start = index
            current += char
    if current:
        units.append((current, start, len(raw_text)))
    return units


def _nfkc_chars_with_spans(raw_text: str) -> list[tuple[str, int, int]]:
    provisional: list[tuple[str, int, int]] = []
    for unit, raw_start, raw_end in _normalization_units(raw_text):
        provisional.extend(
            (char, raw_start, raw_end)
            for char in unicodedata.normalize("NFKC", unit)
        )

    # Unit-wise NFKC is equivalent for normal prose after combining sequences
    # and Hangul Jamo have been grouped.  An unknown cross-unit interaction
    # must fail closed: mapping every output character to the whole input would
    # be in-bounds but would not satisfy the exact-span contract.
    target = unicodedata.normalize("NFKC", raw_text)
    if "".join(char for char, _, _ in provisional) == target:
        return provisional
    raise ValueError(
        "Cannot build an exact NFKC raw-span mapping for this Unicode sequence"
    )


def _dehyphenate_line_breaks(
    chars: list[tuple[str, int, int]],
) -> list[tuple[str, int, int]]:
    """Remove a soft line-wrap hyphen before a lowercase continuation."""

    result: list[tuple[str, int, int]] = []
    index = 0
    while index < len(chars):
        char, _, _ = chars[index]
        if (
            char == "-"
            and result
            and result[-1][0].isalpha()
        ):
            cursor = index + 1
            while cursor < len(chars) and chars[cursor][0] in " \t\r":
                cursor += 1
            if cursor < len(chars) and chars[cursor][0] == "\n":
                cursor += 1
                while cursor < len(chars) and chars[cursor][0] in " \t":
                    cursor += 1
                if cursor < len(chars) and chars[cursor][0].islower():
                    index = cursor
                    continue
        result.append(chars[index])
        index += 1
    return result


def _collapse_whitespace(
    chars: list[tuple[str, int, int]],
    *,
    preserve_newlines: bool,
) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    index = 0
    while index < len(chars):
        char, raw_start, raw_end = chars[index]
        if not char.isspace():
            result.append((char, raw_start, raw_end))
            index += 1
            continue

        run: list[tuple[int, int]] = []
        has_newline = False
        while index < len(chars) and chars[index][0].isspace():
            whitespace, start, end = chars[index]
            has_newline = has_newline or whitespace in "\r\n"
            run.append((start, end))
            index += 1

        collapsed = "\n" if preserve_newlines and has_newline else " "
        start, end = _union_spans(run, raw_start)
        result.append((collapsed, start, end))

    # Trim exactly as ``str.strip`` would for the normalized whitespace forms.
    while result and result[0][0] in {" ", "\n"}:
        result.pop(0)
    while result and result[-1][0] in {" ", "\n"}:
        result.pop()
    return result


def normalize_with_mapping(
    raw_text: str,
    *,
    preserve_newlines: bool = False,
    dehyphenate_line_breaks: bool = False,
) -> NormalizedText:
    """Normalize text and retain a source interval for every output character.

    Transformations are deterministic: Unicode NFKC, zero-width removal,
    optional PDF line-wrap dehyphenation, and whitespace collapse.  Offsets use
    Python/Unicode code points and half-open intervals, not UTF-8 byte offsets.
    """

    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be str")

    chars = [
        item
        for item in _nfkc_chars_with_spans(raw_text)
        if item[0] not in _ZERO_WIDTH
    ]
    if dehyphenate_line_breaks:
        chars = _dehyphenate_line_breaks(chars)
    chars = _collapse_whitespace(chars, preserve_newlines=preserve_newlines)

    normalized_text = "".join(char for char, _, _ in chars)
    segments = [
        {
            "normalized_start": index,
            "normalized_end": index + 1,
            "raw_start": raw_start,
            "raw_end": raw_end,
        }
        for index, (_, raw_start, raw_end) in enumerate(chars)
    ]
    mapping = {
        "version": 1,
        "algorithm": "unicode-nfkc-zero-width-whitespace",
        "config_sha256": canonical_sha256(
            {
                "preserve_newlines": preserve_newlines,
                "dehyphenate_line_breaks": dehyphenate_line_breaks,
            }
        ),
        "coordinate_system": "unicode_code_point",
        "offset_convention": "half_open",
        "raw_length": len(raw_text),
        "normalized_length": len(normalized_text),
        "segments": segments,
    }
    return NormalizedText(normalized_text, mapping)
