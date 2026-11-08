"""Graph provenance, scope isolation, rebuild and deletion invariants."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import stat

import pytest

from services.backend.src.kltn_ai.integrations.indexing.chunking import chunk_elements
from research.evidence_graph import (
    GraphValidationError, LocalGraphStore, make_chunk_reference, make_edge,
    make_node, make_span, validate_snapshot,
)


def _chunk(document_version_id: str, text: str, page: int) -> dict:
    chunk_id = f"chk-{document_version_id}-{page}"
    return {
        "schema_version": 2,
        "chunk_key": chunk_id,
        "chunk_id": chunk_id,
        "document_version_id": document_version_id,
        "raw_text": text,
        "normalized_text": text,
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_spans": [{
            "element_key": f"element-{document_version_id}-{page}",
            "element_type": "PARAGRAPH",
            "element_raw_char_start": 0,
            "element_raw_char_end": len(text),
            "element_normalized_char_start": 0,
            "element_normalized_char_end": len(text),
            "chunk_raw_char_start": 0,
            "chunk_raw_char_end": len(text),
            "chunk_normalized_char_start": 0,
            "chunk_normalized_char_end": len(text),
            "locator": {"page_index": page - 1, "page_number": page},
        }],
    }


def _fixture(*, graph_version: str = "gv1") -> dict:
    scope = {
        "workspace_id": "workspace-A", "report_id": "report-A",
        "report_version_id": "report-v1", "graph_version": graph_version,
        "analysis_run_id": "run-001",
    }
    report_chunk = make_chunk_reference(
        _chunk("report-v1", "BM25 improves recall on the pilot split.", 1),
        document_id="report-A",
    )
    source_chunk = make_chunk_reference(
        _chunk("source-v1", "Pilot: BM25 Recall@10 = 0.83; baseline Recall@10 = 0.70.", 2),
        document_id="source-A",
    )
    report_span = make_span(scope, report_chunk, 0)
    source_span = make_span(scope, source_chunk, 0)
    claim = make_node(
        scope, node_type="CLAIM", label="BM25 improves recall on the pilot split.",
        evidence_span_ids=[report_span["span_id"]], extractor="manual_fixture",
        model_or_rule_version="fixture-v1", confidence=1.0,
        created_at="2026-10-20T00:00:00Z",
        attributes={"claim_kind": "COMPARATIVE", "polarity": "POSITIVE"},
    )
    evidence = make_node(
        scope, node_type="EVIDENCE_SPAN", label="Recall@10 table row",
        evidence_span_ids=[source_span["span_id"]], extractor="manual_fixture",
        model_or_rule_version="fixture-v1", confidence=1.0,
        created_at="2026-10-20T00:00:00Z",
    )
    result = make_node(
        scope, node_type="RESULT", label="Recall@10 = 0.83 on pilot split",
        evidence_span_ids=[source_span["span_id"]], extractor="manual_fixture",
        model_or_rule_version="fixture-v1", confidence=1.0,
        created_at="2026-10-20T00:00:00Z",
        attributes={"metric": "Recall@10", "value": 0.83, "split": "pilot"},
    )
    conclusion = make_node(
        scope, node_type="CONCLUSION", label="The pilot result warrants further testing.",
        evidence_span_ids=[report_span["span_id"]], extractor="manual_fixture",
        model_or_rule_version="fixture-v1", confidence=1.0,
        created_at="2026-10-20T00:00:00Z",
    )
    support = make_edge(
        scope, relation_type="SUPPORTS", from_node_id=evidence["node_id"],
        to_node_id=claim["node_id"], evidence_span_ids=[source_span["span_id"]],
        extractor="manual_fixture", model_or_rule_version="fixture-v1",
        confidence=1.0, review_state="ACCEPTED", reviewer_id="fixture-reviewer",
        reviewed_at="2026-10-20T00:05:00Z",
    )
    conclusion_edge = make_edge(
        scope, relation_type="DRAWS_CONCLUSION", from_node_id=result["node_id"],
        to_node_id=conclusion["node_id"], evidence_span_ids=[source_span["span_id"]],
        extractor="manual_fixture", model_or_rule_version="fixture-v1",
        confidence=1.0, review_state="UNREVIEWED",
    )
    return {
        "schema_version": "evidence-graph-v1", "scope": scope,
        "input_versions": [
            {"document_id": "report-A", "document_version_id": "report-v1", "kind": "REPORT", "rights_state": "APPROVED"},
            {"document_id": "source-A", "document_version_id": "source-v1", "kind": "SOURCE", "rights_state": "APPROVED"},
        ],
        "chunks": [report_chunk, source_chunk],
        "spans": [report_span, source_span],
        "nodes": [claim, evidence, result, conclusion],
        "edges": [support, conclusion_edge],
    }


def test_local_graph_traceable_query_idempotent_rebuild_and_review_gate(tmp_path):
    graph = _fixture()
    assert validate_snapshot(graph)["scope"] == graph["scope"]
    db_path = tmp_path / "evidence.sqlite"
    with LocalGraphStore(db_path) as store:
        assert store.save(graph) == "CREATED"
        reordered = deepcopy(graph)
        for key in ("input_versions", "chunks", "spans", "nodes", "edges"):
            reordered[key].reverse()
        assert store.save(reordered) == "UNCHANGED"
        info = store.graph_info(graph["scope"])
        assert (info["span_count"], info["node_count"], info["edge_count"]) == (2, 4, 2)
        evidence = next(node for node in graph["nodes"] if node["node_type"] == "EVIDENCE_SPAN")
        path = store.outgoing_paths(graph["scope"], evidence["node_id"])
        assert len(path) == 1
        assert path[0]["edge"]["relation_type"] == "SUPPORTS"
        assert path[0]["target"]["node"]["node_type"] == "CLAIM"
        assert path[0]["evidence_spans"][0]["source_span"]["locator"]["page_number"] == 2
        result = next(node for node in graph["nodes"] if node["node_type"] == "RESULT")
        assert store.outgoing_paths(graph["scope"], result["node_id"]) == []
        assert len(store.outgoing_paths(graph["scope"], result["node_id"], accepted_only=False)) == 1
    with LocalGraphStore(db_path) as reopened:
        assert len(reopened.list_nodes(graph["scope"], node_type="CLAIM")) == 1


def test_wrong_scope_cannot_read_other_report_or_version(tmp_path):
    graph = _fixture()
    with LocalGraphStore(tmp_path / "scope.sqlite") as store:
        store.save(graph)
        for key, replacement in (
            ("workspace_id", "workspace-B"),
            ("report_id", "report-B"),
            ("report_version_id", "report-v2"),
            ("analysis_run_id", "run-002"),
        ):
            wrong_scope = {**graph["scope"], key: replacement}
            with pytest.raises(KeyError, match="scope"):
                store.list_nodes(wrong_scope)
        with pytest.raises(KeyError, match="scope"):
            store.get_node(graph["scope"], "gn-from-another-graph")


def test_rejects_dangling_cross_version_and_tampered_span():
    graph = _fixture()
    broken = deepcopy(graph)
    broken["edges"][0]["to_node_id"] = "gn-from-another-version"
    with pytest.raises(GraphValidationError, match="dangling or cross-generation"):
        validate_snapshot(broken)

    broken = deepcopy(graph)
    broken["nodes"][0]["scope"]["report_version_id"] = "report-v2"
    with pytest.raises(GraphValidationError, match="cross-report/version"):
        validate_snapshot(broken)

    broken = deepcopy(graph)
    broken["spans"][1]["source_span"]["locator"]["page_number"] = 99
    with pytest.raises(GraphValidationError, match="parser source span"):
        validate_snapshot(broken)

    broken = deepcopy(graph)
    broken["chunks"][1]["document_version_id"] = "source-v2"
    with pytest.raises(GraphValidationError, match="outside approved input scope"):
        validate_snapshot(broken)


def test_rejects_invalid_relation_and_unapproved_source():
    graph = _fixture()
    broken = deepcopy(graph)
    broken["edges"][0]["relation_type"] = "USES_METHOD"
    with pytest.raises(GraphValidationError, match="invalid endpoint types"):
        validate_snapshot(broken)

    broken = deepcopy(graph)
    broken["input_versions"][1]["rights_state"] = "PENDING"
    with pytest.raises(GraphValidationError, match="APPROVED"):
        validate_snapshot(broken)


def test_unreviewed_contradiction_is_not_an_accepted_evidence_path(tmp_path):
    graph = _fixture()
    evidence = next(node for node in graph["nodes"] if node["node_type"] == "EVIDENCE_SPAN")
    claim = next(node for node in graph["nodes"] if node["node_type"] == "CLAIM")
    source_span = next(span for span in graph["spans"] if span["document_version_id"] == "source-v1")
    graph["edges"].append(make_edge(
        graph["scope"], relation_type="CONTRADICTS",
        from_node_id=evidence["node_id"], to_node_id=claim["node_id"],
        evidence_span_ids=[source_span["span_id"]], extractor="manual_fixture",
        model_or_rule_version="fixture-v1", confidence=0.4,
        review_state="UNREVIEWED",
    ))
    with LocalGraphStore(tmp_path / "unreviewed.sqlite") as store:
        store.save(graph)
        assert store.outgoing_paths(
            graph["scope"], evidence["node_id"], relation_type="CONTRADICTS"
        ) == []
        candidates = store.outgoing_paths(
            graph["scope"], evidence["node_id"], relation_type="CONTRADICTS",
            accepted_only=False,
        )
        assert len(candidates) == 1
        assert candidates[0]["edge"]["review_state"] == "UNREVIEWED"


def test_rejects_cross_report_node_scope_even_when_span_exists():
    graph = _fixture()
    foreign_scope = {**graph["scope"], "report_id": "report-B"}
    graph["nodes"][0] = make_node(
        foreign_scope, node_type="CLAIM", label="A different report's claim",
        evidence_span_ids=[graph["spans"][0]["span_id"]],
        extractor="manual_fixture", model_or_rule_version="fixture-v1",
        confidence=1.0, created_at="2026-10-20T00:00:00Z",
        attributes={"claim_kind": "FACTUAL", "polarity": "POSITIVE"},
    )
    with pytest.raises(GraphValidationError, match="cross-report/version"):
        validate_snapshot(graph)


def test_parser_projection_rejects_modified_content_and_locator_bounds():
    chunk = _chunk("report-v1", "A short claim.", 1)
    chunk["normalized_text"] = "Modified claim."
    with pytest.raises(GraphValidationError, match="does not match normalized text"):
        make_chunk_reference(chunk, document_id="report-A")

    chunk = _chunk("report-v1", "A short claim.", 1)
    chunk["source_spans"][0]["chunk_raw_char_end"] = 1000
    with pytest.raises(GraphValidationError, match="exceeds chunk text"):
        make_chunk_reference(chunk, document_id="report-A")


def test_projection_accepts_real_chunker_output_and_preserves_authoritative_span():
    [chunk] = chunk_elements([{
        "type": "paragraph", "text": "Nội dung báo cáo có provenance thật.",
        "para_index": 2, "page": 3, "section_path": ["Method"],
    }], max_tokens=100, min_tokens=0)
    reference = make_chunk_reference(chunk, document_id="report-A")
    scope = {
        "workspace_id": "workspace-A", "report_id": "report-A",
        "report_version_id": chunk["document_version_id"],
        "graph_version": "gv1", "analysis_run_id": "run-001",
    }
    span = make_span(scope, reference, 0)
    assert reference["chunk_id"] == chunk["chunk_id"]
    assert span["source_span"] == chunk["source_spans"][0]
    assert span["source_span"]["locator"]["legacy_page"] == 3


def test_immutable_generation_tombstone_and_cascade(tmp_path):
    graph = _fixture()
    with LocalGraphStore(tmp_path / "cleanup.sqlite") as store:
        store.save(graph)
        changed = deepcopy(graph)
        changed["edges"][0]["review_state"] = "UNREVIEWED"
        changed["edges"][0]["reviewer_id"] = None
        changed["edges"][0]["reviewed_at"] = None
        with pytest.raises(GraphValidationError, match="graph_version already exists"):
            store.save(changed)
        assert store.graph_info(graph["scope"])["edge_count"] == 2
        assert store.tombstone_document_version("workspace-A", "source-v1") == 1
        assert store.tombstone_document_version("workspace-A", "source-v1") == 0
        with pytest.raises(KeyError, match="scope"):
            store.list_nodes(graph["scope"])
        with pytest.raises(GraphValidationError, match="tombstoned"):
            store.save(graph)
        with pytest.raises(GraphValidationError, match="tombstoned"):
            store.save(_fixture(graph_version="gv2"))
        counts = [store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("graphs", "graph_sources", "graph_spans", "graph_nodes", "graph_edges")]
        assert counts == [0, 0, 0, 0, 0]


def test_database_requires_private_file_and_parent(tmp_path):
    private_dir = tmp_path / "private"
    path = private_dir / "graph.sqlite"
    with LocalGraphStore(path) as store:
        store.save(_fixture())
    assert stat.S_IMODE(private_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    path.chmod(0o644)
    with pytest.raises(GraphValidationError, match="private 0600"):
        LocalGraphStore(path)
    path.chmod(0o600)

    symlink_path = private_dir / "alias.sqlite"
    symlink_path.symlink_to(path)
    with pytest.raises(GraphValidationError, match="symlink"):
        LocalGraphStore(symlink_path)

    public_dir = tmp_path / "public"
    public_dir.mkdir(mode=0o755)
    public_dir.chmod(0o755)
    with pytest.raises(GraphValidationError, match="private 0700"):
        LocalGraphStore(public_dir / "graph.sqlite")
    assert not (public_dir / "graph.sqlite").exists()
