from research.mmdocir_pilot import CachedEncoder, retrieved_pages


def test_page_coverage_deduplicates_zero_based_multi_page_evidence():
    candidates = [{"source_spans": [
        {"locator": {"page_index": 0}},
        {"locator": {"page_index": 2}},
        {"locator": {"page_index": 2}},
        {"locator": {"page_index": None}},
    ]}]
    assert retrieved_pages(candidates) == {0, 2}


def test_dense_cache_keeps_query_and_passage_prefixes_separate():
    class Encoder:
        metadata = {}
        mode = "document"
        calls = []

        def set_mode(self, mode):
            self.mode = mode

        def encode(self, texts):
            self.calls.append((self.mode, list(texts)))
            return [[1.0 if self.mode == "query" else 2.0] for _ in texts]

    base = Encoder()
    cache = CachedEncoder(base)
    assert cache.encode(["identical", "identical"]) == [[2.0], [2.0]]
    assert cache.encode(["identical"]) == [[2.0]]
    cache.set_mode("query")
    assert cache.encode(["identical"]) == [[1.0]]
    cache.set_mode("document")
    assert cache.encode(["identical"]) == [[2.0]]
    assert base.calls == [("document", ["identical"]), ("query", ["identical"])]
