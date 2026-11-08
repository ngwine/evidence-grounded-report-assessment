"""Content-private, offline-only process boundary for the existing two pipelines.

The worker parent retains the Mongo lease; the child receives JSON snapshots,
never database credentials or client-selected paths. A lost lease terminates
the child before any result can be committed.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import re
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[5]
MAX_INPUT = 20 * 1024 * 1024
MAX_OUTPUT = 8 * 1024 * 1024


class PipelineRejected(RuntimeError):
    """Content-safe boundary error, safe to persist in the queue."""


class CachedDocumentEncoder:
    """Reuse verified generation vectors only for the document prefix/mode."""
    def __init__(self, encoder: Any, cache: dict[str, list[float]]):
        self.encoder, self.cache, self.mode = encoder, cache, "document"
        self.metadata = encoder.metadata
        self.reused = 0

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.encoder.set_mode(mode)

    def encode(self, texts):
        if self.mode != "document":
            return self.encoder.encode(texts)
        output = [self.cache.get(text) for text in texts]
        missing = [index for index, value in enumerate(output) if value is None]
        self.reused += len(texts) - len(missing)
        if missing:
            inferred = list(self.encoder.encode([texts[index] for index in missing]))
            if len(inferred) != len(missing):
                raise PipelineRejected("ANALYSIS_VECTOR_COUNT_MISMATCH")
            for index, vector in zip(missing, inferred, strict=True):
                output[index] = vector
        return output


def configuration(config_id: str) -> tuple[dict[str, Any], str]:
    """Load a server-locked profile; NLI v2 requires an Apple GPU via MPS.

    Its model adapter must reject unavailable MPS instead of substituting CPU.
    v1 remains the immutable CPU profile used by historical attempts.
    """
    if config_id not in {"bm25-smoke", "research-v0", "bm25-nli-v1", "rrf-nli-v1", "bm25-nli-v2", "rrf-nli-v2", "bm25-p2-llm-v1", "bm25-p2-llm-v2"}:
        raise ValueError("Unknown server-locked analysis configuration")
    if config_id in {"bm25-nli-v1", "rrf-nli-v1", "bm25-nli-v2", "rrf-nli-v2", "bm25-p2-llm-v1", "bm25-p2-llm-v2"}:
        config = json.loads((ROOT / "services/backend/configs" / f"{config_id}.json").read_text())
        if config.get("config_id") != config_id:
            raise ValueError("Server-locked analysis configuration identity mismatch")
        wall = config.get("limits", {}).get("wall_seconds")
        maximum_wall = 900 if config_id in {"bm25-p2-llm-v1", "bm25-p2-llm-v2"} else 600
        if type(wall) is not int or not 60 <= wall <= maximum_wall:
            raise ValueError("Server-locked analysis wall limit is outside its profile budget")
        if config_id in {"bm25-p2-llm-v1", "bm25-p2-llm-v2"}:
            model = config.get("models", {}).get("assessment_verifier", {})
            if (model.get("backend") != "ollama" or
                    not re.fullmatch(r"sha256:[0-9a-f]{64}", str(model.get("digest", "")))):
                raise ValueError("P2 LLM profile requires an immutable local model digest")
    else:
        # Retain the original resolved contents and hashes for existing runs.
        config = json.loads((ROOT / "research/configs/core-mvp-v0.json").read_text())
        if config_id == "bm25-smoke":
            for name in ("pipeline1", "pipeline2"):
                config[name]["dense_enabled"] = False
                config[name]["reranker_enabled"] = False
            config["models"] = {}
        # Lock these additional operational limits with the scientific settings.
        config.update({"config_id": config_id, "limits": {
            "max_report_chunks": 500, "max_source_chunks": 2000,
            "max_total_text_chars": 1_000_000, "max_result_bytes": MAX_OUTPUT,
            "wall_seconds": 180 if config_id == "research-v0" else 60,
        }})
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return config, digest


def _cpu_seconds(request: dict[str, Any]) -> int:
    """Derive CPU budget only from the hash-verified server profile."""
    config, digest = configuration(request["config_id"])
    if request.get("config_sha256") != digest:
        raise PipelineRejected("ANALYSIS_CONFIG_CHANGED")
    if request["config_id"] in {"bm25-nli-v2", "rrf-nli-v2"}:
        return min(590, config["limits"]["wall_seconds"] - 10)
    return 170


def _loaded_model_device(model: Any) -> str:
    """Read adapter provenance, including the NLI wrapper's nested scorer.

    A requested configuration device is not evidence of actual model use.
    Missing metadata stays unknown rather than silently claiming CPU.
    """
    metadata = getattr(model, "metadata", None)
    if isinstance(metadata, Mapping):
        scorer = metadata.get("scorer", metadata)
        if isinstance(scorer, Mapping):
            device = scorer.get("device")
            if isinstance(device, str) and device.strip():
                return device
    return "unknown"


def execute_snapshot(request: dict[str, Any]) -> dict[str, Any]:
    """Pure adapter shared by the bounded child and injected unit tests."""
    from research.core_mvp.assessment import run_assessment_pipeline
    from research.core_mvp.similarity import run_similarity_pipeline
    from research.core_mvp.contracts import validate_assessment_report, validate_similarity_report
    from research.schema_validation import validate_json_schema

    config, config_sha = configuration(request["config_id"])
    if config_sha != request["config_sha256"]:
        raise PipelineRejected("ANALYSIS_CONFIG_CHANGED")
    chunks, sources = request["report_chunks"], request["source_chunks"]
    limits = config["limits"]
    if (not chunks or len(chunks) > limits["max_report_chunks"]
            or len(sources) > limits["max_source_chunks"]
            or sum(len(item["text"]) for item in chunks + sources) > limits["max_total_text_chars"]):
        raise PipelineRejected("ANALYSIS_INPUT_LIMIT")
    run_type = request["run_type"]
    if run_type not in {"SIMILARITY", "ASSESSMENT", "BOTH"}:
        raise PipelineRejected("ANALYSIS_INVALID_TYPE")
    seed = config["seed"]
    random.seed(seed)
    encoder = reranker = semantic_verifier = llm_verifier = None
    start = time.perf_counter()
    active_pipelines = [config[name] for name, required in (
        ("pipeline1", run_type in {"SIMILARITY", "BOTH"}),
        ("pipeline2", run_type in {"ASSESSMENT", "BOTH"}),
    ) if required]
    needs_dense = any(pipeline.get("dense_enabled", True) for pipeline in active_pipelines)
    needs_reranker = any(pipeline.get("reranker_enabled", True) for pipeline in active_pipelines)
    semantic_policy = config["pipeline1"].get("semantic_verification", {})
    needs_semantic = (run_type in {"SIMILARITY", "BOTH"}
                      and semantic_policy.get("enabled", False))
    llm_policy = config["pipeline2"].get("llm_verification", {})
    needs_llm = run_type in {"ASSESSMENT", "BOTH"} and llm_policy.get("enabled", False)
    if needs_dense or needs_reranker or needs_semantic:
        # Existing adapters force local_files_only=True and immutable revisions.
        from research.core_mvp.runner import _load_encoder, _load_reranker, _seed_everything
        _seed_everything(seed)
        if needs_dense:
            encoder = _load_encoder(config["models"])
            encoder = CachedDocumentEncoder(encoder, request.get("source_vector_cache", {}))
        if needs_reranker:
            reranker = _load_reranker(config["models"])
        if needs_semantic:
            from research.core_mvp.semantic_verification import load_semantic_verifier
            semantic_verifier = load_semantic_verifier(
                config["models"].get("semantic_verifier", {}), semantic_policy,
            )
    if needs_llm:
        from research.core_mvp.llm_assessment import load_llm_assessment_verifier
        llm_verifier = load_llm_assessment_verifier(
            config["models"].get("assessment_verifier", {}), llm_policy,
        )
    timings = {"model_load_seconds": time.perf_counter() - start}
    similarity = assessment = None
    if run_type in {"SIMILARITY", "BOTH"}:
        stage = time.perf_counter()
        similarity = run_similarity_pipeline(chunks, sources, config=config["pipeline1"],
                                             encoder=encoder, reranker=reranker,
                                             **({"semantic_verifier": semantic_verifier}
                                                if semantic_verifier is not None else {}))
        validate_similarity_report(similarity)
        validate_json_schema(similarity, kind="similarity")
        timings["pipeline1_seconds"] = time.perf_counter() - stage
    if run_type in {"ASSESSMENT", "BOTH"}:
        stage = time.perf_counter()
        compiled = deepcopy(request["compiled_rubric"])
        compiled["version"] = compiled["rubric_version"]
        assessment = run_assessment_pipeline(chunks, compiled, config=config["pipeline2"],
                                             encoder=encoder, reranker=reranker,
                                             **({"llm_verifier": llm_verifier}
                                                if llm_verifier is not None else {}))
        if assessment["compiled_rubric"] != request["compiled_rubric"]:
            raise PipelineRejected("RUBRIC_INTEGRITY_FAILED")
        validate_assessment_report(assessment)
        validate_json_schema(assessment, kind="assessment")
        timings["pipeline2_seconds"] = time.perf_counter() - stage
    timings["total_seconds"] = time.perf_counter() - start
    hardware = {"system": platform.system(), "machine": platform.machine(),
                "python": platform.python_version(), "device": "cpu", "cpu_count": os.cpu_count()}
    if request["config_id"] in {"bm25-nli-v2", "rrf-nli-v2"}:
        # v2 explicitly requires Apple GPU NLI; E5 remains on the CPU.
        # Describe loaded models rather than claiming GPU use for a P2-only
        # request, or labelling a mixed CPU/MPS run as CPU-only.
        devices = {
            name: _loaded_model_device(model)
            for name, model in (("encoder", encoder), ("reranker", reranker),
                                ("semantic_verifier", semantic_verifier))
            if model is not None
        }
        hardware["model_devices"] = devices
        distinct = set(devices.values())
        hardware["device"] = ("unknown" if "unknown" in distinct else
                              next(iter(distinct)) if len(distinct) == 1 else
                              "mixed" if distinct else "cpu")
    if llm_verifier is not None:
        # The child performs BM25/validation on CPU. Model inference belongs to
        # the loopback service; do not infer its accelerator from this process.
        hardware["model_devices"] = {
            **hardware.get("model_devices", {}),
            "assessment_verifier": _loaded_model_device(llm_verifier),
        }
        hardware["device"] = "local_model_service"
    return {"similarity": similarity, "assessment": assessment,
            "execution": {"seed": seed, "config_sha256": config_sha,
                "models": {"encoder": getattr(encoder, "metadata", None),
                           "reranker": getattr(reranker, "metadata", None),
                           **({"semantic_verifier": semantic_verifier.metadata}
                              if semantic_verifier is not None else {}),
                           **({"assessment_verifier": llm_verifier.metadata}
                              if llm_verifier is not None else {})},
                "hardware": hardware,
                "timing": timings, "index_vectors_reused": bool(getattr(encoder, "reused", 0)),
                "cached_document_vectors_used": getattr(encoder, "reused", 0),
                "baseline_limitations": [
                    "Scores and similarity labels are proposals requiring lecturer review.",
                    ("Pipeline 2 uses a local LLM with validated evidence references; span validity does not establish semantic correctness or external-source verification."
                     if llm_verifier is not None else
                     "Pipeline 2 uses authored phrase verification, not semantic or cross-source entailment."),
                    "BM25 is reconstructed over the locked combined corpus; verified source dense vectors are reused when document-prefix text matches.",
                ]}}


def run_bounded(request: dict[str, Any], *, heartbeat: Callable[[], None] | None = None) -> dict[str, Any]:
    config, sha = configuration(request["config_id"])
    if request["config_sha256"] != sha:
        raise PipelineRejected("ANALYSIS_CONFIG_CHANGED")
    raw = json.dumps(request, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX_INPUT:
        raise PipelineRejected("ANALYSIS_INPUT_LIMIT")
    # TemporaryDirectory uses mode 0700. Inputs/results never enter repository artifacts.
    with tempfile.TemporaryDirectory(prefix="kltn-analysis-") as directory:
        path = Path(directory)
        incoming, outgoing = path / "request.json", path / "result.json"
        fd = os.open(incoming, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        environment = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "1",
                       "MKL_NUM_THREADS": "1"}
        # Only the parent talks to Mongo; do not propagate URI-bearing variables.
        for key in list(environment):
            if "MONGO" in key or key.endswith("_TOKEN") or key.endswith("_PASSWORD"):
                environment.pop(key)
        process = subprocess.Popen([sys.executable, "-m", __name__, str(incoming), str(outgoing)],
            cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        start = time.monotonic()
        try:
            while True:
                try:
                    code = process.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - start >= config["limits"]["wall_seconds"]:
                        raise PipelineRejected("ANALYSIS_WALL_TIMEOUT") from None
                    if heartbeat is not None:
                        heartbeat()
            if code != 0:
                raise PipelineRejected("ANALYSIS_MODEL_OR_PIPELINE_REJECTED")
            if outgoing.is_symlink() or not outgoing.is_file() or outgoing.stat().st_size > MAX_OUTPUT:
                raise PipelineRejected("ANALYSIS_OUTPUT_LIMIT")
            return json.loads(outgoing.read_text(encoding="utf-8"))
        finally:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=10)


def _child(incoming: Path, outgoing: Path) -> int:
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT, MAX_OUTPUT))
    if sys.platform.startswith("linux"):
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1024 ** 3, 8 * 1024 ** 3))
    if incoming.stat().st_size > MAX_INPUT:
        return 75
    request = json.loads(incoming.read_text(encoding="utf-8"))
    cpu_seconds = _cpu_seconds(request)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    result = execute_snapshot(request)
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False).encode()
    if len(payload) > MAX_OUTPUT:
        return 75
    fd = os.open(outgoing, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_child(Path(sys.argv[1]), Path(sys.argv[2])))
    except Exception:
        raise SystemExit(65) from None
