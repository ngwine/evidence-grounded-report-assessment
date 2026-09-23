"""Golden parser/chunker benchmark used by W4.6.

The manifest contains reviewed expectations and fixture checksums.  This script
never updates those expectations automatically; a parser change that alters a
golden output must be reviewed and the manifest changed explicitly.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.kltn_ai.integrations.indexing.chunking import chunk_elements  # noqa: E402
from src.kltn_ai.integrations.parsing.docx_parser import extract_docx_elements  # noqa: E402
from src.kltn_ai.integrations.parsing.pdf_parser import extract_pdf_elements  # noqa: E402


TESTS_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = TESTS_DIR / "golden" / "parser_chunking_v1" / "manifest.json"
EXTRACTORS: dict[str, Callable[[str], list[dict[str, Any]]]] = {
    "pdf": extract_pdf_elements,
    "docx": extract_docx_elements,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _output_digest(elements: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> str:
    return _sha256_bytes(
        _canonical_json({"elements": elements, "chunks": chunks}).encode("utf-8")
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5)))
    return ordered[index]


def _validate_coverage(
    elements: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    content_elements = {
        element["element_key"]: element
        for element in elements
        if element["type"] != "heading" and element["normalized_text"].strip()
    }
    intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    errors: list[str] = []

    for chunk in chunks:
        if chunk["token_count"] <= 0:
            errors.append(f"{chunk['chunk_key']}: token_count is not positive")
        for source_span in chunk["source_spans"]:
            element_key = source_span["element_key"]
            element = content_elements.get(element_key)
            if element is None:
                errors.append(f"{chunk['chunk_key']}: unknown/non-content element {element_key}")
                continue
            normalized_start = source_span["element_normalized_char_start"]
            normalized_end = source_span["element_normalized_char_end"]
            raw_start = source_span["element_raw_char_start"]
            raw_end = source_span["element_raw_char_end"]
            if not (0 <= normalized_start < normalized_end <= len(element["normalized_text"])):
                errors.append(f"{chunk['chunk_key']}: invalid normalized source span")
            if not (0 <= raw_start < raw_end <= len(element["raw_text"])):
                errors.append(f"{chunk['chunk_key']}: invalid raw source span")
            intervals[element_key].append((normalized_start, normalized_end))

    covered_characters = 0
    expected_characters = sum(len(element["normalized_text"]) for element in content_elements.values())
    for element_key, element in content_elements.items():
        ordered = sorted(intervals.get(element_key, []))
        cursor = 0
        for start, end in ordered:
            if start != cursor:
                errors.append(
                    f"{element_key}: expected next normalized span at {cursor}, got {start}"
                )
            cursor = max(cursor, end)
        if cursor != len(element["normalized_text"]):
            errors.append(
                f"{element_key}: coverage ends at {cursor}, expected {len(element['normalized_text'])}"
            )
        covered_characters += min(cursor, len(element["normalized_text"]))

    return {
        "content_element_count": len(content_elements),
        "expected_normalized_characters": expected_characters,
        "covered_normalized_characters": covered_characters,
        "coverage_ratio": (
            covered_characters / expected_characters if expected_characters else 1.0
        ),
        "error_count": len(errors),
        "errors": errors,
    }


def _summarize_run(
    elements: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "element_count": len(elements),
        "element_type_counts": dict(sorted(Counter(e["type"] for e in elements).items())),
        "chunk_count": len(chunks),
        "chunk_type_counts": dict(sorted(Counter(c["type"] for c in chunks).items())),
        "heading_texts": [
            element["normalized_text"]
            for element in elements
            if element["type"] == "heading"
        ],
        "page_indices": sorted(
            {
                element["locator"]["page_index"]
                for element in elements
                if element["locator"].get("page_index") is not None
            }
        ),
        "max_chunk_tokens": max((chunk["token_count"] for chunk in chunks), default=0),
        "output_sha256": _output_digest(elements, chunks),
        "coverage": _validate_coverage(elements, chunks),
    }


def _assert_expected(fixture_id: str, summary: dict[str, Any], expected: dict[str, Any]) -> None:
    for field, expected_value in expected.items():
        actual_value = summary.get(field)
        if actual_value != expected_value:
            raise AssertionError(
                f"{fixture_id}: expected {field}={expected_value!r}, got {actual_value!r}"
            )
    if summary["coverage"]["error_count"]:
        raise AssertionError(
            f"{fixture_id}: provenance coverage failed: {summary['coverage']['errors']}"
        )
    if summary["coverage"]["coverage_ratio"] != 1.0:
        raise AssertionError(f"{fixture_id}: normalized content coverage is not 100%")


def run_benchmark(manifest_path: Path = DEFAULT_MANIFEST, runs: int = 10) -> dict[str, Any]:
    if runs < 2:
        raise ValueError("runs must be at least 2 to verify determinism")

    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunk_config = manifest["chunk_config"]
    fixture_results: list[dict[str, Any]] = []

    for fixture in manifest["fixtures"]:
        fixture_path = (TESTS_DIR / fixture["path"]).resolve()
        actual_checksum = _sha256_file(fixture_path)
        if actual_checksum != fixture["sha256"]:
            raise AssertionError(
                f"{fixture['id']}: fixture checksum mismatch; expected {fixture['sha256']}, "
                f"got {actual_checksum}"
            )
        extractor = EXTRACTORS[fixture["format"]]
        timings_ms: list[float] = []
        peak_memory_bytes: list[int] = []
        digests: list[str] = []
        first_summary: dict[str, Any] | None = None

        for _ in range(runs):
            tracemalloc.start()
            started = time.perf_counter()
            elements = extractor(str(fixture_path))
            chunks = chunk_elements(elements, **chunk_config)
            elapsed_ms = (time.perf_counter() - started) * 1000
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            summary = _summarize_run(elements, chunks)
            if first_summary is None:
                first_summary = summary
                _assert_expected(fixture["id"], summary, fixture["expected"])
            timings_ms.append(elapsed_ms)
            peak_memory_bytes.append(peak)
            digests.append(summary["output_sha256"])

        if len(set(digests)) != 1:
            raise AssertionError(f"{fixture['id']}: output changed across identical runs")

        fixture_results.append(
            {
                "id": fixture["id"],
                "path": fixture["path"],
                "format": fixture["format"],
                "sha256": actual_checksum,
                "summary": first_summary,
                "deterministic_runs": runs,
                "timing_ms": {
                    "min": min(timings_ms),
                    "p50": statistics.median(timings_ms),
                    "p95": _percentile(timings_ms, 0.95),
                    "max": max(timings_ms),
                },
                "peak_memory_bytes": {
                    "min": min(peak_memory_bytes),
                    "p50": int(statistics.median(peak_memory_bytes)),
                    "max": max(peak_memory_bytes),
                },
            }
        )

    packages = {}
    for package in ("PyMuPDF", "python-docx"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None

    return {
        "schema_version": 1,
        "benchmark_id": manifest["benchmark_id"],
        "manifest_sha256": _sha256_file(manifest_path),
        "chunk_config": chunk_config,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "packages": packages,
        },
        "fixtures": fixture_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run_benchmark(args.manifest, args.runs)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
