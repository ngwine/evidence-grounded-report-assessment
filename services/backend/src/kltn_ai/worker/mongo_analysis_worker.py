"""Durable ANALYZE worker publishing both pipelines under one lease fence."""

from __future__ import annotations

import hashlib
import subprocess
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from bson import ObjectId
from pymongo.database import Database

from ..db.mongo_jobs import MongoJobQueue
from ..domain.analysis import AnalysisService, _sha, bson_limit, evidence_sha
from ..domain.audit import append_event
from ..domain.documents import _common, _options
from ..domain.errors import DomainError
from .bounded_pipeline import PipelineRejected, ROOT, run_bounded
from .mongo_worker import LeaseLost


def _now() -> datetime:
    return datetime.now(UTC)


def _identity(run_id: ObjectId, kind: str, key: str) -> ObjectId:
    return ObjectId(hashlib.sha256(f"{run_id}\0{kind}\0{key}".encode()).digest()[:12])


def _repository() -> dict[str, Any]:
    def git(*arguments: str) -> str | None:
        try:
            result = subprocess.run(["git", *arguments], cwd=ROOT, timeout=5,
                capture_output=True, text=True, check=False)
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None
    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=normal")
    # File names/content never enter the manifest. Dirty status is explicit.
    return {"commit": commit, "dirty": status != "" if status is not None else None}


class MongoAnalysisWorker:
    def __init__(self, database: Database[dict[str, Any]], private_root: Path | str,
                 *, owner: str = "mongo-analysis-worker", transactional: bool = True,
                 executor: Callable[..., dict[str, Any]] | None = None,
                 lease_seconds: int = 60, indexes: Any = None):
        if type(lease_seconds) is not int or not 30 <= lease_seconds <= 3600:
            raise ValueError("Analysis lease must cover heartbeat and commit budgets")
        self.db = database
        self.service = AnalysisService(database, private_root, transactional=transactional, indexes=indexes)
        self.queue = MongoJobQueue(database.jobs)
        self.owner, self.lease_seconds = owner, lease_seconds
        self.executor = executor or run_bounded

    def _lease(self, job: dict[str, Any]) -> dict[str, Any]:
        return {"_id": job["_id"], "state": "RUNNING", "revision": job["revision"],
                "lease_owner": self.owner, "lease_expires_at": {"$gt": _now()}}

    def _authorized(self, job: dict[str, Any], *, session: Any = None) -> tuple[dict[str, Any], dict[str, Any]]:
        if job["resource_ref"]["type"] != "ANALYSIS_RUN" or job["resource_ref"]["version_id"] != job["resource_ref"]["id"]:
            raise DomainError(409, "ANALYSIS_INPUT_CHANGED", "Invalid run job reference")
        run = self.service.get(job["created_by"], job["workspace_id"], job["resource_ref"]["id"], session=session)
        self.service.policy.require(job["created_by"], job["workspace_id"], "run.create", session=session)
        if run["job_id"] != job["_id"] or run["created_by"] != job["created_by"]:
            raise DomainError(409, "ANALYSIS_INPUT_CHANGED", "Invalid run job owner")
        return run, self.service.snapshot(job["created_by"], job["workspace_id"], run, session=session)

    def _start(self, job: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        with self.service.documents.transaction() as session:
            options = _options(session)
            run, snapshot = self._authorized(job, session=session)
            fenced = self.db.jobs.update_one(self._lease(job), {"$set": {"progress": {"step": "ANALYZING"},
                "updated_at": _now()}}, **options)
            if fenced.matched_count != 1:
                raise LeaseLost("Lease lost")
            changed = self.db.analysis_runs.update_one({"_id": run["_id"], "state": {"$in": ["QUEUED", "RUNNING"]},
                "lifecycle_state": "ACTIVE"}, {"$set": {"state": "RUNNING", "updated_at": _now()},
                "$inc": {"revision": 1}}, **options)
            if changed.matched_count != 1:
                raise LeaseLost("Run is no longer writable")
        return run, snapshot

    def _evidence(self, run: dict[str, Any], snapshot: dict[str, Any], output: dict[str, Any]) -> list[dict[str, Any]]:
        report_map = {item["chunk_id"]: item for item in snapshot["report_chunks"]}
        source_map = {item["chunk_id"]: item for item in snapshot["source_chunks"]}
        now = _now()
        records = []

        def record(pipeline: str, key: str, report_chunk: dict[str, Any],
                   source_chunk: dict[str, Any] | None, checklist: str | None,
                   details: dict[str, Any], relation: str, reason: str) -> None:
            source = source_chunk or report_chunk
            quote = source["normalized_text"][:4000]
            evidence = {"evidence_key": key, "source_document_version_id": source["document_version_id"],
                "chunk_ids": [source["chunk_id"]], "locator": deepcopy(source["locator"]),
                "quote_text": quote, "quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
                "verification_state": relation, "verification_reason_code": reason,
                "details": deepcopy(details)}
            value = {"_id": _identity(run["_id"], "evidence", key), **_common(run["created_by"], now),
                "workspace_id": run["workspace_id"], "analysis_run_id": run["_id"],
                "document_version_id": run["document_version_id"], "pipeline": pipeline,
                "report_chunk_id": report_chunk["chunk_id"],
                "source_chunk_id": source_chunk["chunk_id"] if source_chunk else None,
                "source_version_id": ObjectId(source_chunk["document_version_id"]) if source_chunk else None,
                "checklist_id": checklist, "evidence": evidence}
            bson_limit(value)
            records.append(value)

        similarity = output.get("similarity")
        if similarity is not None:
            for match in similarity["matches"]:
                report, source = report_map.get(match["report_chunk_id"]), source_map.get(match["source_chunk_id"])
                if report is None or source is None or match["source_document_id"] != source["document_id"]:
                    raise DomainError(409, "PROVENANCE_INVALID", "Similarity output contains an invalid chunk reference")
                key = f"similarity:{report['chunk_id']}:{source['chunk_id']}"
                exact = match["classification_status"] == "EVIDENCE_BACKED_EXACT_MATCH"
                semantic = match["classification_status"] == "MODEL_SUPPORTED_SEMANTIC_MATCH"
                record("SIMILARITY", key, report, source, None, match,
                       "SUPPORTED" if exact or semantic else "INSUFFICIENT",
                       "EXACT_ALIGNED_TEXT" if exact else "MODEL_SENTENCE_EQUIVALENCE_REQUIRES_REVIEW"
                       if semantic else "UNVERIFIED_RETRIEVAL_CANDIDATE")
        assessment = output.get("assessment")
        if assessment is not None:
            for checklist in assessment["checklist_results"]:
                for evidence in checklist["evidence_pack"]:
                    chunk = report_map.get(evidence["chunk_id"])
                    if chunk is None or evidence["document_version_id"] != str(run["document_version_id"]):
                        raise DomainError(409, "PROVENANCE_INVALID", "Assessment output contains an invalid chunk reference")
                    key = f"assessment:{checklist['checklist_id']}:{chunk['chunk_id']}"
                    record("ASSESSMENT", key, chunk, None, checklist["checklist_id"],
                        {"retrieved_evidence": evidence, "checklist_outcome": checklist["checklist_outcome"],
                         "matched_evidence_spans": checklist["matched_evidence_spans"],
                         "negated_evidence_spans": checklist["negated_evidence_spans"],
                         "non_asserted_evidence_spans": checklist.get("non_asserted_evidence_spans", []),
                         "withheld_contradiction_spans": checklist.get("withheld_contradiction_spans", [])},
                        checklist["verification_relation"], checklist["reason_code"])
        if len(records) > 3000 or len({item["_id"] for item in records}) != len(records):
            raise DomainError(409, "ANALYSIS_OUTPUT_LIMIT", "Evidence output exceeds the local analysis budget")
        return records

    def _persist(self, job: dict[str, Any], run: dict[str, Any], snapshot: dict[str, Any],
                 output: dict[str, Any], repository: dict[str, Any]) -> None:
        from research.core_mvp.contracts import validate_assessment_report, validate_similarity_report
        from research.schema_validation import validate_json_schema
        for kind in ("similarity", "assessment"):
            expected = run["run_type"] == "BOTH" or run["run_type"] == kind.upper()
            if expected != (output.get(kind) is not None):
                raise DomainError(409, "ANALYSIS_OUTPUT_INVALID", "Selected pipeline output is missing or unexpected")
            if expected:
                (validate_similarity_report if kind == "similarity" else validate_assessment_report)(output[kind])
                validate_json_schema(output[kind], kind=kind)
        if output["execution"]["config_sha256"] != run["config_sha256"]:
            raise DomainError(409, "ANALYSIS_CONFIG_CHANGED", "Execution configuration does not match the run")
        now = _now()
        manifest = {"schema_version": 1, "analysis_run_id": str(run["_id"]),
            "run_type": run["run_type"], "config_id": run["config_id"], "config_sha256": run["config_sha256"],
            "repository": repository, "frozen_inputs": deepcopy(run["frozen_inputs"]),
            "index_generation_ids": [str(value) for value in run["index_generation_ids"]],
            "rubric_version_id": str(run["rubric_version_id"]) if run["rubric_version_id"] else None,
            **deepcopy(output["execution"]), "completed_at": now.isoformat(),
            "proposal_only": True, "gold_metrics_available": False}
        result = {"_id": _identity(run["_id"], "result", "v1"), **_common(job["created_by"], now),
            "workspace_id": run["workspace_id"], "analysis_run_id": run["_id"],
            "document_version_id": run["document_version_id"], "similarity": output.get("similarity"),
            "assessment": output.get("assessment"), "manifest": manifest,
            "result_sha256": _sha({"similarity": output.get("similarity"), "assessment": output.get("assessment"), "manifest": manifest})}
        evidence = self._evidence(run, snapshot, output)
        result["evidence_sha256"] = evidence_sha(evidence)
        bson_limit(result)
        with self.service.documents.transaction() as session:
            options = _options(session)
            self._authorized(job, session=session)
            fenced = self.db.jobs.update_one(self._lease(job), {"$set": {"state": "SUCCEEDED",
                "lease_owner": None, "lease_expires_at": None, "finished_at": now, "updated_at": now,
                "progress": {"step": "SUCCEEDED"}}, "$inc": {"revision": 1}}, **options)
            if fenced.matched_count != 1:
                raise LeaseLost("Lease lost")
            self.db.analysis_results.insert_one(result, **options)
            if evidence:
                self.db.evidence_items.insert_many(evidence, **options)
            changed = self.db.analysis_runs.update_one({"_id": run["_id"], "state": "RUNNING",
                "lifecycle_state": "ACTIVE", "result_id": None}, {"$set": {"state": "SUCCEEDED",
                "result_id": result["_id"], "manifest": manifest, "failure_code": None, "completed_at": now,
                "updated_at": now, "updated_by": job["created_by"]}, "$inc": {"revision": 1}}, **options)
            if changed.matched_count != 1:
                raise LeaseLost("Run is no longer writable")
            append_event(self.db, actor_id=job["created_by"], workspace_id=job["workspace_id"],
                action="ANALYSIS_COMPLETED", resource_type="ANALYSIS_RUN", resource_id=run["_id"],
                request_id=job["correlation_id"], session=session)

    def _fail(self, job: dict[str, Any], code: str, *, retryable: bool = False) -> None:
        with self.service.documents.transaction() as session:
            options = _options(session)
            now = _now()
            retry = retryable and job["attempt"] < job["max_attempts"]
            updates = {"state": "QUEUED" if retry else "FAILED_FINAL", "error_code": code,
                "lease_owner": None, "lease_expires_at": None, "available_at": now, "updated_at": now,
                "progress": {"step": "QUEUED" if retry else "FAILED_FINAL"}}
            if not retry:
                updates["finished_at"] = now
            fenced = self.db.jobs.update_one(self._lease(job), {"$set": updates, "$inc": {"revision": 1}}, **options)
            if fenced.matched_count != 1:
                return
            self.db.analysis_runs.update_one({"_id": job["resource_ref"]["id"], "state": {"$in": ["QUEUED", "RUNNING"]},
                "result_id": None}, {"$set": {"state": "QUEUED" if retry else "FAILED", "failure_code": code,
                "completed_at": None if retry else now, "updated_at": now}, "$inc": {"revision": 1}}, **options)
            append_event(self.db, actor_id=job["created_by"], workspace_id=job["workspace_id"],
                action="ANALYSIS_FAILED", resource_type="ANALYSIS_RUN", resource_id=job["resource_ref"]["id"],
                request_id=job["correlation_id"], outcome="ERROR", reason_code=code, session=session)

    def _reconcile(self) -> bool:
        any_changed = False
        for candidate in self.db.jobs.find({"job_type": "ANALYZE", "state": "FAILED_FINAL",
                                            "error_code": "LEASE_EXHAUSTED"}).limit(20):
            with self.service.documents.transaction() as session:
                options = _options(session)
                terminal = self.db.jobs.find_one({"_id": candidate["_id"], "revision": candidate["revision"],
                    "state": "FAILED_FINAL", "error_code": "LEASE_EXHAUSTED"}, **options)
                if terminal is None:
                    continue
                now = _now()
                changed = self.db.analysis_runs.update_one({"_id": terminal["resource_ref"]["id"],
                    "state": {"$in": ["QUEUED", "RUNNING"]}, "result_id": None},
                    {"$set": {"state": "FAILED", "failure_code": "LEASE_EXHAUSTED", "completed_at": now,
                        "updated_at": now}, "$inc": {"revision": 1}}, **options)
                any_changed |= changed.matched_count == 1
        return any_changed

    def process_one(self) -> bool:
        claimed = self.queue.claim(owner=self.owner, job_type="ANALYZE", lease_seconds=self.lease_seconds)
        if claimed is None:
            return self._reconcile()
        running = self.queue.start(job_id=claimed["_id"], owner=self.owner, revision=claimed["revision"])
        if running is None:
            return True
        last = time.monotonic()

        def heartbeat() -> None:
            nonlocal last
            # Check cancellation even between renewal intervals. A parent whose
            # process lost its lease must kill its child, not keep computing.
            if self.db.jobs.find_one(self._lease(running), {"_id": 1}) is None:
                raise LeaseLost("Lease lost")
            if time.monotonic() - last >= min(5, self.lease_seconds / 4):
                renewed = self.queue.heartbeat(job_id=running["_id"], owner=self.owner,
                    revision=running["revision"], lease_seconds=self.lease_seconds)
                if renewed is None:
                    raise LeaseLost("Lease lost")
                running.update(renewed)
                last = time.monotonic()

        try:
            run, snapshot = self._start(running)
            repository = _repository()
            output = self.executor(snapshot, heartbeat=heartbeat)
            heartbeat()
            self._persist(running, run, snapshot, output, repository)
        except LeaseLost:
            pass
        except DomainError as error:
            self._fail(running, error.code)
        except PipelineRejected as error:
            code = str(error)
            if not code.startswith("ANALYSIS_") or len(code) > 64:
                code = "ANALYSIS_PIPELINE_REJECTED"
            self._fail(running, code)
        except Exception:  # noqa: BLE001 - never persist model messages or source content in errors.
            self._fail(running, "ANALYSIS_INTERNAL_ERROR", retryable=True)
        return True
