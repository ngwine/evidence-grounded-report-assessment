"""Parser process budgets must reject incomplete work and preserve provenance."""

from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from research.core_mvp import bounded_documents as module
from research.core_mvp.bounded_documents import ParseLimits, ParserRejected, parse_document_bounded
from research.core_mvp.documents import parse_document


FIXTURE = Path(__file__).parent / "fixtures/core_mvp/report.txt"


def test_child_parser_matches_direct_provenance_and_records_enforced_limits():
    direct = parse_document(FIXTURE, role="student-report", max_tokens=80, min_tokens=1)
    bounded = parse_document_bounded(FIXTURE, role="student-report", max_tokens=80, min_tokens=1)
    assert bounded.elements == direct.elements
    assert bounded.chunks == direct.chunks
    assert bounded.document["sha256"] == direct.document["sha256"]
    assert bounded.document["parser_resource_limits"]["process_isolated"] is True


def test_output_and_text_budgets_produce_no_successful_partial_document(tmp_path):
    path = tmp_path / "report.txt"
    path.write_text("This is more than five characters.", encoding="utf-8")
    with pytest.raises(ParserRejected, match="PARSER_RESOURCE_LIMIT"):
        parse_document_bounded(path, role="student-report", min_tokens=1,
                               limits=replace(ParseLimits(), max_text_chars=5))
    with pytest.raises(ParserRejected, match="PARSER_INPUT_LIMIT"):
        parse_document_bounded(path, role="student-report",
                               limits=replace(ParseLimits(), max_input_bytes=5))


def test_wall_timeout_and_child_failure_are_safe_errors(monkeypatch):
    def expired(*args, **kwargs):
        raise subprocess.TimeoutExpired("parser", 1)
    monkeypatch.setattr(module.subprocess, "run", expired)
    with pytest.raises(ParserRejected, match="PARSER_WALL_TIMEOUT"):
        parse_document_bounded(FIXTURE, role="student-report")
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 65))
    with pytest.raises(ParserRejected, match="PARSER_REJECTED"):
        parse_document_bounded(FIXTURE, role="student-report")


def test_invalid_limits_reject_boolean_nonfinite_and_unknown_values():
    for config in ({"wall_seconds": float("nan")}, {"cpu_seconds": True},
                   {"unknown": 1}, {"max_text_chars": -1}):
        with pytest.raises(ValueError):
            ParseLimits.from_config(config)
