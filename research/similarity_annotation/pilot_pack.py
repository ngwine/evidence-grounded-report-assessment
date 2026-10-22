"""Build a reproducible private annotation pack from a Pipeline 1 run.

Only complete passage-level excerpts in the run report are eligible. An
EXACT_SUBSTRING alignment may contain just a short matched span and cannot by
itself be presented as a full report/source passage to annotators.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


_VAR_ROOT = Path(__file__).resolve().parents[2] / "var"
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_CONTRIBUTION_HEADING = re.compile(r"\bV\.\s*C\s*ONTRIBUTIONS\b", re.IGNORECASE)
_CONTRIBUTION_MARKER = re.compile(r"\bC\s*ONTRIBUTIONS\b", re.IGNORECASE)
_CSV_FIELDS = (
    "pair_id",
    "report_chunk_id",
    "source_chunk_id",
    "source_name",
    "report_text",
    "source_text",
    "report_page",
    "source_page",
    "label",
    "report_evidence_quote",
    "source_evidence_quote",
    "quote_or_citation",
    "confidence",
    "rationale",
)
_ADJUDICATION_FIELDS = (
    "pair_id",
    "quy_label",
    "yen_label",
    "final_label",
    "final_report_evidence_quote",
    "final_source_evidence_quote",
    "final_quote_or_citation",
    "decision_rationale",
    "decision_by",
    "decided_at",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path, description: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def _private_write(path: Path, data: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
        stream.write(data)


def _jsonl(records: Sequence[Mapping[str, Any]]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)


def _csv(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _spreadsheet_safe_text(value: str) -> str:
    """Prevent a passage beginning with a formula token executing in Excel."""

    return "'" + value if re.match(r"^\s*[=+\-@]", value) else value


def _full_passages(matches: Sequence[Mapping[str, Any]], side: str) -> dict[str, dict[str, Any]]:
    passages: dict[str, dict[str, Any]] = {}
    for match in matches:
        alignment = match.get("alignment")
        if not isinstance(alignment, dict) or alignment.get("kind") != "PASSAGE_LEVEL":
            continue
        passage = alignment.get(side)
        if not isinstance(passage, dict) or not isinstance(passage.get("text"), str):
            continue
        chunk_id = str(passage.get("chunk_id", ""))
        if not chunk_id or int(passage.get("normalized_start", -1)) != 0:
            continue
        if int(passage.get("normalized_end", -1)) != len(passage["text"]):
            continue
        previous = passages.get(chunk_id)
        if previous is not None and previous["text"] != passage["text"]:
            raise ValueError(f"Conflicting full text for {side} chunk {chunk_id}")
        passages[chunk_id] = passage
    return passages


def _page(passage: Mapping[str, Any]) -> int | None:
    pages: list[int] = []
    for span in passage.get("source_spans", []):
        if not isinstance(span, dict):
            continue
        locator = span.get("locator")
        if isinstance(locator, dict) and isinstance(locator.get("page_number"), int):
            pages.append(locator["page_number"])
    return min(pages) if pages else None


def _safe_text(text: str) -> bool:
    return "@" not in text and not _EMAIL.search(text) and not _CONTRIBUTION_MARKER.search(text)


def _report_excerpt(passage: Mapping[str, Any]) -> tuple[str, str, int] | None:
    text = str(passage["text"])
    marker = _CONTRIBUTION_HEADING.search(text)
    if marker:
        # Preserve the original normalized offsets in the provenance. The
        # displayed excerpt is [0, marker.start()) from the same chunk.
        excerpt = text[: marker.start()].rstrip()
        policy = "TRIMMED_BEFORE_CONTRIBUTIONS"
    else:
        excerpt = text
        policy = "FULL_CHUNK"
    if not excerpt.strip() or not _safe_text(excerpt):
        return None
    return excerpt, policy, len(excerpt)


def _provenance(
    passage: Mapping[str, Any], *, excerpt_end: int, excerpt_policy: str
) -> dict[str, Any]:
    spans = []
    for span in passage.get("source_spans", []):
        if not isinstance(span, dict):
            continue
        locator = span.get("locator")
        locator = locator if isinstance(locator, dict) else {}
        spans.append(
            {
                **{
                    key: span.get(key)
                    for key in (
                    "element_key",
                    "chunk_normalized_char_start",
                    "chunk_normalized_char_end",
                    "chunk_raw_char_start",
                    "chunk_raw_char_end",
                    "element_normalized_char_start",
                    "element_normalized_char_end",
                    "element_raw_char_start",
                    "element_raw_char_end",
                    "matched_chunk_normalized_start",
                    "matched_chunk_normalized_end",
                    "matched_chunk_raw_start",
                    "matched_chunk_raw_end",
                    "matched_element_raw_start",
                    "matched_element_raw_end",
                    )
                },
                "locator": {
                    key: locator.get(key)
                    for key in (
                            "source_kind",
                            "block_id",
                            "page_index",
                            "page_number",
                            "page_label",
                            "raw_char_start",
                            "raw_char_end",
                    )
                },
            }
        )
    return {
        "chunk_id": passage["chunk_id"],
        "document_id": passage["document_id"],
        "original_normalized_start": passage["normalized_start"],
        "original_normalized_end": passage["normalized_end"],
        "original_raw_start": passage.get("raw_start"),
        "original_raw_end": passage.get("raw_end"),
        "excerpt_normalized_start": 0,
        "excerpt_normalized_end": excerpt_end,
        "excerpt_policy": excerpt_policy,
        "source_spans": spans,
    }


def _pair_id(run_id: str, report_id: str, source_id: str) -> str:
    digest = hashlib.sha256(
        f"{run_id}\0{report_id}\0{source_id}".encode("utf-8")
    ).hexdigest()
    return f"pair-{digest}"


def _match_key(match: Mapping[str, Any]) -> tuple[int, str, str]:
    return (
        int(match["rank"]),
        str(match["report_chunk_id"]),
        str(match["source_chunk_id"]),
    )


def _select(matches: Sequence[dict[str, Any]], target_pairs: int) -> list[dict[str, Any]]:
    by_report: dict[str, list[dict[str, Any]]] = {}
    for match in matches:
        by_report.setdefault(str(match["report_chunk_id"]), []).append(match)
    for values in by_report.values():
        values.sort(key=_match_key)

    chosen: list[dict[str, Any]] = []
    chosen_ids: set[str] = set()

    def add(match: dict[str, Any]) -> None:
        if match["pair_id"] not in chosen_ids:
            chosen.append(match)
            chosen_ids.add(match["pair_id"])

    # Preserve every safe flag from the run, even when its rank is not one.
    for match in sorted(matches, key=_match_key):
        if match["selected_for_manual_review"]:
            add(match)
    # Give every eligible report chunk its first-ranked available candidate.
    for report_id in sorted(by_report):
        rank_one = next((m for m in by_report[report_id] if m["rank"] == 1), None)
        if rank_one is not None:
            add(rank_one)
    if len(chosen) > target_pairs:
        raise ValueError(
            f"Target {target_pairs} is too small for {len(chosen)} mandatory review/rank-1 pairs"
        )

    for document_id in sorted({str(m["source_document_id"]) for m in matches}):
        if not any(str(m["source_document_id"]) == document_id for m in chosen):
            candidate = min(
                (m for m in matches if str(m["source_document_id"]) == document_id),
                key=_match_key,
            )
            add(candidate)
    if len(chosen) > target_pairs:
        raise ValueError("Target is too small to include every available source document")

    while len(chosen) < target_pairs:
        remaining = [m for m in matches if m["pair_id"] not in chosen_ids]
        if not remaining:
            raise ValueError(
                f"Only {len(chosen)} complete, safe pairs available; requested {target_pairs}"
            )
        report_counts = {
            report_id: sum(m["report_chunk_id"] == report_id for m in chosen)
            for report_id in by_report
        }
        source_counts = {
            doc_id: sum(m["source_document_id"] == doc_id for m in chosen)
            for doc_id in {str(m["source_document_id"]) for m in matches}
        }
        add(
            min(
                remaining,
                key=lambda m: (
                    report_counts[str(m["report_chunk_id"])],
                    source_counts[str(m["source_document_id"])],
                    *_match_key(m),
                ),
            )
        )
    return chosen


def build_pilot_pack(
    *,
    similarity_report_path: str | Path,
    run_manifest_path: str | Path,
    output_dir: str | Path,
    target_pairs: int = 40,
    safe_page_one_chunk_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Create blinded local sheets plus private source and prediction records.

    The target directory must be a new directory inside the repository's
    gitignored ``var`` tree. No gold annotations are inferred or prefilled.
    """

    if isinstance(target_pairs, bool) or not isinstance(target_pairs, int) or target_pairs <= 0:
        raise ValueError("target_pairs must be a positive integer")
    output = Path(output_dir).expanduser().resolve()
    var_root = _VAR_ROOT.resolve()
    if not output.is_relative_to(var_root) or output == var_root:
        raise ValueError("output_dir must be a new directory under the ignored repository var/")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite an existing annotation pack: {output}")

    report_file = Path(similarity_report_path).expanduser().resolve(strict=True)
    manifest_file = Path(run_manifest_path).expanduser().resolve(strict=True)
    report = _read_object(report_file, "similarity report")
    manifest = _read_object(manifest_file, "run manifest")
    expected_hash = (
        manifest.get("outputs", {}).get("similarity_report", {}).get("sha256")
    )
    actual_hash = _sha256_file(report_file)
    if expected_hash != actual_hash:
        raise ValueError("Similarity report hash does not match run manifest")
    if not str(report.get("pipeline", "")).startswith("similarity"):
        raise ValueError("Expected a Pipeline 1 similarity report")
    raw_matches = report.get("matches")
    if not isinstance(raw_matches, list):
        raise ValueError("similarity report matches must be a list")
    if not isinstance(manifest.get("run_id"), str):
        raise ValueError("run manifest must contain run_id")
    source_names = {
        str(source["document_id"]): str(source["source_name"])
        for source in manifest.get("inputs", {}).get("sources", [])
    }
    if any(
        Path(name).name != name or "@" in name or _EMAIL.search(name)
        for name in source_names.values()
    ):
        raise ValueError("Source filenames in run manifest contain unsafe metadata")

    report_passages = _full_passages(raw_matches, "report")
    source_passages = _full_passages(raw_matches, "source")
    allowed_page_one = set(safe_page_one_chunk_ids)
    unknown_allowed = allowed_page_one - set(report_passages)
    if unknown_allowed:
        raise ValueError("safe_page_one_chunk_ids contains an unknown full report chunk")
    for chunk_id in allowed_page_one:
        if _page(report_passages[chunk_id]) != 1:
            raise ValueError("safe_page_one_chunk_ids must refer to page-one chunks")

    eligible: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    skipped_incomplete = 0
    skipped_unsafe = 0
    for raw_match in raw_matches:
        if not isinstance(raw_match, dict):
            raise ValueError("Every match must be a JSON object")
        report_id = str(raw_match["report_chunk_id"])
        source_id = str(raw_match["source_chunk_id"])
        key = (report_id, source_id)
        if key in seen_keys:
            raise ValueError("Duplicate report/source chunk pair in similarity report")
        seen_keys.add(key)
        report_passage = report_passages.get(report_id)
        source_passage = source_passages.get(source_id)
        if report_passage is None or source_passage is None:
            skipped_incomplete += 1
            continue
        page = _page(report_passage)
        if page == 1 and report_id not in allowed_page_one:
            skipped_unsafe += 1
            continue
        excerpt = _report_excerpt(report_passage)
        if excerpt is None or not _safe_text(str(source_passage["text"])):
            skipped_unsafe += 1
            continue
        report_text, excerpt_policy, excerpt_end = excerpt
        match = dict(raw_match)
        match["pair_id"] = _pair_id(str(manifest["run_id"]), report_id, source_id)
        match["report_text"] = report_text
        match["source_text"] = str(source_passage["text"])
        match["source_name"] = source_names.get(str(match["source_document_id"]))
        if not match["source_name"]:
            raise ValueError("Match source document is absent from run manifest")
        match["report_provenance"] = _provenance(
            report_passage, excerpt_end=excerpt_end, excerpt_policy=excerpt_policy
        )
        match["source_provenance"] = _provenance(
            source_passage,
            excerpt_end=len(str(source_passage["text"])),
            excerpt_policy="FULL_CHUNK",
        )
        eligible.append(match)

    selected = _select(eligible, target_pairs)
    pairs = [
        {
            "pair_id": m["pair_id"],
            "source_name": m["source_name"],
            "report_text": m["report_text"],
            "source_text": m["source_text"],
            "report_provenance": m["report_provenance"],
            "source_provenance": m["source_provenance"],
        }
        for m in selected
    ]
    annotation_rows = [
        {
            "pair_id": m["pair_id"],
            "report_chunk_id": m["report_chunk_id"],
            "source_chunk_id": m["source_chunk_id"],
            "source_name": m["source_name"],
            "report_text": _spreadsheet_safe_text(m["report_text"]),
            "source_text": _spreadsheet_safe_text(m["source_text"]),
            "report_page": _page(m["report_provenance"]),
            "source_page": _page(m["source_provenance"]),
            "label": "",
            "report_evidence_quote": "",
            "source_evidence_quote": "",
            "quote_or_citation": "",
            "confidence": "",
            "rationale": "",
        }
        for m in selected
    ]
    # Machine output lives only here, never in either independent sheet.
    prediction_fields = (
        "classification_status",
        "similarity_type",
        "provisional_similarity_type",
        "heuristic_score",
        "classification_reasons",
        "selected_for_manual_review",
        "selected_for_document_coverage",
        "rank",
        "retrieval_score",
        "retrieval_score_type",
        "rrf_score",
        "cross_encoder_score",
        "dense_score",
        "features",
    )
    predictions = [
        {
            "pair_id": m["pair_id"],
            "report_chunk_id": m["report_chunk_id"],
            "source_chunk_id": m["source_chunk_id"],
            "source_document_id": m["source_document_id"],
            **{field: m.get(field) for field in prediction_fields},
        }
        for m in selected
    ]
    adjudication_rows = [
        {"pair_id": m["pair_id"], **{field: "" for field in _ADJUDICATION_FIELDS[1:]}}
        for m in selected
    ]

    files = {
        "pairs.jsonl": _jsonl(pairs),
        "annotations_quy.csv": _csv(annotation_rows, _CSV_FIELDS),
        "annotations_yen.csv": _csv(annotation_rows, _CSV_FIELDS),
        "model_predictions.jsonl": _jsonl(predictions),
        "adjudication.csv": _csv(adjudication_rows, _ADJUDICATION_FIELDS),
    }
    pack_manifest = {
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "target_pairs": target_pairs,
        "selected_pairs": len(selected),
        "selected_manual_review_pairs": sum(
            bool(m["selected_for_manual_review"]) for m in selected
        ),
        "selected_source_document_ids": sorted(
            {str(m["source_document_id"]) for m in selected}
        ),
        "safe_page_one_chunk_ids": sorted(allowed_page_one),
        "skipped_incomplete_excerpts": skipped_incomplete,
        "skipped_unsafe_pairs": skipped_unsafe,
        "governance": {
            "status": "PENDING",
            "scope": "LOCAL_ANNOTATION_ONLY",
            "rights_verified": False,
            "production_indexing_allowed": False,
        },
        "inputs": {
            "similarity_report_sha256": actual_hash,
            "run_manifest_sha256": _sha256_file(manifest_file),
            "report_document_sha256": manifest.get("inputs", {}).get("report", {}).get("sha256"),
            "source_document_sha256": sorted(
                str(source.get("sha256"))
                for source in manifest.get("inputs", {}).get("sources", [])
            ),
        },
        "artifacts": {
            filename: {"sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
            for filename, content in files.items()
        },
    }
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    for filename, content in files.items():
        _private_write(output / filename, content)
    _private_write(
        output / "pack-manifest.json",
        json.dumps(pack_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return pack_manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--similarity-report", required=True, type=Path)
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--target-pairs", type=int, default=40)
    parser.add_argument("--safe-page-one-chunk-id", action="append", default=[])
    args = parser.parse_args(argv)
    result = build_pilot_pack(
        similarity_report_path=args.similarity_report,
        run_manifest_path=args.run_manifest,
        output_dir=args.output_dir,
        target_pairs=args.target_pairs,
        safe_page_one_chunk_ids=args.safe_page_one_chunk_id,
    )
    print(json.dumps({"selected_pairs": result["selected_pairs"], "output_dir": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
