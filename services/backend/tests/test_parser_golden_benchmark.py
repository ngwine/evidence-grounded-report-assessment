"""Acceptance tests for the reviewed W4.6 golden manifest."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_parser_chunking import DEFAULT_MANIFEST, run_benchmark  # noqa: E402


def test_golden_manifest_matches_and_three_runs_are_deterministic():
    report = run_benchmark(DEFAULT_MANIFEST, runs=3)

    assert report["benchmark_id"] == "parser-chunker-golden-v1"
    assert len(report["fixtures"]) == 2
    for fixture in report["fixtures"]:
        assert fixture["deterministic_runs"] == 3
        assert fixture["summary"]["coverage"]["coverage_ratio"] == 1.0
        assert fixture["summary"]["coverage"]["error_count"] == 0
        assert fixture["timing_ms"]["min"] > 0
        assert fixture["peak_memory_bytes"]["max"] > 0
