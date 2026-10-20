"""Document ingestion adapter shared by both offline MVP pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable

from research.offline_retrieval.common import sha256_file, sha256_text
from services.backend.src.kltn_ai.integrations.indexing.chunking import (
    chunk_elements,
)
from services.backend.src.kltn_ai.integrations.parsing.docx_parser import (
    extract_docx_elements,
)
from services.backend.src.kltn_ai.integrations.parsing.pdf_parser import (
    extract_pdf_elements,
)
from services.backend.src.kltn_ai.integrations.parsing.text_normalization import (
    build_generation_key,
    build_parser_spec,
    normalize_with_mapping,
    stable_block_id,
    stable_element_key,
)


_TEXT_SUFFIXES = {".md", ".txt"}
_SUPPORTED_SUFFIXES = {".docx", ".pdf", *_TEXT_SUFFIXES}
# Accept both a final paragraph without a newline and the common POSIX text
# file form with one trailing newline.  Horizontal whitespace is kept out of
# the blank-line delimiter so it cannot accidentally consume another block.
_PARAGRAPH_RE = re.compile(
    r"\S(?:.*?\S)?(?=(?:\r?\n[ \t]*){2,}|\s*\Z)",
    re.DOTALL,
)


@dataclass(frozen=True)
class ParsedDocument:
    """One immutable input document and its provenance-preserving chunks."""

    document: dict[str, Any]
    elements: tuple[dict[str, Any], ...]
    chunks: tuple[dict[str, Any], ...]


def _portable_name(path: Path) -> str:
    """Keep artifact paths portable and avoid leaking a developer home path."""

    return path.name


def _text_elements(path: Path, *, document_version_id: str) -> list[dict[str, Any]]:
    try:
        raw_document = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Text input must be UTF-8: {path.name}") from exc
    parser_spec = build_parser_spec(
        name="utf8-paragraph-parser",
        version="1.0.0",
        config={
            "schema_version": 2,
            "paragraph_separator": "blank-line",
            "normalization": "unicode-nfkc-zero-width-whitespace",
        },
    )
    generation_key = build_generation_key(
        document_version_id=document_version_id,
        parser_spec=parser_spec,
    )
    elements: list[dict[str, Any]] = []
    for order, match in enumerate(_PARAGRAPH_RE.finditer(raw_document)):
        raw_text = match.group(0)
        normalized = normalize_with_mapping(raw_text, preserve_newlines=True)
        if not normalized.text.strip():
            continue
        source_coordinate = {
            "document_raw_char_start": match.start(),
            "document_raw_char_end": match.end(),
        }
        raw_digest = sha256_text(raw_text)
        block_id = stable_block_id(
            document_version_id=document_version_id,
            source_kind="utf8-text",
            source_coordinate=source_coordinate,
            raw_text_sha256=raw_digest,
        )
        locator = {
            "locator_version": 1,
            "source_kind": "utf8-text",
            "coordinate_system": {"text": "unicode_code_point", "bbox": None},
            "offset_convention": "half_open",
            "page_index": None,
            "page_number": None,
            "page_label": None,
            "bbox": None,
            "section_path": [],
            "block_id": block_id,
            "block_index": order,
            "paragraph_index": order,
            "table_index": None,
            "document_raw_char_start": match.start(),
            "document_raw_char_end": match.end(),
            "raw_char_start": 0,
            "raw_char_end": len(raw_text),
        }
        element_key = stable_element_key(
            document_version_id=document_version_id,
            element_type="paragraph",
            raw_text_sha256=raw_digest,
            locator=locator,
            level=None,
        )
        elements.append(
            {
                "schema_version": 2,
                "document_version_id": document_version_id,
                "element_key": element_key,
                "element_id": element_key,
                "order": order,
                "type": "paragraph",
                "element_type": "PARAGRAPH",
                "raw_text": raw_text,
                "normalized_text": normalized.text,
                "text": normalized.text,
                "raw_text_sha256": raw_digest,
                "normalized_text_sha256": sha256_text(normalized.text),
                "section_path": [],
                "structure_path": [],
                "locator": locator,
                "normalization_map": normalized.normalization_map,
                "parser_spec": dict(parser_spec),
                "generation_key": generation_key,
            }
        )
    return elements


def parse_document(
    path: str | Path,
    *,
    role: str,
    max_tokens: int = 220,
    min_tokens: int = 30,
) -> ParsedDocument:
    """Parse and chunk one PDF, DOCX or UTF-8 text document.

    ``role`` is part of the document identifier so the same bytes cannot be
    silently confused as both the submitted report and an external source.
    """

    source_path = Path(path).expanduser().resolve(strict=True)
    if not source_path.is_file():
        raise ValueError(f"Input is not a file: {source_path}")
    suffix = source_path.suffix.casefold()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported document type {suffix!r}; expected "
            f"{sorted(_SUPPORTED_SUFFIXES)}"
        )
    if not role or not role.strip():
        raise ValueError("Document role must be non-empty")

    content_sha256 = sha256_file(source_path)
    stable_role = re.sub(r"[^a-z0-9]+", "-", role.casefold()).strip("-")
    document_id = f"{stable_role}-doc-sha256-{content_sha256}"
    document_version_id = f"dv-sha256-{content_sha256}"
    if suffix == ".pdf":
        elements = extract_pdf_elements(
            source_path,
            document_version_id=document_version_id,
        )
    elif suffix == ".docx":
        elements = extract_docx_elements(
            source_path,
            document_version_id=document_version_id,
        )
    else:
        elements = _text_elements(
            source_path,
            document_version_id=document_version_id,
        )
    if not elements:
        raise ValueError(f"Parser produced no elements for {source_path.name}")

    chunks = chunk_elements(
        elements,
        max_tokens=max_tokens,
        min_tokens=min_tokens,
    )
    if not chunks:
        raise ValueError(f"Chunker produced no chunks for {source_path.name}")
    enriched_chunks: list[dict[str, Any]] = []
    for chunk in chunks:
        enriched = dict(chunk)
        enriched["document_id"] = document_id
        enriched["document_version"] = document_version_id
        enriched["document_role"] = role
        enriched["source_name"] = _portable_name(source_path)
        enriched["source_spans"] = [dict(span) for span in chunk["source_spans"]]
        for span in enriched["source_spans"]:
            span["document_id"] = document_id
            span["document_version_id"] = document_version_id
            span["source_name"] = _portable_name(source_path)
        enriched_chunks.append(enriched)

    normalized_text = "\n\n".join(
        str(element.get("normalized_text", ""))
        for element in elements
        if str(element.get("normalized_text", "")).strip()
    )
    document = {
        "schema_version": 1,
        "document_id": document_id,
        "document_version_id": document_version_id,
        "role": role,
        "source_name": _portable_name(source_path),
        "media_type": suffix.lstrip("."),
        "sha256": content_sha256,
        "text": normalized_text,
        "element_count": len(elements),
        "chunk_count": len(enriched_chunks),
    }
    return ParsedDocument(
        document=document,
        elements=tuple(elements),
        chunks=tuple(enriched_chunks),
    )


def parse_documents(
    paths: Iterable[str | Path],
    *,
    role: str,
    max_tokens: int = 220,
    min_tokens: int = 30,
) -> list[ParsedDocument]:
    parsed = [
        parse_document(
            path,
            role=role,
            max_tokens=max_tokens,
            min_tokens=min_tokens,
        )
        for path in paths
    ]
    identifiers = [item.document["document_id"] for item in parsed]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate source document content is not allowed")
    return parsed
