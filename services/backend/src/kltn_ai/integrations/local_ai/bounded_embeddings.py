"""Offline, fixed-budget embedding inference in a disposable child process.

The production path never substitutes a toy/hash encoder or downloads weights.
Only the locked, locally cached E5 model is accepted by the calling service.
"""

from __future__ import annotations

import math
import multiprocessing
import os
import time
from collections.abc import Sequence
from typing import Any


class EmbeddingRejected(RuntimeError):
    """Safe operational failure; never carries source text or model tracebacks."""


def _encode_child(connection: Any, texts: list[str], config: dict[str, Any], mode: str) -> None:
    try:
        for key in list(os.environ):
            if "MONGO" in key or key.endswith("_TOKEN") or key.endswith("_PASSWORD"):
                os.environ.pop(key)
        import resource
        import sys
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
        if sys.platform.startswith("linux"):
            resource.setrlimit(resource.RLIMIT_AS, (8 * 1024 ** 3, 8 * 1024 ** 3))
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        os.environ["OMP_NUM_THREADS"] = "2"
        from research.offline_retrieval.dense import SentenceTransformerEncoder

        encoder = SentenceTransformerEncoder(
            model=config["model"], revision=config["revision"], device="cpu",
            batch_size=min(16, int(config.get("batch_size", 16))),
            query_prefix=config.get("query_prefix", "query: "),
            document_prefix=config.get("document_prefix", "passage: "),
        )
        encoder.set_mode(mode)
        vectors = [[float(value) for value in row] for row in encoder.encode(texts)]
        connection.send({"vectors": vectors, "metadata": encoder.metadata})
    except Exception:
        connection.send({"error": "DENSE_MODEL_UNAVAILABLE"})
    finally:
        connection.close()


def encode_bounded(texts: Sequence[str], model_config: dict[str, Any], *,
                   mode: str = "document", timeout_seconds: float = 120) -> dict[str, Any]:
    if (mode not in {"query", "document"} or not 0 < timeout_seconds <= 120
            or not 1 <= len(texts) <= 5000
            or any(not isinstance(item, str) or not item.strip() for item in texts)
            or sum(len(item) for item in texts) > 2_000_000):
        raise EmbeddingRejected("DENSE_INPUT_LIMIT")
    # Spawn avoids inheriting database sockets, credentials or a loaded torch runtime.
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_encode_child, args=(sender, list(texts), model_config, mode), daemon=True)
    started = time.monotonic()
    try:
        process.start()
        sender.close()
        if not receiver.poll(timeout_seconds):
            raise EmbeddingRejected("DENSE_TIMEOUT")
        try:
            result = receiver.recv()
        except (EOFError, OSError):
            raise EmbeddingRejected("DENSE_MODEL_UNAVAILABLE") from None
        if not isinstance(result, dict) or result.get("error"):
            raise EmbeddingRejected("DENSE_MODEL_UNAVAILABLE")
        vectors = result.get("vectors")
        if (not isinstance(vectors, list) or len(vectors) != len(texts)
                or any(not isinstance(row, list) or len(row) != 384 for row in vectors)
                or any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not math.isfinite(value) for row in vectors for value in row)
                or any(not any(row) for row in vectors)):
            raise EmbeddingRejected("DENSE_OUTPUT_INVALID")
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        return result
    finally:
        receiver.close()
        sender.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
