"""Collection-scoped database identities, separate from application RBAC.

No runtime identity inherits readWrite/dbAdmin/root. The migration principal
can repair data during maintenance but cannot create users/roles or drop data.
Backup/restore credentials are deliberately not provisioned until the restore
procedure and storage manifest are implemented and tested.
"""

from __future__ import annotations

from typing import Any

from pymongo.database import Database


COLLECTIONS = frozenset({
    "users", "workspaces", "memberships", "documents", "document_versions",
    "file_objects", "document_elements", "chunks", "governance_records",
    "dataset_manifests", "dataset_memberships", "rubrics", "rubric_versions",
    "jobs", "index_generations", "graph_nodes", "graph_edges", "analysis_runs",
    "evidence_items", "assessment_proposals", "reviews", "publications",
    "deletion_requests", "tombstones", "audit_events", "schema_migrations",
    "auth_credentials", "auth_sessions", "auth_throttles", "rubric_operations", "document_operations",
    "index_heads", "index_operations", "analysis_results", "analysis_operations", "item_annotations",
})
API_WRITES = frozenset({
    "users", "workspaces", "memberships", "documents", "document_versions",
    "file_objects", "governance_records", "dataset_manifests", "dataset_memberships",
    "rubrics", "rubric_versions", "jobs", "analysis_runs", "reviews", "publications",
    "deletion_requests", "tombstones",
    "auth_credentials", "auth_sessions", "auth_throttles", "rubric_operations", "document_operations",
    "index_generations", "index_heads", "index_operations", "analysis_operations", "item_annotations",
})
WORKER_WRITES = frozenset({
    "documents", "document_versions", "file_objects", "document_elements", "chunks",
    "jobs", "index_generations", "graph_nodes", "graph_edges", "analysis_runs",
    "evidence_items", "assessment_proposals", "deletion_requests", "tombstones",
    "index_heads", "analysis_results",
})
API_READS = COLLECTIONS - {"schema_migrations"}
WORKER_READS = frozenset({
    "users", "workspaces", "memberships", "documents", "document_versions",
    "file_objects", "document_elements", "chunks", "governance_records",
    "dataset_manifests", "dataset_memberships", "rubrics", "rubric_versions", "jobs",
    "index_generations", "graph_nodes", "graph_edges", "analysis_runs",
    "evidence_items", "assessment_proposals", "deletion_requests", "tombstones",
    "index_heads", "analysis_results",
})


def role_specifications(database_name: str) -> dict[str, list[dict[str, Any]]]:
    if not database_name or database_name in {"admin", "config", "local"}:
        raise ValueError("Use a dedicated application database")

    def runtime(reads: frozenset[str], writes: frozenset[str]) -> list[dict[str, Any]]:
        privileges = []
        for name in sorted(reads | writes | {"audit_events"}):
            actions = ["find"] if name in reads else []
            if name in writes:
                actions.extend(["insert", "update"])
            if name in {"audit_events", "item_annotations"}:
                # Authorized principals may append but never mutate or remove.
                # Workers have no item-annotation collection privileges.
                actions = ["find", "insert"] if name in reads else ["insert"]
            privileges.append({"resource": {"db": database_name, "collection": name}, "actions": actions})
        return privileges

    return {
        "kltn_api": runtime(API_READS, API_WRITES),
        "kltn_worker": runtime(WORKER_READS, WORKER_WRITES),
        "kltn_migration": [{
            "resource": {"db": database_name, "collection": ""},
            "actions": ["find", "insert", "update", "createCollection", "collMod",
                        "createIndex", "listCollections", "listIndexes"],
        }],
    }


def provision_roles(database: Database[dict[str, Any]]) -> None:
    """Administrative bootstrap, not callable with any generated runtime role."""
    for name, privileges in role_specifications(database.name).items():
        info = database.command({"rolesInfo": name})
        command = "updateRole" if info["roles"] else "createRole"
        database.command({command: name, "privileges": privileges, "roles": []})
