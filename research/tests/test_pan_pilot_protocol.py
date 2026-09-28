"""Static gates for the versioned PAN pilot protocol and governance templates."""

from __future__ import annotations

from pathlib import Path

from research.offline_retrieval.common import read_json


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "research" / "configs" / "retrieval"
DATASET_DIR = REPO_ROOT / "research" / "datasets" / "similarity"
ASSESSMENT_DATASET_DIR = REPO_ROOT / "research" / "datasets" / "assessment"
LOCKED_E5_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
EXPECTED_METHODS = {
    "fixed_window_bm25",
    "structure_bm25",
    "structure_dense",
    "structure_hybrid_rrf",
}


def test_pan_pilot_configs_lock_same_baselines_and_model_revision():
    pc11 = read_json(CONFIG_DIR / "pan-pc-11-pilot-v1.json")
    pan13 = read_json(CONFIG_DIR / "pan13-component-pilot-v1.json")

    for config in (pc11, pan13):
        assert set(config["methods"]) == EXPECTED_METHODS
        assert config["fixed_window"] == {"size_tokens": 256, "stride_tokens": 128}
        assert config["bm25"] == {"k1": 1.2, "b": 0.75}
        assert config["dense"]["model"] == "intfloat/multilingual-e5-small"
        assert config["dense"]["revision"] == LOCKED_E5_REVISION
        assert config["rrf"] == {"k": 60}
        assert config["protocol"]["official_pan_result"] is False

    assert pc11["metrics"]["target_scope"] == "document"
    assert pan13["metrics"]["target_scope"] == "span"


def test_executed_pan_pc11_dense_and_multiview_configs_are_locked():
    dense_hybrid = read_json(
        CONFIG_DIR / "pan-pc-11-dense-hybrid-pilot-v1.json"
    )
    multiview = read_json(
        CONFIG_DIR / "pan-pc-11-multiview-hybrid-pilot-v1.json"
    )

    for config in (dense_hybrid, multiview):
        assert config["candidate_retrieval_depth"] == 200
        assert config["retrieval_depth"] == 100
        assert config["metric_cutoffs"] == [1, 5, 10, 20, 100]
        assert config["fixed_window"] == {"size_tokens": 256, "stride_tokens": 128}
        assert config["bm25"] == {"k1": 1.2, "b": 0.75}
        assert config["dense"]["model"] == "intfloat/multilingual-e5-small"
        assert config["dense"]["revision"] == LOCKED_E5_REVISION
        assert config["rrf"] == {"k": 60}
        assert config["metrics"]["target_scope"] == "document"
        assert config["protocol"]["official_pan_result"] is False

    assert dense_hybrid["methods"] == [
        "structure_dense",
        "structure_hybrid_rrf",
    ]
    assert multiview["methods"] == [
        "fixed_window_bm25",
        "structure_dense",
        "multiview_hybrid_rrf",
    ]


def test_pan_manifest_templates_remain_fail_closed_until_review():
    templates = [
        DATASET_DIR
        / "pan-pc-11-source-retrieval-pilot-v1"
        / "dataset-manifest.template.json",
        DATASET_DIR
        / "pan13-span-retrieval-oracle-pilot-v1"
        / "dataset-manifest.template.json",
    ]

    for path in templates:
        manifest = read_json(path)
        governance = manifest["governance"]
        assert governance["status"] == "PENDING"
        assert governance["approver"] is None
        assert governance["approved_at"] is None
        assert set(manifest["files"]) == {
            "documents",
            "chunks",
            "queries",
            "qrels",
        }


def test_in_domain_assessment_template_is_mandatory_and_fail_closed():
    manifest = read_json(
        ASSESSMENT_DATASET_DIR
        / "in-domain-report-rubric-pilot-v1"
        / "dataset-manifest.template.json"
    )

    assert manifest["governance"]["status"] == "PENDING"
    assert manifest["governance"]["classification"] == "RESTRICTED_EDUCATION_DATA"
    assert manifest["annotation"]["label_set"] == [
        "MET",
        "UNMET",
        "CANNOT_ASSESS",
    ]
    assert manifest["annotation"]["evidence_relations"] == [
        "SUPPORTED",
        "CONTRADICTED",
        "INSUFFICIENT",
    ]
