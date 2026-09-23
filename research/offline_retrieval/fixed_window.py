"""Fixed-token-window chunking baseline with raw source spans."""

from __future__ import annotations

from typing import Any, Iterable

from .common import canonical_json, sha256_text, token_spans


def build_fixed_windows(
    documents: Iterable[dict[str, Any]],
    *,
    size_tokens: int,
    stride_tokens: int,
) -> list[dict[str, Any]]:
    if size_tokens <= 0:
        raise ValueError("fixed_window.size_tokens must be positive")
    if stride_tokens <= 0 or stride_tokens > size_tokens:
        raise ValueError("fixed_window.stride_tokens must be in [1, size_tokens]")

    windows: list[dict[str, Any]] = []
    seen_documents: set[str] = set()
    for document in documents:
        document_id = document.get("document_id")
        text = document.get("text")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("Each document requires a non-empty document_id")
        if document_id in seen_documents:
            raise ValueError(f"Duplicate document_id: {document_id}")
        seen_documents.add(document_id)
        if not isinstance(text, str):
            raise ValueError(f"Document {document_id} requires string text")

        spans = token_spans(text)
        if not spans:
            continue
        version = str(document.get("version", "1"))
        for token_start in range(0, len(spans), stride_tokens):
            token_end = min(token_start + size_tokens, len(spans))
            raw_start = spans[token_start][0]
            raw_end = spans[token_end - 1][1]
            window_text = text[raw_start:raw_end]
            identity = {
                "document_id": document_id,
                "document_version": version,
                "raw_start": raw_start,
                "raw_end": raw_end,
                "size_tokens": size_tokens,
                "stride_tokens": stride_tokens,
                "text_sha256": sha256_text(window_text),
            }
            windows.append(
                {
                    "chunk_id": "fw-" + sha256_text(canonical_json(identity)),
                    "document_id": document_id,
                    "document_version": version,
                    "text": window_text,
                    "source_spans": [
                        {
                            "document_id": document_id,
                            "raw_start": raw_start,
                            "raw_end": raw_end,
                        }
                    ],
                }
            )
            if token_end == len(spans):
                break
    return windows
