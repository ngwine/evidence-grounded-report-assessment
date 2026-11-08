"""Versioned bounded-context profile contracts; no model inference in these tests."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.backend.src.kltn_ai.db import llm_assessment_v2_schema as migration
from services.backend.src.kltn_ai.db.llm_assessment_schema import INDEXES_V8, VALIDATORS_V8
from services.backend.src.kltn_ai.db.migrations import schema_checksum
from services.backend.src.kltn_ai.domain.indexes import dense_index_required, locked_config
from services.backend.src.kltn_ai.worker import bounded_pipeline as bounded


PROFILE = "bm25-p2-llm-v2"
ROOT = Path(__file__).resolve().parents[3]


def test_v2_is_opt_in_and_keeps_p1_and_model_checkpoint_fixed():
    previous, previous_digest = bounded.configuration("bm25-p2-llm-v1")
    candidate, candidate_digest = bounded.configuration(PROFILE)
    assert candidate["config_id"] == PROFILE
    assert candidate["pipeline1"] == previous["pipeline1"]
    assert candidate["documents"] == previous["documents"]
    assert candidate["models"] == previous["models"]
    assert candidate_digest != previous_digest
    assert locked_config(PROFILE)[0] == candidate
    assert dense_index_required(candidate) is False
    assert candidate["limits"]["wall_seconds"] == 900
    policy = candidate["pipeline2"]["llm_verification"]
    assert policy["enabled"] is True and policy["citation_mode"] == "source_units"
    assert policy["num_ctx"] > previous["pipeline2"]["llm_verification"]["num_ctx"]
    assert policy["num_predict"] < previous["pipeline2"]["llm_verification"]["num_predict"]
    assert 60 < policy["timeout_seconds"] <= 300
    assert candidate["pipeline2"]["evidence_context"]["strategy"] == "all_parsed_chunks_if_bounded"
    assert "evidence_context" not in previous["pipeline2"]
    assert "citation_mode" not in previous["pipeline2"]["llm_verification"]


@pytest.mark.parametrize("field,value,error", [
    ("config_id", "bm25-p2-llm-v1", "identity mismatch"),
    ("wall_seconds", True, "profile budget"),
    ("wall_seconds", 901, "profile budget"),
    ("digest", "latest", "immutable local model digest"),
    ("digest", "a" * 64, "immutable local model digest"),
])
def test_profile_refuses_changed_identity_or_unpinned_runtime_before_loading(monkeypatch, tmp_path, field, value, error):
    source = ROOT / "services/backend/configs" / f"{PROFILE}.json"
    config = json.loads(source.read_text())
    if field == "digest":
        config["models"]["assessment_verifier"][field] = value
    elif field == "wall_seconds":
        config["limits"][field] = value
    else:
        config[field] = value
    target = tmp_path / "services/backend/configs" / source.name
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(config))
    monkeypatch.setattr(bounded, "ROOT", tmp_path)
    with pytest.raises(ValueError, match=error):
        bounded.configuration(PROFILE)


@pytest.mark.parametrize("run_type", ["SIMILARITY", "ASSESSMENT", "BOTH"])
def test_worker_routes_only_p2_to_new_local_verifier(monkeypatch, run_type):
    from research import schema_validation
    from research.core_mvp import assessment, contracts, llm_assessment, similarity

    config, digest = bounded.configuration(PROFILE)
    loaded, p1_calls, p2_calls = [], [], []
    verifier = SimpleNamespace(metadata={"backend": "ollama", "diagnostic": "SYNTHETIC"})

    def load(model, policy):
        loaded.append((model, policy))
        return verifier

    monkeypatch.setattr(llm_assessment, "load_llm_assessment_verifier", load)
    monkeypatch.setattr(similarity, "run_similarity_pipeline", lambda *a, **kw: p1_calls.append(kw) or {})
    monkeypatch.setattr(assessment, "run_assessment_pipeline", lambda *a, **kw: p2_calls.append(kw) or {"compiled_rubric": {"rubric_version": 1}})
    monkeypatch.setattr(contracts, "validate_similarity_report", lambda *a: None)
    monkeypatch.setattr(contracts, "validate_assessment_report", lambda *a: None)
    monkeypatch.setattr(schema_validation, "validate_json_schema", lambda *a, **kw: None)
    request = {
        "config_id": PROFILE, "config_sha256": digest, "run_type": run_type,
        "report_chunks": [{"text": "Synthetic report."}], "source_chunks": [],
        "compiled_rubric": {"rubric_version": 1},
    }
    result = bounded.execute_snapshot(request)
    assert bool(p1_calls) == (run_type in {"SIMILARITY", "BOTH"})
    assert bool(p2_calls) == bool(loaded) == (run_type in {"ASSESSMENT", "BOTH"})
    if p2_calls:
        assert loaded == [(config["models"]["assessment_verifier"], config["pipeline2"]["llm_verification"])]
        assert p2_calls[0]["config"]["evidence_context"] == config["pipeline2"]["evidence_context"]
        assert p2_calls[0]["llm_verifier"] is verifier
        assert result["execution"]["hardware"]["device"] == "local_model_service"
    else:
        assert result["execution"]["models"] == {"encoder": None, "reranker": None}
    # Untrusted request budget never becomes the child CPU budget.
    assert bounded._cpu_seconds({**request, "limits": {"wall_seconds": 1_000_000}}) == 170


def test_v9_adds_only_the_new_profile_without_mutating_applied_v8():
    assert schema_checksum(VALIDATORS_V8, INDEXES_V8) == "3904d53a2dd5a05ab5dce86212d612028f2ab12c24318e0effb527fb0d3eb153"
    for name, validator in migration.VALIDATORS_V9.items():
        copied = deepcopy(validator)
        previous = VALIDATORS_V8[name]["$jsonSchema"]["properties"]["config_id"]
        assert copied["$jsonSchema"]["properties"]["config_id"]["enum"] == [*previous["enum"], PROFILE]
        copied["$jsonSchema"]["properties"]["config_id"] = previous
        assert copied == VALIDATORS_V8[name]
        assert migration.INDEXES_V9[name] == INDEXES_V8[name]


def test_v9_uses_a_separate_ledger_identity(monkeypatch):
    calls = []
    monkeypatch.setattr(migration, "apply_migration", lambda db, **kw: calls.append((db, kw)) or {"status": "APPLIED"})
    database = object()
    assert migration.apply_schema_v9(database, code_commit="a" * 40, applied_by="test-operator") == {"status": "APPLIED"}
    assert calls[0][0] is database
    assert calls[0][1]["migration_id"] == "009-local-llm-assessment-profile-v2"
    assert calls[0][1]["validators"] is migration.VALIDATORS_V9
