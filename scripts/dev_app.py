"""Manage the local authenticated app with macOS launchd, outside chat sessions.

Uses the existing database and identities. No migrations, seeding, or automatic
login startup: these jobs last for the current macOS login session only.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import plistlib
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "var/runtime/dev-app"
PYTHON = ROOT / ".venv-research/bin/python"
DOMAIN = f"gui/{os.getuid()}"
PREFIX = "vn.kltn.dev." + hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]
SERVICES = ("api", "web", "worker")


def launchctl(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/launchctl", *arguments], capture_output=True, text=True, check=False,
    )


def target(name: str) -> str:
    return f"{DOMAIN}/{PREFIX}.{name}"


def information(name: str) -> dict[str, str]:
    result = launchctl("print", target(name))
    if result.returncode:
        return {"state": "stopped"}
    values = {"state": "loaded"}
    for field in ("state", "pid", "last exit code"):
        match = re.search(rf"^\s*{field} = (.+)$", result.stdout, re.MULTILINE)
        if match:
            values[field] = match.group(1)
    return values


def http_status(port: int, route: str) -> int | None:
    # Always use loopback directly, independent of a shell's HTTP proxy settings.
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(Request(f"http://127.0.0.1:{port}{route}"), timeout=1) as response:
            return response.status
    except HTTPError as error:
        return error.code
    except (URLError, OSError):
        return None


def status() -> None:
    for name in SERVICES:
        value = information(name)
        details = ", ".join(f"{key}={item}" for key, item in value.items())
        print(f"{name}: {details}")
    print(f"Web: http://127.0.0.1:5173 (HTTP {http_status(5173, '/')})")
    print(f"API auth guard: HTTP {http_status(8001, '/api/v1/auth/me')} (401 when logged out)")
    print(f"Web → API proxy: HTTP {http_status(5173, '/api/v1/auth/me')}")
    print(f"Private logs: {STATE}")


def preflight() -> str:
    node = shutil.which("node")
    if not PYTHON.is_file() or not node or not (ROOT / "apps/web/node_modules/vite/bin/vite.js").is_file():
        raise RuntimeError("Install the existing Python/web dependencies first.")
    if launchctl("print", DOMAIN).returncode:
        raise RuntimeError("A macOS GUI login session is required.")
    sys.path.insert(0, str(ROOT))
    from services.backend.src.kltn_ai.api.runtime import connect_from_private_file

    for name, role in (("api", "kltn_api"), ("worker", "kltn_worker")):
        client, _ = connect_from_private_file(
            ROOT / f"var/infra/mongodb/{name}_app-uri", role=role,
        )
        client.close()
    for name, port in (("api", 8001), ("web", 5173)):
        if information(name)["state"] == "stopped":
            with socket.socket() as connection:
                connection.settimeout(1)
                if connection.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"Port {port} is already occupied; leave the existing service untouched.")
    return node


def write_private(destination: Path, content: bytes | None = None) -> None:
    flags = os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW
    flags |= os.O_APPEND if content is None else os.O_TRUNC
    descriptor = os.open(destination, flags, 0o600)
    with os.fdopen(descriptor, "ab" if content is None else "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        if content is not None:
            stream.write(content)


def prepare(node: str) -> None:
    if any(folder.is_symlink() for folder in (ROOT / "var", STATE.parent, STATE)):
        raise RuntimeError("Runtime files must stay inside this checkout.")
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    commands = {
        "api": [str(PYTHON), "-m", "uvicorn",
                "services.backend.src.kltn_ai.api.runtime:create_runtime_app",
                "--factory", "--host", "127.0.0.1", "--port", "8001", "--no-access-log"],
        "web": [node, str(ROOT / "apps/web/node_modules/vite/bin/vite.js"),
                "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        "worker": [str(PYTHON), str(ROOT / "scripts/run_mongo_worker.py"),
                   "--max-idle-polls", "3600"],
    }
    for name in SERVICES:
        output, errors = STATE / f"{name}.out.log", STATE / f"{name}.err.log"
        write_private(output)
        write_private(errors)
        environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONUNBUFFERED": "1"}
        if name == "web":
            environment["VITE_APP_MODE"] = "authenticated"
        if name == "api":
            environment["KLTN_MONGO_URI_FILE"] = str(ROOT / "var/infra/mongodb/api_app-uri")
        if name == "worker":
            environment.update({"HF_HOME": str(ROOT / "var/models/hf-home"),
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "TOKENIZERS_PARALLELISM": "false"})
        value = {
            "Label": f"{PREFIX}.{name}", "ProgramArguments": commands[name],
            "WorkingDirectory": str(ROOT / "apps/web" if name == "web" else ROOT),
            "EnvironmentVariables": environment, "RunAtLoad": True,
            "KeepAlive": True, "ThrottleInterval": 5, "ExitTimeOut": 30,
            "StandardInPath": "/dev/null", "StandardOutPath": str(output),
            "StandardErrorPath": str(errors), "Umask": 0o077,
        }
        write_private(STATE / f"{name}.plist", plistlib.dumps(value))


def stop() -> None:
    for name in reversed(SERVICES):
        if information(name)["state"] != "stopped":
            if launchctl("bootout", target(name)).returncode:
                raise RuntimeError(f"Could not stop {name}; inspect launchd status.")
    print("Stopped this checkout's web, API and worker. MongoDB/data are unchanged.")


def start() -> None:
    node = preflight()
    prepare(node)
    started = []
    try:
        for name in SERVICES:
            if information(name)["state"] == "stopped":
                if launchctl("bootstrap", DOMAIN, str(STATE / f"{name}.plist")).returncode:
                    raise RuntimeError(f"Could not start {name}; inspect private logs at {STATE}.")
                started.append(name)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if (http_status(8001, "/api/v1/auth/me") == 401
                    and http_status(5173, "/") == 200
                    and http_status(5173, "/api/v1/auth/me") == 401
                    and information("worker")["state"] == "running"):
                print("Ready: http://127.0.0.1:5173 (authenticated app)")
                print("Services run independently of this terminal/chat until stopped or macOS logout.")
                status()
                return
            time.sleep(0.5)
        raise RuntimeError(f"Startup did not become healthy; inspect private logs at {STATE}.")
    except BaseException:
        for name in reversed(started):
            launchctl("bootout", target(name))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "restart", "stop"))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This launcher uses macOS launchd; use the documented foreground commands on other systems.")
    try:
        if args.action in {"stop", "restart"}:
            stop()
        if args.action in {"start", "restart"}:
            start()
        if args.action == "status":
            status()
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
