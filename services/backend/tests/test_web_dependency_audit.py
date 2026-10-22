"""Offline audit-gate behavior; no test depends on advisory-service uptime."""

import json
from pathlib import Path
import subprocess

import pytest

from scripts.audit_web_dependencies import audit_dependencies


def _report(*, high: int = 0, critical: int = 0, moderate: int = 0) -> dict:
    return {
        "auditReportVersion": 2, "vulnerabilities": {},
        "metadata": {"vulnerabilities": {
            "info": 0, "low": 0, "moderate": moderate, "high": high,
            "critical": critical, "total": high + critical + moderate,
        }},
    }


def _response(report: object, status: int = 1) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["npm"], status, json.dumps(report), "private stderr")


def _exercise(responses: list) -> tuple[int, list, list, list[str]]:
    calls: list = []
    delays: list = []
    messages: list[str] = []

    def fake_run(command: list, **options: object) -> subprocess.CompletedProcess:
        calls.append((command, options))
        value = responses[len(calls) - 1]
        if isinstance(value, BaseException):
            raise value
        return value

    status = audit_dependencies(
        Path("apps/web"), run=fake_run, sleep=delays.append, emit=messages.append,
    )
    return status, calls, delays, messages


def test_clean_audit_includes_dev_and_bounded_npm_network_requests() -> None:
    status, calls, delays, messages = _exercise([_response(_report(), 0)])
    assert status == 0 and len(calls) == 1 and not delays
    command, options = calls[0]
    assert {"--json", "--audit-level=high", "--include=dev", "--fetch-retries=0",
            "--fetch-timeout=5000"} <= set(command)
    assert options == {
        "cwd": Path("apps/web"), "check": False, "capture_output": True,
        "text": True, "timeout": 18,
    }
    assert "PASSED" in messages[0]


def test_moderate_findings_do_not_fail_high_critical_policy() -> None:
    status, _, _, messages = _exercise([_response(_report(moderate=2), 0)])
    assert status == 0 and "moderate=2" in messages[0]


@pytest.mark.parametrize("severity", ["high", "critical"])
@pytest.mark.parametrize("returncode", [0, 1])
def test_real_findings_fail_without_retry_even_with_transport_fields(
    severity: str, returncode: int,
) -> None:
    report = _report(**{severity: 1})
    report["statusCode"] = 503
    status, calls, delays, messages = _exercise([_response(report, returncode)])
    assert status == 1 and len(calls) == 1 and not delays
    assert "FAILED" in messages[0]


def test_advisory_cannot_be_hidden_by_incomplete_metadata() -> None:
    report = {"vulnerabilities": {"example": {"severity": "critical"}}, "statusCode": 503}
    status, calls, _, _ = _exercise([_response(report)])
    assert status == 1 and len(calls) == 1


def test_high_metadata_cannot_be_hidden_by_malformed_report() -> None:
    report = {"metadata": {"vulnerabilities": {"high": 1}}, "statusCode": 503}
    status, calls, _, _ = _exercise([_response(report)])
    assert status == 1 and len(calls) == 1


def test_actual_npm_http_503_shape_retries_then_succeeds_without_raw_errors() -> None:
    # Captured shape from actual npm audit against a local HTTP 503 fixture.
    unavailable = {
        "message": "503 Service Unavailable - POST https://token:secret@private.invalid/audit",
        "method": "POST", "uri": "https://token:secret@private.invalid/audit",
        "statusCode": 503, "body": {"error": "Service Unavailable"},
        "error": {"summary": "", "detail": ""},
    }
    status, calls, delays, messages = _exercise([
        _response(unavailable), _response(_report(), 0),
    ])
    assert status == 0 and len(calls) == 2 and delays == [1.0]
    assert "HTTP_503" in messages[0]
    assert all(token not in " ".join(messages) for token in ("secret", "private.invalid", "stderr"))


@pytest.mark.parametrize("report", [
    {"error": {"code": "ETIMEDOUT"}}, {"code": "ECONNRESET"},
    {"message": "request failed, reason: connect ECONNREFUSED private.invalid:443",
     "error": {"summary": "", "detail": ""}},
    {"error": {"statusCode": 502}},
])
def test_recognized_transport_failures_are_bounded_and_finally_block(report: dict) -> None:
    status, calls, delays, messages = _exercise([_response(report)] * 3)
    assert status == 2 and len(calls) == 3 and delays == [1.0, 2.0]
    assert "exhausted" in messages[-1] and "NOT passed" in messages[-1]
    assert "private.invalid" not in " ".join(messages)


def test_subprocess_timeout_is_bounded_and_can_recover() -> None:
    timeout = subprocess.TimeoutExpired(["npm"], 18, output="private output")
    status, calls, delays, messages = _exercise([timeout, _response(_report(), 0)])
    assert status == 0 and len(calls) == 2 and delays == [1.0]
    assert "PROCESS_TIMEOUT" in messages[0]
    assert "private output" not in " ".join(messages)


@pytest.mark.parametrize("report", [
    {"statusCode": 401}, {"statusCode": 403}, {"statusCode": 429},
    {"error": {"code": "ENOLOCK"}}, {"message": "some arbitrary 503 text"},
    {"message": "NOT_ECONNRESET"}, {}, [], None,
])
def test_auth_configuration_unknown_and_non_5xx_errors_never_retry(report: object) -> None:
    status, calls, delays, _ = _exercise([_response(report)])
    assert status == 2 and len(calls) == 1 and not delays


@pytest.mark.parametrize("stdout", ["not json", "", '{"auditReportVersion":2}'])
def test_malformed_output_never_counts_as_success_or_retry(stdout: str) -> None:
    response = subprocess.CompletedProcess(["npm"], 0, stdout, "private error")
    status, calls, delays, _ = _exercise([response])
    assert status == 2 and len(calls) == 1 and not delays


def test_valid_audit_with_unexplained_nonzero_status_does_not_retry() -> None:
    report = _report()
    status, calls, delays, _ = _exercise([_response(report)])
    assert status == 2 and len(calls) == 1 and not delays


@pytest.mark.parametrize("field,value", [("total", 1), ("high", "0"), ("critical", False)])
def test_malformed_or_inconsistent_counts_never_pass(field: str, value: object) -> None:
    report = _report()
    report["metadata"]["vulnerabilities"][field] = value
    status, calls, delays, _ = _exercise([_response(report, 0)])
    assert status == 2 and len(calls) == 1 and not delays


@pytest.mark.parametrize("field,value", [
    ("error", {"code": "UNKNOWN"}), ("statusCode", 503), ("code", "ECONNRESET"),
])
def test_error_payload_never_passes_even_with_successful_exit_and_valid_metadata(
    field: str, value: object,
) -> None:
    report = _report()
    report[field] = value
    status, calls, delays, _ = _exercise([_response(report, 0)])
    assert status == 2 and len(calls) == 1 and not delays


def test_npm_not_installed_is_blocking_without_retry_or_exception_text() -> None:
    status, calls, delays, messages = _exercise([FileNotFoundError("private/path/npm")])
    assert status == 2 and len(calls) == 1 and not delays
    assert "private/path" not in " ".join(messages)
