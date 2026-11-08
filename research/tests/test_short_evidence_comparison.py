"""Audit controlled-run artifacts before interpreting synthetic A5/A6 metrics."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from research.offline_retrieval.analysis.short_evidence_comparison import (
    compare,
    render,
    verify_candidates,
)
from research.offline_retrieval.common import read_json, read_jsonl, sha256_file
from research.tests.test_short_evidence_runner import A6, _prepare, _run


@pytest.fixture
def completed_synthetic_run(tmp_path):
    manifest_path, config_path, config = _prepare(tmp_path / "input")
    config["candidate_retrieval_depth"] = 100
    config["retrieval_depth"] = 100
    config["metric_cutoffs"] = [1, 10, 100]
    config["protocol"] = {"dataset_role": "TEST_ONLY_CONTROLLED_SHORT_EVIDENCE"}
    config_path.write_text(json.dumps(config), encoding="utf-8")

    manifest = read_json(manifest_path)
    queries_path = manifest_path.parent / manifest["files"]["queries"]["path"]
    queries = read_jsonl(queries_path)
    parents = {query["query_id"]: "synthetic-parent-" + str(index // 2)
               for index, query in enumerate(queries)}
    for query in queries:
        query["parent_annotation_id"] = parents[query["query_id"]]
    queries_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                                    for item in queries), encoding="utf-8")
    qrels_path = manifest_path.parent / manifest["files"]["qrels"]["path"]
    qrels = read_jsonl(qrels_path)
    for qrel in qrels:
        qrel["parent_annotation_id"] = parents[qrel["query_id"]]
    qrels_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                                  for item in qrels), encoding="utf-8")
    for name, path in [("queries", queries_path), ("qrels", qrels_path)]:
        manifest["files"][name]["sha256"] = sha256_file(path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    run_dir = tmp_path / "completed-run"
    _run(manifest_path, config_path, run_dir)
    return run_dir, queries_path


def test_comparison_preserves_test_only_status_and_audits_the_paired_arms(completed_synthetic_run):
    run_dir, queries_path = completed_synthetic_run
    result = compare(run_dir, queries_path, repetitions=100, seed=43)
    assert compare(run_dir, queries_path, repetitions=100, seed=43) == result
    assert result["result_classification"] == "TEST_ONLY"
    assert result["dataset_role"] == "TEST_ONLY_CONTROLLED_SHORT_EVIDENCE"
    assert result["audit"]["candidate_pool_and_supports_equal"] is True
    assert result["audit"]["query_count"] == 3
    assert result["parent_recall_at_100"] == {"A5": 1.0, "A6": 1.0}
    assert set(result["bootstrap"]["paired_deltas"]) == {"A6-A5"}
    assert result["bootstrap"]["parent_count"] == 2
    assert result["bootstrap"]["interval"]["paired_resamples"] is True
    assert result["audit"]["tokenization"]["A6"]["scored_support_requests"] == result["audit"]["tokenization"]["A5"]["scored_support_requests"]
    assert result["audit"]["tokenization"]["A6"]["truncated_support_requests"] == 0
    markdown = render(result)
    assert "TEST_ONLY" in markdown
    assert "A6 minus A5" in markdown
    assert "not independent cold latency" in markdown


@pytest.mark.parametrize("filename", ["predictions.jsonl", "metrics.json"])
def test_comparison_rejects_changed_prediction_or_metric_bytes(completed_synthetic_run, filename):
    run_dir, queries_path = completed_synthetic_run
    artifact = run_dir / filename
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="artifact checksum mismatch"):
        compare(run_dir, queries_path, repetitions=10)


def test_comparison_rejects_changed_parent_mapping_bytes(completed_synthetic_run):
    run_dir, queries_path = completed_synthetic_run
    queries_path.write_bytes(queries_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="parent mapping does not match"):
        compare(run_dir, queries_path, repetitions=10)


@pytest.mark.parametrize("kind, message", [
    ("candidate", "candidate pools differ"),
    ("support", "selected support passages differ"),
    ("head", "reranking head or upstream ranks differ"),
    ("tail", "unscored tails differ"),
    ("gold", "inference-only crop provenance"),
    ("visible_span", "cannot claim full original raw spans"),
])
def test_comparison_refuses_changed_controls_or_unproven_crop_provenance(completed_synthetic_run, kind, message):
    run_dir, _queries_path = completed_synthetic_run
    predictions = deepcopy(read_jsonl(run_dir / "predictions.jsonl"))
    record = next(item for item in predictions if item["method"] == A6)
    head = record["candidates"][0]
    if kind == "candidate":
        head["document_id"] = "changed-candidate"
    elif kind == "support":
        head["cross_encoder_scores_by_support"][0]["support_id"] = "changed-support"
    elif kind == "head":
        head["pre_rerank_rank"] += 1
    elif kind == "tail":
        tail = next(item for item in record["candidates"] if not item["reranked"])
        tail["candidate_score"] += 1
    elif kind == "gold":
        head["cross_encoder_scores_by_support"][0]["cross_encoder_input"]["evidence_window"]["gold_used"] = True
    else:
        head["cross_encoder_scores_by_support"][0]["model_visible_source_spans"] = head["source_spans"]
    with pytest.raises(ValueError, match=message):
        verify_candidates(predictions)
