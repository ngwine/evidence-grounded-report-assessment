"""Transactional SQLite store for local Evidence Graph contract experiments.

It is not the production MongoDB adapter. Every read requires the complete
workspace/report/version/run scope; no unscoped graph enumeration is exposed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Any, Mapping

from .contract import GraphValidationError, _scope, canonical_json, digest, validate_snapshot


_DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS graphs (
    graph_key TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    report_version_id TEXT NOT NULL,
    graph_version TEXT NOT NULL,
    analysis_run_id TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    UNIQUE (workspace_id, report_id, report_version_id, graph_version)
);
CREATE TABLE IF NOT EXISTS graph_sources (
    graph_key TEXT NOT NULL REFERENCES graphs(graph_key) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL,
    document_version_id TEXT NOT NULL,
    PRIMARY KEY (graph_key, document_version_id)
);
CREATE INDEX IF NOT EXISTS graph_sources_version_idx
    ON graph_sources(workspace_id, document_version_id);
CREATE TABLE IF NOT EXISTS graph_spans (
    graph_key TEXT NOT NULL REFERENCES graphs(graph_key) ON DELETE CASCADE,
    span_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY (graph_key, span_id)
);
CREATE INDEX IF NOT EXISTS graph_spans_chunk_idx ON graph_spans(graph_key, chunk_id);
CREATE TABLE IF NOT EXISTS graph_nodes (
    graph_key TEXT NOT NULL REFERENCES graphs(graph_key) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY (graph_key, node_id)
);
CREATE INDEX IF NOT EXISTS graph_nodes_type_idx ON graph_nodes(graph_key, node_type);
CREATE TABLE IF NOT EXISTS graph_edges (
    graph_key TEXT NOT NULL REFERENCES graphs(graph_key) ON DELETE CASCADE,
    edge_id TEXT NOT NULL,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    review_state TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY (graph_key, edge_id),
    FOREIGN KEY (graph_key, from_node_id) REFERENCES graph_nodes(graph_key, node_id),
    FOREIGN KEY (graph_key, to_node_id) REFERENCES graph_nodes(graph_key, node_id)
);
CREATE INDEX IF NOT EXISTS graph_edges_out_idx
    ON graph_edges(graph_key, from_node_id, relation_type, review_state);
CREATE INDEX IF NOT EXISTS graph_edges_in_idx
    ON graph_edges(graph_key, to_node_id, relation_type);
CREATE TABLE IF NOT EXISTS graph_tombstones (
    workspace_id TEXT NOT NULL,
    document_version_id TEXT NOT NULL,
    PRIMARY KEY (workspace_id, document_version_id)
);
"""


class LocalGraphStore:
    """A small file-backed graph generation store with immutable rebuilds."""

    def __init__(self, path: str | Path):
        safe_path = self._prepare_private_path(path)
        self.connection = sqlite3.connect(safe_path, isolation_level=None)
        self.connection.executescript(_DDL)

    @staticmethod
    def _prepare_private_path(path: str | Path) -> str:
        if str(path) == ":memory:":
            return ":memory:"
        db_path = Path(path)
        parent = db_path.parent
        if any(ancestor.is_symlink() for ancestor in db_path.parents):
            raise GraphValidationError("graph database parent cannot traverse a symlink")
        if not parent.exists():
            parent.mkdir(mode=0o700)
        if not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077:
            raise GraphValidationError("graph database parent must be a private 0700 directory")
        if db_path.is_symlink():
            raise GraphValidationError("graph database cannot be a symlink")
        if db_path.exists():
            metadata = db_path.stat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or metadata.st_nlink != 1
            ):
                raise GraphValidationError("existing graph database must be a private 0600 regular file")
        else:
            flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(db_path, flags, 0o600)
            os.close(descriptor)
        return str(db_path)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "LocalGraphStore":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    @staticmethod
    def _graph_key(scope: Mapping[str, Any]) -> str:
        return "gg-" + digest(_scope(scope))

    def save(self, snapshot: Mapping[str, Any]) -> str:
        """Insert a generation atomically, replay it, or reject version reuse.

        Re-extracting with changed inputs/config requires a new graph_version.
        A tombstoned report/source version cannot be silently reintroduced.
        """
        graph = validate_snapshot(snapshot)
        scope = graph["scope"]
        key = self._graph_key(scope)
        serialized = canonical_json(graph)
        content_hash = digest(graph)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for source in graph["input_versions"]:
                tombstone = self.connection.execute(
                    "SELECT 1 FROM graph_tombstones WHERE workspace_id=? AND document_version_id=?",
                    (scope["workspace_id"], source["document_version_id"]),
                ).fetchone()
                if tombstone:
                    raise GraphValidationError("tombstoned input version cannot be rebuilt")

            existing = self.connection.execute(
                """SELECT analysis_run_id, content_sha256 FROM graphs
                   WHERE workspace_id=? AND report_id=? AND report_version_id=? AND graph_version=?""",
                (
                    scope["workspace_id"], scope["report_id"],
                    scope["report_version_id"], scope["graph_version"],
                ),
            ).fetchone()
            if existing:
                if existing == (scope["analysis_run_id"], content_hash):
                    self.connection.commit()
                    return "UNCHANGED"
                raise GraphValidationError("graph_version already exists with different run or content")

            self.connection.execute(
                "INSERT INTO graphs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key, scope["workspace_id"], scope["report_id"],
                    scope["report_version_id"], scope["graph_version"],
                    scope["analysis_run_id"], content_hash, serialized,
                ),
            )
            self.connection.executemany(
                "INSERT INTO graph_sources VALUES (?, ?, ?)",
                [
                    (key, scope["workspace_id"], item["document_version_id"])
                    for item in graph["input_versions"]
                ],
            )
            self.connection.executemany(
                "INSERT INTO graph_spans VALUES (?, ?, ?, ?)",
                [
                    (key, item["span_id"], item["chunk_id"], canonical_json(item))
                    for item in graph["spans"]
                ],
            )
            self.connection.executemany(
                "INSERT INTO graph_nodes VALUES (?, ?, ?, ?)",
                [
                    (key, item["node_id"], item["node_type"], canonical_json(item))
                    for item in graph["nodes"]
                ],
            )
            self.connection.executemany(
                "INSERT INTO graph_edges VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        key, item["edge_id"], item["from_node_id"], item["to_node_id"],
                        item["relation_type"], item["review_state"], canonical_json(item),
                    )
                    for item in graph["edges"]
                ],
            )
            self.connection.commit()
            return "CREATED"
        except Exception:
            self.connection.rollback()
            raise

    def _require_graph(self, scope: Mapping[str, Any]) -> str:
        key = self._graph_key(scope)
        row = self.connection.execute(
            "SELECT 1 FROM graphs WHERE graph_key=?", (key,)
        ).fetchone()
        if row is None:
            raise KeyError("graph generation not found in requested scope")
        return key

    def graph_info(self, scope: Mapping[str, Any]) -> dict[str, Any]:
        key = self._require_graph(scope)
        row = self.connection.execute(
            "SELECT content_sha256, snapshot_json FROM graphs WHERE graph_key=?", (key,)
        ).fetchone()
        graph = json.loads(row[1])
        return {
            "scope": graph["scope"], "content_sha256": row[0],
            "source_versions": graph["input_versions"],
            "span_count": len(graph["spans"]), "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
        }

    def list_nodes(self, scope: Mapping[str, Any], *, node_type: str | None = None) -> list[dict[str, Any]]:
        key = self._require_graph(scope)
        if node_type is None:
            rows = self.connection.execute(
                "SELECT record_json FROM graph_nodes WHERE graph_key=? ORDER BY node_id", (key,)
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT record_json FROM graph_nodes WHERE graph_key=? AND node_type=? ORDER BY node_id",
                (key, node_type),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_node(self, scope: Mapping[str, Any], node_id: str) -> dict[str, Any]:
        key = self._require_graph(scope)
        row = self.connection.execute(
            "SELECT record_json FROM graph_nodes WHERE graph_key=? AND node_id=?",
            (key, node_id),
        ).fetchone()
        if row is None:
            raise KeyError("node not found in requested scope")
        node = json.loads(row[0])
        spans = [self._span(key, span_id) for span_id in node["evidence_span_ids"]]
        return {"node": node, "evidence_spans": spans}

    def _span(self, key: str, span_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT record_json FROM graph_spans WHERE graph_key=? AND span_id=?",
            (key, span_id),
        ).fetchone()
        if row is None:
            raise GraphValidationError("stored graph has dangling evidence span")
        return json.loads(row[0])

    def outgoing_paths(
        self, scope: Mapping[str, Any], from_node_id: str, *,
        relation_type: str | None = None, accepted_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Return traceable one-hop paths. Scoring paths require accepted edges."""
        key = self._require_graph(scope)
        self.get_node(scope, from_node_id)
        query = "SELECT record_json FROM graph_edges WHERE graph_key=? AND from_node_id=?"
        values: list[str] = [key, from_node_id]
        if relation_type is not None:
            query += " AND relation_type=?"
            values.append(relation_type)
        if accepted_only:
            query += " AND review_state='ACCEPTED'"
        query += " ORDER BY edge_id"
        results = []
        for (payload,) in self.connection.execute(query, values):
            edge = json.loads(payload)
            results.append({
                "edge": edge,
                "target": self.get_node(scope, edge["to_node_id"]),
                "evidence_spans": [self._span(key, span_id) for span_id in edge["evidence_span_ids"]],
            })
        return results

    def tombstone_document_version(self, workspace_id: str, document_version_id: str) -> int:
        """Invalidate every generation derived from this version in one transaction."""
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise GraphValidationError("workspace_id is required")
        if not isinstance(document_version_id, str) or not document_version_id.strip():
            raise GraphValidationError("document_version_id is required")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            keys = [row[0] for row in self.connection.execute(
                "SELECT graph_key FROM graph_sources WHERE workspace_id=? AND document_version_id=?",
                (workspace_id, document_version_id),
            )]
            self.connection.execute(
                "INSERT OR IGNORE INTO graph_tombstones VALUES (?, ?)",
                (workspace_id, document_version_id),
            )
            self.connection.executemany(
                "DELETE FROM graphs WHERE graph_key=?", [(key,) for key in keys]
            )
            self.connection.commit()
            return len(keys)
        except Exception:
            self.connection.rollback()
            raise
