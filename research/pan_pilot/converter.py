"""Deterministic, provenance-preserving PAN pilot-pack converter.

The converter deliberately emits a ``PENDING`` governance decision.  Producing
the four runner files is a technical transformation, not evidence that the
corpus licence permits an experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable
import xml.etree.ElementTree as ET


OUTPUT_NAMES = {
    "documents": "documents.jsonl",
    "chunks": "chunks.jsonl",
    "queries": "queries.jsonl",
    "qrels": "qrels.jsonl",
    "manifest": "dataset-manifest.json",
}

DATASET_PROFILES = {
    "pan-pc-11": {
        "dataset_id": "pan-pc-11-source-retrieval-pilot",
        "description": "Annotated suspicious-span to source-document retrieval diagnostic.",
        "evaluation_role": "CORE_SOURCE_RETRIEVAL_DIAGNOSTIC",
        "result_classification": "COMPONENT_DIAGNOSTIC",
        "target_scope": "document",
        "rights_basis": "CC-BY-4.0; project approver still required",
        "source": {
            "provider": "Webis/PAN",
            "landing_page": "https://webis.de/data/pan-pc-11.html",
            "doi": "10.5281/zenodo.3250095",
            "license": "CC-BY-4.0",
        },
    },
    "pan13": {
        "dataset_id": "pan13-span-retrieval-oracle-pilot",
        "description": (
            "Oracle suspicious-span to source-span component diagnostic; "
            "not the official PAN13 text-alignment evaluation."
        ),
        "evaluation_role": "COMPONENT_DIAGNOSTIC_TEXT_ALIGNMENT",
        "result_classification": "COMPONENT_DIAGNOSTIC",
        "target_scope": "span",
        "rights_basis": "RIGHTS_REVIEW_REQUIRED",
        "source": {
            "provider": "PAN/Webis via Zenodo",
            "landing_page": "https://zenodo.org/records/3715980",
            "doi": "10.5281/zenodo.3715980",
            "license": None,
        },
    },
}

_BLANK_LINE_RE = re.compile(r"(?:\r\n|\r|\n)[\t \f\v]*(?:\r\n|\r|\n)+")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[/\\]")


@dataclass(frozen=True)
class ConversionResult:
    """Paths and counts returned after a successful conversion."""

    output_dir: Path
    manifest_path: Path
    document_count: int
    chunk_count: int
    query_count: int
    qrel_count: int


@dataclass(frozen=True)
class _Annotation:
    annotation_path: str
    annotation_sha256: str
    feature_index: int
    suspicious_path: Path
    suspicious_reference: str
    suspicious_start: int
    suspicious_end: int
    source_path: Path
    source_reference: str
    source_start: int
    source_end: int


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return f"{prefix}-{_sha256_text(payload)[:24]}"


def _render_jsonl(records: Iterable[dict[str, Any]]) -> bytes:
    return "".join(f"{_canonical_json(record)}\n" for record in records).encode("utf-8")


def _render_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"Corpus path escapes input root: {path}") from exc


def _read_utf8_exact(path: Path) -> str:
    """Decode UTF-8 without Python's newline translation, preserving offsets."""

    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"PAN text must be UTF-8: {path.name}") from exc


class _CorpusIndex:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("input_root must be a directory")

        self.text_by_relative: dict[str, Path] = {}
        self.text_by_name: dict[str, list[Path]] = {}
        for candidate in sorted(
            (path for path in self.root.rglob("*") if path.suffix.casefold() == ".txt"),
            key=lambda path: path.as_posix(),
        ):
            resolved = candidate.resolve(strict=True)
            relative = _relative_to_root(resolved, self.root)
            self.text_by_relative[relative] = resolved
            self.text_by_name.setdefault(resolved.name, []).append(resolved)

    def resolve_reference(self, reference: str, *, annotation_path: Path) -> Path:
        clean = reference.strip().replace("\\", "/")
        if not clean or "\x00" in clean:
            raise ValueError("PAN file reference must not be empty")
        pure = PurePosixPath(clean)
        if (
            pure.is_absolute()
            or _WINDOWS_ABSOLUTE_RE.match(reference)
            or any(part == ".." for part in pure.parts)
        ):
            raise ValueError(f"Unsafe PAN file reference: {reference!r}")

        # Prefer a file next to the annotation.  PAN releases often repeat the
        # same basename in multiple language/task directories.
        local = (annotation_path.parent / Path(*pure.parts)).resolve()
        if local.is_file():
            _relative_to_root(local, self.root)
            return local

        relative_key = pure.as_posix().lstrip("./")
        indexed = self.text_by_relative.get(relative_key)
        if indexed is not None:
            return indexed

        matches = self.text_by_name.get(pure.name, [])
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"Referenced PAN text does not exist: {reference!r}")
        raise ValueError(f"Ambiguous PAN text reference: {reference!r}")

    def source_candidates(self) -> set[Path]:
        """Return all source texts, including unreferenced negative distractors."""

        candidates: set[Path] = set()
        for relative, path in self.text_by_relative.items():
            parts = [part.casefold() for part in PurePosixPath(relative).parts]
            filename = parts[-1]
            parent_parts = parts[:-1]
            if (
                filename.startswith("source-document")
                or "src" in parent_parts
                or "source-document" in parent_parts
                or "source-documents" in parent_parts
            ):
                candidates.add(path)
        return candidates


def _local_tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _required_non_negative_int(feature: ET.Element, name: str) -> int:
    raw = feature.attrib.get(name)
    try:
        value = int(raw) if raw is not None else -1
    except ValueError as exc:
        raise ValueError(f"Feature attribute {name!r} must be an integer") from exc
    if value < 0:
        raise ValueError(f"Feature attribute {name!r} must be non-negative")
    return value


def _checked_span(text: str, offset: int, length: int, *, label: str) -> tuple[int, int]:
    if length <= 0:
        raise ValueError(f"{label} length must be positive")
    end = offset + length
    if offset >= len(text) or end > len(text):
        raise ValueError(
            f"{label} span [{offset}, {end}) is outside text length {len(text)}"
        )
    if not text[offset:end].strip():
        raise ValueError(f"{label} span contains only whitespace")
    return offset, end


def _parse_annotations(
    index: _CorpusIndex,
) -> tuple[list[_Annotation], dict[Path, str], int, int]:
    annotations: list[_Annotation] = []
    text_cache: dict[Path, str] = {}

    def text_for(path: Path) -> str:
        if path not in text_cache:
            text_cache[path] = _read_utf8_exact(path)
        return text_cache[path]

    xml_paths = sorted(
        (path for path in index.root.rglob("*") if path.suffix.casefold() == ".xml"),
        key=lambda path: path.as_posix(),
    )
    if not xml_paths:
        raise ValueError("No PAN XML annotations found under input_root")

    no_plagiarism_xml_count = 0
    for xml_path in xml_paths:
        resolved_xml = xml_path.resolve(strict=True)
        relative_xml = _relative_to_root(resolved_xml, index.root)
        xml_bytes = resolved_xml.read_bytes()
        lowered = xml_bytes.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ValueError(f"DTD/entities are not allowed in PAN XML: {relative_xml}")
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid PAN XML: {relative_xml}") from exc

        plagiarism_features = [
            feature
            for feature in root.iter()
            if _local_tag(feature) == "feature"
            and feature.attrib.get("name", "").casefold() == "plagiarism"
        ]
        if not plagiarism_features:
            no_plagiarism_xml_count += 1
            continue

        suspicious_reference = root.attrib.get("reference", "").strip()
        if not suspicious_reference:
            raise ValueError(f"PAN XML has no document reference: {relative_xml}")
        suspicious_path = index.resolve_reference(
            suspicious_reference, annotation_path=resolved_xml
        )
        suspicious_text = text_for(suspicious_path)

        for feature_index, feature in enumerate(plagiarism_features):
            source_reference = feature.attrib.get("source_reference", "").strip()
            if not source_reference:
                raise ValueError(
                    f"Plagiarism feature has no source_reference: {relative_xml}"
                )
            source_path = index.resolve_reference(
                source_reference, annotation_path=resolved_xml
            )
            source_text = text_for(source_path)
            this_offset = _required_non_negative_int(feature, "this_offset")
            this_length = _required_non_negative_int(feature, "this_length")
            source_offset = _required_non_negative_int(feature, "source_offset")
            source_length = _required_non_negative_int(feature, "source_length")
            suspicious_start, suspicious_end = _checked_span(
                suspicious_text,
                this_offset,
                this_length,
                label=f"{relative_xml} suspicious",
            )
            source_start, source_end = _checked_span(
                source_text,
                source_offset,
                source_length,
                label=f"{relative_xml} source",
            )
            annotations.append(
                _Annotation(
                    annotation_path=relative_xml,
                    annotation_sha256=_sha256_bytes(xml_bytes),
                    feature_index=feature_index,
                    suspicious_path=suspicious_path,
                    suspicious_reference=suspicious_reference,
                    suspicious_start=suspicious_start,
                    suspicious_end=suspicious_end,
                    source_path=source_path,
                    source_reference=source_reference,
                    source_start=source_start,
                    source_end=source_end,
                )
            )

    if not annotations:
        raise ValueError("No plagiarism features found in PAN XML annotations")
    return annotations, text_cache, len(xml_paths), no_plagiarism_xml_count


def _trim_whitespace(text: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for separator in _BLANK_LINE_RE.finditer(text):
        trimmed = _trim_whitespace(text, cursor, separator.start())
        if trimmed is not None:
            spans.append(trimmed)
        cursor = separator.end()
    trimmed = _trim_whitespace(text, cursor, len(text))
    if trimmed is not None:
        spans.append(trimmed)
    return spans


def _split_long_span(
    text: str, start: int, end: int, *, max_chars: int
) -> list[tuple[int, int]]:
    pieces: list[tuple[int, int]] = []
    cursor = start
    while end - cursor > max_chars:
        hard_end = cursor + max_chars
        minimum_break = cursor + max(1, max_chars // 2)
        break_at = hard_end
        for position in range(hard_end, minimum_break - 1, -1):
            if position < end and text[position].isspace():
                break_at = position
                break
        trimmed = _trim_whitespace(text, cursor, break_at)
        if trimmed is not None:
            pieces.append(trimmed)
        cursor = break_at
        while cursor < end and text[cursor].isspace():
            cursor += 1
    trimmed = _trim_whitespace(text, cursor, end)
    if trimmed is not None:
        pieces.append(trimmed)
    return pieces


def _chunk_spans(text: str, *, max_chars: int) -> list[tuple[int, int]]:
    atoms: list[tuple[int, int]] = []
    for start, end in _paragraph_spans(text):
        atoms.extend(_split_long_span(text, start, end, max_chars=max_chars))

    chunks: list[tuple[int, int]] = []
    pending: tuple[int, int] | None = None
    for start, end in atoms:
        if pending is None:
            pending = (start, end)
        elif end - pending[0] <= max_chars:
            pending = (pending[0], end)
        else:
            chunks.append(pending)
            pending = (start, end)
    if pending is not None:
        chunks.append(pending)
    return chunks


def _corpus_fingerprint(root: Path) -> tuple[str, int]:
    records: list[dict[str, str]] = []
    for candidate in sorted(root.rglob("*"), key=lambda path: path.as_posix()):
        if not candidate.is_file() or candidate.suffix.casefold() not in {".txt", ".xml"}:
            continue
        resolved = candidate.resolve(strict=True)
        records.append(
            {
                "path": _relative_to_root(resolved, root),
                "sha256": _sha256_file(resolved),
            }
        )
    return _sha256_text(_canonical_json(records)), len(records)


def _write_outputs(
    output_dir: Path, rendered: dict[str, bytes], *, overwrite: bool
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    destinations = {name: output_dir / filename for name, filename in OUTPUT_NAMES.items()}
    collisions = sorted(str(path.name) for path in destinations.values() if path.exists())
    symlinks = sorted(str(path.name) for path in destinations.values() if path.is_symlink())
    if symlinks:
        raise ValueError(
            "Refusing to write generated output through symlinks: " + ", ".join(symlinks)
        )
    if collisions and not overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing pilot files: " + ", ".join(collisions)
        )
    for name in ("documents", "chunks", "queries", "qrels", "manifest"):
        mode = "wb" if overwrite else "xb"
        with destinations[name].open(mode) as stream:
            stream.write(rendered[name])


def convert_pan_pilot(
    *,
    dataset: str,
    input_root: str | Path,
    output_dir: str | Path,
    dataset_version: str,
    split_name: str = "extracted-pilot",
    max_chunk_chars: int = 1200,
    overwrite: bool = False,
) -> ConversionResult:
    """Convert PAN XML/TXT into deterministic runner inputs.

    ``PAN-PC-11`` is evaluated at source-document scope while retaining its
    annotated source span.  ``PAN13`` remains an exact-span component
    diagnostic and must not be presented as an end-to-end plagiarism score.
    """

    dataset_key = dataset.strip().casefold()
    if dataset_key not in DATASET_PROFILES:
        raise ValueError(f"dataset must be one of {sorted(DATASET_PROFILES)}")
    if not dataset_version.strip():
        raise ValueError("dataset_version must not be empty")
    if not split_name.strip():
        raise ValueError("split_name must not be empty")
    if isinstance(max_chunk_chars, bool) or max_chunk_chars < 32:
        raise ValueError("max_chunk_chars must be an integer >= 32")

    profile = DATASET_PROFILES[dataset_key]
    index = _CorpusIndex(Path(input_root))
    annotations, text_cache, xml_file_count, no_plagiarism_xml_count = _parse_annotations(
        index
    )

    source_paths = sorted(
        {annotation.source_path for annotation in annotations}
        | index.source_candidates(),
        key=lambda path: _relative_to_root(path, index.root),
    )
    documents: list[dict[str, Any]] = []
    document_by_path: dict[Path, dict[str, Any]] = {}
    for source_path in source_paths:
        if source_path not in text_cache:
            text_cache[source_path] = _read_utf8_exact(source_path)
        source_text = text_cache[source_path]
        if not source_text.strip():
            raise ValueError(f"Source document is empty: {source_path.name}")
        relative = _relative_to_root(source_path, index.root)
        raw_sha256 = _sha256_text(source_text)
        document = {
            "document_id": _stable_id(
                "doc", profile["dataset_id"], relative, raw_sha256
            ),
            "source_reference": relative,
            "text": source_text,
            "raw_sha256": raw_sha256,
            "version": f"sha256:{raw_sha256}",
            "dataset_version": dataset_version.strip(),
        }
        documents.append(document)
        document_by_path[source_path] = document
    documents.sort(key=lambda record: record["document_id"])

    chunks: list[dict[str, Any]] = []
    for document in documents:
        for order, (start, end) in enumerate(
            _chunk_spans(document["text"], max_chars=max_chunk_chars)
        ):
            chunk_text = document["text"][start:end]
            chunks.append(
                {
                    "chunk_id": _stable_id(
                        "chunk",
                        document["document_id"],
                        start,
                        end,
                        _sha256_text(chunk_text),
                    ),
                    "document_id": document["document_id"],
                    "document_version": document["version"],
                    "order": order,
                    "text": chunk_text,
                    "source_spans": [
                        {
                            "document_id": document["document_id"],
                            "raw_start": start,
                            "raw_end": end,
                        }
                    ],
                    "chunking": {
                        "strategy": "paragraph_aware_v1",
                        "max_chars": max_chunk_chars,
                    },
                }
            )
    chunks.sort(key=lambda record: record["chunk_id"])

    queries: list[dict[str, Any]] = []
    qrels: list[dict[str, Any]] = []
    for annotation in annotations:
        suspicious_text = text_cache[annotation.suspicious_path]
        source_text = text_cache[annotation.source_path]
        query_text = suspicious_text[
            annotation.suspicious_start : annotation.suspicious_end
        ]
        suspicious_relative = _relative_to_root(annotation.suspicious_path, index.root)
        query_id = _stable_id(
            "query",
            profile["dataset_id"],
            annotation.annotation_path,
            annotation.feature_index,
            suspicious_relative,
            annotation.suspicious_start,
            annotation.suspicious_end,
            annotation.source_reference,
            annotation.source_start,
            annotation.source_end,
        )
        queries.append(
            {
                "query_id": query_id,
                "text": query_text,
                "query_role": "SUSPICIOUS_SPAN",
                "annotation_provenance": {
                    "xml_path": annotation.annotation_path,
                    "xml_sha256": annotation.annotation_sha256,
                    "feature_index": annotation.feature_index,
                    "suspicious_document": suspicious_relative,
                    "declared_suspicious_reference": annotation.suspicious_reference,
                    "suspicious_document_sha256": _sha256_text(suspicious_text),
                    "raw_start": annotation.suspicious_start,
                    "raw_end": annotation.suspicious_end,
                    "text_sha256": _sha256_text(query_text),
                },
            }
        )

        document = document_by_path[annotation.source_path]
        # Keep the original PAN alignment span in both profiles.  The explicit
        # target_scope tells evaluation whether that span identifies a relevant
        # source document (PAN-PC-11) or is itself the diagnostic target (PAN13).
        qrel_start, qrel_end = annotation.source_start, annotation.source_end
        annotated_text = source_text[annotation.source_start : annotation.source_end]
        qrels.append(
            {
                "qrel_id": _stable_id(
                    "qrel",
                    query_id,
                    document["document_id"],
                    qrel_start,
                    qrel_end,
                    profile["target_scope"],
                ),
                "query_id": query_id,
                "document_id": document["document_id"],
                "raw_start": qrel_start,
                "raw_end": qrel_end,
                "relevance": 1,
                "target_scope": profile["target_scope"],
                "source_reference": _relative_to_root(
                    annotation.source_path, index.root
                ),
                "declared_source_reference": annotation.source_reference,
                "annotated_source_span": {
                    "raw_start": annotation.source_start,
                    "raw_end": annotation.source_end,
                    "text_sha256": _sha256_text(annotated_text),
                },
            }
        )
    queries.sort(key=lambda record: record["query_id"])
    qrels.sort(key=lambda record: record["qrel_id"])

    rendered = {
        "documents": _render_jsonl(documents),
        "chunks": _render_jsonl(chunks),
        "queries": _render_jsonl(queries),
        "qrels": _render_jsonl(qrels),
    }
    fingerprint, input_file_count = _corpus_fingerprint(index.root)
    manifest = {
        "schema_version": 1,
        "dataset_id": profile["dataset_id"],
        "dataset_version": dataset_version.strip(),
        "description": profile["description"],
        "evaluation_role": profile["evaluation_role"],
        "result_classification": profile["result_classification"],
        "source": profile["source"],
        "governance": {
            "status": "PENDING",
            "rights_basis": profile["rights_basis"],
            "allowed_purposes": ["RETRIEVAL_EXPERIMENT"],
            "classification": "RESEARCH_DATA",
            "contains_pii": "UNKNOWN",
            "retention": None,
            "approver": None,
            "approved_at": None,
        },
        "source_extract": {
            "format": "PAN_XML_TXT",
            "input_fingerprint_sha256": fingerprint,
            "input_file_count": input_file_count,
            "xml_file_count": xml_file_count,
            "no_plagiarism_xml_skipped": no_plagiarism_xml_count,
            "plagiarism_annotation_count": len(annotations),
        },
        "transformation": {
            "converter": "research.pan_pilot",
            "converter_version": "1.0.0",
            "query_unit": "annotated_suspicious_span",
            "target_scope": profile["target_scope"],
            "chunker": "paragraph-aware-v1",
            "max_chunk_chars": max_chunk_chars,
            "offset_convention": "zero-based-half-open-unicode-code-point",
        },
        "split": {
            "name": split_name.strip(),
            "unit": "source_document",
            "document_ids": sorted(record["document_id"] for record in documents),
            "query_ids": sorted(record["query_id"] for record in queries),
        },
        "files": {
            name: {
                "path": OUTPUT_NAMES[name],
                "sha256": _sha256_bytes(rendered[name]),
                "records": len(records),
            }
            for name, records in (
                ("documents", documents),
                ("chunks", chunks),
                ("queries", queries),
                ("qrels", qrels),
            )
        },
    }
    rendered["manifest"] = _render_json(manifest)

    resolved_output = Path(output_dir).resolve()
    _write_outputs(resolved_output, rendered, overwrite=overwrite)
    return ConversionResult(
        output_dir=resolved_output,
        manifest_path=resolved_output / OUTPUT_NAMES["manifest"],
        document_count=len(documents),
        chunk_count=len(chunks),
        query_count=len(queries),
        qrel_count=len(qrels),
    )
