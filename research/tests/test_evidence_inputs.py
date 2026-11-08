"""Synthetic checks for inference-only short Cross-Encoder input windows."""

from __future__ import annotations

import hashlib
import inspect
import re
import time

import pytest

from research.offline_retrieval.evidence_inputs import EvidenceWindowPairScorer


class OffsetTokenizer:
    is_fast = True

    def __call__(self, text, text_pair=None, *, add_special_tokens=True,
                 return_offsets_mapping=False, **_kwargs):
        tokens = list(re.finditer(r"\w+|[^\w\s]", text))
        result = {"input_ids": [index + 1 for index in range(len(tokens))]}
        if text_pair is not None:
            count = len(list(re.finditer(r"\w+|[^\w\s]", text_pair)))
            result["input_ids"] += list(range(1, count + 1))
        if add_special_tokens:
            result["input_ids"] += [0, 0, 0]
        if return_offsets_mapping:
            result["offset_mapping"] = [match.span() for match in tokens]
        return result


class RecordingScorer:
    def __init__(self, tokenizer=None):
        self.metadata = {"backend": "injected_test", "revision": "synthetic-locked"}
        self.tokenizer = tokenizer or OffsetTokenizer()
        self.calls = []
        self.deadlines = []

    def score_pairs(self, pairs):
        self.calls.append(list(pairs))
        return [float(len(query) + len(passage)) for query, passage in pairs]

    def pair_diagnostics(self, pairs):
        return [{
            "available": True, "truncated": False,
            "tokens_before_truncation": len(self.tokenizer(query, passage)["input_ids"]),
            "tokens_model_input": len(self.tokenizer(query, passage)["input_ids"]),
            "max_length": 512, "truncation_strategy": "longest_first",
        } for query, passage in pairs]

    def set_deadline(self, value):
        self.deadlines.append(value)


def make(*, query_tokens=192, passage_tokens=256, max_length=512, tokenizer=None):
    base = RecordingScorer(tokenizer)
    wrapper = EvidenceWindowPairScorer(
        base, tokenizer=base.tokenizer, max_length=max_length,
        query_token_budget=query_tokens, passage_token_budget=passage_tokens,
    )
    return base, wrapper


def test_short_pairs_retain_original_strings_and_order():
    base, wrapper = make()
    pairs = [("short query", "  short passage  "), ("next query", "other support")]
    values = wrapper.score_pairs(pairs)
    assert base.calls == [pairs]
    assert values == [float(len(q) + len(p)) for q, p in pairs]
    diagnostics = wrapper.pair_diagnostics(pairs)
    assert all(item["truncated"] is False for item in diagnostics)
    assert all(item["source_span_scope"] == "CROPPED_PAIR_OFFSETS_ONLY" for item in diagnostics)
    assert all(item["evidence_window"]["query_cropped"] is False for item in diagnostics)
    assert all(item["evidence_window"]["passage_cropped"] is False for item in diagnostics)


def test_query_prefix_budget_is_explicit_and_invisible_terms_do_not_select_window():
    base, wrapper = make(query_tokens=2, passage_tokens=2)
    pairs = [("alpha beta secret", "secret filler alpha beta")]
    wrapper.score_pairs(pairs)
    assert base.calls == [[("alpha beta", "alpha beta")]]
    [item] = wrapper.pair_diagnostics(pairs)
    window = item["evidence_window"]
    assert window["query_cropped"] is True
    assert window["query_char_range"] == {"start": 0, "end": len("alpha beta")}
    assert window["prepared_query_tokens"] == 2
    assert window["prepared_passage_tokens"] == 2
    assert window["prepared_pair_tokens"] == 7


def test_window_prefers_distinct_query_terms_over_repeated_term_frequency():
    base, wrapper = make(passage_tokens=3)
    pairs = [("alpha beta gamma", "alpha alpha neutral neutral beta gamma")]
    wrapper.score_pairs(pairs)
    assert base.calls == [[("alpha beta gamma", "neutral beta gamma")]]
    [item] = wrapper.pair_diagnostics(pairs)
    assert item["evidence_window"]["distinct_query_term_overlap"] == 2


def test_equal_window_coverage_prefers_earliest_position():
    base, wrapper = make(passage_tokens=2)
    pair = ("alpha beta", "alpha beta filler alpha beta")
    wrapper.score_pairs([pair])
    assert base.calls == [[("alpha beta", "alpha beta")]]
    assert wrapper.pair_diagnostics([pair])[0]["evidence_window"]["passage_char_range"] == {
        "start": 0, "end": len("alpha beta"),
    }


def test_whole_words_match_instead_of_substrings():
    base, wrapper = make(passage_tokens=1)
    wrapper.score_pairs([("cat", "concatenate neutral cat")])
    assert base.calls == [[("cat", "cat")]]


def test_unicode_casefold_and_original_character_offsets():
    base, wrapper = make(passage_tokens=2)
    pair = ("DỮ LIỆU", "khác dự LIỆU dữ")
    wrapper.score_pairs([pair])
    assert base.calls == [[("DỮ LIỆU", "LIỆU dữ")]]
    window = wrapper.pair_diagnostics([pair])[0]["evidence_window"]
    span = window["passage_char_range"]
    assert pair[1][span["start"]:span["end"]] == "LIỆU dữ"
    assert window["cropped_passage_sha256"] == hashlib.sha256("LIỆU dữ".encode()).hexdigest()
    assert window["original_passage_sha256"] == hashlib.sha256(pair[1].encode()).hexdigest()
    assert window["distinct_query_term_overlap"] == 2


def test_zero_overlap_has_earliest_window_and_no_gold_arguments():
    base, wrapper = make(passage_tokens=2)
    wrapper.score_pairs([("query", "  first second third")])
    assert base.calls == [[("query", "first second")]]
    assert "gold" not in inspect.signature(EvidenceWindowPairScorer).parameters
    assert "qrels" not in inspect.signature(EvidenceWindowPairScorer).parameters
    assert wrapper.metadata["input_policy"]["gold_used"] is False


def test_single_character_query_terms_do_not_change_coverage():
    base, wrapper = make(passage_tokens=1)
    wrapper.score_pairs([("a zz", "a a zz bb")])
    assert base.calls == [[("a zz", "zz")]]


def test_duplicate_inputs_retain_pair_count_but_preparation_is_cached():
    base, wrapper = make(passage_tokens=2)
    pair = ("alpha", "filler alpha tail")
    wrapper.score_pairs([pair, pair])
    wrapper.pair_diagnostics([pair])
    assert len(base.calls[0]) == 2
    assert wrapper.metadata["input_preparation"]["unique_original_pairs"] == 1


def test_diagnostics_refer_to_actual_short_pair_and_are_defensive_copies():
    _base, wrapper = make(query_tokens=2, passage_tokens=2)
    pair = ("alpha beta gamma delta", "irrelevant stuff alpha beta tail")
    wrapper.score_pairs([pair])
    [item] = wrapper.pair_diagnostics([pair])
    assert item["tokens_before_truncation"] == item["evidence_window"]["prepared_pair_tokens"] == 7
    assert item["evidence_window"]["original_pair_tokens"] > 7
    item["evidence_window"]["query_char_range"]["end"] = -1
    assert wrapper.pair_diagnostics([pair])[0]["evidence_window"]["query_char_range"]["end"] > 0


@pytest.mark.parametrize("name, value", [
    ("max_length", 0), ("max_length", True),
    ("query_token_budget", -1), ("passage_token_budget", 1.5),
])
def test_invalid_budgets_fail_before_inference(name, value):
    base = RecordingScorer()
    with pytest.raises(ValueError, match="positive integer"):
        EvidenceWindowPairScorer(base, tokenizer=base.tokenizer, **{name: value})
    assert base.calls == []


def test_slow_or_missing_fast_tokenizer_is_rejected():
    tokenizer = OffsetTokenizer()
    tokenizer.is_fast = False
    with pytest.raises(ValueError, match="fast tokenizer"):
        EvidenceWindowPairScorer(RecordingScorer(), tokenizer=tokenizer)


@pytest.mark.parametrize("offsets", [None, [(0, 999)], [(3, 1)], [(0, 0)], [(True, 1)]])
def test_unusable_offsets_fail_before_model_inference(offsets):
    class BadTokenizer(OffsetTokenizer):
        def __call__(self, *args, **kwargs):
            result = super().__call__(*args, **kwargs)
            if kwargs.get("return_offsets_mapping"):
                result["offset_mapping"] = offsets
            return result
    base, wrapper = make(tokenizer=BadTokenizer())
    with pytest.raises(ValueError, match="offset"):
        wrapper.score_pairs([("query", "passage")])
    assert base.calls == []


def test_actual_pair_budget_is_verified_even_if_individual_caps_fit():
    base, wrapper = make(query_tokens=3, passage_tokens=3, max_length=8)
    with pytest.raises(ValueError, match="locked token budget"):
        wrapper.score_pairs([("one two three", "four five six")])
    assert base.calls == []


def test_isolated_boundary_retokenization_is_repaired_at_original_boundaries():
    class BoundaryTokenizer(OffsetTokenizer):
        def __call__(self, text, text_pair=None, **kwargs):
            result = super().__call__(text, text_pair, **kwargs)
            # The last word piece in the full text expands to two tokens when
            # used alone, simulating a changed WordPiece substring boundary.
            if text_pair is None and text == "prefix fragment":
                result["input_ids"] = [1, 2, 3]
                if kwargs.get("return_offsets_mapping"):
                    result["offset_mapping"] = [(0, 6), (7, 11), (11, 15)]
            if text_pair is None and text == "tail fragment":
                result["input_ids"] = [1, 2, 3]
                if kwargs.get("return_offsets_mapping"):
                    result["offset_mapping"] = [(0, 4), (5, 9), (9, 13)]
            return result

    base, wrapper = make(query_tokens=2, passage_tokens=2, tokenizer=BoundaryTokenizer())
    pair = ("prefix fragment final", "tail fragment final")
    wrapper.score_pairs([pair])
    assert base.calls == [[("prefix", "tail")]]
    window = wrapper.pair_diagnostics([pair])[0]["evidence_window"]
    assert window["query_budget_repair_steps"] == 1
    assert window["passage_budget_repair_steps"] == 1
    assert window["passage_selection_char_range"]["end"] == len("tail fragment")
    assert window["passage_char_range"]["end"] == len("tail")
    assert window["prepared_query_tokens"] <= 2
    assert window["prepared_passage_tokens"] <= 2
    assert wrapper.metadata["input_preparation"]["query_budget_repaired_pairs"] == 1
    assert wrapper.metadata["input_preparation"]["passage_budget_repaired_pairs"] == 1
    assert wrapper.pair_diagnostics([pair])[0]["evidence_window"] == window


def test_diagnostics_must_match_the_tokenizer_used_by_actual_model():
    class InconsistentScorer(RecordingScorer):
        def pair_diagnostics(self, pairs):
            result = super().pair_diagnostics(pairs)
            result[0]["tokens_before_truncation"] += 1
            return result
    base = InconsistentScorer()
    wrapper = EvidenceWindowPairScorer(base, tokenizer=base.tokenizer)
    with pytest.raises(ValueError, match="disagree"):
        wrapper.pair_diagnostics([("query", "passage")])


def test_deadline_is_forwarded_and_expired_preparation_stops_before_inference():
    base, wrapper = make()
    deadline = time.perf_counter() - 1
    wrapper.set_deadline(deadline)
    assert base.deadlines == [deadline]
    with pytest.raises(TimeoutError, match="preparation deadline"):
        wrapper.score_pairs([("query", "passage")])
    assert base.calls == []
    wrapper.set_deadline(None)
    assert base.deadlines[-1] is None
    assert wrapper.score_pairs([("query", "passage")])
