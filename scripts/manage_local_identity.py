"""Operator CLI for local accounts/workspaces; no public signup or default password."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
import re
import sys

from bson import ObjectId
from pymongo.errors import PyMongoError
from pymongo.write_concern import WriteConcern


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backend.src.kltn_ai.api.runtime import connect_from_private_file  # noqa: E402
from services.backend.src.kltn_ai.auth.service import create_local_user  # noqa: E402
from services.backend.src.kltn_ai.domain.audit import append_event  # noqa: E402
from services.backend.src.kltn_ai.domain.errors import DomainError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri-file", type=Path, default=ROOT / "var/infra/mongodb/migration_app-uri")
    commands = parser.add_subparsers(dest="command", required=True)
    user = commands.add_parser("user")
    user.add_argument("--email", required=True)
    user.add_argument("--display-name", required=True)
    workspace = commands.add_parser("workspace")
    workspace.add_argument("--key", required=True)
    workspace.add_argument("--name", required=True)
    workspace.add_argument("--purpose", required=True)
    member = commands.add_parser("membership")
    member.add_argument("--user-id", required=True)
    member.add_argument("--workspace-id", required=True)
    member.add_argument("--role", required=True, choices=["STUDENT", "LECTURER", "OPERATOR", "DATA_APPROVER"])
    args = parser.parse_args()
    try:
        password = None
        if args.command == "user":
            password = getpass("New local password (15+ characters): ")
            if password != getpass("Confirm password: "):
                raise ValueError("Password confirmation differs")
        client, database = connect_from_private_file(args.uri_file, role="kltn_migration")
        try:
            with client.start_session() as session:
                with session.start_transaction(write_concern=WriteConcern("majority", wtimeout=30000)):
                    now = datetime.now(timezone.utc)
                    common = {"schema_version": 1, "created_at": now, "created_by": None,
                              "updated_at": now, "updated_by": None, "revision": 1}
                    if args.command == "user":
                        assert password is not None
                        identity = create_local_user(database, args.email, args.display_name,
                                                     password, session=session)
                        identifier = ObjectId(identity["id"])
                        resource_type = "USER"
                    elif args.command == "workspace":
                        if (not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", args.key)
                                or not 1 <= len(args.name.strip()) <= 256
                                or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", args.purpose)):
                            raise ValueError("Invalid workspace key/name/purpose")
                        identifier = ObjectId()
                        database.workspaces.insert_one({"_id": identifier, **common,
                            "workspace_key": args.key, "name": args.name.strip(), "kind": "RESEARCH",
                            "default_purpose": args.purpose, "status": "ACTIVE"}, session=session)
                        resource_type = "WORKSPACE"
                    else:
                        if not ObjectId.is_valid(args.user_id) or not ObjectId.is_valid(args.workspace_id):
                            raise ValueError("Invalid identity/workspace identifier")
                        user_id, workspace_id = ObjectId(args.user_id), ObjectId(args.workspace_id)
                        if (database.users.find_one({"_id": user_id, "status": "ACTIVE"}, session=session) is None
                                or database.workspaces.find_one({"_id": workspace_id, "status": "ACTIVE"}, session=session) is None):
                            raise ValueError("Active user and workspace are required")
                        identifier = ObjectId()
                        database.memberships.insert_one({"_id": identifier, **common,
                            "user_id": user_id, "workspace_id": workspace_id, "roles": [args.role],
                            "status": "ACTIVE", "valid_from": None, "valid_until": None}, session=session)
                        resource_type = "MEMBERSHIP"
                    append_event(database, actor_id=None, workspace_id=None,
                                 action="IDENTITY_BOOTSTRAPPED", resource_type=resource_type,
                                 resource_id=identifier, request_id="operator-bootstrap", session=session)
            print(f"Created {resource_type} id={identifier}; no password/PII displayed.")
        finally:
            client.close()
    except (ValueError, DomainError):
        print("Identity setup rejected; verify input, permissions and existing identities.", file=sys.stderr)
        return 2
    except (RuntimeError, OSError, PyMongoError):
        print("Identity setup failed; no credentials or database details displayed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
