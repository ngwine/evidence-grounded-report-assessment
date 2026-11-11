"""Command-line interface for the two-pipeline offline core MVP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runner import run_core_mvp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        default=[],
        help="Comparison source for Pipeline 1; repeat for multiple files",
    )
    parser.add_argument("--rubric", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--pipeline",
        choices=("similarity", "assessment", "both"),
        default="both",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_core_mvp(
            report_path=args.report,
            source_paths=args.source,
            rubric_path=args.rubric,
            config_path=args.config,
            output_dir=args.output_dir,
            pipeline=args.pipeline,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        json.dumps(
            {
                "summary": result["summary"],
                "output_paths": result["output_paths"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0
