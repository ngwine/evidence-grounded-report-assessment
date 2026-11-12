"""One-process offline runner for both thesis core-MVP pipelines."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

from research.offline_retrieval.common import read_json, sha256_file, write_json
from research.offline_retrieval.cross_encoder import (
    PairScorer,
    SentenceTransformersCrossEncoder,
)
from research.offline_retrieval.dense import Encoder, SentenceTransformerEncoder

from .assessment import run_assessment_pipeline
from .contracts import validate_assessment_report, validate_similarity_report
from .documents import ParsedDocument, parse_document, parse_documents
from .similarity import run_similarity_pipeline


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _git_value(*args: str) -> str | None:
    try:
        process = subprocess.run(
            ["git", *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if process.returncode != 0:
        return None
    # Keep leading spaces: ``git status --porcelain`` uses them as part of its
    # two-column status code.  Stripping them corrupts the first dirty path.
    return process.stdout.rstrip("\r\n")


def _repository_state() -> dict[str, Any]:
    status = _git_value("status", "--porcelain=v1")
    dirty_lines = status.splitlines() if status else []
    return {
        "commit": _git_value("rev-parse", "HEAD"),
        "branch": _git_value("branch", "--show-current"),
        "dirty": bool(dirty_lines),
        "dirty_paths": [line[3:] if len(line) > 3 else line for line in dirty_lines],
    }


def _hardware() -> dict[str, Any]:
    result: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python": sys.version.split()[0],
        "logical_cpu_count": os.cpu_count(),
    }
    try:
        import torch

        result["torch"] = {
            "version": torch.__version__,
            "mps_available": bool(
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            ),
            "cuda_available": bool(torch.cuda.is_available()),
        }
    except ImportError:
        result["torch"] = None
    return result


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy

        numpy.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:
        pass


def _load_encoder(config: Mapping[str, Any]) -> Encoder:
    dense = _object(config.get("dense"), "models.dense")
    if dense.get("backend") != "sentence_transformers":
        raise ValueError("models.dense.backend must be sentence_transformers")
    return SentenceTransformerEncoder(
        model=str(dense["model"]),
        revision=str(dense["revision"]),
        device=str(dense.get("device", "cpu")),
        batch_size=int(dense.get("batch_size", 16)),
        query_prefix=str(dense.get("query_prefix", "query: ")),
        document_prefix=str(dense.get("document_prefix", "passage: ")),
    )


def _load_reranker(config: Mapping[str, Any]) -> PairScorer:
    cross_encoder = _object(config.get("cross_encoder"), "models.cross_encoder")
    if cross_encoder.get("backend") != "sentence_transformers_cross_encoder":
        raise ValueError(
            "models.cross_encoder.backend must be sentence_transformers_cross_encoder"
        )
    return SentenceTransformersCrossEncoder(
        model=str(cross_encoder["model"]),
        revision=str(cross_encoder["revision"]),
        device=str(cross_encoder.get("device", "cpu")),
        batch_size=int(cross_encoder.get("batch_size", 8)),
        max_length=(
            int(cross_encoder["max_length"])
            if cross_encoder.get("max_length") is not None
            else None
        ),
        score_output=str(cross_encoder.get("score_output", "raw_logit")),
    )


def _document_snapshot(parsed: ParsedDocument) -> dict[str, Any]:
    document = parsed.document
    return {
        "document_id": document["document_id"],
        "document_version_id": document["document_version_id"],
        "role": document["role"],
        "source_name": document["source_name"],
        "media_type": document["media_type"],
        "sha256": document["sha256"],
        "element_count": document["element_count"],
        "chunk_count": document["chunk_count"],
    }


def _require_file(path: str | Path, field: str) -> Path:
    resolved = Path(path).expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"{field} is not a file: {resolved}")
    return resolved


def _normalise_pipeline(value: str) -> str:
    canonical = value.casefold()
    aliases = {"1": "similarity", "2": "assessment", "all": "both"}
    canonical = aliases.get(canonical, canonical)
    if canonical not in {"similarity", "assessment", "both"}:
        raise ValueError("pipeline must be similarity, assessment, or both")
    return canonical


def run_core_mvp(
    *,
    report_path: str | Path,
    source_paths: Sequence[str | Path],
    rubric_path: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
    pipeline: str = "both",
    encoder: Encoder | None = None,
    reranker: PairScorer | None = None,
) -> dict[str, Any]:
    """Execute the selected core pipelines and write reproducible artifacts."""

    selected_pipeline = _normalise_pipeline(pipeline)
    report_file = _require_file(report_path, "report_path")
    rubric_file = _require_file(rubric_path, "rubric_path")
    config_file = _require_file(config_path, "config_path")
    sources = [_require_file(path, "source_paths") for path in source_paths]
    if selected_pipeline in {"similarity", "both"} and not sources:
        raise ValueError("Similarity pipeline requires at least one source document")
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    initial_hashes = {
        "report": sha256_file(report_file),
        "rubric": sha256_file(rubric_file),
        "config": sha256_file(config_file),
        "sources": [sha256_file(path) for path in sources],
    }
    raw_config = read_json(config_file)
    rubric = read_json(rubric_file)
    config = _object(raw_config, "config")
    _object(rubric, "rubric")
    if config.get("schema_version") != 1:
        raise ValueError("config.schema_version must equal 1")
    seed = config.get("seed", 20261013)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("config.seed must be an integer")
    _seed_everything(seed)

    document_config = _object(config.get("documents", {}), "config.documents")
    max_tokens = int(document_config.get("max_tokens", 220))
    min_tokens = int(document_config.get("min_tokens", 30))
    if max_tokens <= 0 or min_tokens <= 0 or min_tokens > max_tokens:
        raise ValueError("documents requires 0 < min_tokens <= max_tokens")

    timings: dict[str, float] = {}
    started = time.perf_counter()
    stage = time.perf_counter()
    report = parse_document(
        report_file,
        role="student-report",
        max_tokens=max_tokens,
        min_tokens=min_tokens,
    )
    source_documents = parse_documents(
        sources,
        role="comparison-source",
        max_tokens=max_tokens,
        min_tokens=min_tokens,
    )
    if any(
        source.document["sha256"] == report.document["sha256"]
        for source in source_documents
    ):
        raise ValueError("Source corpus must not contain the submitted report itself")
    timings["parse_and_chunk_seconds"] = time.perf_counter() - stage

    pipeline1_config = _object(config.get("pipeline1", {}), "config.pipeline1")
    pipeline2_config = _object(config.get("pipeline2", {}), "config.pipeline2")
    needs_dense = (
        selected_pipeline in {"similarity", "both"}
        and bool(pipeline1_config.get("dense_enabled", True))
    ) or (
        selected_pipeline in {"assessment", "both"}
        and bool(pipeline2_config.get("dense_enabled", True))
    )
    needs_reranker = (
        selected_pipeline in {"similarity", "both"}
        and bool(pipeline1_config.get("reranker_enabled", True))
    ) or (
        selected_pipeline in {"assessment", "both"}
        and bool(pipeline2_config.get("reranker_enabled", True))
    )
    model_config = _object(config.get("models", {}), "config.models")
    stage = time.perf_counter()
    if needs_dense and encoder is None:
        encoder = _load_encoder(model_config)
    if needs_reranker and reranker is None:
        reranker = _load_reranker(model_config)
    timings["model_load_seconds"] = time.perf_counter() - stage

    similarity_report: dict[str, Any] | None = None
    assessment_report: dict[str, Any] | None = None
    output_paths: dict[str, Path] = {}
    if selected_pipeline in {"similarity", "both"}:
        stage = time.perf_counter()
        source_chunks = [
            chunk for document in source_documents for chunk in document.chunks
        ]
        similarity_report = run_similarity_pipeline(
            report.chunks,
            source_chunks,
            config=pipeline1_config,
            encoder=encoder,
            reranker=reranker,
        )
        validate_similarity_report(similarity_report)
        similarity_path = output / "similarity-report.json"
        write_json(similarity_path, similarity_report)
        output_paths["similarity_report"] = similarity_path
        timings["pipeline1_seconds"] = time.perf_counter() - stage

    if selected_pipeline in {"assessment", "both"}:
        stage = time.perf_counter()
        assessment_report = run_assessment_pipeline(
            report.chunks,
            rubric,
            config=pipeline2_config,
            encoder=encoder,
            reranker=reranker,
        )
        validate_assessment_report(assessment_report)
        assessment_path = output / "assessment-report.json"
        write_json(assessment_path, assessment_report)
        output_paths["assessment_report"] = assessment_path
        timings["pipeline2_seconds"] = time.perf_counter() - stage

    current_hashes = {
        "report": sha256_file(report_file),
        "rubric": sha256_file(rubric_file),
        "config": sha256_file(config_file),
        "sources": [sha256_file(path) for path in sources],
    }
    if current_hashes != initial_hashes:
        raise RuntimeError("An input file changed while the MVP run was executing")

    timings["total_seconds"] = time.perf_counter() - started
    summary = {
        "schema_version": 1,
        "run_type": "CORE_MVP_FEASIBILITY_NOT_FINAL_EVALUATION",
        "pipeline": selected_pipeline,
        "pipeline1": (
            {
                "report_chunks": similarity_report["report_chunk_count"],
                "source_chunks": similarity_report["source_chunk_count"],
                "flagged_passage_coverage_percentage": similarity_report[
                    "flagged_passage_coverage_percentage"
                ],
                "provisional_review_report_chunks": similarity_report[
                    "provisional_review_report_chunks"
                ],
                "provisional_review_passage_coverage_percentage": similarity_report[
                    "provisional_review_passage_coverage_percentage"
                ],
                "exact_match_coverage_percentage": similarity_report[
                    "exact_match_coverage_percentage"
                ],
                "calibrated_similarity_percentage": similarity_report[
                    "calibrated_similarity_percentage"
                ],
                "selected_label_counts": similarity_report[
                    "label_counts_for_selected_matches"
                ],
                "classification_policy": similarity_report["classification_policy"],
                "semantic_classifier_available": similarity_report["semantic_classifier_available"],
                "review_source_groups": len(similarity_report["review_source_groups"]),
                "repeated_source_review_groups": sum(
                    group["report_chunk_count"] > 1
                    for group in similarity_report["review_source_groups"]
                ),
            }
            if similarity_report is not None
            else None
        ),
        "pipeline2": (
            {
                "checklist_outcome_counts": assessment_report[
                    "checklist_outcome_counts"
                ],
                "proposed_total_score": assessment_report["proposed_total_score"],
                "max_score": assessment_report["max_score"],
                "requires_lecturer_review": assessment_report[
                    "requires_lecturer_review"
                ],
            }
            if assessment_report is not None
            else None
        ),
        "timings_seconds": {key: round(value, 6) for key, value in timings.items()},
    }
    summary_path = output / "mvp-summary.json"
    write_json(summary_path, summary)
    output_paths["summary"] = summary_path

    manifest = {
        "schema_version": 1,
        "run_id": (
            "core-mvp-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + initial_hashes["report"][:12]
        ),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "FEASIBILITY_RUN_NOT_FINAL_RESEARCH_RESULT",
        "selected_pipeline": selected_pipeline,
        "seed": seed,
        "repository": _repository_state(),
        "hardware": _hardware(),
        "inputs": {
            "report": _document_snapshot(report),
            "sources": [_document_snapshot(item) for item in source_documents],
            "rubric": {"name": rubric_file.name, "sha256": initial_hashes["rubric"]},
            "config": {"name": config_file.name, "sha256": initial_hashes["config"]},
            "governance": {
                "mode": "MANUALLY_SUPPLIED_LOCAL_FEASIBILITY_INPUTS",
                "rights_verified_by_runner": False,
                "production_indexing_allowed": False,
            },
        },
        "models": {
            "dense": deepcopy(getattr(encoder, "metadata", None)),
            "cross_encoder": deepcopy(getattr(reranker, "metadata", None)),
        },
        "timings_seconds": {key: round(value, 6) for key, value in timings.items()},
        "outputs": {
            name: {"name": path.name, "sha256": sha256_file(path)}
            for name, path in sorted(output_paths.items())
        },
        "interpretation_limit": (
            "This run proves executable integration and produces inspectable evidence; "
            "it does not establish accuracy or superiority without a frozen labelled test set."
        ),
    }
    manifest_path = output / "run-manifest.json"
    write_json(manifest_path, manifest)
    output_paths["run_manifest"] = manifest_path
    return {
        "summary": summary,
        "manifest": manifest,
        "output_paths": {key: str(path) for key, path in output_paths.items()},
    }
