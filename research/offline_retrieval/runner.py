"""One-command offline retrieval experiment runner."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import platform
import random
import re
import subprocess
import time
from typing import Any

from .bm25 import rank_bm25
from .common import (
    canonical_json,
    read_json,
    read_jsonl,
    sha256_bytes,
    sha256_file,
    sha256_text,
    write_json,
    write_jsonl,
)
from .dense import Encoder, SentenceTransformerEncoder, rank_dense
from .fixed_window import build_fixed_windows
from .metrics import evaluate_document_rankings, evaluate_rankings
from .rrf import fuse_rrf
from .validation import (
    validate_approved_governance,
    validate_pan_semantic_provenance,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_METHODS = {
    "fixed_window_bm25",
    "structure_bm25",
    "structure_dense",
    "structure_hybrid_rrf",
}


def _portable_path(path: Path) -> str:
    """Avoid embedding developer home-directory paths in research artifacts."""

    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_unique(records: list[dict[str, Any]], field: str, label: str) -> None:
    values = [_require_non_empty_string(record.get(field), f"{label}.{field}") for record in records]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {field} in {label}")


def _resolve_dataset_files(manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Path]:
    files = manifest.get("files")
    required = {"documents", "chunks", "queries", "qrels"}
    if not isinstance(files, dict) or not required <= files.keys():
        raise ValueError(f"dataset manifest files must contain {sorted(required)}")
    resolved: dict[str, Path] = {}
    for name in sorted(required):
        entry = files[name]
        if not isinstance(entry, dict):
            raise ValueError(f"dataset files.{name} must be an object")
        relative_path = _require_non_empty_string(entry.get("path"), f"files.{name}.path")
        expected_checksum = _require_non_empty_string(
            entry.get("sha256"), f"files.{name}.sha256"
        )
        path = (manifest_path.parent / relative_path).resolve()
        try:
            path.relative_to(manifest_path.parent.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Dataset file path escapes the pack directory: {relative_path}"
            ) from exc
        if not path.is_file():
            raise ValueError(f"Dataset file does not exist: {path}")
        actual_checksum = sha256_file(path)
        if actual_checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch for {name}: expected {expected_checksum}, got {actual_checksum}"
            )
        resolved[name] = path
    return resolved


def validate_inputs(
    dataset_manifest_path: str | Path,
    config_path: str | Path,
    *,
    allow_test_encoder: bool = False,
) -> dict[str, Any]:
    dataset_manifest_path = Path(dataset_manifest_path).resolve()
    config_path = Path(config_path).resolve()
    manifest = read_json(dataset_manifest_path)
    config = read_json(config_path)
    if not isinstance(manifest, dict) or not isinstance(config, dict):
        raise ValueError("Dataset manifest and config must be JSON objects")

    governance = manifest.get("governance")
    if not isinstance(governance, dict):
        raise ValueError("Dataset governance record is required")
    if governance.get("status") != "APPROVED":
        raise ValueError("Dataset is not APPROVED; indexing/experiments are denied")
    purposes = governance.get("allowed_purposes")
    if not isinstance(purposes, list) or "RETRIEVAL_EXPERIMENT" not in purposes:
        raise ValueError("Dataset is not approved for RETRIEVAL_EXPERIMENT")
    _require_non_empty_string(governance.get("approver"), "governance.approver")
    _require_non_empty_string(governance.get("approved_at"), "governance.approved_at")
    _require_non_empty_string(governance.get("rights_basis"), "governance.rights_basis")
    validate_approved_governance(manifest)
    _require_non_empty_string(manifest.get("dataset_id"), "dataset_id")
    _require_non_empty_string(manifest.get("dataset_version"), "dataset_version")

    paths = _resolve_dataset_files(dataset_manifest_path, manifest)
    documents = read_jsonl(paths["documents"])
    chunks = read_jsonl(paths["chunks"])
    queries = read_jsonl(paths["queries"])
    qrels = read_jsonl(paths["qrels"])
    if not documents or not chunks or not queries or not qrels:
        raise ValueError("documents, chunks, queries and qrels must all be non-empty")
    _validate_unique(documents, "document_id", "documents")
    _validate_unique(chunks, "chunk_id", "chunks")
    _validate_unique(queries, "query_id", "queries")
    _validate_unique(qrels, "qrel_id", "qrels")

    document_map = {document["document_id"]: document for document in documents}
    query_ids = {query["query_id"] for query in queries}
    for document in documents:
        if not isinstance(document.get("text"), str):
            raise ValueError(f"Document {document['document_id']} requires string text")
    for query in queries:
        if not isinstance(query.get("text"), str) or not query["text"].strip():
            raise ValueError(f"Query {query['query_id']} requires non-empty text")
    for chunk in chunks:
        if not isinstance(chunk.get("text"), str) or not chunk["text"].strip():
            raise ValueError(f"Chunk {chunk['chunk_id']} requires non-empty text")
        document_id = _require_non_empty_string(chunk.get("document_id"), "chunk.document_id")
        if document_id not in document_map:
            raise ValueError(f"Chunk {chunk['chunk_id']} references unknown document {document_id}")
        spans = chunk.get("source_spans")
        if not isinstance(spans, list) or not spans:
            raise ValueError(f"Chunk {chunk['chunk_id']} requires source_spans")
        for span in spans:
            span_document_id = span.get("document_id", document_id)
            if span_document_id != document_id:
                raise ValueError(f"Chunk {chunk['chunk_id']} mixes document ids")
            start, end = span.get("raw_start"), span.get("raw_end")
            if (
                isinstance(start, bool)
                or isinstance(end, bool)
                or not isinstance(start, int)
                or not isinstance(end, int)
                or not 0 <= start < end <= len(document_map[document_id]["text"])
            ):
                raise ValueError(f"Chunk {chunk['chunk_id']} has invalid raw source span")
            span["document_id"] = document_id

    for qrel_index, qrel in enumerate(qrels):
        query_id = _require_non_empty_string(qrel.get("query_id"), "qrel.query_id")
        document_id = _require_non_empty_string(qrel.get("document_id"), "qrel.document_id")
        if query_id not in query_ids:
            raise ValueError(f"qrels[{qrel_index}] references unknown query {query_id}")
        if document_id not in document_map:
            raise ValueError(f"qrels[{qrel_index}] references unknown document {document_id}")
        start, end = qrel.get("raw_start"), qrel.get("raw_end")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(document_map[document_id]["text"]):
            raise ValueError(f"qrels[{qrel_index}] has invalid raw span")
        relevance = qrel.get("relevance")
        if (
            isinstance(relevance, bool)
            or not isinstance(relevance, (int, float))
            or relevance <= 0
        ):
            raise ValueError(f"qrels[{qrel_index}] relevance must be positive")

    qrel_query_ids = {qrel["query_id"] for qrel in qrels}
    if qrel_query_ids != query_ids:
        missing = sorted(query_ids - qrel_query_ids)
        extra = sorted(qrel_query_ids - query_ids)
        raise ValueError(
            "Every pilot query must have positive qrels; "
            f"missing={missing}, extra={extra}"
        )

    split = manifest.get("split")
    if not isinstance(split, dict) or not isinstance(split.get("document_ids"), list):
        raise ValueError("Dataset split.document_ids is required")
    split_ids = split["document_ids"]
    if len(split_ids) != len(set(split_ids)):
        raise ValueError("Dataset split.document_ids must not contain duplicates")
    split_document_ids = set(split_ids)
    if split_document_ids != set(document_map):
        raise ValueError("Pilot manifest must list every document exactly once in split.document_ids")
    split_query_ids = split.get("query_ids")
    if split_query_ids is not None:
        if not isinstance(split_query_ids, list):
            raise ValueError("Dataset split.query_ids must be a list")
        if len(split_query_ids) != len(set(split_query_ids)):
            raise ValueError("Dataset split.query_ids must not contain duplicates")
        if set(split_query_ids) != query_ids:
            raise ValueError(
                "Pilot manifest must list every query exactly once in split.query_ids"
            )

    _require_non_empty_string(config.get("experiment_id"), "config.experiment_id")
    methods = config.get("methods")
    if not isinstance(methods, list) or set(methods) != REQUIRED_METHODS:
        raise ValueError(f"config.methods must contain exactly {sorted(REQUIRED_METHODS)}")
    seed = config.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("config.seed must be an integer")
    retrieval_depth = config.get("retrieval_depth")
    if not isinstance(retrieval_depth, int) or retrieval_depth <= 0:
        raise ValueError("config.retrieval_depth must be positive")
    cutoffs = config.get("metric_cutoffs")
    if not isinstance(cutoffs, list) or not cutoffs or any(not isinstance(value, int) or value <= 0 for value in cutoffs):
        raise ValueError("config.metric_cutoffs must be positive integers")
    if max(cutoffs) > retrieval_depth:
        raise ValueError("retrieval_depth must be >= every metric cutoff")
    candidate_depth = config.get("candidate_retrieval_depth", retrieval_depth)
    if (
        isinstance(candidate_depth, bool)
        or not isinstance(candidate_depth, int)
        or candidate_depth < retrieval_depth
    ):
        raise ValueError(
            "candidate_retrieval_depth must be an integer >= retrieval_depth"
        )

    fixed_window = config.get("fixed_window")
    bm25 = config.get("bm25")
    dense = config.get("dense")
    rrf = config.get("rrf")
    metrics = config.get("metrics")
    for name, value in (("fixed_window", fixed_window), ("bm25", bm25), ("dense", dense), ("rrf", rrf), ("metrics", metrics)):
        if not isinstance(value, dict):
            raise ValueError(f"config.{name} must be an object")
    size_tokens = fixed_window.get("size_tokens")
    stride_tokens = fixed_window.get("stride_tokens")
    if (
        isinstance(size_tokens, bool)
        or not isinstance(size_tokens, int)
        or size_tokens <= 0
    ):
        raise ValueError("fixed_window.size_tokens must be a positive integer")
    if (
        isinstance(stride_tokens, bool)
        or not isinstance(stride_tokens, int)
        or not 0 < stride_tokens <= size_tokens
    ):
        raise ValueError("fixed_window.stride_tokens must be in [1, size_tokens]")
    k1 = bm25.get("k1")
    b = bm25.get("b")
    if isinstance(k1, bool) or not isinstance(k1, (int, float)) or k1 <= 0:
        raise ValueError("bm25.k1 must be positive")
    if isinstance(b, bool) or not isinstance(b, (int, float)) or not 0 <= b <= 1:
        raise ValueError("bm25.b must be in [0, 1]")
    rrf_k = rrf.get("k")
    if isinstance(rrf_k, bool) or not isinstance(rrf_k, int) or rrf_k <= 0:
        raise ValueError("rrf.k must be a positive integer")
    overlap_threshold = metrics.get("gold_overlap_threshold")
    if (
        isinstance(overlap_threshold, bool)
        or not isinstance(overlap_threshold, (int, float))
        or not 0 < overlap_threshold <= 1
    ):
        raise ValueError("metrics.gold_overlap_threshold must be in (0, 1]")
    target_scope = metrics.get("target_scope", "span")
    if target_scope not in {"span", "document"}:
        raise ValueError("metrics.target_scope must be span or document")
    for index, qrel in enumerate(qrels):
        qrel_scope = qrel.get("target_scope", "span")
        if qrel_scope != target_scope:
            raise ValueError(
                f"qrels[{index}].target_scope={qrel_scope} does not match "
                f"metrics.target_scope={target_scope}"
            )
    transformation = manifest.get("transformation")
    if isinstance(transformation, dict):
        manifest_target_scope = transformation.get("target_scope")
        if manifest_target_scope is not None and manifest_target_scope != target_scope:
            raise ValueError(
                "Dataset transformation.target_scope does not match "
                "config.metrics.target_scope"
            )
    if dense.get("backend") == "injected_test":
        if not allow_test_encoder:
            raise ValueError("injected_test dense backend is test-only")
    elif dense.get("backend") != "sentence_transformers":
        raise ValueError("dense.backend must be sentence_transformers")
    _require_non_empty_string(dense.get("model"), "dense.model")
    revision = _require_non_empty_string(dense.get("revision"), "dense.revision")
    if revision.startswith("SET_"):
        raise ValueError("dense.revision must be an exact revision/checksum, not a placeholder")
    if dense.get("backend") == "sentence_transformers":
        model_value = dense["model"]
        configured_path = Path(model_value).expanduser()
        if not configured_path.is_absolute():
            configured_path = (config_path.parent / configured_path).resolve()
        if configured_path.exists():
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", revision):
                raise ValueError("A local Dense model requires revision=sha256:<64 hex>")
        elif not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
            raise ValueError("A cached model id requires an immutable 40–64 hex revision")

    validate_pan_semantic_provenance(
        manifest,
        documents,
        chunks,
        queries,
        qrels,
    )

    return {
        "dataset_manifest_path": dataset_manifest_path,
        "config_path": config_path,
        "dataset_manifest": manifest,
        "config": config,
        "paths": paths,
        "documents": documents,
        "chunks": chunks,
        "queries": queries,
        "qrels": qrels,
    }


def _git_metadata() -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    try:
        status = run("status", "--porcelain=v1", "--untracked-files=all")
        diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        untracked_output = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        untracked_records = []
        for raw_relative in untracked_output.split(b"\0"):
            if not raw_relative:
                continue
            relative = os.fsdecode(raw_relative)
            path = REPO_ROOT / relative
            if path.is_file():
                untracked_records.append(
                    {"path": relative, "sha256": sha256_file(path)}
                )
        return {
            "commit": run("rev-parse", "HEAD"),
            "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(status),
            "status_sha256": sha256_text(status),
            "tracked_diff_sha256": sha256_bytes(diff),
            "untracked_content_sha256": sha256_text(canonical_json(untracked_records)),
        }
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"error": type(exc).__name__}


def _total_memory_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _environment_metadata() -> dict[str, Any]:
    packages = {}
    for package in ("sentence-transformers", "torch", "numpy"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "memory_bytes": _total_memory_bytes(),
        "packages": packages,
    }


def _make_encoder(config: dict[str, Any], config_path: Path) -> Encoder:
    dense = config["dense"]
    model = dense["model"]
    configured_path = Path(model).expanduser()
    if not configured_path.is_absolute():
        candidate = (config_path.parent / configured_path).resolve()
        if candidate.exists():
            configured_path = candidate
    if configured_path.exists():
        model = str(configured_path)
    encoder = SentenceTransformerEncoder(
        model=model,
        revision=dense["revision"],
        device=dense.get("device", "cpu"),
        batch_size=int(dense.get("batch_size", 16)),
        query_prefix=dense.get("query_prefix", ""),
        document_prefix=dense.get("document_prefix", ""),
    )
    encoder.metadata["model"] = dense["model"]
    return encoder


def run_experiment(
    dataset_manifest_path: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
    *,
    encoder: Encoder | None = None,
    allow_test_encoder: bool = False,
) -> dict[str, Any]:
    loaded = validate_inputs(
        dataset_manifest_path,
        config_path,
        allow_test_encoder=allow_test_encoder,
    )
    config = loaded["config"]
    dense_backend = config["dense"]["backend"]
    if encoder is not None and dense_backend != "injected_test":
        raise ValueError(
            "An injected encoder is allowed only with dense.backend=injected_test; "
            "scientific runs must load the locked model from config"
        )
    random.seed(config["seed"])
    try:
        import torch
    except ImportError:
        torch = None
    if torch is not None:
        torch.manual_seed(config["seed"])

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    stage_timings: dict[str, float] = {}

    stage_start = time.perf_counter()
    fixed_windows = build_fixed_windows(
        loaded["documents"],
        size_tokens=int(config["fixed_window"]["size_tokens"]),
        stride_tokens=int(config["fixed_window"]["stride_tokens"]),
    )
    stage_timings["fixed_window_build"] = time.perf_counter() - stage_start

    depth = int(config["retrieval_depth"])
    candidate_depth = int(config.get("candidate_retrieval_depth", depth))
    target_scope = config["metrics"].get("target_scope", "span")
    stage_start = time.perf_counter()
    fixed_bm25 = rank_bm25(
        fixed_windows,
        loaded["queries"],
        top_k=candidate_depth,
        k1=float(config["bm25"]["k1"]),
        b=float(config["bm25"]["b"]),
        group_by_document=target_scope == "document",
    )
    stage_timings["fixed_window_bm25"] = time.perf_counter() - stage_start

    stage_start = time.perf_counter()
    structure_bm25 = rank_bm25(
        loaded["chunks"],
        loaded["queries"],
        top_k=candidate_depth,
        k1=float(config["bm25"]["k1"]),
        b=float(config["bm25"]["b"]),
        group_by_document=target_scope == "document",
    )
    stage_timings["structure_bm25"] = time.perf_counter() - stage_start

    if encoder is None:
        encoder = _make_encoder(config, loaded["config_path"])
    stage_start = time.perf_counter()
    structure_dense = rank_dense(
        loaded["chunks"],
        loaded["queries"],
        encoder=encoder,
        top_k=candidate_depth,
        group_by_document=target_scope == "document",
    )
    stage_timings["structure_dense"] = time.perf_counter() - stage_start

    stage_start = time.perf_counter()
    rrf_key = "document_id" if target_scope == "document" else "chunk_id"
    # RRF must see the configured candidate pool. Truncating each component to
    # the final output depth first hides consensus candidates that rank just
    # below that cutoff in the individual methods.
    hybrid = fuse_rrf(
        {"bm25": structure_bm25, "dense": structure_dense},
        rrf_k=int(config["rrf"]["k"]),
        top_k=depth,
        key_field=rrf_key,
    )
    fixed_bm25 = {
        query_id: candidates[:depth]
        for query_id, candidates in fixed_bm25.items()
    }
    structure_bm25 = {
        query_id: candidates[:depth]
        for query_id, candidates in structure_bm25.items()
    }
    structure_dense = {
        query_id: candidates[:depth]
        for query_id, candidates in structure_dense.items()
    }
    stage_timings["structure_hybrid_rrf"] = time.perf_counter() - stage_start

    rankings = {
        "fixed_window_bm25": fixed_bm25,
        "structure_bm25": structure_bm25,
        "structure_dense": structure_dense,
        "structure_hybrid_rrf": hybrid,
    }
    stage_start = time.perf_counter()
    if target_scope == "document":
        metric_results = {
            method: evaluate_document_rankings(
                result,
                loaded["qrels"],
                cutoffs=sorted(set(config["metric_cutoffs"])),
            )
            for method, result in rankings.items()
        }
    else:
        metric_results = {
            method: evaluate_rankings(
                result,
                loaded["qrels"],
                cutoffs=sorted(set(config["metric_cutoffs"])),
                overlap_threshold=float(
                    config["metrics"]["gold_overlap_threshold"]
                ),
            )
            for method, result in rankings.items()
        }
    stage_timings["evaluation"] = time.perf_counter() - stage_start

    prediction_records = [
        {"method": method, "query_id": query_id, "candidates": candidates}
        for method in sorted(rankings)
        for query_id, candidates in sorted(rankings[method].items())
    ]
    predictions_path = output_dir / "predictions.jsonl"
    metrics_path = output_dir / "metrics.json"
    write_jsonl(predictions_path, prediction_records)
    write_json(metrics_path, metric_results)

    finished_at = datetime.now(timezone.utc)
    config_sha256 = sha256_text(canonical_json(config))
    dataset_manifest = loaded["dataset_manifest"]
    manifest = {
        "schema_version": 1,
        "run_id": (
            f"{config['experiment_id']}-{started_at.strftime('%Y%m%dT%H%M%S%fZ')}-"
            f"{config_sha256[:10]}"
        ),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "result_classification": (
            "TEST_ONLY" if dense_backend == "injected_test" else dataset_manifest.get("result_classification", "PILOT")
        ),
        "git": _git_metadata(),
        "dataset": {
            "dataset_id": dataset_manifest["dataset_id"],
            "dataset_version": dataset_manifest["dataset_version"],
            "manifest_path": _portable_path(loaded["dataset_manifest_path"]),
            "manifest_sha256": sha256_file(loaded["dataset_manifest_path"]),
            "files": {
                name: {
                    "path": dataset_manifest["files"][name]["path"],
                    "sha256": sha256_file(path),
                }
                for name, path in sorted(loaded["paths"].items())
            },
            "split": dataset_manifest["split"],
            "governance": dataset_manifest["governance"],
        },
        "config": {
            "path": _portable_path(loaded["config_path"]),
            "sha256": config_sha256,
            "resolved": config,
        },
        "seed": config["seed"],
        "dense_encoder": getattr(encoder, "metadata", {"backend": dense_backend}),
        "hardware": _environment_metadata(),
        "timing_seconds": stage_timings,
        "artifacts": {
            "predictions": {
                "path": predictions_path.name,
                "sha256": sha256_file(predictions_path),
            },
            "metrics": {
                "path": metrics_path.name,
                "sha256": sha256_file(metrics_path),
            },
        },
    }
    manifest_path = output_dir / "run_manifest.json"
    write_json(manifest_path, manifest)
    return {
        "run_manifest": manifest,
        "run_manifest_path": manifest_path,
        "predictions_path": predictions_path,
        "metrics_path": metrics_path,
    }
