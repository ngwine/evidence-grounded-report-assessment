"""Dedicated local runtime lifecycle boundaries without launching services."""

import plistlib
from types import SimpleNamespace

import pytest

from scripts import dev_p2_llm as launcher


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher, "STATE", tmp_path / "var/runtime/dev-p2-llm")
    monkeypatch.setattr(launcher, "BINARY", tmp_path / "var/runtime/ollama-v0.40.13/ollama")
    monkeypatch.setattr(launcher, "MODELS", tmp_path / "var/models/ollama-p2")
    monkeypatch.setattr(launcher, "PLIST", launcher.STATE / "ollama.plist")
    return tmp_path


def owned_output():
    return f'''{launcher.TARGET} = {{
    path = {launcher.PLIST}
    state = running
    program = {launcher.BINARY}
    arguments = {{
        {launcher.BINARY}
        serve
    }}
    environment = {{
        OLLAMA_HOST => {launcher.HOST}
        OLLAMA_MODELS => {launcher.MODELS}
    }}
    pid = 90210
}}'''


def test_prepare_keeps_runtime_private_local_and_bounded(checkout):
    launcher.prepare()
    config = plistlib.loads(launcher.PLIST.read_bytes())
    assert config["ProgramArguments"] == [str(launcher.BINARY), "serve"]
    assert config["KeepAlive"] == {"SuccessfulExit": False}
    assert config["EnvironmentVariables"]["OLLAMA_HOST"] == "127.0.0.1:11435"
    assert config["EnvironmentVariables"]["OLLAMA_MODELS"] == str(launcher.MODELS)
    assert config["EnvironmentVariables"]["OLLAMA_NO_CLOUD"] == "1"
    assert config["EnvironmentVariables"]["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert config["EnvironmentVariables"]["OLLAMA_NUM_PARALLEL"] == "1"
    assert config["EnvironmentVariables"]["OLLAMA_MAX_QUEUE"] == "1"
    assert config["EnvironmentVariables"]["LLAMA_ARG_CACHE_RAM"] == "0"
    assert "11434" not in launcher.PLIST.read_text()
    assert launcher.STATE.stat().st_mode & 0o777 == 0o700
    assert launcher.MODELS.stat().st_mode & 0o777 == 0o700
    for path in launcher.STATE.iterdir():
        assert path.stat().st_mode & 0o777 == 0o600


def test_prepare_rejects_symlinked_runtime_parent(checkout):
    destination = checkout / "outside"
    destination.mkdir()
    (checkout / "var").symlink_to(destination, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlinks"):
        launcher.prepare()
    assert not list(destination.iterdir())


def test_binary_pin_rejects_executable_content_drift(checkout):
    launcher.BINARY.parent.mkdir(parents=True)
    launcher.BINARY.write_bytes(b"synthetic executable, not a model runtime")
    launcher.BINARY.chmod(0o755)
    with pytest.raises(RuntimeError, match="checksum"):
        launcher._verify_binary()


@pytest.mark.parametrize("change", ["program", "arguments", "host", "models", "path"])
def test_job_identity_requires_its_program_arguments_environment_and_plist(checkout, change):
    output = owned_output()
    assert launcher._owned(output)
    replacements = {"program": (f"program = {launcher.BINARY}", "program = /tmp/foreign-runtime"),
                    "arguments": ("        serve", "        run foreign-model"),
                    "host": (launcher.HOST, "127.0.0.1:11434"),
                    "models": (f"OLLAMA_MODELS => {launcher.MODELS}", "OLLAMA_MODELS => /tmp/foreign-models"),
                    "path": (f"path = {launcher.PLIST}", "path = /tmp/foreign.plist")}
    before, after = replacements[change]
    assert not launcher._owned(output.replace(before, after))


def test_start_rejects_foreign_listener_without_writing_or_launching(checkout, monkeypatch):
    calls = []
    monkeypatch.setattr(launcher, "_verify_binary", lambda: None)
    monkeypatch.setattr(launcher, "launchctl", lambda *a: calls.append(a) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(launcher, "_job", lambda: ({"state": "stopped"}, ""))
    monkeypatch.setattr(launcher, "_listener_pids", lambda: {"12345"})
    with pytest.raises(RuntimeError, match="foreign listener"):
        launcher.start()
    assert calls == [("print", launcher.DOMAIN)]
    assert not launcher.STATE.exists()


def test_stop_rejects_foreign_listener_without_bootout(checkout, monkeypatch):
    calls = []
    monkeypatch.setattr(launcher, "launchctl", lambda *a: calls.append(a) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(launcher, "_job", lambda: ({"state": "stopped"}, ""))
    monkeypatch.setattr(launcher, "_listener_pids", lambda: {"12345"})
    with pytest.raises(RuntimeError, match="foreign listener"):
        launcher.stop()
    assert calls == []


def test_stop_only_boots_out_the_verified_checkout_job(checkout, monkeypatch):
    calls = []
    monkeypatch.setattr(launcher, "launchctl", lambda *a: calls.append(a) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(launcher, "_job", lambda: ({"state": "running", "pid": "90210"}, owned_output()))
    monkeypatch.setattr(launcher, "_listener_pids", lambda: {"90210"})
    launcher.stop()
    assert calls == [("bootout", launcher.TARGET)]


def test_fresh_start_loads_only_its_plist_and_checks_release(checkout, monkeypatch):
    calls = []
    loaded = False
    def launchctl(*args):
        nonlocal loaded
        calls.append(args)
        if args[0] == "bootstrap":
            loaded = True
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(launcher, "_verify_binary", lambda: None)
    monkeypatch.setattr(launcher, "launchctl", launchctl)
    monkeypatch.setattr(launcher, "_job", lambda: ({"state": "running", "pid": "90210"}, owned_output()) if loaded else ({"state": "stopped"}, ""))
    monkeypatch.setattr(launcher, "_listener_pids", lambda: {"90210"} if loaded else set())
    monkeypatch.setattr(launcher, "metadata", lambda route: {"version": launcher.RELEASE})
    launcher.start()
    assert calls == [("print", launcher.DOMAIN), ("bootstrap", launcher.DOMAIN, str(launcher.PLIST))]
    assert launcher.PLIST.is_file()


def test_wrong_release_does_not_stop_a_preexisting_owned_job(checkout, monkeypatch):
    calls = []
    monkeypatch.setattr(launcher, "_verify_binary", lambda: None)
    monkeypatch.setattr(launcher, "launchctl", lambda *a: calls.append(a) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(launcher, "_job", lambda: ({"state": "running", "pid": "90210"}, owned_output()))
    monkeypatch.setattr(launcher, "_listener_pids", lambda: {"90210"})
    monkeypatch.setattr(launcher, "metadata", lambda route: {"version": "0.0.0-synthetic"})
    with pytest.raises(RuntimeError, match="different Ollama release"):
        launcher.start()
    assert calls == [("print", launcher.DOMAIN)]


def test_metadata_access_has_no_generation_or_pull_routes():
    for route in ("/api/chat", "/api/generate", "/api/pull", "https://external.invalid"):
        with pytest.raises(ValueError, match="metadata routes"):
            launcher.metadata(route)


def test_status_is_metadata_only_and_handles_malformed_model_list(checkout, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "_job", lambda: ({"state": "stopped"}, ""))
    monkeypatch.setattr(launcher, "metadata", lambda route: {"version": launcher.RELEASE} if route == "/api/version" else {"models": {"unexpected": "shape"}})
    launcher.status()
    assert '"models": []' in capsys.readouterr().out
