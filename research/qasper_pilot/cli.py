"""CLI for the within-paper QASPER LOCAL evidence diagnostic."""

from __future__ import annotations

import argparse
from pathlib import Path

from .benchmark import run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("var/datasets/raw/qasper-v0.3/qasper-dev-v0.3.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("research/results/rq2-qasper/local-paragraph-dev-v03-p40-s20261018"))
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument("--max-papers", type=int, default=40)
    parser.add_argument("--dense", action="store_true", help="Also run cached multilingual E5-small and BM25+E5 RRF")
    args = parser.parse_args()
    result = run_benchmark(input_path=args.input, output_dir=args.output_dir, seed=args.seed, max_papers=args.max_papers, dense=args.dense)
    coverage = result["coverage"]
    print(f"QASPER papers={result['scope']['papers_selected']} questions={coverage['questions_total']} evaluable={coverage['questions_evaluable']}")
    for name, method in result["methods"].items():
        row = method["macro"]["10"]
        print(f"{name}: hit@10={row['hit']:.4f} best_annotator_recall@10={row['best_annotation_recall']:.4f} complete@10={row['complete_annotation']:.4f}")
    print(f"Aggregate artifacts: {args.output_dir / 'metrics.json'}, {args.output_dir / 'run_manifest.json'}")
    return 0
