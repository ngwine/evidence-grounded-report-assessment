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
import subprocess
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

EXPECTED_ARCHIVE_MD5 = {
    "pan-pc-11": {
        "pan-plagiarism-corpus-2011.part1.rar": "b2930f859497dd48ba5bb606d3f4a4f3",
        "pan-plagiarism-corpus-2011.part2.rar": "b23d86c17a47d2bfbdc4c314ea5810df",
    },
    "pan13": {
        "pan13-text-alignment-test-and-training.zip": "fec7fca7a82193a97fbb97cde7781b63",
    },
}

_BLANK_LINE_RE = re.compile(r"(?:\r\n|\r|\n)[\t \f\v]*(?:\r\n|\r|\n)+")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[/\\]")
_UNICODE_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)


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


@dataclass(frozen=True)
class _AnnotationScan:
    annotations: tuple[_Annotation, ...]
    xml_file_count: int
    no_plagiarism_xml_count: int
    non_suspicious_xml_count: int
    zero_length_annotation_count: int
    xml_inventory: tuple[dict[str, Any], ...]


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


def _md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
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


def _scan_annotations(index: _CorpusIndex) -> _AnnotationScan:
    """Read XML metadata only; no corpus TXT content is opened here."""

    annotations: list[_Annotation] = []
    xml_inventory: list[dict[str, Any]] = []
    xml_paths = sorted(
        (path for path in index.root.rglob("*") if path.suffix.casefold() == ".xml"),
        key=lambda path: path.as_posix(),
    )
    if not xml_paths:
        raise ValueError("No PAN XML annotations found under input_root")

    no_plagiarism_xml_count = 0
    non_suspicious_xml_count = 0
    zero_length_annotation_count = 0
    for xml_path in xml_paths:
        resolved_xml = xml_path.resolve(strict=True)
        relative_xml = _relative_to_root(resolved_xml, index.root)
        xml_bytes = resolved_xml.read_bytes()
        xml_sha256 = _sha256_bytes(xml_bytes)
        xml_inventory.append(
            {
                "path": relative_xml,
                "size_bytes": len(xml_bytes),
                "sha256": xml_sha256,
            }
        )
        lowered = xml_bytes.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ValueError(f"DTD/entities are not allowed in PAN XML: {relative_xml}")
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid PAN XML: {relative_xml}") from exc

        suspicious_reference = root.attrib.get("reference", "").strip()
        reference_path = PurePosixPath(suspicious_reference.replace("\\", "/"))
        reference_name = reference_path.name.casefold()
        reference_parts = {part.casefold() for part in reference_path.parts[:-1]}
        relative_parts = {
            part.casefold() for part in PurePosixPath(relative_xml).parts[:-1]
        }
        suspicious_directory_names = {
            "susp",
            "suspicious-document",
            "suspicious-documents",
        }
        is_suspicious_xml = reference_name.startswith("suspicious-document") or bool(
            suspicious_directory_names & (reference_parts | relative_parts)
        )
        if not is_suspicious_xml:
            non_suspicious_xml_count += 1
            continue

        plagiarism_features = [
            feature
            for feature in root.iter()
            if _local_tag(feature) == "feature"
            and feature.attrib.get("name", "").casefold() == "plagiarism"
        ]
        if not plagiarism_features:
            no_plagiarism_xml_count += 1
            continue

        if not suspicious_reference:
            raise ValueError(f"PAN XML has no document reference: {relative_xml}")
        suspicious_path = index.resolve_reference(
            suspicious_reference, annotation_path=resolved_xml
        )

        for feature_index, feature in enumerate(plagiarism_features):
            source_reference = feature.attrib.get("source_reference", "").strip()
            if not source_reference:
                raise ValueError(
                    f"Plagiarism feature has no source_reference: {relative_xml}"
                )
            source_path = index.resolve_reference(
                source_reference, annotation_path=resolved_xml
            )
            this_offset = _required_non_negative_int(feature, "this_offset")
            this_length = _required_non_negative_int(feature, "this_length")
            source_offset = _required_non_negative_int(feature, "source_offset")
            source_length = _required_non_negative_int(feature, "source_length")
            # PAN-PC-11 contains at least one provider annotation whose
            # suspicious span has length zero. It cannot form a retrieval
            # query, so exclude it explicitly and record the exclusion in the
            # manifest instead of accepting an empty query or aborting the
            # whole corpus conversion.
            if this_length == 0 or source_length == 0:
                zero_length_annotation_count += 1
                continue
            annotations.append(
                _Annotation(
                    annotation_path=relative_xml,
                    annotation_sha256=xml_sha256,
                    feature_index=feature_index,
                    suspicious_path=suspicious_path,
                    suspicious_reference=suspicious_reference,
                    suspicious_start=this_offset,
                    suspicious_end=this_offset + this_length,
                    source_path=source_path,
                    source_reference=source_reference,
                    source_start=source_offset,
                    source_end=source_offset + source_length,
                )
            )

    if not annotations:
        raise ValueError("No plagiarism features found in PAN XML annotations")
    return _AnnotationScan(
        annotations=tuple(annotations),
        xml_file_count=len(xml_paths),
        no_plagiarism_xml_count=no_plagiarism_xml_count,
        non_suspicious_xml_count=non_suspicious_xml_count,
        zero_length_annotation_count=zero_length_annotation_count,
        xml_inventory=tuple(xml_inventory),
    )


def _annotation_id(dataset_id: str, annotation: _Annotation) -> str:
    """Stable positive ID derived only from XML metadata and paths."""

    return _stable_id(
        "annotation",
        dataset_id,
        annotation.annotation_path,
        annotation.feature_index,
        annotation.suspicious_reference,
        annotation.suspicious_start,
        annotation.suspicious_end,
        annotation.source_reference,
        annotation.source_start,
        annotation.source_end,
    )


def _hash_order(seed: int, namespace: str, value: str) -> tuple[str, str]:
    return (_sha256_text(f"{seed}\x1f{namespace}\x1f{value}"), value)


def _select_annotations(
    annotations: Iterable[_Annotation],
    *,
    dataset_id: str,
    max_positive_annotations: int | None,
    seed: int,
) -> list[_Annotation]:
    """Hash-order positives within XML-parent strata, then round-robin strata."""

    all_annotations = list(annotations)
    if max_positive_annotations is None or max_positive_annotations >= len(all_annotations):
        return sorted(
            all_annotations,
            key=lambda item: _annotation_id(dataset_id, item),
        )

    strata: dict[str, list[_Annotation]] = {}
    for annotation in all_annotations:
        stratum = PurePosixPath(annotation.annotation_path).parent.as_posix() or "."
        strata.setdefault(stratum, []).append(annotation)
    for stratum, members in strata.items():
        members.sort(
            key=lambda item: _hash_order(
                seed,
                f"positive:{stratum}",
                _annotation_id(dataset_id, item),
            )
        )

    stratum_order = sorted(
        strata,
        key=lambda value: _hash_order(seed, "stratum", value),
    )
    cursors = {stratum: 0 for stratum in stratum_order}
    selected: list[_Annotation] = []
    while len(selected) < max_positive_annotations:
        added = False
        for stratum in stratum_order:
            cursor = cursors[stratum]
            members = strata[stratum]
            if cursor >= len(members):
                continue
            selected.append(members[cursor])
            cursors[stratum] += 1
            added = True
            if len(selected) == max_positive_annotations:
                break
        if not added:
            break
    return sorted(selected, key=lambda item: _annotation_id(dataset_id, item))


def _select_source_paths(
    index: _CorpusIndex,
    all_annotations: Iterable[_Annotation],
    selected_annotations: Iterable[_Annotation],
    *,
    max_candidate_documents: int,
    seed: int,
) -> tuple[list[Path], dict[str, int]]:
    """Keep every selected positive source, then hash-sample negative sources."""

    all_annotation_sources = {item.source_path for item in all_annotations}
    full_candidates = index.source_candidates() | all_annotation_sources
    relevant = {item.source_path for item in selected_annotations}
    if len(relevant) > max_candidate_documents:
        raise ValueError(
            "max_candidate_documents is smaller than the number of relevant "
            f"source documents ({max_candidate_documents} < {len(relevant)})"
        )

    distractors = sorted(
        full_candidates - relevant,
        key=lambda path: _hash_order(
            seed,
            "distractor-source",
            _relative_to_root(path, index.root),
        ),
    )
    selected_distractors = distractors[: max_candidate_documents - len(relevant)]
    selected = sorted(
        relevant | set(selected_distractors),
        key=lambda path: _relative_to_root(path, index.root),
    )
    return selected, {
        "source_documents_available": len(full_candidates),
        "relevant_source_documents_available": len(all_annotation_sources),
        "relevant_source_documents_selected": len(relevant),
        "distractor_documents_available": len(full_candidates - relevant),
        "distractor_documents_selected": len(selected_distractors),
        "candidate_documents_selected": len(selected),
    }


def _query_windows(
    text: str, *, max_word_tokens: int, stride_word_tokens: int
) -> list[dict[str, int]]:
    r"""Return deterministic character spans bounded by Unicode ``\w+`` tokens."""

    tokens = list(_UNICODE_WORD_RE.finditer(text))
    token_count = len(tokens)
    if token_count <= max_word_tokens:
        return [
            {
                "index": 0,
                "token_start": 0,
                "token_end": token_count,
                "raw_start": 0,
                "raw_end": len(text),
                "word_token_count": token_count,
            }
        ]

    starts = list(range(0, token_count - max_word_tokens + 1, stride_word_tokens))
    final_start = token_count - max_word_tokens
    if starts[-1] != final_start:
        starts.append(final_start)
    windows: list[dict[str, int]] = []
    for index, token_start in enumerate(starts):
        token_end = min(token_count, token_start + max_word_tokens)
        windows.append(
            {
                "index": index,
                "token_start": token_start,
                "token_end": token_end,
                "raw_start": tokens[token_start].start(),
                "raw_end": tokens[token_end - 1].end(),
                "word_token_count": token_end - token_start,
            }
        )
    return windows


def _archive_provenance(
    dataset_key: str, source_archives: Iterable[str | Path]
) -> list[dict[str, Any]]:
    expected_by_name = EXPECTED_ARCHIVE_MD5[dataset_key]
    records: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    seen_names: set[str] = set()
    for raw_path in source_archives:
        path = Path(raw_path).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"source_archive must be a file: {path.name}")
        if path in seen_paths:
            raise ValueError(f"Duplicate source_archive: {path.name}")
        seen_paths.add(path)
        normalized_name = path.name.casefold()
        if normalized_name in seen_names:
            raise ValueError(f"Duplicate source_archive name: {path.name}")
        seen_names.add(normalized_name)
        local_md5 = _md5_file(path)
        expected_md5 = expected_by_name.get(normalized_name)
        if expected_md5 is not None and local_md5 != expected_md5:
            raise ValueError(
                f"Provider MD5 mismatch for {path.name}: "
                f"expected {expected_md5}, got {local_md5}"
            )
        records.append(
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "provider_md5": expected_md5,
                "local_md5": local_md5,
                "provider_checksum_verified": expected_md5 is not None,
                "local_sha256": _sha256_file(path),
            }
        )
    verified_names = {
        record["name"].casefold()
        for record in records
        if record["provider_checksum_verified"]
    }
    if verified_names and verified_names != set(expected_by_name):
        missing = sorted(set(expected_by_name) - verified_names)
        raise ValueError(
            "Incomplete official archive set; missing: " + ", ".join(missing)
        )
    return sorted(records, key=lambda item: item["name"].casefold())


def _converter_provenance() -> dict[str, Any]:
    converter_file = Path(__file__).resolve(strict=True)
    provenance: dict[str, Any] = {
        "file": "research/pan_pilot/converter.py",
        "code_sha256": _sha256_file(converter_file),
        "git_commit": None,
        "git_dirty": None,
    }
    try:
        root_result = subprocess.run(
            ["git", "-C", str(converter_file.parent), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        repo_root = Path(root_result.stdout.strip())
        commit_result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        converter_relative = converter_file.relative_to(repo_root).as_posix()
        status_result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "status",
                "--porcelain",
                "--untracked-files=no",
                "--",
                converter_relative,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        provenance["git_commit"] = commit_result.stdout.strip()
        # Unrelated untracked notes must not make the exact converter source
        # look dirty; its own content hash is already recorded above.
        provenance["git_dirty"] = bool(status_result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return provenance


def _input_inventory_fingerprint(
    index: _CorpusIndex, scan: _AnnotationScan
) -> tuple[str, int]:
    """Fingerprint metadata without opening every potentially huge source TXT."""

    text_inventory = [
        {
            "path": relative,
            "size_bytes": path.stat().st_size,
        }
        for relative, path in sorted(index.text_by_relative.items())
    ]
    payload = {
        "method": "xml-content-sha256+text-path-size-v1",
        "xml": list(scan.xml_inventory),
        "text": text_inventory,
    }
    return _sha256_text(_canonical_json(payload)), len(scan.xml_inventory) + len(
        text_inventory
    )


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
    max_positive_annotations: int | None = 30,
    max_candidate_documents: int = 200,
    seed: int = 20260923,
    max_query_word_tokens: int = 256,
    query_stride_word_tokens: int = 128,
    source_archives: Iterable[str | Path] = (),
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
    if (
        max_positive_annotations is not None
        and (
            isinstance(max_positive_annotations, bool)
            or max_positive_annotations < 1
        )
    ):
        raise ValueError("max_positive_annotations must be null or an integer >= 1")
    if dataset_key == "pan-pc-11" and max_positive_annotations is None:
        raise ValueError("PAN-PC-11 requires a bounded max_positive_annotations")
    if isinstance(max_candidate_documents, bool) or max_candidate_documents < 1:
        raise ValueError("max_candidate_documents must be an integer >= 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(max_query_word_tokens, bool) or max_query_word_tokens < 1:
        raise ValueError("max_query_word_tokens must be an integer >= 1")
    if (
        isinstance(query_stride_word_tokens, bool)
        or query_stride_word_tokens < 1
        or query_stride_word_tokens > max_query_word_tokens
    ):
        raise ValueError(
            "query_stride_word_tokens must be between 1 and max_query_word_tokens"
        )

    profile = DATASET_PROFILES[dataset_key]
    index = _CorpusIndex(Path(input_root))
    scan = _scan_annotations(index)
    annotations = _select_annotations(
        scan.annotations,
        dataset_id=profile["dataset_id"],
        max_positive_annotations=max_positive_annotations,
        seed=seed,
    )
    source_paths, source_sampling_counts = _select_source_paths(
        index,
        scan.annotations,
        annotations,
        max_candidate_documents=max_candidate_documents,
        seed=seed,
    )
    archive_records = _archive_provenance(dataset_key, source_archives)
    text_cache: dict[Path, str] = {}

    def text_for(path: Path) -> str:
        if path not in text_cache:
            text_cache[path] = _read_utf8_exact(path)
        return text_cache[path]

    documents: list[dict[str, Any]] = []
    document_by_path: dict[Path, dict[str, Any]] = {}
    for source_path in source_paths:
        source_text = text_for(source_path)
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
        suspicious_text = text_for(annotation.suspicious_path)
        source_text = text_for(annotation.source_path)
        suspicious_start, suspicious_end = _checked_span(
            suspicious_text,
            annotation.suspicious_start,
            annotation.suspicious_end - annotation.suspicious_start,
            label=f"{annotation.annotation_path} suspicious",
        )
        source_start, source_end = _checked_span(
            source_text,
            annotation.source_start,
            annotation.source_end - annotation.source_start,
            label=f"{annotation.annotation_path} source",
        )
        annotation_text = suspicious_text[suspicious_start:suspicious_end]
        suspicious_relative = _relative_to_root(annotation.suspicious_path, index.root)
        parent_annotation_id = _annotation_id(profile["dataset_id"], annotation)
        document = document_by_path[annotation.source_path]
        # Keep the original PAN alignment span in both profiles.  The explicit
        # target_scope tells evaluation whether that span identifies a relevant
        # source document (PAN-PC-11) or is itself the diagnostic target (PAN13).
        annotated_text = source_text[source_start:source_end]
        windows = _query_windows(
            annotation_text,
            max_word_tokens=max_query_word_tokens,
            stride_word_tokens=query_stride_word_tokens,
        )
        for window in windows:
            window_text = annotation_text[window["raw_start"] : window["raw_end"]]
            window_raw_start = suspicious_start + window["raw_start"]
            window_raw_end = suspicious_start + window["raw_end"]
            query_id = _stable_id(
                "query",
                parent_annotation_id,
                window["index"],
                window["token_start"],
                window["token_end"],
                window_raw_start,
                window_raw_end,
            )
            queries.append(
                {
                    "query_id": query_id,
                    "parent_annotation_id": parent_annotation_id,
                    "text": window_text,
                    "query_role": "SUSPICIOUS_SPAN_WINDOW",
                    "query_window": {
                        **window,
                        "raw_start": window_raw_start,
                        "raw_end": window_raw_end,
                        "annotation_relative_raw_start": window["raw_start"],
                        "annotation_relative_raw_end": window["raw_end"],
                        "total_annotation_word_tokens": len(
                            _UNICODE_WORD_RE.findall(annotation_text)
                        ),
                        "max_word_tokens": max_query_word_tokens,
                        "stride_word_tokens": query_stride_word_tokens,
                    },
                    "annotation_provenance": {
                        "xml_path": annotation.annotation_path,
                        "xml_sha256": annotation.annotation_sha256,
                        "feature_index": annotation.feature_index,
                        "suspicious_document": suspicious_relative,
                        "declared_suspicious_reference": annotation.suspicious_reference,
                        "suspicious_document_sha256": _sha256_text(suspicious_text),
                        "raw_start": suspicious_start,
                        "raw_end": suspicious_end,
                        "annotation_text_sha256": _sha256_text(annotation_text),
                        "window_text_sha256": _sha256_text(window_text),
                        "text_sha256": _sha256_text(window_text),
                    },
                }
            )
            qrels.append(
                {
                    "qrel_id": _stable_id(
                        "qrel",
                        query_id,
                        document["document_id"],
                        source_start,
                        source_end,
                        profile["target_scope"],
                    ),
                    "query_id": query_id,
                    "parent_annotation_id": parent_annotation_id,
                    "query_window_index": window["index"],
                    "document_id": document["document_id"],
                    "raw_start": source_start,
                    "raw_end": source_end,
                    "relevance": 1,
                    "target_scope": profile["target_scope"],
                    "source_reference": _relative_to_root(
                        annotation.source_path, index.root
                    ),
                    "declared_source_reference": annotation.source_reference,
                    "annotated_source_span": {
                        "raw_start": source_start,
                        "raw_end": source_end,
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
    fingerprint, input_file_count = _input_inventory_fingerprint(index, scan)
    selected_annotation_ids = sorted(
        _annotation_id(profile["dataset_id"], annotation) for annotation in annotations
    )
    selected_source_paths = sorted(
        _relative_to_root(path, index.root) for path in source_paths
    )
    source_record = {**profile["source"], "archives": archive_records}
    full_corpus_result = (
        len(annotations) == len(scan.annotations)
        and len(source_paths) == source_sampling_counts["source_documents_available"]
    )
    manifest = {
        "schema_version": 1,
        "dataset_id": profile["dataset_id"],
        "dataset_version": dataset_version.strip(),
        "description": profile["description"],
        "evaluation_role": profile["evaluation_role"],
        "result_classification": profile["result_classification"],
        "source": source_record,
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
            "input_fingerprint_method": "xml-content-sha256+text-path-size-v1",
            "input_file_count": input_file_count,
            "xml_file_count": scan.xml_file_count,
            "no_plagiarism_xml_skipped": scan.no_plagiarism_xml_count,
            "non_suspicious_xml_skipped": scan.non_suspicious_xml_count,
            "zero_length_annotations_skipped": scan.zero_length_annotation_count,
            "plagiarism_annotation_count_available": len(scan.annotations),
            "plagiarism_annotation_count_selected": len(annotations),
            "plagiarism_annotation_count": len(annotations),
        },
        "sampling": {
            "strategy": "xml-parent-stratified-sha256-round-robin-v1",
            "positive_unit": "plagiarism_feature",
            "stratum": "annotation_xml_parent_directory",
            "ordering": "sha256(seed, namespace, stable_id)",
            "seed": seed,
            "max_positive_annotations": max_positive_annotations,
            "max_annotations": max_positive_annotations,
            "max_candidate_documents": max_candidate_documents,
            "positive_annotations_available": len(scan.annotations),
            "positive_annotations_selected": len(annotations),
            **source_sampling_counts,
            "selected_annotation_ids": selected_annotation_ids,
            "selected_annotation_ids_sha256": _sha256_text(
                _canonical_json(selected_annotation_ids)
            ),
            "selected_candidate_source_paths_sha256": _sha256_text(
                _canonical_json(selected_source_paths)
            ),
            "full_corpus_result": full_corpus_result,
        },
        "transformation": {
            "converter": "research.pan_pilot",
            "converter_version": "2.0.0",
            "converter_provenance": _converter_provenance(),
            "query_unit": "annotated_suspicious_span_window",
            "target_scope": profile["target_scope"],
            "chunker": "paragraph-aware-v1",
            "max_chunk_chars": max_chunk_chars,
            "query_window": {
                "tokenizer": "python-unicode-word-regex-v1",
                "max_word_tokens": max_query_word_tokens,
                "stride_word_tokens": query_stride_word_tokens,
            },
            "offset_convention": "zero-based-half-open-unicode-code-point",
        },
        "split": {
            "name": split_name.strip(),
            "unit": "source_document",
            "seed": seed,
            "document_ids": sorted(record["document_id"] for record in documents),
            "query_ids": sorted(record["query_id"] for record in queries),
            "parent_annotation_ids": selected_annotation_ids,
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
