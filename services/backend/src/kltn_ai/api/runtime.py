"""Load a private, least-privilege Mongo credential for the loopback app."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import stat
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from .app import create_app


ROOT = Path(__file__).resolve().parents[5]


def connect_from_private_file(path: Path, *, role: str = "kltn_api"):
    client: MongoClient[dict[str, Any]] | None = None
    try:
        if any(parent.is_symlink() for parent in [path, *path.parents]):
            raise ValueError("Credential path must not traverse symlinks")
        parent = path.parent.stat()
        if parent.st_mode & 0o077 or parent.st_uid != os.getuid():
            raise ValueError("Credential directory must be private and owned by the runtime user")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                    or info.st_uid != os.getuid() or info.st_size > 4096):
                raise ValueError("Credential file must be private and owned by the runtime user")
            uri = stream.read(4097).strip()
        parts = urlsplit(uri)
        query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
        if (parts.scheme != "mongodb" or parts.hostname != "127.0.0.1"
                or not parts.username or not parts.password or not parts.port
                or not parts.path.startswith("/kltn_") or parts.fragment
                or set(query) - {"directConnection", "replicaSet", "authSource"}
                or query.get("directConnection") != ["true"]
                or query.get("replicaSet") != ["kltn-rs"]
                or query.get("authSource", [parts.path[1:]]) != [parts.path[1:]]):
            raise ValueError("Only the dedicated loopback MongoDB deployment is supported")
        client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000, timeoutMS=30000)
        database = client.get_default_database()
        information = database.command("connectionStatus")["authInfo"]
        expected = {"role": role, "db": database.name}
        if information["authenticatedUserRoles"] != [expected]:
            raise ValueError("Runtime must authenticate as the exact dedicated least-privilege identity")
        return client, database
    except (PyMongoError, ValueError, OSError, UnicodeError):
        if client is not None:
            client.close()
        raise RuntimeError("Could not establish the required private MongoDB identity") from None


def create_runtime_app():
    path = Path(os.environ.get("KLTN_MONGO_URI_FILE", ROOT / "var/infra/mongodb/api_app-uri"))
    client, database = connect_from_private_file(path)
    app = create_app(database)

    @app.on_event("shutdown")
    def close_database():
        client.close()

    return app
