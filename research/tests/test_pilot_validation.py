"""Unit tests for approved-pack governance and semantic provenance gates."""

from __future__ import annotations

import pytest

from research.offline_retrieval.validation import validate_approved_governance


def _approved_manifest():
    return {
        "governance": {
            "status": "APPROVED",
            "classification": "RESEARCH_DATA",
            "contains_pii": False,
            "retention": "Delete local copy after thesis acceptance",
        },
        "source": {
            "archives": [
                {
                    "name": "corpus.zip",
                    "local_sha256": "a" * 64,
                    "size_bytes": 123,
                    "provider_checksum_verified": True,
                }
            ]
        },
        "transformation": {
            "converter": "research.pan_pilot",
            "converter_provenance": {"code_sha256": "b" * 64},
        },
    }


def test_approved_pack_requires_explicit_pii_and_retention_decisions():
    manifest = _approved_manifest()
    manifest["governance"]["contains_pii"] = "UNKNOWN"
    with pytest.raises(ValueError, match="explicit boolean"):
        validate_approved_governance(manifest)

    manifest = _approved_manifest()
    manifest["governance"]["retention"] = None
    with pytest.raises(ValueError, match="governance.retention"):
        validate_approved_governance(manifest)


def test_approved_pan_pack_requires_verified_archive_and_converter_provenance():
    manifest = _approved_manifest()
    validate_approved_governance(manifest)

    manifest["source"]["archives"][0]["provider_checksum_verified"] = False
    with pytest.raises(ValueError, match="provider checksum"):
        validate_approved_governance(manifest)

    manifest = _approved_manifest()
    manifest["transformation"]["converter_provenance"]["code_sha256"] = "unknown"
    with pytest.raises(ValueError, match="code_sha256"):
        validate_approved_governance(manifest)
