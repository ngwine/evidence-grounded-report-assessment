"""No-network checks of private Mongo credentials and least-privilege startup."""

from __future__ import annotations

from pathlib import Path
import os

import pytest
from pymongo.errors import ConnectionFailure

from services.backend.src.kltn_ai.api import runtime


DATABASE_NAME = "kltn_runtime_fixture"
URI = (f"mongodb://fixture_api:fixture_password@127.0.0.1:27188/{DATABASE_NAME}"
       f"?authSource={DATABASE_NAME}&directConnection=true&replicaSet=kltn-rs")


class FakeDatabase:
    name = DATABASE_NAME

    def __init__(self, roles=None, fail=False):
        self.roles = roles if roles is not None else [{"role": "kltn_api", "db": self.name}]
        self.fail = fail

    def command(self, command):
        assert command == "connectionStatus"
        if self.fail:
            raise ConnectionFailure("untrusted-secret-driver-text")
        return {"authInfo": {"authenticatedUserRoles": self.roles}}


class FakeClient:
    def __init__(self, database=None):
        self.database = database or FakeDatabase()
        self.closed = False

    def get_default_database(self):
        return self.database

    def close(self):
        self.closed = True


@pytest.fixture
def credential_file(tmp_path):
    private = tmp_path / "private-runtime"
    private.mkdir(mode=0o700)
    path = private / "api-uri"
    path.write_text(URI)
    path.chmod(0o600)
    return path


def install_client(monkeypatch, client):
    calls = []

    def factory(uri, **options):
        calls.append((uri, options))
        return client

    monkeypatch.setattr(runtime, "MongoClient", factory)
    return calls


def test_private_file_connects_only_exact_role_and_finite_timeouts(credential_file, monkeypatch):
    client = FakeClient()
    calls = install_client(monkeypatch, client)
    returned, database = runtime.connect_from_private_file(credential_file)
    assert returned is client and database is client.database
    assert not client.closed
    assert len(calls) == 1
    assert calls[0][1]["serverSelectionTimeoutMS"] <= 5000
    assert calls[0][1]["timeoutMS"] <= 30000
    assert calls[0][1]["tz_aware"] is True


@pytest.mark.parametrize("roles", [[], [{"role": "root", "db": "admin"}],
                                  [{"role": "kltn_api", "db": "wrong_database"}],
                                  [{"role": "kltn_worker", "db": DATABASE_NAME}],
                                  [{"role": "kltn_api", "db": DATABASE_NAME}, {"role": "root", "db": "admin"}]])
def test_runtime_rejects_missing_wrong_or_additional_database_roles(credential_file, monkeypatch, roles):
    client = FakeClient(FakeDatabase(roles=roles))
    install_client(monkeypatch, client)
    with pytest.raises(RuntimeError) as failure:
        runtime.connect_from_private_file(credential_file)
    assert "fixture_password" not in str(failure.value)
    assert client.closed


@pytest.mark.parametrize("mode,target", [(0o644, "file"), (0o660, "file"),
                                        (0o755, "directory"), (0o770, "directory")])
def test_group_or_world_accessible_file_or_directory_rejected(credential_file, monkeypatch, mode, target):
    calls = install_client(monkeypatch, FakeClient())
    (credential_file if target == "file" else credential_file.parent).chmod(mode)
    with pytest.raises((ValueError, RuntimeError)):
        runtime.connect_from_private_file(credential_file)
    assert not calls


def test_symlink_credential_file_rejected_before_connection(credential_file, monkeypatch):
    link = credential_file.parent / "api-uri-link"
    link.symlink_to(credential_file)
    calls = install_client(monkeypatch, FakeClient())
    with pytest.raises((ValueError, RuntimeError)):
        runtime.connect_from_private_file(link)
    assert not calls


def test_fifo_credential_file_rejected_without_waiting_for_a_writer(credential_file, monkeypatch):
    pipe = credential_file.parent / "not-a-credential"
    os.mkfifo(pipe, 0o600)
    calls = install_client(monkeypatch, FakeClient())
    with pytest.raises(RuntimeError):
        runtime.connect_from_private_file(pipe)
    assert not calls


def test_symlink_private_directory_rejected(credential_file, monkeypatch):
    link = credential_file.parent.parent / "linked-private"
    link.symlink_to(credential_file.parent, target_is_directory=True)
    calls = install_client(monkeypatch, FakeClient())
    with pytest.raises((ValueError, RuntimeError)):
        runtime.connect_from_private_file(link / credential_file.name)
    assert not calls


@pytest.mark.parametrize("uri", [
    "mongodb+srv://fixture:fixture@cluster.example/kltn_fixture",
    "mongodb://fixture:fixture@192.0.2.10:27188/kltn_fixture",
    "mongodb://fixture:fixture@127.0.0.1:27188/admin",
    "mongodb://127.0.0.1:27188/kltn_fixture",
    "mongodb://fixture@127.0.0.1:27188/kltn_fixture",
    "mongodb://fixture:fixture@127.0.0.1/kltn_fixture",
])
def test_uri_rejects_remote_srv_unscoped_or_credentialless_connection(credential_file, monkeypatch, uri):
    credential_file.write_text(uri)
    calls = install_client(monkeypatch, FakeClient())
    with pytest.raises((ValueError, RuntimeError)) as failure:
        runtime.connect_from_private_file(credential_file)
    assert "fixture:fixture" not in str(failure.value)
    assert not calls


def test_uri_file_size_budget_is_checked_before_client(credential_file, monkeypatch):
    credential_file.write_text("x" * 4097)
    calls = install_client(monkeypatch, FakeClient())
    with pytest.raises((ValueError, RuntimeError)):
        runtime.connect_from_private_file(credential_file)
    assert not calls


def test_failed_connection_is_closed_and_never_exposes_driver_details(credential_file, monkeypatch):
    client = FakeClient(FakeDatabase(fail=True))
    install_client(monkeypatch, client)
    with pytest.raises(RuntimeError) as failure:
        runtime.connect_from_private_file(credential_file)
    assert "untrusted-secret-driver-text" not in str(failure.value)
    assert "fixture_password" not in str(failure.value)
    assert client.closed


def test_proxy_query_cannot_turn_loopback_uri_into_remote_transport(credential_file, monkeypatch):
    credential_file.write_text(URI + "&proxyHost=attacker.example&proxyPort=1080")
    calls = install_client(monkeypatch, FakeClient())
    with pytest.raises((ValueError, RuntimeError)):
        runtime.connect_from_private_file(credential_file)
    assert not calls


def test_credential_file_is_read_once_so_validation_and_connection_use_same_snapshot(credential_file, monkeypatch):
    original = Path.read_text
    read_count = 0

    def read(path, *args, **kwargs):
        nonlocal read_count
        if path == credential_file:
            read_count += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    install_client(monkeypatch, FakeClient())
    runtime.connect_from_private_file(credential_file)
    # Secure os.open/fstat implementations may bypass Path.read_text entirely.
    assert read_count <= 1


def test_operator_role_must_be_explicit_never_accepted_by_api_default(credential_file, monkeypatch):
    client = FakeClient(FakeDatabase(roles=[{"role": "kltn_migration", "db": DATABASE_NAME}]))
    install_client(monkeypatch, client)
    with pytest.raises(RuntimeError):
        runtime.connect_from_private_file(credential_file)
    replacement = FakeClient(FakeDatabase(roles=[{"role": "kltn_migration", "db": DATABASE_NAME}]))
    install_client(monkeypatch, replacement)
    returned, _ = runtime.connect_from_private_file(credential_file, role="kltn_migration")
    assert returned is replacement


def test_runtime_requires_file_and_directory_owned_by_current_user(credential_file, monkeypatch):
    calls = install_client(monkeypatch, FakeClient())
    with monkeypatch.context() as patch:
        patch.setattr(runtime.os, "getuid", lambda: credential_file.stat().st_uid + 1)
        with pytest.raises(RuntimeError):
            runtime.connect_from_private_file(credential_file)
    assert not calls


def test_missing_private_file_has_safe_error_not_path_disclosure(tmp_path):
    with pytest.raises(RuntimeError) as failure:
        runtime.connect_from_private_file(tmp_path / "not-an-existing-private-credential")
    assert str(tmp_path) not in str(failure.value)
