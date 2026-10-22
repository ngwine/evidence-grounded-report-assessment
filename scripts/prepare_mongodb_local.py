"""Create private local MongoDB development secrets, without printing them."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import secrets
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1] / "var/infra/mongodb"


def prepare() -> None:
    port = os.environ.get("KLTN_MONGO_PORT", "27188")
    if not port.isdecimal() or not 1024 <= int(port) <= 65535:
        raise ValueError("Invalid KLTN_MONGO_PORT")
    ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    if ROOT.is_symlink() or ROOT.stat().st_mode & 0o077:
        raise ValueError("MongoDB secret directory must be private")
    values = {
        "root-user": "kltn_local_admin",
        "root-password": secrets.token_urlsafe(48),
        "replica-key": base64.b64encode(secrets.token_bytes(384)).decode("ascii"),
    }
    for name, value in values.items():
        path = ROOT / name
        if path.is_symlink():
            raise ValueError("Secret file cannot be a symlink")
        if path.exists():
            if not path.is_file() or path.stat().st_mode & 0o077:
                raise ValueError("Existing secret file must be private")
            if not path.read_text().strip():
                raise ValueError("Existing secret file must not be empty")
            continue
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value + "\n")
    uri_path = ROOT / "admin-uri"
    if uri_path.is_symlink():
        raise ValueError("URI file cannot be a symlink")
    username = (ROOT / "root-user").read_text().strip()
    password = (ROOT / "root-password").read_text().strip()
    uri = (f"mongodb://{quote(username, safe='')}:{quote(password, safe='')}"
           f"@127.0.0.1:{port}/admin?directConnection=true&replicaSet=kltn-rs")
    if uri_path.exists():
        if not uri_path.is_file() or uri_path.stat().st_mode & 0o077:
            raise ValueError("Existing admin URI must be a private regular file")
        if uri_path.read_text().strip() != uri:
            raise ValueError("Existing admin URI differs; reconcile local port/credentials explicitly without deleting data")
    else:
        descriptor = os.open(uri_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(uri + "\n")
    print("MongoDB secrets ready under ignored var/infra/mongodb; credentials not displayed.")


if __name__ == "__main__":
    prepare()
