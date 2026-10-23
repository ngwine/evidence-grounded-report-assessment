"""Ephemeral self-authored browser fixture; never run against real user data.

Opt-in test bootstrap only. Creates its own random database/users and removes
only those on exit. API/worker then use scoped identities, never the admin URI.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
from uuid import uuid4

from bson import ObjectId
from pymongo import MongoClient
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backend.src.kltn_ai.api.app import create_app  # noqa: E402
from services.backend.src.kltn_ai.auth.service import create_local_user  # noqa: E402
from services.backend.src.kltn_ai.db.migrations import apply_schema_v1  # noqa: E402
from services.backend.src.kltn_ai.db.application_schema import apply_schema_v2  # noqa: E402
from services.backend.src.kltn_ai.db.document_schema import apply_schema_v3  # noqa: E402
from services.backend.src.kltn_ai.db.analysis_schema import apply_schema_v4  # noqa: E402
from services.backend.src.kltn_ai.db.roles import provision_roles  # noqa: E402
from services.backend.src.kltn_ai.domain.documents import _common  # noqa: E402
from services.backend.src.kltn_ai.domain.rubrics import RubricService  # noqa: E402
from services.backend.src.kltn_ai.worker.mongo_worker import MongoParseWorker  # noqa: E402
from services.backend.src.kltn_ai.worker.mongo_index_worker import MongoIndexWorker  # noqa: E402
from services.backend.src.kltn_ai.worker.mongo_analysis_worker import (  # noqa: E402
    MongoAnalysisWorker,
)

WORKSPACE = ObjectId("000000000000000000000101")


def main():
    if os.environ.get("KLTN_RUN_AUTH_MONGO_E2E") != "1":
        raise SystemExit("Opt-in required: KLTN_RUN_AUTH_MONGO_E2E=1")
    from urllib.parse import urlsplit

    uri = (ROOT / "var/infra/mongodb/admin-uri").read_text().strip()
    if urlsplit(uri).hostname != "127.0.0.1":
        raise SystemExit("Dedicated loopback test deployment required")
    admin = MongoClient(
        uri, tz_aware=True, serverSelectionTimeoutMS=3000, timeoutMS=30000
    )
    database_name = "kltn_browser_test_" + uuid4().hex
    db = admin[database_name]
    runtime_clients = []
    try:
        for migrate in (
            apply_schema_v1,
            apply_schema_v2,
            apply_schema_v3,
            apply_schema_v4,
        ):
            migrate(db, code_commit="0" * 40, applied_by="synthetic-browser-fixture")
        now = datetime.now(UTC)
        actor = ObjectId(
            create_local_user(
                db,
                "browser@example.invalid",
                "Synthetic browser lecturer",
                "Browser-Fixture-Only-Password",
            )["id"]
        )
        common = _common(actor, now)
        db.workspaces.insert_one(
            {
                "_id": WORKSPACE,
                **common,
                "workspace_key": "browser-fixture",
                "name": "Browser fixture",
                "kind": "RESEARCH",
                "status": "ACTIVE",
                "default_purpose": "SYNTHETIC_BROWSER_TEST",
            }
        )
        db.memberships.insert_one(
            {
                "_id": ObjectId(),
                **common,
                "workspace_id": WORKSPACE,
                "user_id": actor,
                "roles": ["LECTURER"],
                "status": "ACTIVE",
                "valid_from": None,
                "valid_until": None,
            }
        )
        for suffix in ("201", "202"):
            db.governance_records.insert_one(
                {
                    "_id": ObjectId("0" * 21 + suffix),
                    **common,
                    "workspace_id": WORKSPACE,
                    "resource_type": "DOCUMENT",
                    "resource_id": ObjectId(),
                    "record_version": 1,
                    "data_owner": {"kind": "SYNTHETIC_FIXTURE"},
                    "rights_basis": "INTERNAL_APPROVAL",
                    "license_id": None,
                    "rights_evidence": {"kind": "SELF_AUTHORED_TEST_BYTES_ONLY"},
                    "allowed_purposes": ["SYNTHETIC_BROWSER_TEST"],
                    "redistribution": "ALLOWED",
                    "data_class": "INTERNAL",
                    "anonymization": {"required": False},
                    "retention_policy": {},
                    "approver_id": actor,
                    "approved_at": now,
                    "valid_from": None,
                    "valid_until": None,
                    "status": "APPROVED",
                }
            )
        rubric_service = RubricService(db)
        rubric = rubric_service.create(
            actor,
            WORKSPACE,
            {
                "rubric_key": "browser-rubric",
                "title": "Browser fixture rubric",
                "definition": {
                    "max_score": 10,
                    "criteria": [
                        {
                            "criterion_key": "C1",
                            "title": "Benchmark",
                            "weight": 10,
                            "scoring_mode": "PROPORTIONAL_CHECKLIST_V0",
                            "checklists": [
                                {
                                    "checklist_key": "C1.1",
                                    "statement": "Presents measured benchmark evidence",
                                    "evidence_mode": "LOCAL",
                                    "requirements": [
                                        {
                                            "requirement_id": "R1",
                                            "any_of": ["benchmark"],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            },
            idempotency_key="browser-rubric-create",
            request_id="browser-fixture",
        )
        rubric_service.publish_version(
            actor,
            WORKSPACE,
            rubric["current_version_id"],
            expected_revision=1,
            idempotency_key="browser-rubric-publish",
            request_id="browser-fixture",
        )
        provision_roles(db)
        for role in ("api", "worker"):
            secret = secrets.token_urlsafe(24)
            db.command(
                "createUser",
                "browser_" + role,
                pwd=secret,
                roles=[{"role": "kltn_" + role, "db": database_name}],
            )
            host, port = admin.address
            runtime_clients.append(
                MongoClient(
                    host=host,
                    port=port,
                    username="browser_" + role,
                    password=secret,
                    authSource=database_name,
                    directConnection=True,
                    tz_aware=True,
                    serverSelectionTimeoutMS=3000,
                    timeoutMS=30000,
                )
            )
        with tempfile.TemporaryDirectory(prefix="kltn-browser-private-") as folder:
            storage = Path(folder)
            workers = [
                kind(runtime_clients[1][database_name], storage)
                for kind in (MongoParseWorker, MongoIndexWorker, MongoAnalysisWorker)
            ]
            stop = threading.Event()

            def work():
                while not stop.is_set():
                    try:
                        did_work = any(worker.process_one() for worker in workers)
                    except Exception:
                        # Test surfaces a missing result; never log credentials/content.
                        print("Synthetic worker failed safely", flush=True)
                        return
                    if not did_work:
                        stop.wait(0.1)

            thread = threading.Thread(target=work, daemon=True)
            app = create_app(runtime_clients[0][database_name], private_root=storage)

            @asynccontextmanager
            async def lifespan(_app):
                thread.start()
                try:
                    yield
                finally:
                    stop.set()
                    thread.join(timeout=15)

            app.router.lifespan_context = lifespan
            uvicorn.run(
                app, host="127.0.0.1", port=8001, log_level="error", access_log=False
            )
    finally:
        for client in runtime_clients:
            client.close()
        for user in db.command("usersInfo")["users"]:
            db.command("dropUser", user["user"])
        for role in db.command("rolesInfo")["roles"]:
            db.command("dropRole", role["role"])
        admin.drop_database(database_name)
        admin.close()


if __name__ == "__main__":
    main()
