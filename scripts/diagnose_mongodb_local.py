"""Allowlisted Docker failure diagnostics; never publish raw Mongo logs/env."""

from __future__ import annotations

import json
import re
import subprocess


CONTAINER = "kltn-evidence-db-mongo-1"
PATTERNS = {
    "FILE_PERMISSION_DENIED": r"(?i)permission denied|operation not permitted",
    "INVALID_RUNTIME_IDENTITY": r"(?i)invalid (?:user|group)|unknown user",
    "SECRET_FILE_NOT_FOUND": r"(?i)(?:install|root_user|root_password|replica_key).*no such file",
    "SECRET_FILE_PERMISSIONS": r"(?i)permissions.*too open|bad permissions",
    "CPU_INSTRUCTION_UNSUPPORTED": r"(?i)requires.*AVX|illegal instruction|requires ARMv8",
    "KEYFILE_OR_SECURITY_FAILURE": r"(?i)unable to acquire security key|error reading file|bad key",
    "MONGO_ENTRYPOINT_STARTED": r"(?i)MongoDB init process complete|about to fork child process",
    "MONGO_INIT_AUTH_CONFIGURATION": r"(?i)missing.*MONGO_INITDB|both.*(?:must|are set)",
}


def summarize(log: str) -> dict[str, object]:
    categories = sorted(name for name, pattern in PATTERNS.items() if re.search(pattern, log))
    fatal_ids: set[int] = set()
    for line in log.splitlines():
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(record, dict) and record.get("s") in {"E", "F"} and type(record.get("id")) is int:
            fatal_ids.add(record["id"])
    if 12257600 in fatal_ids:
        categories.append("KERNEL_TCMALLOC_RSEQ_GUARD")
    return {"recognized_categories": categories, "mongo_error_event_ids": sorted(fatal_ids)}


def main() -> int:
    # Never inspect Config.Env, health command output or arbitrary containers.
    state = subprocess.run(
        ["docker", "inspect", "--format", "{{json .State}}", CONTAINER],
        capture_output=True, text=True, check=False, timeout=10,
    )
    summary: dict[str, object] = {"container": CONTAINER}
    try:
        value = json.loads(state.stdout)
    except ValueError:
        value = {}
    if isinstance(value, dict):
        for source, target, expected in (("ExitCode", "exit_code", int),
                                         ("OOMKilled", "oom_killed", bool)):
            if type(value.get(source)) is expected:
                summary[target] = value[source]
        if value.get("Status") in {"created", "running", "paused", "restarting", "removing", "exited", "dead"}:
            summary["status"] = value["Status"]
    logs = subprocess.run(["docker", "logs", "--tail", "200", CONTAINER],
                          capture_output=True, text=True, check=False, timeout=10)
    summary.update(summarize(logs.stdout + "\n" + logs.stderr))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
