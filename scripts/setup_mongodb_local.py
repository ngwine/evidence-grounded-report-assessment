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
from services.backend.src.kltn_ai.db.migrations import MigrationError, apply_schema_v1  # noqa: E402
from services.backend.src.kltn_ai.db.roles import provision_roles  # noqa: E402


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
        outcome = apply_schema_v1(migrator[database_name], code_commit=commit, applied_by=operator)
    print(f"Applied {outcome['migration_id']} to {database_name}; validator/index read-back passed.")
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
