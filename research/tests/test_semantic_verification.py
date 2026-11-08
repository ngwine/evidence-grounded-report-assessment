"""Contract checks for segment-level, abstaining NLI verification.

Injected probabilities test software policy only, never model accuracy.
"""

from copy import deepcopy
import hashlib
from types import SimpleNamespace

import pytest

from research.core_mvp.semantic_verification import (
    BidirectionalNliVerifier,
    TransformersNliScorer,
    load_semantic_verifier,
    is_safe_single_numeric_marker,
)


REPORT = "Every document version keeps immutable report bytes."
SOURCE = "Report bytes stay unchanged for every saved version."
ENTAIL = {"entailment": 0.94, "neutral": 0.04, "contradiction": 0.02}
NEUTRAL = {"entailment": 0.03, "neutral": 0.94, "contradiction": 0.03}
CONTRADICT = {"entailment": 0.02, "neutral": 0.03, "contradiction": 0.95}


class TableScorer:
    metadata = {"backend": "injected_test", "model": "software-check-only"}

    def __init__(self, rows=None, default=None):
        self.rows = rows or {}
        self.default = default or NEUTRAL
        self.calls = []

    def predict_relations(self, pairs):
        self.calls.append(list(pairs))
        return [deepcopy(self.rows.get(pair, self.default)) for pair in pairs]


def equivalent_scorer(report=REPORT, source=SOURCE):
    return TableScorer({(report, source): ENTAIL, (source, report): ENTAIL})


def test_mutual_entailment_emits_only_the_compared_sentence_ranges():
    report = "\n  " + REPORT + "\nThis other sentence discusses a different experiment."
    source = "  " + SOURCE + "\nAnother source paragraph describes network latency measurements."
    result = BidirectionalNliVerifier(equivalent_scorer()).verify_pairs([(report, source)])[0]
    assert result["similarity_type"] == "PARAPHRASE"
    assert result["decision"] == "PARAPHRASE_SUPPORTED"
    assert result["score_calibration_status"] == "UNCALIBRATED"
    assert result["evidence_scope"] == "COMPARED_SENTENCE_SPANS_ONLY"
    evidence = result["evidence"][0]
    assert report[evidence["report_range"]["start"]:evidence["report_range"]["end"]] == REPORT
    assert source[evidence["source_range"]["start"]:evidence["source_range"]["end"]] == SOURCE
    assert evidence["report_range"]["end"] < len(report)
    assert result["total_sentence_pairs"] == 4


def test_one_direction_entailment_is_not_paraphrase_or_summary():
    scorer = TableScorer({(REPORT, SOURCE): ENTAIL})
    result = BidirectionalNliVerifier(scorer).verify_pairs([(REPORT, SOURCE)])[0]
    assert result["decision"] == "ABSTAIN"
    assert result["similarity_type"] is None
    assert result["evidence"] == []
    assert "NLI_UNCERTAIN_OR_DIRECTIONAL" in result["reason_codes"]


@pytest.mark.parametrize("probabilities", [NEUTRAL, CONTRADICT])
def test_complete_strong_bidirectional_non_equivalence_can_return_none(probabilities):
    result = BidirectionalNliVerifier(TableScorer(default=probabilities)).verify_pairs([(REPORT, SOURCE)])[0]
    assert result["decision"] == "NOT_EQUIVALENT"
    assert result["similarity_type"] == "NONE"
    assert result["comparison_complete"] is True


def test_non_equivalence_is_withheld_for_unchecked_sentence_pairs():
    report = REPORT + " Another experiment measures the recognition error rate."
    result = BidirectionalNliVerifier(TableScorer(), max_sentence_pairs=1).verify_pairs([(report, SOURCE)])[0]
    assert result["total_sentence_pairs"] == 2
    assert result["comparison_count"] == 1
    assert result["comparison_complete"] is False
    assert result["decision"] == "ABSTAIN"
    assert "SENTENCE_PAIR_BUDGET_EXHAUSTED" in result["reason_codes"]


def test_partial_search_can_support_only_a_found_segment():
    report = REPORT + " A separate topic concerns the greenhouse irrigation mechanism."
    result = BidirectionalNliVerifier(equivalent_scorer(), max_sentence_pairs=1).verify_pairs([(report, SOURCE)])[0]
    assert result["similarity_type"] == "PARAPHRASE"
    assert result["comparison_complete"] is False
    assert result["evidence"][0]["report_range"] == {"start": 0, "end": len(REPORT)}


def test_unsupported_long_input_abstains_without_fallback_truncation():
    scorer = TableScorer(default={"supported": False, "reason": "NLI_INPUT_TOO_LONG", "tokens": 800, "max_length": 512})
    result = BidirectionalNliVerifier(scorer).verify_pairs([(REPORT, SOURCE)])[0]
    assert result["decision"] == "ABSTAIN"
    assert result["comparisons"][0]["forward"]["tokens"] == 800


@pytest.mark.parametrize("report,source", [("", SOURCE), ("Only three words.", SOURCE)])
def test_empty_and_short_inputs_abstain(report, source):
    scorer = TableScorer(default=ENTAIL)
    result = BidirectionalNliVerifier(scorer).verify_pairs([(report, source)])[0]
    assert result["decision"] == "ABSTAIN"
    assert result["similarity_type"] is None
    assert scorer.calls == []


def test_conflicting_explicit_numbers_override_model_entailment():
    report = "The experiment measured precision at 90 percent."
    source = "The experiment measured precision at 60 percent."
    result = BidirectionalNliVerifier(equivalent_scorer(report, source)).verify_pairs([(report, source)])[0]
    assert result["decision"] == "ABSTAIN"
    assert "NUMERIC_DISAGREEMENT" in result["reason_codes"]


def test_one_sided_explicit_quantity_also_withholds_model_entailment():
    report = "The experiment retained 20 source recordings for review."
    source = "The experiment retained source recordings for later review."
    result = BidirectionalNliVerifier(equivalent_scorer(report, source)).verify_pairs([(report, source)])[0]
    assert result["decision"] == "ABSTAIN"
    assert result["reason_codes"] == ["NUMERIC_DISAGREEMENT"]


def test_same_word_multiset_with_changed_roles_abstains_despite_entailment():
    report = "Alice sends the completed report to Bob today."
    source = "Bob sends the completed report to Alice today."
    result = BidirectionalNliVerifier(equivalent_scorer(report, source)).verify_pairs([(report, source)])[0]
    assert result["decision"] == "ABSTAIN"
    assert result["reason_codes"] == ["WORD_ORDER_ROLE_BINDING_UNRESOLVED"]


def test_swapped_quantities_are_not_equivalent_just_because_numeric_inventory_matches():
    report = "Alice processes 10 reports while Bob processes 20 reports."
    source = "Alice processes 20 reports while Bob processes 10 reports."
    result = BidirectionalNliVerifier(equivalent_scorer(report, source)).verify_pairs([(report, source)])[0]
    assert result["decision"] == "ABSTAIN"
    assert result["reason_codes"] == ["WORD_ORDER_ROLE_BINDING_UNRESOLVED"]


def test_equivalent_decimal_notation_does_not_create_numeric_disagreement():
    report = "The experiment measured precision at 90 percent."
    source = "The experiment measured precision at 90.0 percent."
    result = BidirectionalNliVerifier(equivalent_scorer(report, source)).verify_pairs([(report, source)])[0]
    assert result["similarity_type"] == "PARAPHRASE"


def test_identical_case_whitespace_segments_defer_to_exact_match_policy():
    source = REPORT.upper().replace(" ", "  ")
    result = BidirectionalNliVerifier(TableScorer(default=ENTAIL)).verify_pairs([(REPORT, source)])[0]
    assert result["decision"] == "ABSTAIN"
    assert result["similarity_type"] is None
    assert result["reason_codes"] == ["IDENTICAL_SEGMENTS_REQUIRE_EXACT_POLICY"]


def _marker_hint(report, marker="[4]"):
    start = report.index(marker)
    return {"report": [{"start": start, "end": start + len(marker)}], "source": []}


def test_explicit_single_marker_hint_masks_only_number_guard_and_preserves_nli_text_and_hashes():
    report = "Prior research [4] describes the immutable archive mechanism."
    source = "Previous research describes the immutable archive mechanism."
    scorer = equivalent_scorer(report, source)
    verifier = BidirectionalNliVerifier(scorer)
    original = verifier.verify_pairs([(report, source)])[0]
    hint = _marker_hint(report)
    hinted = verifier.verify_pairs([(report, source)], number_exclusion_ranges=[hint])[0]
    assert original["decision"] == "ABSTAIN"
    assert original["reason_codes"] == ["NUMERIC_DISAGREEMENT"]
    assert hinted["similarity_type"] == "PARAPHRASE"
    assert scorer.calls == [[(report, source), (source, report)]]
    assert hinted["report_text_sha256"] == original["report_text_sha256"] == hashlib.sha256(report.encode()).hexdigest()
    assert hinted["academic_citation_validity"] == "NOT_ASSESSED"
    excluded = hinted["evidence"][0]["number_exclusion_ranges"]["report"]
    assert excluded == [{**hint["report"][0], "marker_sha256": hashlib.sha256(b"[4]").hexdigest()}]
    assert hinted["number_exclusion_ranges"]["report"] == excluded


def test_hinted_citation_does_not_hide_other_measurement_numbers():
    report = "Prior research [4] processed 12 source recordings during evaluation."
    source = "Previous research processed 15 source recordings during evaluation."
    result = BidirectionalNliVerifier(equivalent_scorer(report, source)).verify_pairs(
        [(report, source)], number_exclusion_ranges=[_marker_hint(report)],
    )[0]
    assert result["decision"] == "ABSTAIN"
    assert result["reason_codes"] == ["NUMERIC_DISAGREEMENT"]


def test_exclusions_stay_scoped_to_original_sentence_offsets():
    first = "The system requires 4 complete review samples. "
    report = first + "Prior research [4] describes the immutable archive mechanism."
    source = "Previous research describes the immutable archive mechanism."
    sentence = report[len(first):]
    result = BidirectionalNliVerifier(equivalent_scorer(sentence, source)).verify_pairs(
        [(report, source)], number_exclusion_ranges=[_marker_hint(report)],
    )[0]
    assert result["similarity_type"] == "PARAPHRASE"
    assert result["evidence"][0]["report_range"]["start"] == len(first)
    earlier = next(row for row in result["comparisons"] if row["report_range"]["start"] == 0)
    assert earlier["number_exclusion_ranges"]["report"] == []
    assert earlier["reason"] == "NUMERIC_DISAGREEMENT"


@pytest.mark.parametrize("text,marker", [
    ("The archive uses field [1,2] in the stored record.", "[1,2]"),
    ("Prior research [ 4 ] describes the archive mechanism.", "[ 4 ]"),
    ("Prior research [٤] describes the archive mechanism.", "[٤]"),
    ("The array[4] stores the immutable archive metadata.", "[4]"),
    ("The array = [4] stores the archive metadata.", "[4]"),
    ("The recorded value [4] was retained for analysis.", "[4]"),
    ("The observed temperature increased by [4] °C during measurement.", "[4]"),
    ("Thời gian xử lý là [4] giây trong phép đo.", "[4]"),
    ("The equation uses [4] + five for initialization.", "[4]"),
])
def test_invalid_format_array_and_measurement_hints_fail_closed(text, marker):
    scorer = TableScorer(default=ENTAIL)
    with pytest.raises(ValueError, match="safe single numeric marker"):
        BidirectionalNliVerifier(scorer).verify_pairs(
            [(text, SOURCE)], number_exclusion_ranges=[_marker_hint(text, marker)],
        )
    assert scorer.calls == []


@pytest.mark.parametrize("hints", [
    [], [{"report": [], "source": [], "unknown": []}],
    [{"report": [], "unknown": []}], [{"report": "[4]", "source": []}],
    [{"report": [{"start": -1, "end": 5}], "source": []}],
    [{"report": [{"start": True, "end": 5}], "source": []}],
    [{"report": [{"start": 0, "end": 10000}], "source": []}],
])
def test_unaligned_unknown_or_invalid_range_hints_are_rejected(hints):
    with pytest.raises(ValueError):
        BidirectionalNliVerifier(TableScorer()).verify_pairs([(REPORT, SOURCE)], number_exclusion_ranges=hints)


def test_duplicate_hints_and_hint_bound_are_rejected_before_scoring():
    report = "Prior research [4] describes the immutable archive mechanism."
    hint = _marker_hint(report)
    for count in (2, 65):
        with pytest.raises(ValueError):
            BidirectionalNliVerifier(TableScorer()).verify_pairs(
                [(report, SOURCE)], number_exclusion_ranges=[{"report": hint["report"] * count, "source": []}],
            )


def test_same_offsets_from_another_text_do_not_authorize_exclusion():
    report = "Prior research [4] describes the immutable archive mechanism."
    hint = _marker_hint(report)
    changed = report.replace("[4]", "404")
    with pytest.raises(ValueError, match="safe single numeric marker"):
        BidirectionalNliVerifier(TableScorer()).verify_pairs([(changed, SOURCE)], number_exclusion_ranges=[hint])


def test_local_marker_shape_check_never_proves_a_reference_link():
    report = "Prior research [4] describes the immutable archive mechanism."
    hint = _marker_hint(report)["report"][0]
    assert is_safe_single_numeric_marker(report, hint["start"], hint["end"])
    assert not is_safe_single_numeric_marker(report, hint["start"] + 1, hint["end"] - 1)


def test_vietnamese_unicode_offsets_resolve_original_strings():
    report = "  Hệ thống giữ nguyên dữ liệu của phiên bản đã công bố."
    source = "Dữ liệu không bị thay đổi sau khi công bố phiên bản."
    scorer = equivalent_scorer(report.strip(), source)
    result = BidirectionalNliVerifier(scorer).verify_pairs([(report, source)])[0]
    evidence = result["evidence"][0]
    assert report[evidence["report_range"]["start"]:evidence["report_range"]["end"]] == report.strip()
    assert evidence["report_range"]["start"] == 2


@pytest.mark.parametrize("report,reason", [
    ("x" * 20_001, "INPUT_CHARACTER_BUDGET_EXCEEDED"),
    ((REPORT + " ") * 65, "INPUT_SENTENCE_BUDGET_EXCEEDED"),
])
def test_oversized_inputs_abstain_before_scoring_or_hidden_truncation(report, reason):
    scorer = TableScorer(default=ENTAIL)
    result = BidirectionalNliVerifier(scorer).verify_pairs([(report, SOURCE)])[0]
    assert scorer.calls == []
    assert result["decision"] == "ABSTAIN"
    assert result["reason_codes"] == [reason]
    assert result["comparisons"] == []


def test_cross_product_is_streamed_to_bounded_heap(monkeypatch):
    import research.core_mvp.semantic_verification as module
    original = module.heapq.nsmallest
    calls = []
    def bounded(n, iterable, **kwargs):
        assert not isinstance(iterable, (list, tuple))
        assert n == 3
        calls.append(n)
        return original(n, iterable, **kwargs)
    monkeypatch.setattr(module.heapq, "nsmallest", bounded)
    report = " ".join(f"Report sentence topic numberword{i} contains enough terms." for i in range(64))
    source = " ".join(f"Source sentence topic numberword{i} contains enough terms." for i in range(64))
    scorer = TableScorer()
    result = BidirectionalNliVerifier(scorer, max_sentence_pairs=3).verify_pairs([(report, source)])[0]
    assert calls == [3]
    assert result["total_sentence_pairs"] == 64 * 64
    assert result["comparison_count"] == 3
    assert len(scorer.calls[0]) == 6


def test_adjacent_context_windows_preserve_antecedents_and_original_spans():
    report = "The irrigation controller opens the water valve. It stops after the soil becomes wet."
    source = "Watering starts when the controller opens its valve. The controller halts watering once wet soil is detected."
    scorer = equivalent_scorer(report, source)
    result = BidirectionalNliVerifier(scorer, max_context_sentences=2).verify_pairs([(report, source)])[0]
    assert result["decision"] == "PARAPHRASE_SUPPORTED"
    assert result["max_context_sentences"] == 2
    assert result["evidence"][0]["report_range"] == {"start": 0, "end": len(report)}
    assert result["evidence"][0]["source_range"] == {"start": 0, "end": len(source)}


def test_total_directional_budget_withholds_batch_without_silently_prioritizing_first_pairs():
    pairs = [(
        f"Report word{i} explains fixed data provenance. Report word{i} describes immutable source identifiers.",
        f"Source word{i} explains fixed data provenance. Source word{i} describes immutable source identifiers.",
    ) for i in range(600)]
    scorer = TableScorer(default=ENTAIL)
    results = BidirectionalNliVerifier(scorer).verify_pairs(pairs)
    assert len(results) == 600
    assert scorer.calls == []
    assert all(row["decision"] == "ABSTAIN" for row in results)
    assert all(row["reason_codes"] == ["DIRECTIONAL_PAIR_BUDGET_EXCEEDED"] for row in results)


def test_input_pair_batch_hard_limit_fails_before_scoring():
    scorer = TableScorer()
    with pytest.raises(ValueError, match="input-pair batch"):
        BidirectionalNliVerifier(scorer).verify_pairs([(REPORT, SOURCE)] * 2049)
    assert scorer.calls == []


def test_directional_pairs_batch_and_cache_across_requests():
    scorer = equivalent_scorer()
    verifier = BidirectionalNliVerifier(scorer)
    first = verifier.verify_pairs([(REPORT, SOURCE), (REPORT, SOURCE)])
    second = verifier.verify_pairs([(REPORT, SOURCE)])
    assert len(scorer.calls) == 1
    assert len(scorer.calls[0]) == 2
    assert first[0] == first[1] == second[0]
    first[0]["evidence"][0]["forward"]["entailment"] = 0
    assert verifier.verify_pairs([(REPORT, SOURCE)])[0]["evidence"][0]["forward"]["entailment"] == 0.94


@pytest.mark.parametrize("row", [
    {"entailment": float("nan"), "neutral": 0, "contradiction": 0},
    {"entailment": True, "neutral": 0, "contradiction": 0},
    {"entailment": 0.8, "neutral": 0.8, "contradiction": 0.1},
    {"entailment": 0.8, "neutral": 0.2},
    {"supported": False},
])
def test_invalid_scorer_values_fail_closed(row):
    with pytest.raises(ValueError):
        BidirectionalNliVerifier(TableScorer(default=row)).verify_pairs([(REPORT, SOURCE)])


def test_wrong_prediction_count_fails_closed():
    scorer = TableScorer()
    scorer.predict_relations = lambda pairs: []
    with pytest.raises(ValueError, match="wrong number"):
        BidirectionalNliVerifier(scorer).verify_pairs([(REPORT, SOURCE)])


@pytest.mark.parametrize("kwargs", [
    {"entailment_threshold": 0}, {"rejection_threshold": True},
    {"margin": float("inf")}, {"max_sentence_pairs": 0}, {"min_sentence_words": False},
    {"max_sentence_pairs": 65}, {"max_context_sentences": 3},
])
def test_invalid_policy_limits_fail_closed(kwargs):
    with pytest.raises(ValueError):
        BidirectionalNliVerifier(TableScorer(), **kwargs)


def test_checkpoint_requires_exact_revision_without_loading_model():
    with pytest.raises(ValueError, match="immutable"):
        TransformersNliScorer("model-name", "main")


def test_shared_loader_is_offline_opt_in_and_rejects_relevance_backend(monkeypatch):
    import research.core_mvp.semantic_verification as module
    calls = []
    monkeypatch.setattr(module, "TransformersNliScorer", lambda *a, **k: calls.append((a, k)) or TableScorer())
    assert load_semantic_verifier({}, {"enabled": False}) is None
    assert calls == []
    with pytest.raises(ValueError, match="transformers_nli"):
        load_semantic_verifier({"backend": "sentence_transformers_cross_encoder"}, {"enabled": True})
    result = load_semantic_verifier({"backend": "transformers_nli", "model": "model", "revision": "a" * 40}, {"enabled": True})
    assert isinstance(result, BidirectionalNliVerifier)
    assert calls[0][1]["local_files_only"] is True


def test_loader_validates_pipeline_only_citation_guard_without_forwarding_to_constructor(monkeypatch):
    import research.core_mvp.semantic_verification as module
    monkeypatch.setattr(module, "TransformersNliScorer", lambda *a, **k: TableScorer())
    model = {"backend": "transformers_nli", "model": "model", "revision": "a" * 40}
    verifier = load_semantic_verifier(model, {"enabled": True, "citation_number_guard": "LINKED_SINGLE_NUMERIC_MARKERS"})
    assert verifier.metadata["citation_number_guard"] == "LINKED_SINGLE_NUMERIC_MARKERS"
    for invalid in (True, "IGNORE_ALL_NUMBERS"):
        with pytest.raises(ValueError, match="citation number guard"):
            load_semantic_verifier(model, {"enabled": True, "citation_number_guard": invalid})


def test_transformers_adapter_checks_real_input_length_and_label_mapping(monkeypatch):
    import torch
    import transformers

    calls = []

    class Tokenizer:
        def __call__(self, a, b, **kwargs):
            calls.append(kwargs)
            assert kwargs["truncation"] is False
            if isinstance(a, str):
                return {"input_ids": list(range(700 if a == "long" else 12))}
            return {"input_ids": torch.ones((len(a), 12), dtype=torch.long)}

    class Model:
        config = SimpleNamespace(id2label={0: "contradiction", 1: "neutral", 2: "entailment"})

        def to(self, device):
            return self

        def eval(self):
            return self

        def __call__(self, **kwargs):
            return SimpleNamespace(logits=torch.tensor([[0.0, 0.0, 6.0]] * len(kwargs["input_ids"])))

    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", lambda *a, **k: Tokenizer())
    monkeypatch.setattr(transformers.AutoModelForSequenceClassification, "from_pretrained", lambda *a, **k: Model())
    adapter = TransformersNliScorer("locked-model", "a" * 40, batch_size=2)
    result = adapter.predict_relations([("long", "source"), (REPORT, SOURCE)])
    assert result[0] == {"supported": False, "reason": "NLI_INPUT_TOO_LONG", "tokens": 700, "max_length": 512}
    assert result[1]["entailment"] > 0.99
    assert result[1]["contradiction"] < 0.01
    assert len(calls) == 3


def test_mps_adapter_explicitly_requests_float32_without_cpu_fallback(monkeypatch):
    import torch
    import transformers
    calls = []
    class Model:
        config = SimpleNamespace(id2label={0: "entailment", 1: "neutral", 2: "contradiction"})
        def to(self, device):
            assert device == "mps"
            return self
        def eval(self):
            return self
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", lambda *a, **k: object())
    monkeypatch.setattr(transformers.AutoModelForSequenceClassification, "from_pretrained",
                        lambda *a, **k: calls.append(k) or Model())
    adapter = TransformersNliScorer("locked-model", "a" * 40, device="mps")
    assert calls[0]["dtype"] is torch.float32
    assert adapter.metadata["device"] == "mps"
    assert adapter.metadata["requested_dtype"] == "float32"
