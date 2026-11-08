"""Manage this checkout's local P2 model service with macOS launchd.

This launcher does not install software or download models. The dedicated
binary, model directory, loopback port and job identity are independent of
the existing app and any Ollama service on port 11434.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "var/runtime/dev-p2-llm"
BINARY = ROOT / "var/runtime/ollama-v0.40.13/ollama"
MODELS = ROOT / "var/models/ollama-p2"
HOST = "127.0.0.1:11435"
ENDPOINT = "http://" + HOST
RELEASE = "0.40.13"
EXPECTED_BINARY_SHA256 = "270089e59e1d411ac4d0987154b4e95f48b29a81c9d274833c6b766d6df88300"
DOMAIN = f"gui/{os.getuid()}"
LABEL = "vn.kltn.p2-llm." + hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]
TARGET = DOMAIN + "/" + LABEL
PLIST = STATE / "ollama.plist"


def launchctl(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["/bin/launchctl", *arguments], capture_output=True,
                          text=True, check=False, timeout=10)


def _safe_path(path: Path) -> None:
    relative = path.relative_to(ROOT)
    current = ROOT
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            raise RuntimeError("P2 runtime paths must not contain symlinks.")


def _verify_binary() -> None:
    _safe_path(BINARY)
    if (not BINARY.is_file() or not os.access(BINARY, os.X_OK)
            or BINARY.stat().st_mode & 0o022):
        raise RuntimeError("Install the verified project-local Ollama binary before starting P2.")
    checksum = hashlib.sha256()
    with BINARY.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    if checksum.hexdigest() != EXPECTED_BINARY_SHA256:
        raise RuntimeError("Project-local Ollama binary checksum does not match the pinned release.")


def _job() -> tuple[dict[str, str], str]:
    result = launchctl("print", TARGET)
    if result.returncode:
        return {"state": "stopped"}, ""
    values = {"state": "loaded"}
    for field in ("state", "pid", "last exit code"):
        match = re.search(rf"^\s*{field} = (.+)$", result.stdout, re.MULTILINE)
        if match:
            values[field] = match.group(1).strip()
    return values, result.stdout


def _owned(output: str) -> bool:
    def field(name):
        match = re.search(rf"^\s*{name} = (.+)$", output, re.MULTILINE)
        return match.group(1).strip().strip('"') if match else None
    arguments = re.search(r"^\s*arguments = \{\s*\n(.*?)^\s*\}", output, re.MULTILINE | re.DOTALL)
    args = [line.strip().strip('"') for line in arguments.group(1).splitlines() if line.strip()] if arguments else []
    return (field("path") == str(PLIST) and field("program") == str(BINARY)
            and args == [str(BINARY), "serve"]
            and re.search(rf"^\s*OLLAMA_HOST => {re.escape(HOST)}\s*$", output, re.MULTILINE) is not None
            and re.search(rf"^\s*OLLAMA_MODELS => {re.escape(str(MODELS))}\s*$", output, re.MULTILINE) is not None)


def _listener_pids() -> set[str]:
    result = subprocess.run(["/usr/sbin/lsof", "-nP", "-iTCP:11435", "-sTCP:LISTEN", "-t"],
                            capture_output=True, text=True, check=False, timeout=5)
    if result.returncode not in (0, 1):
        raise RuntimeError("Cannot verify ownership of the dedicated P2 port.")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _ownership_guard(job: dict[str, str], output: str) -> None:
    if output and not _owned(output):
        raise RuntimeError("The P2 launchd label belongs to another configuration; it was left untouched.")
    listeners = _listener_pids()
    if listeners and (not output or listeners != {job.get("pid")}):
        raise RuntimeError("Port 11435 has a foreign listener; it was left untouched.")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise URLError("Local model metadata redirects are not allowed")


def metadata(route: str) -> dict | None:
    if route not in ("/api/version", "/api/tags"):
        raise ValueError("Only model metadata routes are supported")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(Request(ENDPOINT + route), timeout=2) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return None
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (OSError, URLError, ValueError):
        return None


def _write_private(path: Path, content: bytes | None = None) -> None:
    _safe_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_APPEND if content is None else os.O_TRUNC)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "ab" if content is None else "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        if content is not None:
            stream.write(content)


def prepare() -> None:
    _safe_path(STATE)
    _safe_path(MODELS)
    for folder in (STATE, MODELS):
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        folder.chmod(0o700)
    output, errors = STATE / "ollama.out.log", STATE / "ollama.err.log"
    _write_private(output)
    _write_private(errors)
    settings = {
        "Label": LABEL, "ProgramArguments": [str(BINARY), "serve"], "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {"PATH": str(BINARY.parent) + ":/usr/bin:/bin:/usr/sbin:/sbin",
            "OLLAMA_HOST": HOST, "OLLAMA_MODELS": str(MODELS), "OLLAMA_NO_CLOUD": "1",
            "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_NUM_PARALLEL": "1",
            "OLLAMA_MAX_QUEUE": "1", "LLAMA_ARG_CACHE_RAM": "0",
            "OLLAMA_CONTEXT_LENGTH": "16384", "OLLAMA_KEEP_ALIVE": "60s"},
        "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 5,
        "ExitTimeOut": 20, "Umask": 0o077, "StandardInPath": "/dev/null",
        "StandardOutPath": str(output), "StandardErrorPath": str(errors),
    }
    _write_private(PLIST, plistlib.dumps(settings))


def status() -> None:
    job, output = _job()
    ownership = "owned" if output and _owned(output) else "unmanaged" if output else "not loaded"
    version, tags = metadata("/api/version"), metadata("/api/tags")
    model_items = (tags or {}).get("models", [])
    model_items = model_items if isinstance(model_items, list) else []
    models = [{"name": item.get("name"), "digest": item.get("digest"), "size": item.get("size")}
              for item in model_items[:32] if isinstance(item, dict)]
    print(json.dumps({"job": job, "ownership": ownership, "endpoint": ENDPOINT,
                      "version": (version or {}).get("version"), "models": models,
                      "private_logs": str(STATE)}, ensure_ascii=False, indent=2))


def start() -> None:
    _verify_binary()
    for path in (STATE, MODELS, PLIST):
        _safe_path(path)
    if launchctl("print", DOMAIN).returncode:
        raise RuntimeError("A macOS GUI login session is required.")
    job, output = _job()
    _ownership_guard(job, output)
    created = False
    if not output:
        prepare()
        if launchctl("bootstrap", DOMAIN, str(PLIST)).returncode:
            raise RuntimeError("Could not start the dedicated P2 model service; inspect its private logs.")
        created = True
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            current, details = _job()
            _ownership_guard(current, details)
            version = metadata("/api/version")
            if version and version.get("version") == RELEASE:
                print(f"Ready: {ENDPOINT} (Ollama {RELEASE}, project-local models)")
                print("Model download is separate; this command did not pull a model.")
                return
            if version and version.get("version") != RELEASE:
                raise RuntimeError("The dedicated port returned a different Ollama release.")
            time.sleep(0.5)
        raise RuntimeError("P2 model service did not become ready within 30 seconds; inspect private logs.")
    except BaseException:
        if created:
            current, details = _job()
            if details and _owned(details):
                launchctl("bootout", TARGET)
        raise


def stop() -> None:
    _safe_path(PLIST)
    job, output = _job()
    _ownership_guard(job, output)
    if output and launchctl("bootout", TARGET).returncode:
        raise RuntimeError("Could not stop this checkout's P2 model job.")
    print("Stopped this checkout's P2 model job; model files and other services are unchanged.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "stop", "restart"))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This launcher requires a macOS GUI login session.")
    try:
        if args.action in {"stop", "restart"}:
            stop()
        if args.action in {"start", "restart"}:
            start()
        if args.action == "status":
            status()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
