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
    shard_documents: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if not group_by_document:
        return rank_bm25_reference(
            corpus, queries, top_k=top_k, k1=k1, b=b, group_by_document=False
        )
    if shard_documents is not None:
        return rank_bm25_sharded(
            corpus,
            queries,
            top_k=top_k,
            k1=k1,
            b=b,
            query_batch_size=query_batch_size,
            shard_documents=shard_documents,
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


# ---------------------------------------------------------------------------
# Bản chạy theo khối tài liệu (tiết kiệm RAM cho pool lớn).
# Lượt 1: duyệt toàn bộ chunk, chỉ lấy thống kê toàn cục (N, độ dài trung bình,
# df, từ vựng) nên idf và avgdl giống hệt bản không chia khối.
# Lượt 2: mỗi lần dựng ma trận BM25 cho một khối tài liệu, chấm mọi truy vấn,
# giữ top_k tài liệu của khối rồi gộp. Tài liệu của các khối không giao nhau
# và điểm một chunk chỉ phụ thuộc thống kê toàn cục, nên top_k sau khi gộp
# bằng top_k của bản gốc (phá hoà: (-điểm, document_id); trong một tài liệu
# lấy chunk_id nhỏ nhất).
#
# Lõi `_rank_bm25_over_shards` nhận `shard_factory`: hàm không đối số, mỗi lần
# gọi trả về iterator các khối (list chunk), mỗi khối chứa trọn các tài liệu và
# không tài liệu nào xuất hiện ở hai khối. Hàm được gọi đúng 2 lần (lượt 1 và
# lượt 2) và phải sinh cùng dữ liệu cả hai lần.
# ---------------------------------------------------------------------------
def _rank_bm25_over_shards(
    shard_factory: Any,
    queries: Iterable[dict[str, Any]],
    *,
    top_k: int,
    k1: float,
    b: float,
    query_batch_size: int,
) -> dict[str, list[dict[str, Any]]]:
    import numpy as np
    from array import array
    from scipy import sparse

    queries = list(queries)

    # ---- Lượt 1: thống kê toàn cục -----------------------------------
    vocab: dict[str, int] = {}
    df_arr = array("q")
    seen_ids: set[str] = set()
    document_ids: set[str] = set()
    total_length = 0
    for shard in shard_factory():
        for item in shard:
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
            document_ids.add(document_id)
            tokens = tokenize(text)
            total_length += len(tokens)
            for term in set(tokens):
                term_index = vocab.get(term)
                if term_index is None:
                    term_index = vocab[term] = len(df_arr)
                    df_arr.append(0)
                df_arr[term_index] += 1
    n_items = len(seen_ids)
    del seen_ids
    if n_items == 0:
        return {str(query["query_id"]): [] for query in queries}
    n_terms = len(vocab)
    average_length = total_length / n_items or 1.0
    df = np.frombuffer(df_arr, dtype=np.int64).astype(np.float64)
    idf = np.log(1 + (n_items - df + 0.5) / (df + 0.5))
    del df

    doc_rank = {d: i for i, d in enumerate(sorted(document_ids))}
    del document_ids

    # ---- Ma trận truy vấn, dùng chung cho mọi khối ------------------
    batches = []
    seen_query_ids: set[str] = set()
    for start in range(0, len(queries), query_batch_size):
        rows, cols, vals, batch_ids = [], [], [], []
        for row, query in enumerate(queries[start : start + query_batch_size]):
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
        batches.append(
            (
                batch_ids,
                sparse.csr_matrix(
                    (vals, (rows, cols)), shape=(len(batch_ids), n_terms)
                ),
            )
        )

    # kept[query_id] = [(document_rank, score, document_id, chunk_id, source_spans)]
    # (tối đa top_k). Chỉ giữ các trường cần xuất, không giữ cả dict chunk
    # (kèm text) để khỏi giữ hàng trăm nghìn cửa sổ trong RAM.
    kept: dict[str, list[tuple[int, float, str, str, Any]]] = {
        query_id: [] for ids, _ in batches for query_id in ids
    }

    # ---- Lượt 2: từng khối tài liệu ----------------------------------
    for items in shard_factory():
        if not items:
            continue
        shard_n = len(items)
        indptr = array("q", [0])
        indices = array("i")
        term_freqs = array("d")
        lengths = array("d")
        for item in items:
            tokens = tokenize(item["text"])
            lengths.append(len(tokens))
            for term, frequency in Counter(tokens).items():
                indices.append(vocab[term])
                term_freqs.append(frequency)
            indptr.append(len(indices))
        indptr_np = np.frombuffer(indptr, dtype=np.int64)
        indices_np = np.frombuffer(indices, dtype=np.int32)
        tf = np.frombuffer(term_freqs, dtype=np.float64)
        lengths_np = np.frombuffer(lengths, dtype=np.float64)
        row_lengths = np.repeat(lengths_np, np.diff(indptr_np))
        weights = idf[indices_np] * (
            tf * (k1 + 1) / (tf + k1 * (1 - b + b * row_lengths / average_length))
        )
        del row_lengths
        term_item = sparse.csr_matrix(
            (weights, indices_np, indptr_np), shape=(shard_n, n_terms)
        ).T.tocsr()
        del weights

        # tài liệu trong khối xếp theo document_id; chunk xếp theo chunk_id
        shard_docs = sorted({item["document_id"] for item in items}, key=doc_rank.get)
        local_pos = {d: i for i, d in enumerate(shard_docs)}
        item_doc = np.fromiter(
            (local_pos[item["document_id"]] for item in items),
            dtype=np.int64,
            count=shard_n,
        )
        per_doc: list[list[int]] = [[] for _ in shard_docs]
        for item_index in range(shard_n):
            per_doc[item_doc[item_index]].append(item_index)
        per_doc_np = [
            np.array(sorted(m, key=lambda i: items[i]["chunk_id"]), dtype=np.int64)
            for m in per_doc
        ]
        del per_doc

        for batch_ids, query_matrix in batches:
            batch_scores = (query_matrix @ term_item).tocsr()
            for row, query_id in enumerate(batch_ids):
                lo, hi = batch_scores.indptr[row], batch_scores.indptr[row + 1]
                matched = batch_scores.indices[lo:hi]
                matched_scores = batch_scores.data[lo:hi]
                keep = matched_scores > 0.0
                matched, matched_scores = matched[keep], matched_scores[keep]
                if matched.size == 0:
                    continue
                dense = np.zeros(shard_n, dtype=np.float64)
                dense[matched] = matched_scores
                best = np.full(len(shard_docs), -np.inf)
                np.maximum.at(best, item_doc[matched], matched_scores)
                candidates = np.flatnonzero(best > 0.0)
                order = candidates[np.lexsort((candidates, -best[candidates]))][
                    :top_k
                ]
                bucket = kept[query_id]
                for local_doc in order:
                    members = per_doc_np[local_doc]
                    item = items[int(members[int(np.argmax(dense[members]))])]
                    bucket.append(
                        (
                            doc_rank[shard_docs[local_doc]],
                            float(best[local_doc]),
                            item["document_id"],
                            item["chunk_id"],
                            item.get("source_spans", []),
                        )
                    )
                bucket.sort(key=lambda entry: (-entry[1], entry[0]))
                del bucket[top_k:]
        del term_item, items, item_doc, per_doc_np

    results: dict[str, list[dict[str, Any]]] = {}
    for ids, _ in batches:
        for query_id in ids:
            results[query_id] = [
                {
                    "document_id": document_id,
                    "supporting_chunk_id": chunk_id,
                    "score": score,
                    "rank": rank,
                    "source_spans": spans,
                }
                for rank, (_, score, document_id, chunk_id, spans) in enumerate(
                    kept[query_id], 1
                )
            ]
    return results


def _check_bm25_args(top_k: int, k1: float, b: float, shard_documents: Any) -> None:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires k1 > 0 and b in [0, 1]")
    if (
        isinstance(shard_documents, bool)
        or not isinstance(shard_documents, int)
        or shard_documents <= 0
    ):
        raise ValueError("shard_documents must be a positive integer")


def rank_bm25_sharded(
    corpus: Iterable[dict[str, Any]],
    queries: Iterable[dict[str, Any]],
    *,
    top_k: int,
    k1: float = 1.2,
    b: float = 0.75,
    query_batch_size: int = 32,
    shard_documents: int = 500,
) -> dict[str, list[dict[str, Any]]]:
    """BM25 gộp về tài liệu, chạy theo khối; corpus là list chunk đã nằm trong RAM."""

    _check_bm25_args(top_k, k1, b, shard_documents)
    if not isinstance(corpus, (list, tuple)):
        corpus = list(corpus)
    queries = list(queries)
    if not corpus:
        return {str(query["query_id"]): [] for query in queries}

    document_ids = set()
    for item in corpus:
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("Every retrieval candidate requires document_id")
        document_ids.add(document_id)
    shard_of = {d: i // shard_documents for i, d in enumerate(sorted(document_ids))}
    members_by_shard: list[list[dict[str, Any]]] = [
        [] for _ in range((len(shard_of) + shard_documents - 1) // shard_documents)
    ]
    for item in corpus:
        members_by_shard[shard_of[item["document_id"]]].append(item)
    del shard_of, document_ids

    return _rank_bm25_over_shards(
        lambda: iter(members_by_shard),
        queries,
        top_k=top_k,
        k1=k1,
        b=b,
        query_batch_size=query_batch_size,
    )


def rank_bm25_fixed_windows(
    documents: Iterable[dict[str, Any]],
    queries: Iterable[dict[str, Any]],
    *,
    size_tokens: int,
    stride_tokens: int,
    top_k: int,
    k1: float = 1.2,
    b: float = 0.75,
    query_batch_size: int = 32,
    shard_documents: int = 500,
) -> dict[str, list[dict[str, Any]]]:
    """BM25 trên cửa sổ cố định, gộp về tài liệu, KHÔNG dựng cả list cửa sổ.

    Cửa sổ được sinh theo từng nhóm `shard_documents` tài liệu (và sinh lại ở
    lượt 2), nên RAM chỉ giữ cửa sổ của một nhóm. Kết quả bằng
    rank_bm25(build_fixed_windows(documents, ...), group_by_document=True).
    """

    from .fixed_window import build_fixed_windows

    _check_bm25_args(top_k, k1, b, shard_documents)
    documents = list(documents)
    queries = list(queries)

    def shard_factory():
        for start in range(0, len(documents), shard_documents):
            yield build_fixed_windows(
                documents[start : start + shard_documents],
                size_tokens=size_tokens,
                stride_tokens=stride_tokens,
            )

    # build_fixed_windows kiểm tra trùng document_id trong từng nhóm; kiểm tra toàn cục tại đây
    ids = [document.get("document_id") for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate document_id in documents")
    return _rank_bm25_over_shards(
        shard_factory,
        queries,
        top_k=top_k,
        k1=k1,
        b=b,
        query_batch_size=query_batch_size,
    )
