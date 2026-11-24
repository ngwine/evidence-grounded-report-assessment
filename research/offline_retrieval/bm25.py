"""Small deterministic Okapi BM25 baseline with no service dependency."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Any, Iterable

from .aggregation import render_ranked_candidates
from .common import tokenize


def rank_bm25_reference(
    corpus: Iterable[dict[str, Any]],
    queries: Iterable[dict[str, Any]],
    *,
    top_k: int,
    k1: float = 1.2,
    b: float = 0.75,
    group_by_document: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires k1 > 0 and b in [0, 1]")

    items = list(corpus)
    if not items:
        return {str(query["query_id"]): [] for query in queries}

    document_lengths: list[int] = []
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for item in items:
        chunk_id = item.get("chunk_id")
        text = item.get("text")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("Every corpus item requires a non-empty chunk_id")
        if chunk_id in seen_ids:
            raise ValueError(f"Duplicate chunk_id: {chunk_id}")
        seen_ids.add(chunk_id)
        if not isinstance(text, str):
            raise ValueError(f"Corpus item {chunk_id} requires string text")
        tokens = tokenize(text)
        counts = Counter(tokens)
        document_lengths.append(len(tokens))
        for term, frequency in counts.items():
            postings[term].append((len(document_lengths) - 1, frequency))

    average_length = sum(document_lengths) / len(items)
    average_length = average_length or 1.0
    corpus_size = len(items)

    results: dict[str, list[dict[str, Any]]] = {}
    seen_query_ids: set[str] = set()
    for query in queries:
        query_id = query.get("query_id")
        query_text = query.get("text")
        if not isinstance(query_id, str) or not query_id:
            raise ValueError("Every query requires a non-empty query_id")
        if query_id in seen_query_ids:
            raise ValueError(f"Duplicate query_id: {query_id}")
        seen_query_ids.add(query_id)
        if not isinstance(query_text, str):
            raise ValueError(f"Query {query_id} requires string text")

        query_terms = Counter(tokenize(query_text))
        scores: dict[int, float] = defaultdict(float)
        for term, query_frequency in query_terms.items():
            term_postings = postings.get(term)
            if not term_postings:
                continue
            document_frequency = len(term_postings)
            inverse_document_frequency = math.log(
                1
                + (corpus_size - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            for item_index, frequency in term_postings:
                document_length = document_lengths[item_index]
                denominator = frequency + k1 * (
                    1 - b + b * document_length / average_length
                )
                scores[item_index] += query_frequency * inverse_document_frequency * (
                    frequency * (k1 + 1) / denominator
                )

        # A non-match has no retrieval evidence. Omitting zero-score chunks also
        # avoids arbitrary chunk-id tie breaks filling a requested top-k.
        scored = [
            (score, items[item_index]["chunk_id"], items[item_index])
            for item_index, score in scores.items()
            if score > 0.0
        ]

        results[query_id] = render_ranked_candidates(
            scored,
            top_k=top_k,
            group_by_document=group_by_document,
        )
    return results


# ---------------------------------------------------------------------------
# Bản nhanh (vector hoá bằng scipy.sparse). Cùng công thức, cùng cách gộp về
# tài liệu và cùng quy tắc phá hoà như rank_bm25_reference; chỉ khác thứ tự
# cộng số thực nên điểm có thể lệch ~1e-12.
# ---------------------------------------------------------------------------
def rank_bm25(
    corpus: Iterable[dict[str, Any]],
    queries: Iterable[dict[str, Any]],
    *,
    top_k: int,
    k1: float = 1.2,
    b: float = 0.75,
    group_by_document: bool = False,
    query_batch_size: int = 32,
) -> dict[str, list[dict[str, Any]]]:
    if not group_by_document:
        return rank_bm25_reference(
            corpus, queries, top_k=top_k, k1=k1, b=b, group_by_document=False
        )
    import numpy as np
    from array import array
    from scipy import sparse

    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires k1 > 0 and b in [0, 1]")
    items = list(corpus)
    queries = list(queries)
    if not items:
        return {str(query["query_id"]): [] for query in queries}

    vocab: dict[str, int] = {}
    indptr = array("q", [0])
    indices = array("i")
    term_freqs = array("d")
    lengths = array("d")
    seen_ids: set[str] = set()
    for item in items:
        chunk_id = item.get("chunk_id")
        text = item.get("text")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("Every corpus item requires a non-empty chunk_id")
        if chunk_id in seen_ids:
            raise ValueError(f"Duplicate chunk_id: {chunk_id}")
        seen_ids.add(chunk_id)
        if not isinstance(text, str):
            raise ValueError(f"Corpus item {chunk_id} requires string text")
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("Every retrieval candidate requires document_id")
        tokens = tokenize(text)
        lengths.append(len(tokens))
        for term, frequency in Counter(tokens).items():
            term_index = vocab.get(term)
            if term_index is None:
                term_index = vocab[term] = len(vocab)
            indices.append(term_index)
            term_freqs.append(frequency)
        indptr.append(len(indices))
    del seen_ids

    n_items, n_terms = len(items), len(vocab)
    indptr_np = np.frombuffer(indptr, dtype=np.int64)
    indices_np = np.frombuffer(indices, dtype=np.int32)
    tf = np.frombuffer(term_freqs, dtype=np.float64)
    lengths_np = np.frombuffer(lengths, dtype=np.float64)
    average_length = float(lengths_np.sum()) / n_items or 1.0
    df = np.bincount(indices_np, minlength=n_terms).astype(np.float64)
    idf = np.log(1 + (n_items - df + 0.5) / (df + 0.5))
    row_lengths = np.repeat(lengths_np, np.diff(indptr_np))
    weights = idf[indices_np] * (
        tf * (k1 + 1) / (tf + k1 * (1 - b + b * row_lengths / average_length))
    )
    del row_lengths, term_freqs
    # term x item: mỗi hàng là posting list đã nhân sẵn trọng số BM25
    term_item = sparse.csr_matrix(
        (weights, indices_np, indptr_np), shape=(n_items, n_terms)
    ).T.tocsr()
    del weights

    # Gom chunk theo tài liệu; trong mỗi tài liệu xếp chunk theo chunk_id để
    # argmax lấy chunk có id nhỏ nhất khi hoà (giống bản gốc).
    doc_ids = sorted({item["document_id"] for item in items})
    doc_pos = {d: i for i, d in enumerate(doc_ids)}
    item_doc = np.fromiter(
        (doc_pos[item["document_id"]] for item in items), dtype=np.int64, count=n_items
    )
    per_doc: list[list[int]] = [[] for _ in doc_ids]
    for item_index, item in enumerate(items):
        per_doc[item_doc[item_index]].append(item_index)
    per_doc_np = [
        np.array(sorted(members, key=lambda i: items[i]["chunk_id"]), dtype=np.int64)
        for members in per_doc
    ]
    del per_doc

    results: dict[str, list[dict[str, Any]]] = {}
    seen_query_ids: set[str] = set()
    for start in range(0, len(queries), query_batch_size):
        batch = queries[start : start + query_batch_size]
        rows, cols, vals, batch_ids = [], [], [], []
        for row, query in enumerate(batch):
            query_id = query.get("query_id")
            query_text = query.get("text")
            if not isinstance(query_id, str) or not query_id:
                raise ValueError("Every query requires a non-empty query_id")
            if query_id in seen_query_ids:
                raise ValueError(f"Duplicate query_id: {query_id}")
            seen_query_ids.add(query_id)
            if not isinstance(query_text, str):
                raise ValueError(f"Query {query_id} requires string text")
            batch_ids.append(query_id)
            for term, query_frequency in Counter(tokenize(query_text)).items():
                term_index = vocab.get(term)
                if term_index is not None:
                    rows.append(row)
                    cols.append(term_index)
                    vals.append(float(query_frequency))
        query_matrix = sparse.csr_matrix(
            (vals, (rows, cols)), shape=(len(batch), n_terms)
        )
        batch_scores = (query_matrix @ term_item).tocsr()
        for row, query_id in enumerate(batch_ids):
            lo, hi = batch_scores.indptr[row], batch_scores.indptr[row + 1]
            matched = batch_scores.indices[lo:hi]
            matched_scores = batch_scores.data[lo:hi]
            keep = matched_scores > 0.0
            matched, matched_scores = matched[keep], matched_scores[keep]
            if matched.size == 0:
                results[query_id] = []
                continue
            dense = np.zeros(n_items, dtype=np.float64)
            dense[matched] = matched_scores
            best = np.full(len(doc_ids), -np.inf)
            np.maximum.at(best, item_doc[matched], matched_scores)
            candidates = np.flatnonzero(best > 0.0)
            # (-điểm, document_id): doc_ids đã sort nên chỉ số = thứ tự theo id
            order = candidates[np.lexsort((candidates, -best[candidates]))][:top_k]
            ranked = []
            for rank, doc_index in enumerate(order, 1):
                members = per_doc_np[doc_index]
                item = items[int(members[int(np.argmax(dense[members]))])]
                ranked.append(
                    {
                        "document_id": item["document_id"],
                        "supporting_chunk_id": item["chunk_id"],
                        "score": float(best[doc_index]),
                        "rank": rank,
                        "source_spans": item.get("source_spans", []),
                    }
                )
            results[query_id] = ranked
    return results
