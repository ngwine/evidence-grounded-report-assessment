"""Executable feasibility baseline for evidence-grounded assessment."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence

from research.offline_retrieval.bm25 import rank_bm25
from research.offline_retrieval.cross_encoder import PairScorer
from research.offline_retrieval.dense import Encoder, rank_dense
from research.offline_retrieval.rrf import fuse_rrf

from .graph import rank_graph, validate_graph_config
from .rubric import compile_rubric
from .similarity import _rerank_chunks, _resolve_normalized_range


_RELATIONS = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT"}
_OUTCOMES = {"MET", "UNMET", "CANNOT_ASSESS"}


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def validate_assessment_config(config: Mapping[str, Any]) -> dict[str, Any]:
    candidate_depth = _positive_int(
        config.get("candidate_depth", 20), "pipeline2.candidate_depth"
    )
    rerank_depth = _positive_int(
        config.get("rerank_depth", 10), "pipeline2.rerank_depth"
    )
    top_k = _positive_int(config.get("top_k", 5), "pipeline2.top_k")
    if top_k > candidate_depth:
        raise ValueError("pipeline2.top_k must be <= candidate_depth")
    if rerank_depth > candidate_depth:
        raise ValueError("pipeline2.rerank_depth must be <= candidate_depth")
    reranker_enabled = bool(config.get("reranker_enabled", True))
    if reranker_enabled and top_k > rerank_depth:
        raise ValueError(
            "pipeline2.top_k must be <= rerank_depth when reranking is enabled"
        )
    graph_value = config.get("graph", {})
    if not isinstance(graph_value, Mapping):
        raise ValueError("pipeline2.graph must be an object")
    graph = validate_graph_config({**graph_value, "top_k": top_k})
    return {
        "candidate_depth": candidate_depth,
        "rerank_depth": rerank_depth,
        "top_k": top_k,
        "dense_enabled": bool(config.get("dense_enabled", True)),
        "reranker_enabled": reranker_enabled,
        "bm25_k1": float(config.get("bm25_k1", 1.2)),
        "bm25_b": float(config.get("bm25_b", 0.75)),
        "rrf_k": _positive_int(config.get("rrf_k", 60), "pipeline2.rrf_k"),
        "graph": graph,
    }


def _query_for_checklist(checklist: Mapping[str, Any]) -> str:
    parts = [str(checklist["query"]), str(checklist["statement"])]
    for requirement in checklist["requirements"]:
        parts.extend(str(value) for value in requirement["any_of"])
    parts.extend(str(value) for value in checklist["contradiction_patterns"])
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        key = part.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(part)
    return " ".join(unique)


def _rank_local(
    checklist: Mapping[str, Any],
    report_chunks: Sequence[dict[str, Any]],
    *,
    config: Mapping[str, Any],
    encoder: Encoder | None,
    reranker: PairScorer | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query_id = str(checklist["checklist_id"])
    query_text = _query_for_checklist(checklist)
    queries = [{"query_id": query_id, "text": query_text}]
    bm25 = rank_bm25(
        report_chunks,
        queries,
        top_k=int(config["candidate_depth"]),
        k1=float(config["bm25_k1"]),
        b=float(config["bm25_b"]),
    )
    methods: dict[str, dict[str, list[dict[str, Any]]]] = {"bm25": bm25}
    if config["dense_enabled"]:
        if encoder is None:
            raise ValueError("Pipeline 2 Dense retrieval requires an encoder")
        methods["dense"] = rank_dense(
            report_chunks,
            queries,
            encoder=encoder,
            top_k=int(config["candidate_depth"]),
        )
    if len(methods) == 1:
        rankings = deepcopy(bm25)
        for candidate in rankings.get(query_id, []):
            candidate["score_type"] = "bm25"
    else:
        rankings = fuse_rrf(
            methods,
            rrf_k=int(config["rrf_k"]),
            top_k=int(config["candidate_depth"]),
        )
        for candidate in rankings.get(query_id, []):
            candidate["score_type"] = "rrf"
    if config["reranker_enabled"]:
        if reranker is None:
            raise ValueError("Pipeline 2 reranking requires a Cross-Encoder")
        source_map = {str(chunk["chunk_id"]): chunk for chunk in report_chunks}
        rankings = _rerank_chunks(
            rankings,
            queries,
            source_map,
            scorer=reranker,
            rerank_depth=int(config["rerank_depth"]),
        )
    return rankings.get(query_id, [])[: int(config["top_k"])], {
        "mode": "LOCAL",
        "query": query_text,
        "retrieval_methods": sorted(methods),
        "reranked": bool(config["reranker_enabled"]),
    }


def _phrase_match(text: str, phrase: str) -> tuple[int, int] | None:
    canonical_phrase = unicodedata.normalize("NFKC", phrase).strip()
    if not canonical_phrase:
        return None
    pattern = re.escape(canonical_phrase).replace(r"\ ", r"\s+")
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.span() if match is not None else None


def _evidence_record(
    candidate: Mapping[str, Any],
    chunk: Mapping[str, Any],
) -> dict[str, Any]:
    text = str(chunk.get("normalized_text", chunk.get("text", "")))
    excerpt = text if len(text) <= 480 else text[:477] + "..."
    return {
        "evidence_id": f"evidence-{chunk['chunk_id']}",
        "chunk_id": chunk["chunk_id"],
        "document_id": chunk["document_id"],
        "document_version_id": chunk.get("document_version"),
        "source_name": chunk.get("source_name"),
        "rank": int(candidate["rank"]),
        "retrieval_score": candidate.get("score"),
        "retrieval_score_type": candidate.get("score_type"),
        "cross_encoder_score": candidate.get("cross_encoder_score"),
        "excerpt": excerpt,
        "source_spans": deepcopy(chunk.get("source_spans", [])),
    }


def _verify(
    checklist: Mapping[str, Any],
    candidates: Sequence[dict[str, Any]],
    report_chunks: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    evidence = [
        _evidence_record(candidate, report_chunks[str(candidate["chunk_id"])])
        for candidate in candidates
    ]
    requirement_results: list[dict[str, Any]] = []
    matched_spans: list[dict[str, Any]] = []
    for requirement in checklist["requirements"]:
        hits: list[dict[str, Any]] = []
        for candidate in candidates:
            chunk = report_chunks[str(candidate["chunk_id"])]
            text = str(chunk.get("normalized_text", chunk.get("text", "")))
            for alternative in requirement["any_of"]:
                location = _phrase_match(text, str(alternative))
                if location is None:
                    continue
                start, end = location
                resolved = _resolve_normalized_range(chunk, start, end)
                hit = {
                    "requirement_id": requirement["requirement_id"],
                    "matched_alternative": alternative,
                    "evidence_id": f"evidence-{chunk['chunk_id']}",
                    "span": resolved,
                }
                hits.append(hit)
                matched_spans.append(hit)
                break
        requirement_results.append(
            {
                "requirement_id": requirement["requirement_id"],
                "description": requirement["description"],
                "satisfied": bool(hits),
                "hits": hits,
            }
        )

    contradiction_hits: list[dict[str, Any]] = []
    for pattern in checklist["contradiction_patterns"]:
        for candidate in candidates:
            chunk = report_chunks[str(candidate["chunk_id"])]
            text = str(chunk.get("normalized_text", chunk.get("text", "")))
            location = _phrase_match(text, str(pattern))
            if location is None:
                continue
            start, end = location
            contradiction_hits.append(
                {
                    "pattern": pattern,
                    "evidence_id": f"evidence-{chunk['chunk_id']}",
                    "span": _resolve_normalized_range(chunk, start, end),
                }
            )

    satisfied_count = sum(item["satisfied"] for item in requirement_results)
    all_satisfied = satisfied_count == len(requirement_results)
    if contradiction_hits and all_satisfied:
        relation = "INSUFFICIENT"
        outcome = "CANNOT_ASSESS"
        reason_code = "CONFLICTING_REPORT_EVIDENCE"
    elif contradiction_hits:
        relation = "CONTRADICTED"
        outcome = "UNMET"
        reason_code = "AUTHOR_DEFINED_CONTRADICTION_PATTERN_FOUND"
    elif all_satisfied:
        relation = "SUPPORTED"
        outcome = "MET"
        reason_code = "ALL_EXPLICIT_REQUIREMENTS_EVIDENCED"
    else:
        relation = "INSUFFICIENT"
        outcome = "CANNOT_ASSESS"
        reason_code = "MISSING_REQUIRED_EVIDENCE"
    if relation not in _RELATIONS or outcome not in _OUTCOMES:
        raise AssertionError("Invalid verifier state")
    return {
        "verification_relation": relation,
        "checklist_outcome": outcome,
        "reason_code": reason_code,
        "requirements_satisfied": satisfied_count,
        "requirements_total": len(requirement_results),
        "requirement_results": requirement_results,
        "contradiction_hits": contradiction_hits,
        "matched_evidence_spans": matched_spans,
        "evidence_pack": evidence,
        "rationale": (
            f"{relation}: {satisfied_count}/{len(requirement_results)} explicit "
            f"evidence requirements matched; {len(contradiction_hits)} authored "
            f"contradiction pattern(s) matched. Decision={outcome} "
            f"({reason_code})."
        ),
    }


def _score_criteria(
    compiled_rubric: Mapping[str, Any],
    checklist_results: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], float | None, float]:
    result_map = {
        str(result["checklist_id"]): result for result in checklist_results
    }
    rules = compiled_rubric["decision_rules"]
    criterion_results: list[dict[str, Any]] = []
    assessable_subtotal = 0.0
    all_scorable = True
    for criterion in compiled_rubric["criteria"]:
        values = [result_map[item["checklist_id"]] for item in criterion["checklists"]]
        counts = Counter(str(value["checklist_outcome"]) for value in values)
        total = len(values)
        unable = counts["CANNOT_ASSESS"]
        unable_ratio = unable / total
        needs_review = (
            unable >= int(rules["cannot_assess_count_threshold"])
            or unable_ratio > float(rules["cannot_assess_ratio_threshold"])
        )
        required_unmet = [
            checklist["checklist_id"]
            for checklist in criterion["checklists"]
            if checklist["importance"] in {"CORE", "REQUIRED"}
            and result_map[checklist["checklist_id"]]["checklist_outcome"] == "UNMET"
        ]
        score: float | None
        reason: str
        if needs_review:
            score = None
            reason = "TOO_MUCH_INSUFFICIENT_EVIDENCE"
            all_scorable = False
        elif required_unmet:
            score = min(
                float(criterion["weight"]),
                float(rules["required_unmet_score"]),
            )
            reason = "REQUIRED_CHECKLIST_UNMET"
        else:
            denominator = counts["MET"] + counts["UNMET"]
            if denominator == 0:
                score = None
                reason = "NO_ASSESSABLE_CHECKLIST"
                all_scorable = False
            else:
                score = round(
                    float(criterion["weight"]) * counts["MET"] / denominator,
                    1,
                )
                reason = "PROPORTIONAL_MET_RATIO"
        if score is not None:
            assessable_subtotal += score
        criterion_results.append(
            {
                "criterion_id": criterion["criterion_id"],
                "title": criterion["title"],
                "weight": criterion["weight"],
                "outcome_counts": dict(sorted(counts.items())),
                "cannot_assess_ratio": round(unable_ratio, 6),
                "required_unmet_checklist_ids": required_unmet,
                "proposed_score": score,
                "score_reason": reason,
                "requires_lecturer_review": score is None,
            }
        )
    proposed_total = round(assessable_subtotal, 1) if all_scorable else None
    return criterion_results, proposed_total, round(assessable_subtotal, 1)


def run_assessment_pipeline(
    report_chunks: Sequence[dict[str, Any]],
    rubric: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
    encoder: Encoder | None,
    reranker: PairScorer | None,
) -> dict[str, Any]:
    """Run rubric compiler, LOCAL/GRAPH retrieval, verification and scoring."""

    if not report_chunks:
        raise ValueError("Pipeline 2 requires at least one report chunk")
    resolved = validate_assessment_config(config)
    compiled = compile_rubric(rubric)
    report_map = {str(chunk["chunk_id"]): chunk for chunk in report_chunks}
    if len(report_map) != len(report_chunks):
        raise ValueError("Report chunk IDs must be unique")

    checklist_results: list[dict[str, Any]] = []
    for criterion in compiled["criteria"]:
        for checklist in criterion["checklists"]:
            if checklist["mode"] == "LOCAL":
                candidates, retrieval = _rank_local(
                    checklist,
                    report_chunks,
                    config=resolved,
                    encoder=encoder,
                    reranker=reranker,
                )
            else:
                candidates, graph_diagnostics = rank_graph(
                    report_chunks,
                    query_id=str(checklist["checklist_id"]),
                    query_text=_query_for_checklist(checklist),
                    config=resolved["graph"],
                    seed_queries=[
                        " ".join(str(value) for value in requirement["any_of"])
                        for requirement in checklist["requirements"]
                    ],
                )
                retrieval = {
                    "mode": "GRAPH",
                    "query": _query_for_checklist(checklist),
                    "retrieval_methods": ["bm25_seeded_personalized_pagerank"],
                    "reranked": False,
                    "graph_diagnostics": graph_diagnostics,
                }
            verification = _verify(checklist, candidates, report_map)
            checklist_results.append(
                {
                    "criterion_id": criterion["criterion_id"],
                    "checklist_id": checklist["checklist_id"],
                    "statement": checklist["statement"],
                    "mode": checklist["mode"],
                    "importance": checklist["importance"],
                    "retrieval": retrieval,
                    **verification,
                }
            )

    criterion_results, total, assessable_subtotal = _score_criteria(
        compiled, checklist_results
    )
    outcome_counts = Counter(
        str(result["checklist_outcome"]) for result in checklist_results
    )
    return {
        "schema_version": 1,
        "pipeline": "evidence-grounded-assessment-core-mvp-v0",
        "research_status": "FEASIBILITY_BASELINE_REQUIRES_GOLD_VALIDATION",
        "compiled_rubric": compiled,
        "configuration": resolved,
        "report_chunk_count": len(report_chunks),
        "checklist_outcome_counts": dict(sorted(outcome_counts.items())),
        "checklist_results": checklist_results,
        "criterion_results": criterion_results,
        "proposed_total_score": total,
        "assessable_subtotal": assessable_subtotal,
        "max_score": compiled["max_score"],
        "requires_lecturer_review": total is None,
        "limitations": [
            "Verification v0 uses explicit authored phrase requirements and does not infer semantic entailment.",
            "GRAPH v0 is a structure-and-term PPR baseline, not the complete HippoRAG architecture.",
            "Automatic decomposition of free-form rubric criteria is outside this feasibility baseline.",
            "Every proposed score remains subject to lecturer review and gold-set validation.",
        ],
    }
