"""Exercise the dedicated Compose replica set; never print its credentials."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import PyMongoError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backend.src.kltn_ai.db.mongo_jobs import MongoJobQueue  # noqa: E402


def restart_recovery(uri: str) -> None:
    name = "kltn_restart_test_" + uuid4().hex
    client = MongoClient(uri, serverSelectionTimeoutMS=2000, tz_aware=True)
    instant = datetime.now(timezone.utc)
    try:
        assert client.admin.command("hello").get("setName") == "kltn-rs"
        queue = MongoJobQueue(client[name].jobs)
        queue.ensure_indexes()
        record = queue.enqueue(
            workspace_id=ObjectId(), job_type="ANALYZE",
            resource_ref={"type": "DOCUMENT", "id": ObjectId(), "version_id": ObjectId()},
            config_ref=None, idempotency_scope="restart-test", idempotency_key="one",
            correlation_id="restart-test", now=instant,
        )
        first = queue.claim(owner="worker-before-restart", lease_seconds=1, now=instant)
        assert first is not None
        subprocess.run(
            ["docker", "compose", "-f", "infra/mongodb/compose.yaml", "restart", "mongo"],
            cwd=ROOT, check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 45
        while True:
            try:
                if client.admin.command("hello").get("isWritablePrimary"):
                    break
            except PyMongoError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("MongoDB primary did not return after restart")
            time.sleep(0.25)
        after = instant + timedelta(seconds=2)
        reclaimed = queue.claim(owner="worker-after-restart", now=after)
        assert reclaimed is not None and reclaimed["_id"] == record["_id"]
        assert reclaimed["attempt"] == 2
        assert queue.complete(job_id=record["_id"], owner="worker-before-restart",
                              revision=first["revision"], now=after) is None
        print("PASS: durable job survived MongoDB restart; expired lease reclaimed; stale worker fenced.")
    finally:
        client.drop_database(name)
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart", action="store_true", help="Restart only the dedicated KLTN Compose Mongo service")
    args = parser.parse_args()
    uri = (ROOT / "var/infra/mongodb/admin-uri").read_text().strip()
    environment = dict(os.environ, KLTN_MONGO_TEST_URI=uri)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "services/backend/tests/test_mongo_jobs_integration.py"],
        cwd=ROOT, env=environment, check=False,
    )
    if result.returncode == 0 and args.restart:
        restart_recovery(uri)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
