"""Run PDF/DOCX parsing in a child process with enforceable run budgets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from typing import Any, Mapping

from research.offline_retrieval.common import sha256_file
from .documents import ParsedDocument


class ParserRejected(RuntimeError):
    """Content-safe boundary error exposed to the caller."""


@dataclass(frozen=True)
class ParseLimits:
    wall_seconds: float = 60.0
    cpu_seconds: int = 45
    max_input_bytes: int = 20 * 1024 * 1024
    max_output_bytes: int = 64 * 1024 * 1024
    max_text_chars: int = 2_000_000
    max_chunks: int = 20_000
    linux_address_space_bytes: int = 2 * 1024 * 1024 * 1024

    @classmethod
    def from_config(cls, value: Mapping[str, Any] | None = None) -> "ParseLimits":
        if value is None:
            return cls()
        if not isinstance(value, Mapping) or set(value) - set(cls.__dataclass_fields__):
            raise ValueError("Unknown parser resource limit")
        resolved = cls(**value)
        if (isinstance(resolved.wall_seconds, bool)
                or not isinstance(resolved.wall_seconds, (int, float))
                or not math.isfinite(resolved.wall_seconds)
                or not 0 < resolved.wall_seconds <= 600):
            raise ValueError("Parser wall_seconds must be in (0, 600]")
        for field in cls.__dataclass_fields__:
            if field == "wall_seconds":
                continue
            number = getattr(resolved, field)
            if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
                raise ValueError(f"Parser {field} must be a positive integer")
        return resolved


def parse_document_bounded(
    path: str | Path, *, role: str, max_tokens: int = 220, min_tokens: int = 30,
    limits: ParseLimits | None = None,
    document_id: str | None = None, document_version_id: str | None = None,
) -> ParsedDocument:
    limits = ParseLimits.from_config(asdict(limits)) if limits is not None else ParseLimits()
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.stat().st_size > limits.max_input_bytes:
        raise ParserRejected("PARSER_INPUT_LIMIT")
    before = sha256_file(source)
    request = {
        "path": str(source), "role": role,
        "max_tokens": max_tokens, "min_tokens": min_tokens, "limits": asdict(limits),
        "document_id": document_id, "document_version_id": document_version_id,
    }
    # Temporary content stays private and is removed on success or failure.
    with tempfile.TemporaryDirectory(prefix="kltn-parse-") as temporary:
        destination = Path(temporary) / "parsed.json"
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "research.core_mvp.bounded_documents", str(destination)],
                input=json.dumps(request).encode("utf-8"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=limits.wall_seconds,
                cwd=Path(__file__).resolve().parents[2], check=False,
            )
        except subprocess.TimeoutExpired as error:
            # subprocess.run kills and waits for its direct child on timeout.
            raise ParserRejected("PARSER_WALL_TIMEOUT") from error
        if completed.returncode != 0:
            code = "PARSER_REJECTED"
            if completed.returncode in (75, -signal.SIGXCPU, -signal.SIGXFSZ):
                code = "PARSER_RESOURCE_LIMIT"
            raise ParserRejected(code)
        if (not destination.is_file() or destination.is_symlink()
                or destination.stat().st_size > limits.max_output_bytes):
            raise ParserRejected("PARSER_OUTPUT_LIMIT")
        value = json.loads(destination.read_text(encoding="utf-8"))
    if sha256_file(source) != before or value["document"]["sha256"] != before:
        raise ParserRejected("PARSER_INPUT_CHANGED")
    return ParsedDocument(
        document=value["document"], elements=tuple(value["elements"]),
        chunks=tuple(value["chunks"]),
    )


def _child(destination: Path, request: Mapping[str, Any]) -> int:
    import resource

    limits = ParseLimits.from_config(request["limits"])
    resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits.max_output_bytes, limits.max_output_bytes))
    memory_enforced = sys.platform.startswith("linux")
    if memory_enforced:
        resource.setrlimit(resource.RLIMIT_AS, (
            limits.linux_address_space_bytes, limits.linux_address_space_bytes,
        ))
    from .documents import parse_document

    parsed = parse_document(
        request["path"], role=request["role"],
        max_tokens=request["max_tokens"], min_tokens=request["min_tokens"],
        document_id=request.get("document_id"),
        document_version_id=request.get("document_version_id"),
    )
    if (len(parsed.chunks) > limits.max_chunks
            or sum(len(item.get("raw_text", "")) for item in parsed.elements) > limits.max_text_chars):
        return 75
    document = dict(parsed.document)
    document["parser_resource_limits"] = {
        **asdict(limits), "process_isolated": True,
        "address_space_limit_enforced": memory_enforced,
    }
    payload = json.dumps({
        "document": document, "elements": parsed.elements, "chunks": parsed.chunks,
    }, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(payload) > limits.max_output_bytes:
        return 75
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    return 0


if __name__ == "__main__":
    try:
        result = _child(Path(sys.argv[1]), json.load(sys.stdin))
    except Exception:
        result = 65
    raise SystemExit(result)
