"""Provision dedicated local identities and apply the versioned schema.

Administrative bootstrap only. Do not pass credentials in CLI arguments.
Pause API/worker and terminate any previous migrator before running this.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from urllib.parse import quote, urlsplit, urlunsplit

from pymongo import MongoClient
from pymongo.errors import PyMongoError


ROOT = Path(__file__).resolve().parents[1]
SECRET_ROOT = ROOT / "var/infra/mongodb"
sys.path.insert(0, str(ROOT))
from services.backend.src.kltn_ai.db.migrations import (  # noqa: E402
    MigrationError, _check_indexes, apply_schema_v1, schema_checksum,
)
from services.backend.src.kltn_ai.db.application_schema import apply_schema_v2  # noqa: E402
from services.backend.src.kltn_ai.db.document_schema import apply_schema_v3  # noqa: E402
from services.backend.src.kltn_ai.db.analysis_schema import (  # noqa: E402
    INDEXES_V4, VALIDATORS_V4, apply_schema_v4,
)
from services.backend.src.kltn_ai.db.annotation_schema import apply_schema_v5  # noqa: E402
from services.backend.src.kltn_ai.db.semantic_analysis_schema import (  # noqa: E402
    INDEXES_V6, MIGRATION_ID_V6, VALIDATORS_V6, apply_schema_v6,
)
from services.backend.src.kltn_ai.db.semantic_runtime_schema import (  # noqa: E402
    INDEXES_V7, MIGRATION_ID_V7, VALIDATORS_V7, apply_schema_v7,
)
from services.backend.src.kltn_ai.db.llm_assessment_schema import (  # noqa: E402
    INDEXES_V8, MIGRATION_ID_V8, VALIDATORS_V8, apply_schema_v8,
)
from services.backend.src.kltn_ai.db.llm_assessment_v2_schema import (  # noqa: E402
    INDEXES_V9, MIGRATION_ID_V9, VALIDATORS_V9, apply_schema_v9,
)
from services.backend.src.kltn_ai.db.roles import provision_roles  # noqa: E402


_V4_MIGRATION_ID = "004-index-and-analysis-results-v1"


def _verify_applied_entry(database, migration_id: str, validators, indexes) -> None:
    entry = database.schema_migrations.find_one({"_id": migration_id})
    if (entry is None or entry.get("kind") != "ENTRY" or entry.get("status") != "APPLIED"
            or entry.get("checksum") != schema_checksum(validators, indexes)):
        raise MigrationError("Applied migration ledger identity/checksum does not match its locked catalog")


def _verify_catalog(database, validators, indexes) -> None:
    """Read current document/validator/index state without reinstalling an old catalog."""
    names = set(database.list_collection_names())
    for name, validator in validators.items():
        if name not in names:
            raise MigrationError(f"Missing expected collection in {name}")
        collection = database[name]
        if collection.find_one({"$nor": [validator]}, projection={"_id": 1}, max_time_ms=30000) is not None:
            raise MigrationError(f"Existing documents fail validator in {name}; no automatic repair")
        options = collection.options()
        if (options.get("validator") != validator or options.get("validationLevel") != "strict"
                or options.get("validationAction") != "error"):
            raise MigrationError(f"Validator read-back failed in {name}")
        _check_indexes(database, name, require_all=True, indexes=indexes)


def apply_schema_chain(database, *, code_commit: str, applied_by: str):
    """Apply schemas without narrowing an already-applied V6/V7/V8/V9 successor.

    V6 only expands three V4 config enums. Reinstalling V4 would reject current
    NLI/RRF documents or temporarily narrow their validators. Its original
    catalog and ledger remain immutable: verify the predecessor identity, then
    use the latest effective catalog for those three collections. V7 likewise
    supersedes V6 for separately locked runtime profiles, and V8 adds local
    LLM assessment. V9 adds its bounded-context opt-in successor. Other V4
    collections retain full document/validator/index verification.
    """
    has_v6 = database.schema_migrations.find_one({"_id": MIGRATION_ID_V6}) is not None
    has_v7 = database.schema_migrations.find_one({"_id": MIGRATION_ID_V7}) is not None
    has_v8 = database.schema_migrations.find_one({"_id": MIGRATION_ID_V8}) is not None
    has_v9 = database.schema_migrations.find_one({"_id": MIGRATION_ID_V9}) is not None
    if has_v6 or has_v7 or has_v8 or has_v9:
        # Fail before any DDL if the successor or predecessor is not an exact
        # completed migration. A partial/unknown ledger is not a skip token.
        _verify_applied_entry(database, _V4_MIGRATION_ID, VALIDATORS_V4, INDEXES_V4)
        _verify_applied_entry(database, MIGRATION_ID_V6, VALIDATORS_V6, INDEXES_V6)
        if has_v7 or has_v8 or has_v9:
            _verify_applied_entry(database, MIGRATION_ID_V7, VALIDATORS_V7, INDEXES_V7)
        if has_v8 or has_v9:
            _verify_applied_entry(database, MIGRATION_ID_V8, VALIDATORS_V8, INDEXES_V8)
        if has_v9:
            _verify_applied_entry(database, MIGRATION_ID_V9, VALIDATORS_V9, INDEXES_V9)
    outcome = apply_schema_v1(database, code_commit=code_commit, applied_by=applied_by)
    apply_schema_v2(database, code_commit=code_commit, applied_by=applied_by)
    apply_schema_v3(database, code_commit=code_commit, applied_by=applied_by)
    if has_v6 or has_v7 or has_v8 or has_v9:
        unchanged = {name: value for name, value in VALIDATORS_V4.items() if name not in VALIDATORS_V6}
        _verify_catalog(database, unchanged, {name: INDEXES_V4[name] for name in unchanged})
    else:
        apply_schema_v4(database, code_commit=code_commit, applied_by=applied_by)
    apply_schema_v5(database, code_commit=code_commit, applied_by=applied_by)
    if not has_v7 and not has_v8 and not has_v9:
        apply_schema_v6(database, code_commit=code_commit, applied_by=applied_by)
    if not has_v8 and not has_v9:
        apply_schema_v7(database, code_commit=code_commit, applied_by=applied_by)
    if not has_v9:
        apply_schema_v8(database, code_commit=code_commit, applied_by=applied_by)
    latest = apply_schema_v9(database, code_commit=code_commit, applied_by=applied_by)
    _verify_catalog(database, {**VALIDATORS_V4, **VALIDATORS_V9}, {**INDEXES_V4, **INDEXES_V9})
    return outcome, latest


def _private_read(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError("Credential files must be private regular files")
    return path.read_text().strip()


def _private_create(path: Path, value: str) -> str:
    if path.is_symlink():
        raise ValueError("Credential file cannot be a symlink")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _private_read(path)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(value + "\n")
    return value


def setup(*, database_name: str, operator: str) -> None:
    if not re.fullmatch(r"kltn_[a-z0-9_]{1,56}", database_name):
        raise ValueError("Use a dedicated kltn_ application database")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", operator):
        raise ValueError("Use a safe operator identifier, not report text or credentials")
    if SECRET_ROOT.is_symlink() or SECRET_ROOT.stat().st_mode & 0o077:
        raise ValueError("Secret directory must already exist and be private")
    paths = ["services/backend/src/kltn_ai/db", "scripts/setup_mongodb_local.py"]
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal", "--", *paths], cwd=ROOT,
    )
    if dirty.strip():
        raise ValueError("Commit migration/bootstrap source before applying; the ledger must name its actual code")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    admin_uri = _private_read(SECRET_ROOT / "admin-uri")
    parts = urlsplit(admin_uri)
    if parts.scheme != "mongodb" or parts.hostname != "127.0.0.1" or not parts.port:
        raise ValueError("Bootstrap is restricted to the dedicated loopback Mongo deployment")
    with MongoClient(admin_uri, serverSelectionTimeoutMS=5000, timeoutMS=30000, tz_aware=True) as admin:
        database = admin[database_name]
        provision_roles(database)
        connection_uris = {}
        for name, role in (("api_app", "kltn_api"), ("worker_app", "kltn_worker"),
                           ("migration_app", "kltn_migration")):
            password = _private_create(SECRET_ROOT / (name + "-password"), secrets.token_urlsafe(48))
            existing = database.command("usersInfo", name)["users"]
            roles = [{"role": role, "db": database_name}]
            if existing:
                database.command("updateUser", name, roles=roles)
            else:
                database.command("createUser", name, pwd=password, roles=roles)
            runtime_uri = urlunsplit((
                parts.scheme, f"{quote(name, safe='')}:{quote(password, safe='')}@127.0.0.1:{parts.port}",
                "/" + database_name, parts.query, "",
            ))
            path = SECRET_ROOT / (name + "-uri")
            if _private_create(path, runtime_uri) != runtime_uri:
                raise ValueError("Existing runtime URI differs; reconcile private credentials explicitly")
            # Authenticate, not merely unauthenticated ping, before handing off.
            with MongoClient(runtime_uri, serverSelectionTimeoutMS=5000, timeoutMS=30000) as runtime:
                status = runtime[database_name].command("connectionStatus")
                if not status["authInfo"]["authenticatedUsers"]:
                    raise ValueError("Runtime identity did not authenticate")
            connection_uris[name] = runtime_uri
    with MongoClient(connection_uris["migration_app"], serverSelectionTimeoutMS=5000,
                     timeoutMS=30000, tz_aware=True) as migrator:
        outcome, latest = apply_schema_chain(migrator[database_name], code_commit=commit, applied_by=operator)
    print(f"Verified {outcome['migration_id']} through {latest['migration_id']} in {database_name}; validator/index read-back passed.")
    print("API/worker/migration URI files are private under ignored var/infra/mongodb; credentials not displayed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="kltn_plagiarism_assessment")
    parser.add_argument("--operator", required=True)
    args = parser.parse_args()
    try:
        setup(database_name=args.database, operator=args.operator)
    except (ValueError, MigrationError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, PyMongoError, subprocess.SubprocessError):
        # Do not dump driver exceptions that can include document/URI values.
        print("MongoDB setup failed; no credentials or input documents displayed. Check private server/operator logs.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
