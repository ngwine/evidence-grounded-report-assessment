"""Focused checks for QASPER paragraph gold and within-paper evaluation."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from research.offline_retrieval.bm25 import rank_bm25
from research.qasper_pilot.benchmark import (
    normalized_evidence,
    paper_paragraphs,
    prepare_paper,
    score_rankings,
    select_papers,
    git_provenance,
)


def answer(evidence, *, unanswerable=False):
    return {"answer": {"evidence": evidence, "unanswerable": unanswerable}}


def question(identifier, text, *answers):
    return {"question_id": identifier, "question": text, "answers": list(answers)}


def test_exact_paragraph_mapping_and_multiple_human_annotations():
    paper = {
        "abstract": "A short summary.",
        "full_text": [
            {"paragraphs": ["The alpha method improves recall.", "The beta method improves precision."]}
        ],
        "figures_and_tables": [],
        "qas": [
            question(
                "q1", "Which method improves recall?",
                answer(["The alpha method improves recall. "]),
                answer(["The beta method improves precision."]),
            )
        ],
    }
    candidates, queries, gold, counts = prepare_paper(paper)
    assert normalized_evidence("  THE  alpha method  ") == "the alpha method"
    assert len(candidates) == 3
    assert queries == [{"query_id": "q1", "text": "Which method improves recall?"}]
    assert gold["q1"] == [{"s0000-p0000"}, {"s0000-p0001"}]
    assert counts["questions_annotator_evidence_disagreement"] == 1
    scores = score_rankings(
        {"q1": [{"chunk_id": "s0000-p0001"}]}, gold,
        candidate_ids={item["chunk_id"] for item in candidates},
    )
    assert scores["1"] == {
        "hit": 1.0,
        "best_annotation_recall": 1.0,
        "complete_annotation": 1.0,
        "mrr": 1.0,
    }


def test_excludes_float_unanswerable_mixed_unmatched_and_ambiguous_evidence():
    paper = {
        "abstract": "",
        "full_text": [{"section_name": "Methods", "paragraphs": ["Same paragraph.", "Same paragraph.", "Unique evidence paragraph."]}],
        "figures_and_tables": [{"caption": "Table 1: Scores."}],
        "qas": [
            question("float", "Table?", answer(["FLOAT SELECTED: Table 1: Scores."])),
            question("unanswerable", "Unknown?", answer([], unanswerable=True)),
            question("mixed", "Mixed?", answer(["Unique evidence paragraph."]), answer([], unanswerable=True)),
            question("unmatched", "Substring?", answer(["evidence paragraph"])),
            question("duplicate", "Same?", answer(["Same paragraph."])),
            question("heading", "Heading?", answer(["Methods"])),
            question("good", "Unique?", answer(["Unique evidence paragraph."])),
        ],
    }
    _candidates, queries, gold, counts = prepare_paper(paper)
    assert [item["query_id"] for item in queries] == ["good"]
    assert gold["good"] == [{"s0000-p0002"}]
    assert counts["questions_total"] == 7
    assert counts["questions_evaluable"] == 1
    assert counts["questions_excluded"] == 6
    for reason in (
        "figure_table_evidence", "unanswerable_only", "mixed_answerability",
        "unmatched_evidence", "ambiguous_paragraph", "section_heading_evidence",
    ):
        assert counts[f"excluded_reason_{reason}"] == 1


def test_requires_all_answerable_annotations_to_map_completely():
    paper = {
        "abstract": "",
        "full_text": [{"paragraphs": ["Mapped paragraph."]}],
        "figures_and_tables": [],
        "qas": [
            question("q", "Question?", answer(["Mapped paragraph."]), answer(["Not in paper."]))
        ],
    }
    _candidates, queries, gold, counts = prepare_paper(paper)
    assert queries == []
    assert gold == {}
    assert counts["excluded_reason_unmatched_evidence"] == 1


def test_selection_is_stable_and_scoring_rejects_cross_paper_candidates():
    papers = {str(i): {"full_text": []} for i in range(8)}
    assert select_papers(papers, seed=17, max_papers=3) == select_papers(papers, seed=17, max_papers=3)
    with pytest.raises(ValueError, match="cross-paper"):
        score_rankings({"q": [{"chunk_id": "other-paper"}]}, {"q": [{"own"}]}, candidate_ids={"own"})


def test_bm25_candidates_are_only_own_paper_paragraphs():
    own = {"abstract": "", "full_text": [{"paragraphs": ["Graph reasoning result.", "Other method."]}]}
    other = {"abstract": "", "full_text": [{"paragraphs": ["Graph reasoning result."]}]}
    own_candidates = paper_paragraphs(own)
    other_candidates = paper_paragraphs(other)
    assert len(own_candidates) == 2 and len(other_candidates) == 1
    rankings = rank_bm25(own_candidates, [{"query_id": "q", "text": "graph reasoning"}], top_k=10)
    assert {item["chunk_id"] for item in rankings["q"]} <= {item["chunk_id"] for item in own_candidates}


def test_standalone_zip_does_not_require_a_git_repository(monkeypatch):
    monkeypatch.setattr(
        "research.qasper_pilot.benchmark.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=128, stdout="", stderr="not a git repository"),
    )
    assert git_provenance() == {
        "available": False,
        "commit": None,
        "dirty": None,
        "status_sha256": None,
    }
