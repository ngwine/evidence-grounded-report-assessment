"""Opt-in paragraph context and proof provenance; no model-quality claims.

The fake transport deliberately supplies relations. These tests check what
evidence reaches the model and how exact proof is resolved, not whether an LLM
can correctly count quotations or distinguish a writer from a quoted speaker.
"""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from research.core_mvp import llm_assessment as llm
from research.tests.test_llm_assessment_verifier import (
    MODEL, FakeOllama, assert_unknown, checklist, scoped_pack,
)


POLICY = {
    "enabled": True,
    "citation_mode": "source_units",
    "source_unit_policy": "context_bundles_v1",
}


def _data(payload):
    return json.loads(payload["messages"][1]["content"])


def _propose(payload, *, relation="SUPPORTED", passage=0, unit=0):
    data = _data(payload)
    chosen = data["evidence_passages"][passage]["units"][unit]["unit_id"]
    return {
        "checklist_id": data["checklist_id"],
        "requirements": [{
            "requirement_id": requirement["requirement_id"],
            "relation": relation,
            "rationale": "Synthetic transport proposal; semantic correctness is not certified.",
            "evidence": [] if relation == "INSUFFICIENT" else [{"unit_id": chosen}],
        } for requirement in data["requirements"]],
    }


def _verify(texts, *, content=_propose, policy=None, pack=None):
    transport = FakeOllama(content)
    verifier = llm.LlmAssessmentVerifier(MODEL, policy or POLICY, transport=transport)
    result = verifier.verify(checklist(), scoped_pack(*texts) if pack is None else pack)
    return result, transport, verifier


def _two_elements(left, right, separator="\n\n"):
    text = left + separator + right
    pack = scoped_pack(text)
    entry = pack[0]
    first = deepcopy(entry.chunk["source_spans"][0])
    first["chunk_normalized_char_end"] = len(left)
    second = deepcopy(first)
    second.update(
        element_key="P0002",
        chunk_normalized_char_start=len(left) + len(separator),
        chunk_normalized_char_end=len(text),
    )
    entry.chunk["source_spans"] = [first, second]
    entry.record["source_spans"] = deepcopy(entry.chunk["source_spans"])
    return text, pack


@pytest.mark.parametrize("text", [
    'The C.S. Mott team reported a survey. It said, “Parents need support.” '
    'The writer then described their own experience.',
    'FBI Director J. Morgan said, “The earlier claim was incomplete.” '
    'That is Morgan\'s position; the writer explicitly disagrees with it.',
])
def test_initials_and_adjacent_attribution_are_not_split_into_quote_fragments(text):
    result, transport, _ = _verify([text])
    assert result["checklist_outcome"] == "MET"  # A forced transport proposal.
    [passage] = _data(transport.chat_calls[0][2])["evidence_passages"]
    [unit] = passage["units"]
    assert unit["text"] == text
    [proof] = result["matched_evidence_spans"]
    assert proof["span"]["text"] == text
    assert proof["span"]["normalized_start"] == 0
    assert proof["span"]["normalized_end"] == len(text)


def test_two_quotation_occurrences_keep_their_source_and_surrounding_explanation():
    text = (
        'In her article, Dr. Lê said, “The method needs a control group.” '
        'Later in the same article, Lê said, “The comparison must be fair.” '
        'The student connects both quotations to the experiment design.'
    )
    _, transport, _ = _verify([text])
    [unit] = _data(transport.chat_calls[0][2])["evidence_passages"][0]["units"]
    assert unit["text"] == text
    assert unit["text"].count("“") == 2
    assert "Dr. Lê" in unit["text"] and "same article" in unit["text"]


def test_repeated_quotation_occurrences_are_not_deduplicated_by_context_grouping():
    quote = 'The author wrote, “A comparison needs evidence.”'
    text = quote + " The student responds to it. " + quote
    _, transport, _ = _verify([text])
    [unit] = _data(transport.chat_calls[0][2])["evidence_passages"][0]["units"]
    assert unit["text"] == text
    # One context unit can contain multiple quotation occurrences. Unit count
    # must not be mistaken for quotation count by a downstream evaluator.
    assert unit["text"].count('“A comparison needs evidence.”') == 2


def test_independent_source_elements_are_not_glued_into_a_single_proof():
    left = 'Source A says, “The first claim is uncertain.”'
    right = 'Source B says, “A different claim is supported.”'
    text, pack = _two_elements(left, right)
    result, transport, _ = _verify([], pack=pack, content=lambda p: _propose(p, unit=1))
    assert result["checklist_outcome"] == "MET"
    units = _data(transport.chat_calls[0][2])["evidence_passages"][0]["units"]
    assert [unit["text"] for unit in units] == [left, right]
    [proof] = result["matched_evidence_spans"]
    assert proof["span"]["text"] == right
    assert proof["span"]["normalized_start"] == text.index(right)
    assert [s["element_key"] for s in proof["span"]["source_spans"]] == ["P0002"]


def test_title_and_body_stay_distinct_when_the_parser_gives_distinct_elements():
    title = '“Memory” and “Experience”'
    body = 'This report discusses those concepts, without quoting a primary source.'
    _, pack = _two_elements(title, body)
    result, transport, _ = _verify(
        [], pack=pack, content=lambda p: _propose(p, relation="INSUFFICIENT"),
    )
    assert_unknown(result)
    assert result["llm_verification"]["status"] == "VALIDATED"
    assert not result["matched_evidence_spans"]
    assert [u["text"] for u in _data(transport.chat_calls[0][2])["evidence_passages"][0]["units"]] == [title, body]


def test_unicode_and_leading_whitespace_resolve_to_exact_source_coordinates():
    body = 'Tôi đã thử nghiệm. C.S. là chữ viết tắt; “đây là lời dẫn”.'
    text = " \n\t" + body + "  \n"
    result, _, _ = _verify([text])
    [proof] = result["matched_evidence_spans"]
    span = proof["span"]
    assert span["text"] == body
    assert span["normalized_start"] == len(" \n\t")
    assert span["normalized_end"] == len(" \n\t") + len(body)
    assert text[span["normalized_start"]:span["normalized_end"]] == body
    assert span["raw_start"] == span["normalized_start"]
    assert span["raw_end"] == span["normalized_end"]


def test_long_context_is_bounded_and_covers_all_nonwhitespace_source_characters():
    text = " \n" + ("Người viết giải thích bằng chứng. " * 160) + ("x" * 1901) + "\n "
    # This exercises range partitioning, not the separately tested request-byte
    # guard; leave enough context for the Vietnamese UTF-8 text and schema.
    result, transport, verifier = _verify([text], policy={**POLICY, "num_ctx": 32768})
    assert result["llm_verification"]["status"] == "VALIDATED"
    units = _data(transport.chat_calls[0][2])["evidence_passages"][0]["units"]
    limit = verifier.metadata["source_unit_policy"]["max_chars"]
    assert limit == llm.CONTEXT_BUNDLE_MAX_CHARS
    assert len(units) > 1
    assert all(0 < len(unit["text"]) <= limit for unit in units)
    assert len({unit["unit_id"] for unit in units}) == len(units)
    assert "".join(c for unit in units for c in unit["text"] if not c.isspace()) == "".join(
        c for c in text if not c.isspace()
    )
    scoped = llm.LlmAssessmentVerifier._scope(scoped_pack(text))
    _, catalog = llm._source_unit_catalog(scoped, policy="context_bundles_v1")
    for (_evidence_id, unit_id), (_entry, start, end) in catalog.items():
        unit = next(u for u in units if u["unit_id"] == unit_id)
        assert text[start:end] == unit["text"]


def test_catalog_budget_fails_before_generation_instead_of_silently_dropping_passages():
    texts = ["A."] * (llm.SOURCE_UNIT_MAX_COUNT + 1)
    result, transport, _ = _verify(texts)
    assert_unknown(result)
    assert result["reason_code"] == "LLM_UNIT_CATALOG_BUDGET_EXCEEDED"
    assert not transport.chat_calls


def test_selected_only_auditor_receives_the_complete_chosen_context_bundle():
    text = 'Dr. C.S. Lê said, “The control matters.” The writer disputes this interpretation.'
    hidden = "UNSELECTED_PASSAGE_MARKER is present only in a different passage."

    def content(payload):
        data = _data(payload)
        if "evidence_passages" in data:
            return {
                "checklist_id": data["checklist_id"],
                "requirements": [{
                    "requirement_id": r["requirement_id"],
                    "evidence": [{"unit_id": data["evidence_passages"][0]["units"][0]["unit_id"]}],
                } for r in data["requirements"]],
            }
        return {
            "checklist_id": data["checklist_id"],
            "requirements": [{
                "requirement_id": r["requirement_id"], "relation": "SUPPORTED",
                "rationale": "A forced transport proposal for provenance testing.",
                "used_unit_ids": [r["selected_units"][0]["unit_id"]],
            } for r in data["requirements"]],
        }

    result, transport, _ = _verify(
        [text, hidden], content=content, policy={**POLICY, "citation_audit": True},
    )
    assert len(transport.chat_calls) == 2
    selector_data, auditor_data = [_data(call[2]) for call in transport.chat_calls]
    assert hidden in json.dumps(selector_data)
    assert hidden not in json.dumps(auditor_data)
    assert auditor_data["requirements"][0]["selected_units"] == [{"unit_id": "u1.1", "text": text}]
    assert result["matched_evidence_spans"][0]["span"]["text"] == text


def test_empty_selection_does_not_invent_document_absence_or_unmet():
    def empty_selection(payload):
        data = _data(payload)
        return {"checklist_id": data["checklist_id"], "requirements": [{
            "requirement_id": requirement["requirement_id"], "evidence": [],
        } for requirement in data["requirements"]]}

    result, transport, _ = _verify(
        ['The article has an ambiguous discussion of “a claim”.'],
        content=empty_selection, policy={**POLICY, "citation_audit": True},
    )
    assert_unknown(result)
    assert not result["contradiction_hits"]
    assert len(transport.chat_calls) == 1
    assert result["llm_verification"]["citation_audit"]["status"] == "SKIPPED_EMPTY_SELECTION"


@pytest.mark.parametrize("audit", [False, True])
def test_new_policy_versions_the_prompt_without_mutating_legacy_configuration(audit):
    legacy_policy = {"enabled": True, "citation_mode": "source_units", "citation_audit": audit}
    before = llm.LlmAssessmentVerifier(MODEL, legacy_policy, transport=FakeOllama())
    new = llm.LlmAssessmentVerifier(MODEL, {**POLICY, "citation_audit": audit}, transport=FakeOllama())
    after = llm.LlmAssessmentVerifier(MODEL, legacy_policy, transport=FakeOllama())
    assert "source_unit_policy" not in before.policy
    assert before.policy == after.policy
    assert before.metadata["policy_sha256"] == after.metadata["policy_sha256"]
    assert before.metadata["prompt_sha256"] == after.metadata["prompt_sha256"]
    assert before.metadata["prompt_sha256"] != new.metadata["prompt_sha256"]
    assert before.metadata["prompt_version"] != new.metadata["prompt_version"]
    assert new.metadata["source_unit_policy"]["max_chars"] == llm.CONTEXT_BUNDLE_MAX_CHARS
    if audit:
        assert before.metadata["citation_audit"]["prompt_sha256"] == after.metadata["citation_audit"]["prompt_sha256"]
        assert before.metadata["citation_audit"]["prompt_sha256"] != new.metadata["citation_audit"]["prompt_sha256"]


@pytest.mark.parametrize("value", [None, True, [], {}, "unknown-context-policy"])
def test_invalid_context_policy_is_rejected_before_model_loading(value):
    with pytest.raises(ValueError, match="source_unit_policy"):
        llm.validate_llm_policy({**POLICY, "source_unit_policy": value})


def test_context_policy_requires_source_units_protocol():
    with pytest.raises(ValueError, match="source_units"):
        llm.validate_llm_policy({"enabled": True, "source_unit_policy": "context_bundles_v1"})


def test_bundle_cannot_fabricate_attribution_across_unmapped_source_text():
    left = 'The writer said, “A genuine quotation.”'
    right = 'A different section contains another statement.'
    # A malformed chunk pretends the intervening factual text has no owner.
    _, pack = _two_elements(left, right, separator=" UNMAPPED ATTRIBUTION ")
    result, transport, _ = _verify([], pack=pack)
    assert_unknown(result)
    assert not transport.chat_calls
    assert not result["matched_evidence_spans"]


def test_overlapping_nonwhitespace_source_ownership_is_withheld_before_generation():
    text = 'Two parser elements cannot both own this same attribution.'
    pack = scoped_pack(text)
    duplicate = deepcopy(pack[0].chunk["source_spans"][0])
    duplicate.update(element_key="P0002", chunk_normalized_char_start=4)
    pack[0].chunk["source_spans"].append(duplicate)
    pack[0].record["source_spans"] = deepcopy(pack[0].chunk["source_spans"])
    result, transport, _ = _verify([], pack=pack)
    assert_unknown(result)
    assert result["reason_code"] == "LLM_AMBIGUOUS_CONTEXT_BUNDLE_SCOPE"
    assert not transport.chat_calls
    assert not result["matched_evidence_spans"]
