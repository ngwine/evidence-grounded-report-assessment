"""Run the real localhost API and worker for synthetic browser E2E only.

Playwright owns this process. It creates a private temporary LocalStore, approves
only the checked-in synthetic source fixture, and terminates its own children
when Playwright stops. No user report, model cache, or existing var/ is touched.
"""

from __future__ import annotations

import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research/tests/fixtures/core_mvp/source-overlap.txt"
HOST = "127.0.0.1"
PORT = 8001  # Vite's existing loopback proxy target.
STOP = False


def _signal_stop(_number: int, _frame: object) -> None:
    global STOP
    STOP = True


def _port_in_use() -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((HOST, PORT)) == 0


def _terminate(children: list[subprocess.Popen[bytes]]) -> None:
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def main() -> int:
    if _port_in_use():
        print(f"Refusing to reuse occupied {HOST}:{PORT}", file=sys.stderr)
        return 2
    if not SOURCE.is_file():
        print(f"Missing committed synthetic source fixture: {SOURCE}", file=sys.stderr)
        return 2
    signal.signal(signal.SIGTERM, _signal_stop)
    signal.signal(signal.SIGINT, _signal_stop)
    children: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="kltn-e2e-") as temporary:
        root = Path(temporary)
        subprocess.run(
            [
                sys.executable, "-m", "services.backend.src.kltn_ai.local_approvals",
                "--root", str(root), "approve-source", str(SOURCE),
                "--approver", "synthetic-e2e-harness",
                "--rationale", "Repository-authored synthetic fixture; private browser test only",
                "--attest-rights",
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        env = os.environ.copy()
        env.update({
            "KLTN_LOCAL_APP_ROOT": str(root),
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
        })
        try:
            children.append(subprocess.Popen(
                [
                    sys.executable, "-m", "services.backend.src.kltn_ai.worker.local_worker",
                    "--root", str(root), "--poll-seconds", "0.1",
                ],
                cwd=ROOT, env=env,
            ))
            children.append(subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "services.backend.src.kltn_ai.api.local_app:app",
                    "--host", HOST, "--port", str(PORT), "--no-access-log",
                ],
                cwd=ROOT, env=env,
            ))
            deadline = time.monotonic() + 60
            while not STOP and time.monotonic() < deadline:
                if any(child.poll() is not None for child in children):
                    raise RuntimeError("E2E API or worker exited during startup")
                try:
                    with urlopen(f"http://{HOST}:{PORT}/api/local/v1/health", timeout=1) as response:
                        if response.status == 200:
                            print("Synthetic local API and worker ready", flush=True)
                            break
                except (OSError, URLError):
                    pass
                time.sleep(0.1)
            else:
                if not STOP:
                    raise TimeoutError("Synthetic local API did not become healthy")
            while not STOP:
                if any(child.poll() is not None for child in children):
                    raise RuntimeError("E2E API or worker exited unexpectedly")
                time.sleep(0.2)
        finally:
            _terminate(children)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
