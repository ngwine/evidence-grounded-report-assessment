"""Fail closed on npm advisories; retry only bounded transport failures.

Raw npm output is never echoed: it may contain a private registry URL or token.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
NETWORK_CODES = {
    "ECONNRESET", "ECONNREFUSED", "ETIMEDOUT", "ESOCKETTIMEDOUT",
    "EAI_AGAIN", "ENOTFOUND", "EHOSTUNREACH", "ENETUNREACH", "ERR_SOCKET_TIMEOUT",
}
NETWORK_PATTERN = re.compile(r"\b(" + "|".join(sorted(NETWORK_CODES)) + r")\b")


def _high_findings(report: object) -> bool:
    if not isinstance(report, dict):
        return False
    metadata = report.get("metadata")
    counts = metadata.get("vulnerabilities") if isinstance(metadata, dict) else None
    if isinstance(counts, dict) and any(
        type(counts.get(key)) is int and counts[key] > 0 for key in ("high", "critical")
    ):
        return True
    findings = report.get("vulnerabilities")
    return isinstance(findings, dict) and any(
        isinstance(value, dict) and value.get("severity") in ("high", "critical")
        for value in findings.values()
    )


def _counts(report: object) -> dict[str, int] | None:
    if not isinstance(report, dict) or report.get("auditReportVersion") != 2:
        return None
    findings = report.get("vulnerabilities")
    metadata = report.get("metadata")
    counts = metadata.get("vulnerabilities") if isinstance(metadata, dict) else None
    severities = ("info", "low", "moderate", "high", "critical")
    if not isinstance(findings, dict) or not isinstance(counts, dict) or any(
        type(counts.get(key)) is not int or counts[key] < 0 for key in severities
    ):
        return None
    if type(counts.get("total")) is not int or counts["total"] != sum(counts[key] for key in severities):
        return None
    if any(not isinstance(value, dict) or value.get("severity") not in severities
           for value in findings.values()):
        return None
    return {key: counts[key] for key in severities}


def _transport_error(report: object) -> str | None:
    if not isinstance(report, dict):
        return None
    error = report.get("error")
    error = error if isinstance(error, dict) else {}
    # Actual npm HTTP 503 JSON has top-level statusCode and no error.code.
    for status in (report.get("statusCode"), error.get("statusCode")):
        if type(status) is int and 500 <= status <= 599:
            return f"HTTP_{status}"
    for code in (report.get("code"), error.get("code")):
        if isinstance(code, str) and code in NETWORK_CODES:
            return code
    # Some npm versions omit error.code even for ECONNREFUSED. Match only
    # explicit network-code tokens in the JSON message, not generic prose.
    message = report.get("message")
    if isinstance(message, str):
        match = NETWORK_PATTERN.search(message)
        if match:
            return match.group(1)
    return None


def audit_dependencies(
    web_directory: Path,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
    emit: Callable[[str], None] = print,
) -> int:
    """Return 0=clean at high threshold, 1=advisory, 2=no trustworthy audit."""
    command = [
        "npm", "audit", "--json", "--audit-level=high", "--include=dev",
        "--fetch-retries=0", "--fetch-timeout=5000",
    ]
    for attempt in range(1, 4):
        reason = None
        try:
            completed = run(
                command, cwd=web_directory, check=False,
                capture_output=True, text=True, timeout=18,
            )
        except subprocess.TimeoutExpired:
            reason = "PROCESS_TIMEOUT"
        except OSError:
            emit("npm audit unavailable: process could not start; audit NOT passed.")
            return 2
        else:
            try:
                report = json.loads(completed.stdout)
            except (json.JSONDecodeError, TypeError):
                emit("npm audit returned invalid JSON; audit NOT passed.")
                return 2
            # Findings win even if the same payload contains malformed fields
            # or a transport error. No advisory finding is retried or waived.
            if _high_findings(report):
                emit("npm audit FAILED: high/critical advisory found; no retry or waiver applied.")
                return 1
            counts = _counts(report)
            if completed.returncode == 0 and counts is not None and not any(
                field in report for field in ("error", "statusCode", "code")
            ):
                emit(
                    "npm audit PASSED at high/critical threshold (including dev): "
                    f"high=0, critical=0, moderate={counts['moderate']}, low={counts['low']}."
                )
                return 0
            # An otherwise valid report with an unexplained nonzero exit must
            # not be reclassified as a transient network failure.
            reason = _transport_error(report) if counts is None else None
        if reason is None:
            emit("npm audit failed without a recognized transport error; audit NOT passed.")
            return 2
        emit(f"npm audit transport failure {reason}; attempt {attempt}/3.")
        if attempt < 3:
            sleep(float(attempt))
    emit("npm audit transport retries exhausted; audit NOT passed (blocking failure).")
    return 2


def main() -> int:
    return audit_dependencies(ROOT / "apps/web")


if __name__ == "__main__":
    sys.exit(main())
