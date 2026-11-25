"""Command-line interface for the PAN pilot converter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .converter import DATASET_PROFILES, convert_pan_pilot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert extracted PAN XML/TXT into a gated retrieval pilot pack."
    )
    parser.add_argument("--dataset", required=True, choices=sorted(DATASET_PROFILES))
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--split-name", default="extracted-pilot")
    parser.add_argument("--max-chunk-chars", type=int, default=1200)
    parser.add_argument(
        "--max-positive-annotations",
        "--max-annotations",
        dest="max_positive_annotations",
        type=int,
        default=30,
        help="Maximum sampled plagiarism annotations (default: 30).",
    )
    parser.add_argument(
        "--max-candidate-documents",
        type=int,
        default=200,
        help="Maximum relevant plus distractor source documents (default: 200).",
    )
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--max-query-word-tokens", type=int, default=256)
    parser.add_argument("--query-stride-word-tokens", type=int, default=128)
    parser.add_argument(
        "--source-archive",
        action="append",
        type=Path,
        default=[],
        help=(
            "Original provider archive; repeat for multipart PAN-PC-11. "
            "Known provider MD5 values are verified before conversion."
        ),
    )
    parser.add_argument(
        "--exclude-manifest",
        action="append",
        type=Path,
        default=[],
        help=(
            "Prior derived dataset manifest whose parent annotations, "
            "suspicious documents and complete source-candidate pool must be "
            "excluded. Repeat for multiple earlier splits."
        ),
    )
    parser.add_argument(
        "--annotation-type",
        default=None,
        help=(
            "Keep only plagiarism features whose XML type matches (for example "
            "simulated). Applied after prior-split exclusion."
        ),
    )
    parser.add_argument(
        "--max-annotations-per-suspicious-document",
        type=int,
        default=None,
        help=(
            "Keep at most this many positives per suspicious document, chosen "
            "by seeded hash order (default: no cap)."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only the five known generated files if they already exist.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = convert_pan_pilot(
            dataset=args.dataset,
            input_root=args.input_root,
            output_dir=args.output_dir,
            dataset_version=args.dataset_version,
            split_name=args.split_name,
            max_chunk_chars=args.max_chunk_chars,
            max_positive_annotations=args.max_positive_annotations,
            max_candidate_documents=args.max_candidate_documents,
            seed=args.seed,
            max_query_word_tokens=args.max_query_word_tokens,
            query_stride_word_tokens=args.query_stride_word_tokens,
            source_archives=args.source_archive,
            exclude_manifests=args.exclude_manifest,
            overwrite=args.overwrite,
            annotation_type=args.annotation_type,
            max_annotations_per_suspicious_document=(
                args.max_annotations_per_suspicious_document
            ),
        )
    except (FileExistsError, OSError, ValueError) as exc:
        raise SystemExit(f"PAN conversion failed: {exc}") from exc

    print(
        json.dumps(
            {
                "manifest": str(result.manifest_path),
                "documents": result.document_count,
                "chunks": result.chunk_count,
                "queries": result.query_count,
                "qrels": result.qrel_count,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0
