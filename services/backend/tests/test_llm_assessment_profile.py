"""Opt-in P2 model boundaries; orchestration doubles do not measure LLM quality."""

from copy import deepcopy
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from services.backend.src.kltn_ai.db import llm_assessment_schema as migration
from services.backend.src.kltn_ai.db.migrations import schema_checksum
from services.backend.src.kltn_ai.db.semantic_runtime_schema import INDEXES_V7, VALIDATORS_V7
from services.backend.src.kltn_ai.domain.indexes import dense_index_required, locked_config
from services.backend.src.kltn_ai.worker import bounded_pipeline as bounded


PROFILE = "bm25-p2-llm-v1"
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def configured_catalog(monkeypatch, tmp_path):
    """A synthetic pin allows orchestration tests without a running model."""
    config = json.loads((ROOT / "services/backend/configs" / f"{PROFILE}.json").read_text())
    config["models"]["assessment_verifier"]["digest"] = "sha256:" + "a" * 64
    path = tmp_path / "services/backend/configs" / f"{PROFILE}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config))
    research = tmp_path / "research/configs/core-mvp-v0.json"
    research.parent.mkdir(parents=True)
    research.write_bytes((ROOT / "research/configs/core-mvp-v0.json").read_bytes())
    monkeypatch.setattr(bounded, "ROOT", tmp_path)
    return config, path


def _snapshot(run_type):
    _, digest = bounded.configuration(PROFILE)
    return {"config_id": PROFILE, "config_sha256": digest, "run_type": run_type,
            "report_chunks": [{"text": "Synthetic report evidence."}], "source_chunks": [],
            "compiled_rubric": {"rubric_version": 1}}


def _stub_pipelines(monkeypatch):
    from research.core_mvp import assessment, contracts, similarity
    from research import schema_validation

    calls = []
    monkeypatch.setattr(similarity, "run_similarity_pipeline", lambda *a, **kw: calls.append(("p1", kw)) or {"test": "similarity"})
    monkeypatch.setattr(assessment, "run_assessment_pipeline", lambda *a, **kw: calls.append(("p2", kw)) or {"compiled_rubric": {"rubric_version": 1}})
    monkeypatch.setattr(contracts, "validate_similarity_report", lambda *a: None)
    monkeypatch.setattr(contracts, "validate_assessment_report", lambda *a: None)
    monkeypatch.setattr(schema_validation, "validate_json_schema", lambda *a, **kw: None)
    return calls


def test_profile_keeps_retrieval_and_p1_settings_and_adds_only_p2_llm(configured_catalog):
    old, _ = bounded.configuration("bm25-smoke")
    new, digest = bounded.configuration(PROFILE)
    assert new["pipeline1"] == old["pipeline1"]
    p2 = deepcopy(new["pipeline2"])
    assert p2.pop("llm_verification")["enabled"] is True
    assert p2 == old["pipeline2"]
    assert set(new["models"]) == {"assessment_verifier"}
    assert new["models"]["assessment_verifier"]["backend"] == "ollama"
    assert new["models"]["assessment_verifier"]["endpoint"] == "http://127.0.0.1:11435"
    assert new["limits"]["wall_seconds"] == 900
    assert len(digest) == 64
    assert dense_index_required(new) is False


def test_checked_in_profile_has_real_immutable_model_pin():
    config, digest = bounded.configuration(PROFILE)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", config["models"]["assessment_verifier"]["digest"])
    assert len(digest) == 64
    assert locked_config(PROFILE)[0] == config


@pytest.mark.parametrize("digest", ["ROOT_WILL_SUPPLY_REAL_SHA", "latest", "a" * 64, "sha256:" + "g" * 64, ""])
def test_unconfigured_or_malformed_model_pin_is_rejected_before_models(configured_catalog, digest):
    config, path = configured_catalog
    config["models"]["assessment_verifier"]["digest"] = digest
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="immutable local model digest"):
        bounded.configuration(PROFILE)


@pytest.mark.parametrize("wall", [True, 59, 901, 1_000_000])
def test_new_profile_has_its_own_bounded_wall_budget(configured_catalog, wall):
    config, path = configured_catalog
    config["limits"]["wall_seconds"] = wall
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="profile budget"):
        bounded.configuration(PROFILE)


def test_p1_only_does_not_contact_p2_model(configured_catalog, monkeypatch):
    from research.core_mvp import llm_assessment
    calls = _stub_pipelines(monkeypatch)
    monkeypatch.setattr(llm_assessment, "load_llm_assessment_verifier", lambda *a, **k: pytest.fail("P1 cannot contact the P2 model service"))
    result = bounded.execute_snapshot(_snapshot("SIMILARITY"))
    assert [name for name, _ in calls] == ["p1"]
    assert result["execution"]["models"] == {"encoder": None, "reranker": None}
    assert result["execution"]["hardware"]["device"] == "cpu"


@pytest.mark.parametrize("run_type", ["ASSESSMENT", "BOTH"])
def test_p2_loads_only_its_local_verifier_and_forwards_metadata(configured_catalog, monkeypatch, run_type):
    from research.core_mvp import llm_assessment, runner
    calls = _stub_pipelines(monkeypatch)
    metadata = {"backend": "ollama", "model": "SYNTHETIC_VERIFIER", "digest": "sha256:" + "a" * 64}
    verifier = SimpleNamespace(metadata=metadata)
    loaded = []
    def load(model, policy):
        loaded.append((model, policy))
        return verifier
    monkeypatch.setattr(llm_assessment, "load_llm_assessment_verifier", load)
    monkeypatch.setattr(runner, "_load_encoder", lambda *a: pytest.fail("No Dense model in this profile"))
    monkeypatch.setattr(runner, "_load_reranker", lambda *a: pytest.fail("No relevance reranker in this profile"))
    result = bounded.execute_snapshot(_snapshot(run_type))
    assert len(loaded) == 1 and loaded[0][1]["enabled"] is True
    assert [name for name, _ in calls] == (["p1", "p2"] if run_type == "BOTH" else ["p2"])
    assert calls[-1][1]["llm_verifier"] is verifier
    assert result["execution"]["models"] == {"encoder": None, "reranker": None, "assessment_verifier": metadata}
    assert result["execution"]["hardware"]["device"] == "local_model_service"
    assert result["execution"]["hardware"]["model_devices"] == {"assessment_verifier": "unknown"}
    assert "local LLM" in result["execution"]["baseline_limitations"][1]


def test_loader_failure_does_not_silently_use_phrase_baseline(configured_catalog, monkeypatch):
    from research.core_mvp import llm_assessment
    calls = _stub_pipelines(monkeypatch)
    def unavailable(*args):
        raise RuntimeError("Synthetic local model failure")
    monkeypatch.setattr(llm_assessment, "load_llm_assessment_verifier", unavailable)
    with pytest.raises(RuntimeError, match="Synthetic local model failure"):
        bounded.execute_snapshot(_snapshot("ASSESSMENT"))
    assert calls == []


def test_changed_configuration_hash_rejects_before_llm_load(configured_catalog, monkeypatch):
    from research.core_mvp import llm_assessment
    _stub_pipelines(monkeypatch)
    monkeypatch.setattr(llm_assessment, "load_llm_assessment_verifier", lambda *a, **kw: pytest.fail("Config rejected before model loading"))
    request = _snapshot("ASSESSMENT")
    request["config_sha256"] = "0" * 64
    with pytest.raises(bounded.PipelineRejected, match="ANALYSIS_CONFIG_CHANGED"):
        bounded.execute_snapshot(request)


def test_external_model_wait_does_not_expand_untrusted_child_cpu_budget(configured_catalog):
    request = _snapshot("ASSESSMENT")
    request["limits"] = {"wall_seconds": 1_000_000}
    assert bounded._cpu_seconds(request) == 170


def test_v8_only_expands_profile_enum_and_preserves_applied_v7():
    assert schema_checksum(VALIDATORS_V7, INDEXES_V7) == "854fd1687a8fbba31ca9081547c0a0b8e973f0b1168218e5adbbb30e4499f6a0"
    for name, validator in migration.VALIDATORS_V8.items():
        copied = deepcopy(validator)
        assert copied["$jsonSchema"]["properties"]["config_id"]["enum"] == [
            *VALIDATORS_V7[name]["$jsonSchema"]["properties"]["config_id"]["enum"], PROFILE]
        copied["$jsonSchema"]["properties"]["config_id"] = VALIDATORS_V7[name]["$jsonSchema"]["properties"]["config_id"]
        assert copied == VALIDATORS_V7[name]
        assert migration.INDEXES_V8[name] == INDEXES_V7[name]


def test_new_migration_records_separate_ledger_identity(monkeypatch):
    calls = []
    monkeypatch.setattr(migration, "apply_migration", lambda db, **kw: calls.append((db, kw)) or {"status": "APPLIED"})
    database = object()
    assert migration.apply_schema_v8(database, code_commit="a" * 40, applied_by="test-operator") == {"status": "APPLIED"}
    assert calls[0][0] is database
    assert calls[0][1]["migration_id"] == "008-local-llm-assessment-profile-v1"
    assert calls[0][1]["validators"] is migration.VALIDATORS_V8
