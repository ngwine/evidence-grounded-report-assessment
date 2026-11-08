"""Opt-in profile boundaries; doubles test orchestration, not NLI quality."""

from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from services.backend.src.kltn_ai.db.analysis_schema import INDEXES_V4, VALIDATORS_V4
from services.backend.src.kltn_ai.db.migrations import schema_checksum
from services.backend.src.kltn_ai.db import semantic_analysis_schema as migration
from services.backend.src.kltn_ai.db import semantic_runtime_schema as runtime_migration
from services.backend.src.kltn_ai.domain.indexes import locked_config
from services.backend.src.kltn_ai.worker import bounded_pipeline as bounded


@pytest.mark.parametrize("profile,expected", [
    ("bm25-smoke", "23cba942effdce878ac4c6a53927b9dbca22f686bdc4ba080b879102b0122c14"),
    ("research-v0", "b564a28ce9bb4c4aa130c192192408e4ef24180ad4df4d983c5052bc863c94d6"),
])
def test_historical_operational_configuration_hashes_are_unchanged(profile, expected):
    assert bounded.configuration(profile)[1] == expected


def test_new_profile_keeps_bm25_retrieval_and_p2_and_adds_only_opt_in_verifier():
    old, _ = bounded.configuration("bm25-smoke")
    new, sha = bounded.configuration("bm25-nli-v1")
    assert new["pipeline2"] == old["pipeline2"]
    assert {k: v for k, v in new["pipeline1"].items() if k != "semantic_verification"} == old["pipeline1"]
    assert set(new["models"]) == {"semantic_verifier"}
    assert new["pipeline1"]["semantic_verification"]["enabled"] is True
    assert new["pipeline1"]["semantic_verification"]["max_context_sentences"] == 2
    assert new["pipeline1"]["semantic_verification"]["entailment_threshold"] == 0.65
    assert new["models"]["semantic_verifier"]["model"] == "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
    assert new["models"]["semantic_verifier"]["revision"] == "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"
    indexed, _ = locked_config("bm25-nli-v1")
    assert indexed == new
    assert len(sha) == 64


def test_rrf_profile_changes_only_the_dense_view_with_the_same_nli_and_p2():
    baseline, _ = bounded.configuration("bm25-nli-v1")
    new, sha = bounded.configuration("rrf-nli-v1")
    research, _ = bounded.configuration("research-v0")
    assert new["pipeline2"] == baseline["pipeline2"]
    assert new["models"]["semantic_verifier"] == baseline["models"]["semantic_verifier"]
    assert new["models"]["dense"] == research["models"]["dense"]
    assert set(new["models"]) == {"dense", "semantic_verifier"}
    assert new["pipeline1"] == {**baseline["pipeline1"], "dense_enabled": True}
    assert new["pipeline1"]["reranker_enabled"] is False
    assert new["limits"] == baseline["limits"]
    assert new["limits"]["wall_seconds"] == 180
    assert locked_config("rrf-nli-v1")[0] == new
    assert len(sha) == 64


@pytest.mark.parametrize("profile", ["bm25-nli", "rrf-nli"])
def test_v2_profile_preserves_v1_and_adds_explicit_citation_guard_and_runtime(profile):
    old, _ = bounded.configuration(profile + "-v1")
    new, _ = bounded.configuration(profile + "-v2")
    assert old["limits"]["wall_seconds"] == 180
    assert new["limits"]["wall_seconds"] == 600
    for key in ("pipeline2", "seed", "documents"):
        assert new[key] == old[key]
    pipeline1 = deepcopy(new["pipeline1"])
    assert pipeline1["semantic_verification"].pop("citation_number_guard") == "LINKED_SINGLE_NUMERIC_MARKERS"
    assert pipeline1 == old["pipeline1"]
    assert old["models"]["semantic_verifier"]["device"] == "cpu"
    assert new["models"]["semantic_verifier"]["device"] == "mps"
    models = deepcopy(new["models"])
    models["semantic_verifier"]["device"] = "cpu"
    assert models == old["models"]
    if "dense" in new["models"]:
        assert new["models"]["dense"]["device"] == "cpu"
    assert {k: v for k, v in new["limits"].items() if k != "wall_seconds"} == {
        k: v for k, v in old["limits"].items() if k != "wall_seconds"}
    path = bounded.ROOT / "services/backend/configs" / (profile + "-v1.json")
    expected = {"bm25-nli": "cb4da282e6c158eb084aebfbcd7ca6fda4bfe34ea7f1a34870af68bd515c6eb7",
                "rrf-nli": "f66f20e1f840c8bfc733095972eb2b166e5edd9abb2e142ab11d8577f59d0038"}
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[profile]


def test_v7_expands_only_new_profile_ids_and_preserves_applied_v6_catalog():
    assert schema_checksum(migration.VALIDATORS_V6, migration.INDEXES_V6) == "99d56e805475d347bfe3ba819fd466024f978434c758fb910f1e23479a00c38a"
    for name, validator in runtime_migration.VALIDATORS_V7.items():
        copied = deepcopy(validator)
        assert copied["$jsonSchema"]["properties"]["config_id"]["enum"] == [
            "bm25-smoke", "research-v0", "bm25-nli-v1", "rrf-nli-v1", "bm25-nli-v2", "rrf-nli-v2"]
        copied["$jsonSchema"]["properties"]["config_id"] = migration.VALIDATORS_V6[name]["$jsonSchema"]["properties"]["config_id"]
        assert copied == migration.VALIDATORS_V6[name]
        assert runtime_migration.INDEXES_V7[name] == migration.INDEXES_V6[name]


@pytest.mark.parametrize("profile,expected", [
    ("bm25-smoke", 170), ("research-v0", 170), ("bm25-nli-v1", 170),
    ("rrf-nli-v1", 170), ("bm25-nli-v2", 590), ("rrf-nli-v2", 590),
])
def test_child_cpu_budget_is_derived_from_hash_verified_server_profile(monkeypatch, tmp_path, profile, expected):
    import resource
    calls = []
    monkeypatch.setattr(resource, "setrlimit", lambda kind, values: calls.append((kind, values)))
    monkeypatch.setattr(bounded, "execute_snapshot", lambda request: {"synthetic": True})
    _, sha = bounded.configuration(profile)
    incoming, outgoing = tmp_path / "request.json", tmp_path / "result.json"
    # Untrusted request-local limits cannot change the server budget.
    incoming.write_text(json.dumps({"config_id": profile, "config_sha256": sha,
                                    "limits": {"wall_seconds": 1_000_000}}))
    assert bounded._child(incoming, outgoing) == 0
    assert (resource.RLIMIT_CPU, (expected, expected)) in calls
    assert json.loads(outgoing.read_text()) == {"synthetic": True}
    assert outgoing.stat().st_mode & 0o777 == 0o600


def test_cpu_budget_rejects_stale_config_hash_before_inference():
    with pytest.raises(bounded.PipelineRejected, match="ANALYSIS_CONFIG_CHANGED"):
        bounded._cpu_seconds({"config_id": "rrf-nli-v2", "config_sha256": "0" * 64})


def test_migration_expands_only_config_enum_without_mutating_historical_v4_catalog():
    assert schema_checksum(VALIDATORS_V4, INDEXES_V4) == "0a171fcea33f72d329404c56cce59ab364d7e87ba75a8f36645373edf5ac0b79"
    assert set(migration.VALIDATORS_V6) == {"index_generations", "index_heads", "analysis_runs"}
    for name, validator in migration.VALIDATORS_V6.items():
        copied = deepcopy(validator)
        assert copied["$jsonSchema"]["properties"]["config_id"]["enum"] == ["bm25-smoke", "research-v0", "bm25-nli-v1", "rrf-nli-v1"]
        copied["$jsonSchema"]["properties"]["config_id"] = VALIDATORS_V4[name]["$jsonSchema"]["properties"]["config_id"]
        assert copied == VALIDATORS_V4[name]
        assert migration.INDEXES_V6[name] == INDEXES_V4[name]
    assert VALIDATORS_V4["analysis_runs"]["$jsonSchema"]["properties"]["config_id"]["enum"] == ["bm25-smoke", "research-v0"]


def test_new_migration_records_its_own_ledger_identity(monkeypatch):
    calls = []
    monkeypatch.setattr(migration, "apply_migration", lambda database, **kwargs: calls.append((database, kwargs)) or {"status": "APPLIED"})
    database = object()
    assert migration.apply_schema_v6(database, code_commit="a" * 40, applied_by="test-operator") == {"status": "APPLIED"}
    assert calls[0][0] is database
    assert calls[0][1]["migration_id"] == "006-bm25-semantic-verification-profile-v1"
    assert calls[0][1]["validators"] is migration.VALIDATORS_V6


def _snapshot(profile, run_type):
    _, sha = bounded.configuration(profile)
    return {"config_id": profile, "config_sha256": sha, "run_type": run_type,
            "report_chunks": [{"text": "Synthetic report evidence."}], "source_chunks": [],
            "compiled_rubric": {"rubric_version": 1}}


def _stub_pipelines(monkeypatch):
    from research.core_mvp import assessment, similarity, contracts
    from research import schema_validation
    called = []
    monkeypatch.setattr(similarity, "run_similarity_pipeline", lambda *a, **k: called.append(("p1", k)) or {"test": "similarity"})
    monkeypatch.setattr(assessment, "run_assessment_pipeline", lambda chunks, rubric, **k: called.append(("p2", k)) or {"compiled_rubric": {"rubric_version": 1}})
    monkeypatch.setattr(contracts, "validate_similarity_report", lambda result: None)
    monkeypatch.setattr(contracts, "validate_assessment_report", lambda result: None)
    monkeypatch.setattr(schema_validation, "validate_json_schema", lambda *a, **k: None)
    return called


def test_nli_profile_loads_only_nli_and_forwards_its_metadata(monkeypatch):
    from research.core_mvp import runner, semantic_verification
    called = _stub_pipelines(monkeypatch)
    verifier = SimpleNamespace(metadata={"policy": "NLI_TEST_DOUBLE"})
    def forbidden(*args, **kwargs):
        pytest.fail("NLI-only BM25 profile must not load relevance/Dense models")
    monkeypatch.setattr(runner, "_load_encoder", forbidden)
    monkeypatch.setattr(runner, "_load_reranker", forbidden)
    monkeypatch.setattr(runner, "_seed_everything", lambda seed: None)
    monkeypatch.setattr(semantic_verification, "load_semantic_verifier", lambda model, policy: verifier)
    result = bounded.execute_snapshot(_snapshot("bm25-nli-v1", "SIMILARITY"))
    assert called[0][0] == "p1"
    assert called[0][1]["semantic_verifier"] is verifier
    assert result["execution"]["models"] == {"encoder": None, "reranker": None, "semantic_verifier": verifier.metadata}
    assert "model_devices" not in result["execution"]["hardware"]


@pytest.mark.parametrize("profile", ["bm25-nli-v1", "rrf-nli-v1"])
def test_assessment_only_request_does_not_load_unrequested_p1_models(monkeypatch, profile):
    from research.core_mvp import runner, semantic_verification
    called = _stub_pipelines(monkeypatch)
    def forbidden(*args, **kwargs):
        pytest.fail("ASSESSMENT-only request must not load P1's Dense/NLI models")
    monkeypatch.setattr(semantic_verification, "load_semantic_verifier", forbidden)
    monkeypatch.setattr(runner, "_load_encoder", forbidden)
    monkeypatch.setattr(runner, "_load_reranker", forbidden)
    result = bounded.execute_snapshot(_snapshot(profile, "ASSESSMENT"))
    assert [row[0] for row in called] == ["p2"]
    assert result["execution"]["models"] == {"encoder": None, "reranker": None}


def test_rrf_profile_loads_dense_and_nli_without_relevance_cross_encoder(monkeypatch):
    from research.core_mvp import runner, semantic_verification
    called = _stub_pipelines(monkeypatch)
    verifier = SimpleNamespace(metadata={"policy": "NLI_TEST_DOUBLE"})
    dense = SimpleNamespace(metadata={"model": "E5_TEST_DOUBLE"})
    loaded = []
    monkeypatch.setattr(runner, "_load_encoder", lambda models: loaded.append(models["dense"]) or dense)
    monkeypatch.setattr(runner, "_seed_everything", lambda seed: None)
    def forbidden(*args, **kwargs):
        pytest.fail("Controlled RRF profile must not load a relevance Cross-Encoder")
    monkeypatch.setattr(runner, "_load_reranker", forbidden)
    monkeypatch.setattr(semantic_verification, "load_semantic_verifier", lambda model, policy: verifier)
    result = bounded.execute_snapshot(_snapshot("rrf-nli-v1", "BOTH"))
    assert len(loaded) == 1
    assert [row[0] for row in called] == ["p1", "p2"]
    assert called[0][1]["config"]["dense_enabled"] is True
    assert called[0][1]["semantic_verifier"] is verifier
    assert called[0][1]["reranker"] is None
    assert called[1][1]["config"]["dense_enabled"] is False
    assert result["execution"]["models"] == {
        "encoder": dense.metadata, "reranker": None, "semantic_verifier": verifier.metadata,
    }


@pytest.mark.parametrize("profile,expected", [("bm25-nli-v2", "mps"), ("rrf-nli-v2", "mixed")])
def test_v2_execution_reports_actual_nli_mps_and_e5_cpu_devices(monkeypatch, profile, expected):
    from research.core_mvp import runner, semantic_verification
    _stub_pipelines(monkeypatch)
    # Use the real wrapper so its scorer metadata shape cannot be flattened
    # accidentally by a double while the production adapter stays nested.
    verifier = semantic_verification.BidirectionalNliVerifier(SimpleNamespace(metadata={
        "backend": "transformers_bidirectional_nli", "model": "NLI_TEST_DOUBLE", "device": "mps",
    }))
    dense = SimpleNamespace(metadata={"model": "E5_TEST_DOUBLE", "device": "cpu"})
    monkeypatch.setattr(runner, "_load_encoder", lambda models: dense)
    monkeypatch.setattr(runner, "_load_reranker", lambda *a: pytest.fail("No relevance CE in NLI v2"))
    monkeypatch.setattr(runner, "_seed_everything", lambda seed: None)
    def load(model, policy):
        assert model["device"] == "mps"
        return verifier
    monkeypatch.setattr(semantic_verification, "load_semantic_verifier", load)
    result = bounded.execute_snapshot(_snapshot(profile, "BOTH"))
    hardware = result["execution"]["hardware"]
    assert hardware["device"] == expected
    assert hardware["model_devices"]["semantic_verifier"] == "mps"
    assert result["execution"]["models"]["semantic_verifier"]["scorer"]["device"] == "mps"
    if profile == "rrf-nli-v2":
        assert hardware["model_devices"]["encoder"] == "cpu"
        assert result["execution"]["models"]["encoder"]["device"] == "cpu"


@pytest.mark.parametrize("metadata", [
    {}, {"scorer": {}}, {"scorer": None}, {"scorer": {"device": None}},
    {"scorer": {"device": ""}}, {"scorer": {"device": "   "}},
])
def test_v2_loaded_model_without_device_metadata_does_not_invent_cpu_or_mps(monkeypatch, metadata):
    from research.core_mvp import runner, semantic_verification
    _stub_pipelines(monkeypatch)
    monkeypatch.setattr(runner, "_seed_everything", lambda seed: None)
    monkeypatch.setattr(semantic_verification, "load_semantic_verifier",
                        lambda model, policy: SimpleNamespace(metadata=metadata))
    result = bounded.execute_snapshot(_snapshot("bm25-nli-v2", "SIMILARITY"))
    assert result["execution"]["hardware"]["device"] == "unknown"
    assert result["execution"]["hardware"]["model_devices"] == {"semantic_verifier": "unknown"}
    assert result["execution"]["models"]["semantic_verifier"] == metadata


def test_v2_reports_loaded_device_instead_of_requested_profile_device(monkeypatch):
    from research.core_mvp import runner, semantic_verification
    _stub_pipelines(monkeypatch)
    metadata = {"scorer": {"device": "cpu"}}
    monkeypatch.setattr(runner, "_seed_everything", lambda seed: None)
    def load(model, policy):
        assert model["device"] == "mps"
        return SimpleNamespace(metadata=metadata)
    monkeypatch.setattr(semantic_verification, "load_semantic_verifier", load)
    result = bounded.execute_snapshot(_snapshot("bm25-nli-v2", "SIMILARITY"))
    assert result["execution"]["hardware"]["device"] == "cpu"
    assert result["execution"]["hardware"]["model_devices"] == {"semantic_verifier": "cpu"}


def test_v2_assessment_only_request_does_not_claim_gpu_inference(monkeypatch):
    from research.core_mvp import runner, semantic_verification
    _stub_pipelines(monkeypatch)
    def forbidden(*args, **kwargs):
        pytest.fail("P2-only BM25 must not load a GPU or Dense model")
    monkeypatch.setattr(runner, "_load_encoder", forbidden)
    monkeypatch.setattr(semantic_verification, "load_semantic_verifier", forbidden)
    result = bounded.execute_snapshot(_snapshot("rrf-nli-v2", "ASSESSMENT"))
    assert result["execution"]["hardware"]["device"] == "cpu"
    assert result["execution"]["hardware"]["model_devices"] == {}


def test_v2_unavailable_locked_mps_does_not_fallback_to_cpu(monkeypatch):
    from research.core_mvp import runner, semantic_verification
    called = _stub_pipelines(monkeypatch)
    monkeypatch.setattr(runner, "_seed_everything", lambda seed: None)
    def unavailable(model, policy):
        assert model["device"] == "mps"
        raise RuntimeError("Synthetic MPS unavailable")
    monkeypatch.setattr(semantic_verification, "load_semantic_verifier", unavailable)
    with pytest.raises(RuntimeError, match="MPS unavailable"):
        bounded.execute_snapshot(_snapshot("bm25-nli-v2", "SIMILARITY"))
    assert called == []


def test_bad_profile_hash_is_rejected_before_models_or_pipelines(monkeypatch):
    _stub_pipelines(monkeypatch)
    request = _snapshot("bm25-nli-v1", "SIMILARITY")
    request["config_sha256"] = "0" * 64
    with pytest.raises(bounded.PipelineRejected, match="ANALYSIS_CONFIG_CHANGED"):
        bounded.execute_snapshot(request)
