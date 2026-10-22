"""Offline checks use only new temporary credentials, never local user secrets."""

from pathlib import Path

import pytest

from scripts import prepare_mongodb_local as preparation


@pytest.fixture
def secret_directory(tmp_path, monkeypatch):
    directory = tmp_path / "private-mongo"
    monkeypatch.setattr(preparation, "ROOT", directory)
    monkeypatch.delenv("KLTN_MONGO_PORT", raising=False)
    return directory


def test_prepare_private_files_idempotent_and_no_credential_output(secret_directory, capsys):
    preparation.prepare()
    before = {path.name: path.read_bytes() for path in secret_directory.iterdir()}
    preparation.prepare()
    assert {path.name: path.read_bytes() for path in secret_directory.iterdir()} == before
    assert secret_directory.stat().st_mode & 0o077 == 0
    assert all(path.stat().st_mode & 0o077 == 0 for path in secret_directory.iterdir())
    output = capsys.readouterr().out
    assert "mongodb://" not in output
    assert before["root-password"].decode().strip() not in output


def test_prepare_refuses_exposed_uri_without_changing_it(secret_directory):
    preparation.prepare()
    uri = secret_directory / "admin-uri"
    original = uri.read_bytes()
    uri.chmod(0o644)
    with pytest.raises(ValueError, match="private regular file"):
        preparation.prepare()
    assert uri.read_bytes() == original


def test_prepare_refuses_port_drift_and_keeps_existing_credentials(secret_directory, monkeypatch):
    preparation.prepare()
    original = {path.name: path.read_bytes() for path in secret_directory.iterdir()}
    monkeypatch.setenv("KLTN_MONGO_PORT", "27189")
    with pytest.raises(ValueError, match="differs"):
        preparation.prepare()
    assert {path.name: path.read_bytes() for path in secret_directory.iterdir()} == original


def test_prepare_refuses_uri_symlink_without_touching_target(secret_directory, tmp_path):
    secret_directory.mkdir(mode=0o700)
    outside = tmp_path / "unrelated"
    outside.write_text("unrelated fixture")
    (secret_directory / "admin-uri").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        preparation.prepare()
    assert outside.read_text() == "unrelated fixture"


@pytest.mark.parametrize("port", ["0", "65536", "invalid"])
def test_prepare_invalid_port_does_not_create_any_secret(secret_directory: Path, monkeypatch, port):
    monkeypatch.setenv("KLTN_MONGO_PORT", port)
    with pytest.raises(ValueError, match="KLTN_MONGO_PORT"):
        preparation.prepare()
    assert not secret_directory.exists()
