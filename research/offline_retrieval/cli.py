"""Command-line entry point for offline retrieval experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from .dense import local_model_revision
from .runner import run_experiment, validate_inputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate governance, checksums and config")
    validate.add_argument("--dataset-manifest", type=Path, required=True)
    validate.add_argument("--config", type=Path, required=True)

    run = subparsers.add_parser(
        "run", help="Run the retrieval/reranking variants selected in config"
    )
    run.add_argument("--dataset-manifest", type=Path, required=True)
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)

    checksum = subparsers.add_parser(
        "model-checksum", help="Compute the revision string for a local Dense model"
    )
    checksum.add_argument("--model-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            loaded = validate_inputs(args.dataset_manifest, args.config)
            print(
                f"OK: {loaded['dataset_manifest']['dataset_id']}@"
                f"{loaded['dataset_manifest']['dataset_version']}"
            )
            return 0
        if args.command == "model-checksum":
            print(local_model_revision(args.model_dir))
            return 0
        result = run_experiment(args.dataset_manifest, args.config, args.output_dir)
        print(result["run_manifest_path"])
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
