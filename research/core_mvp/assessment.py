"""Executable feasibility baseline for evidence-grounded assessment."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
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
_NEGATION_CUE = re.compile(
    r"\b(?:not|never|without|no|cannot|không|chưa|chẳng|chả)\b"
    r"|\b\w+n['’]t\b",
    flags=re.IGNORECASE,
)
_CLAUSE_BREAK = re.compile(
    r"[.!?;:,\n]|\b(?:but|however|nhưng|tuy nhiên)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class _ScopedEvidence:
    """A retrieval hit resolved against the current report, never a raw hit."""

    record: dict[str, Any]
    chunk: Mapping[str, Any]


def _document_version(item: Mapping[str, Any]) -> str | None:
    """Accept the chunk and span field names without silently mixing versions."""

    values = [
        value
        for key in ("document_version", "document_version_id")
        if (value := item.get(key)) is not None
    ]
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError("Evidence document version must be a non-empty string")
    if len(set(values)) > 1:
        raise ValueError("Conflicting evidence document versions")
    return values[0] if values else None


def _report_scope(
    report_chunks: Sequence[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str, str | None]:
    """Require one report/version even when a caller bypasses parse_document."""

    report_map: dict[str, dict[str, Any]] = {}
    report_id = report_chunks[0].get("document_id")
    if not isinstance(report_id, str) or not report_id:
        raise ValueError("Report chunks require a non-empty document_id")
    version = _document_version(report_chunks[0])
    for chunk in report_chunks:
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("Report chunks require a non-empty chunk_id")
        if chunk_id in report_map:
            raise ValueError("Report chunk IDs must be unique")
        if chunk.get("document_id") != report_id:
            raise ValueError("Report chunks must belong to one report")
        if _document_version(chunk) != version:
            raise ValueError("Report chunks must belong to one document version")
        report_map[chunk_id] = chunk
    return report_map, report_id, version


def _validated_evidence_pack(
    candidates: Sequence[dict[str, Any]],
    report_map: Mapping[str, dict[str, Any]],
    *,
    report_id: str,
    report_version: str | None,
) -> list[_ScopedEvidence]:
    """Resolve every hit to a canonical report chunk before verification."""

    pack: list[_ScopedEvidence] = []
    seen_ids: set[str] = set()
    for candidate in candidates:
        chunk_id = candidate.get("chunk_id")
        if not isinstance(chunk_id, str) or chunk_id not in report_map:
            raise ValueError(f"Dangling evidence chunk_id: {chunk_id!r}")
        if chunk_id in seen_ids:
            raise ValueError(f"Duplicate evidence chunk_id: {chunk_id}")
        seen_ids.add(chunk_id)
        chunk = report_map[chunk_id]
        if candidate.get("document_id") != report_id or chunk["document_id"] != report_id:
            raise ValueError(f"Cross-report evidence chunk_id: {chunk_id}")
        candidate_version = _document_version(candidate)
        if candidate_version is not None and candidate_version != report_version:
            raise ValueError(f"Cross-version evidence chunk_id: {chunk_id}")
        if _document_version(chunk) != report_version:
            raise ValueError(f"Cross-version evidence chunk_id: {chunk_id}")
        spans = chunk.get("source_spans", [])
        if isinstance(spans, (str, bytes)) or not isinstance(spans, Sequence):
            raise ValueError(f"Invalid evidence source spans for {chunk_id}")
        if report_version is not None and not spans:
            raise ValueError(f"Missing evidence source spans for {chunk_id}")
        for span in spans:
            if not isinstance(span, Mapping):
                raise ValueError(f"Invalid evidence source span for {chunk_id}")
            if span.get("document_id") != report_id:
                raise ValueError(f"Cross-report evidence source span for {chunk_id}")
            span_version = _document_version(span)
            if span_version != report_version:
                raise ValueError(f"Cross-version evidence source span for {chunk_id}")
        pack.append(_ScopedEvidence(_evidence_record(candidate, chunk), chunk))
    return pack


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


def _phrase_matches(text: str, phrase: str) -> list[tuple[int, int]]:
    canonical_phrase = unicodedata.normalize("NFKC", phrase).strip()
    if not canonical_phrase:
        return []
    pattern = re.escape(canonical_phrase).replace(r"\ ", r"\s+")
    if canonical_phrase[0].isalnum():
        pattern = r"(?<!\w)" + pattern
    if canonical_phrase[-1].isalnum():
        pattern += r"(?!\w)"
    return [
        match.span()
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    ]


def _phrase_match(text: str, phrase: str) -> tuple[int, int] | None:
    locations = _phrase_matches(text, phrase)
    return locations[0] if locations else None


def _negated_clause(
    text: str, start: int, end: int
) -> tuple[int, int] | None:
    """Find a nearby negation cue in this clause, without claiming NLI."""

    left = 0
    right = len(text)
    for boundary in _CLAUSE_BREAK.finditer(text):
        if boundary.end() <= start:
            left = boundary.end()
        elif boundary.start() >= end:
            right = boundary.start()
            break
    clause = text[left:right]
    for cue in _NEGATION_CUE.finditer(clause):
        cue_start = left + cue.start()
        cue_end = left + cue.end()
        if cue_start < end and cue_end > start:
            continue  # An authored phrase may itself express a negative claim.
        between = text[cue_end:start] if cue_end <= start else text[end:cue_start]
        if len(re.findall(r"\b\w+\b", between)) <= 4:
            return left, right
    return None


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
        "document_version_id": _document_version(chunk),
        "source_name": chunk.get("source_name"),
        "section_path": deepcopy(chunk.get("section_path", [])),
        "locator": deepcopy(chunk.get("locator")),
        "rank": int(candidate["rank"]),
        "retrieval_score": candidate.get("score"),
        "retrieval_score_type": candidate.get("score_type"),
        "cross_encoder_score": candidate.get("cross_encoder_score"),
        "excerpt": excerpt,
        "source_spans": deepcopy(chunk.get("source_spans", [])),
    }


def _verify(
    checklist: Mapping[str, Any],
    evidence_pack: Sequence[_ScopedEvidence],
) -> dict[str, Any]:
    evidence = [entry.record for entry in evidence_pack]
    requirement_results: list[dict[str, Any]] = []
    matched_spans: list[dict[str, Any]] = []
    negated_spans: list[dict[str, Any]] = []
    for requirement in checklist["requirements"]:
        hits: list[dict[str, Any]] = []
        negated_hits: list[dict[str, Any]] = []
        for entry in evidence_pack:
            chunk = entry.chunk
            text = str(chunk.get("normalized_text", chunk.get("text", "")))
            for alternative in requirement["any_of"]:
                for start, end in _phrase_matches(text, str(alternative)):
                    negated_clause = _negated_clause(text, start, end)
                    span_start, span_end = (
                        negated_clause if negated_clause is not None else (start, end)
                    )
                    hit = {
                        "requirement_id": requirement["requirement_id"],
                        "matched_alternative": alternative,
                        "evidence_id": entry.record["evidence_id"],
                        "span": _resolve_normalized_range(chunk, span_start, span_end),
                    }
                    if negated_clause is not None:
                        negated_hits.append(hit)
                        negated_spans.append(hit)
                    else:
                        hits.append(hit)
                        matched_spans.append(hit)
        requirement_results.append(
            {
                "requirement_id": requirement["requirement_id"],
                "description": requirement["description"],
                "satisfied": bool(hits),
                "hits": hits,
                "negated_hits": negated_hits,
            }
        )

    contradiction_hits: list[dict[str, Any]] = []
    for pattern in checklist["contradiction_patterns"]:
        for entry in evidence_pack:
            chunk = entry.chunk
            text = str(chunk.get("normalized_text", chunk.get("text", "")))
            location = _phrase_match(text, str(pattern))
            if location is None:
                continue
            start, end = location
            contradiction_hits.append(
                {
                    "pattern": pattern,
                    "evidence_id": entry.record["evidence_id"],
                    "span": _resolve_normalized_range(chunk, start, end),
                }
            )

    satisfied_count = sum(item["satisfied"] for item in requirement_results)
    all_satisfied = satisfied_count == len(requirement_results)
    if (contradiction_hits or negated_spans) and all_satisfied:
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
    elif negated_spans:
        relation = "INSUFFICIENT"
        outcome = "CANNOT_ASSESS"
        reason_code = "NEGATED_REQUIRED_EVIDENCE"
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
        "negated_evidence_spans": negated_spans,
        "evidence_pack": evidence,
        "rationale": (
            f"{relation}: {satisfied_count}/{len(requirement_results)} explicit "
            f"evidence requirements matched; {len(contradiction_hits)} authored "
            f"contradiction pattern(s) matched; {len(negated_spans)} negated "
            f"mention(s) withheld from support. Decision={outcome} "
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
        required_unknown = [
            checklist["checklist_id"]
            for checklist in criterion["checklists"]
            if checklist["importance"] in {"CORE", "REQUIRED"}
            and result_map[checklist["checklist_id"]]["checklist_outcome"]
            == "CANNOT_ASSESS"
        ]
        score: float | None
        reason: str
        if required_unknown:
            score = None
            reason = "REQUIRED_CHECKLIST_CANNOT_ASSESS"
            all_scorable = False
        elif unable:
            score = None
            reason = (
                "TOO_MUCH_INSUFFICIENT_EVIDENCE"
                if needs_review
                else "UNRESOLVED_CHECKLIST_EVIDENCE"
            )
            all_scorable = False
        elif required_unmet:
            score = min(
                float(criterion["weight"]),
                float(rules["required_unmet_score"]),
            )
            reason = "REQUIRED_CHECKLIST_UNMET"
        else:
            assessable_count = counts["MET"] + counts["UNMET"]
            if assessable_count == 0:
                score = None
                reason = "NO_ASSESSABLE_CHECKLIST"
                all_scorable = False
            else:
                score = round(
                    float(criterion["weight"]) * counts["MET"] / assessable_count,
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
                "required_cannot_assess_checklist_ids": required_unknown,
                "proposed_score": score,
                "score_reason": reason,
                "requires_lecturer_review": score is None or unable > 0,
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
    report_map, report_id, report_version = _report_scope(report_chunks)

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
            evidence_pack = _validated_evidence_pack(
                candidates,
                report_map,
                report_id=report_id,
                report_version=report_version,
            )
            verification = _verify(checklist, evidence_pack)
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
        "requires_lecturer_review": total is None or any(
            item["requires_lecturer_review"] for item in criterion_results
        ),
        "limitations": [
            "Verification v0 uses explicit authored phrase requirements and does not infer semantic entailment.",
            "Negation handling uses nearby lexical cues; scope and context still require human review.",
            "Any CANNOT_ASSESS checklist withholds its criterion and total score; assessable_subtotal is diagnostic only.",
            "GRAPH v0 is a structure-and-term PPR baseline, not the complete HippoRAG architecture.",
            "Automatic decomposition of free-form rubric criteria is outside this feasibility baseline.",
            "Every proposed score remains subject to lecturer review and gold-set validation.",
        ],
    }
