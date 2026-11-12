"""Conservative paragraph-level evidence retrieval on QASPER v0.3 dev.

Only aggregate results leave this module. Text, question IDs, annotation IDs,
gold paragraph IDs, and per-query rankings remain in memory.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unicodedata
from typing import Any

from research.offline_retrieval.bm25 import rank_bm25
from research.offline_retrieval.common import sha256_file, write_json
from research.offline_retrieval.dense import SentenceTransformerEncoder, rank_dense
from research.offline_retrieval.rrf import fuse_rrf


DEV_FILE_SHA256 = "2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93"
ARCHIVE_SHA256 = "a28fdf966db827bcee3d873107d6b6669864fb7ca8fbf73a192f5e39191bdb5a"
E5_MODEL = "intfloat/multilingual-e5-small"
E5_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
CUTOFFS = (1, 3, 5, 10)


def normalized_evidence(value: str) -> str:
    """Normalize only Unicode, case, and whitespace for exact matching."""

    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def select_papers(dataset: dict[str, Any], *, seed: int, max_papers: int) -> list[tuple[str, dict[str, Any]]]:
    if max_papers <= 0:
        raise ValueError("max_papers must be positive")
    ordered = sorted(
        dataset,
        key=lambda paper_id: (
            hashlib.sha256(f"{seed}:{paper_id}".encode("utf-8")).hexdigest(),
            paper_id,
        ),
    )
    return [(paper_id, dataset[paper_id]) for paper_id in ordered[:max_papers]]


def paper_paragraphs(paper: dict[str, Any]) -> list[dict[str, str]]:
    """Candidate units are abstract/full-text paragraphs, never other papers."""

    records: list[dict[str, str]] = []
    abstract = paper.get("abstract")
    if isinstance(abstract, str) and abstract.strip():
        records.append({"chunk_id": "abstract", "document_id": "own-paper", "text": abstract})
    for section_index, section in enumerate(paper.get("full_text", [])):
        for paragraph_index, paragraph in enumerate(section.get("paragraphs", [])):
            if isinstance(paragraph, str) and paragraph.strip():
                records.append(
                    {
                        "chunk_id": f"s{section_index:04d}-p{paragraph_index:04d}",
                        "document_id": "own-paper",
                        "text": paragraph,
                    }
                )
    return records


def prepare_paper(paper: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, list[set[str]]], Counter[str]]:
    """Keep a question only when every answerable annotation maps completely.

    Gold strings must equal a unique own-paper paragraph after conservative
    normalization. Caption-only, empty, unmatched, and duplicate-text evidence
    are excluded rather than guessed. Mixed answerability is excluded too.
    """

    candidates = paper_paragraphs(paper)
    paragraph_ids: dict[str, list[str]] = {}
    for item in candidates:
        paragraph_ids.setdefault(normalized_evidence(item["text"]), []).append(item["chunk_id"])
    captions = {
        normalized_evidence(item["caption"])
        for item in paper.get("figures_and_tables", [])
        if isinstance(item, dict) and isinstance(item.get("caption"), str)
    }
    section_headings = {
        normalized_evidence(section["section_name"])
        for section in paper.get("full_text", [])
        if isinstance(section.get("section_name"), str)
    }
    queries: list[dict[str, str]] = []
    gold_by_query: dict[str, list[set[str]]] = {}
    counts: Counter[str] = Counter()
    counts["candidate_paragraphs"] = len(candidates)
    counts["long_paragraphs_over_512_whitespace_tokens"] = sum(
        len(item["text"].split()) > 512 for item in candidates
    )
    counts["figure_table_captions"] = len(paper.get("figures_and_tables", []))
    for qa in paper.get("qas", []):
        counts["questions_total"] += 1
        reasons: set[str] = set()
        annotations = qa.get("answers", [])
        answerable = [item.get("answer", {}) for item in annotations if not item.get("answer", {}).get("unanswerable", False)]
        unanswerable_count = len(annotations) - len(answerable)
        counts["annotations_total"] += len(annotations)
        counts["annotations_answerable"] += len(answerable)
        counts["annotations_unanswerable"] += unanswerable_count
        if not answerable:
            reasons.add("unanswerable_only")
        if answerable and unanswerable_count:
            reasons.add("mixed_answerability")
        if not isinstance(qa.get("question"), str) or not qa["question"].strip():
            reasons.add("empty_question")
        annotation_gold: list[set[str]] = []
        for answer in answerable:
            evidence = answer.get("evidence", [])
            if not isinstance(evidence, list) or not evidence:
                reasons.add("missing_evidence")
                continue
            gold: set[str] = set()
            for raw in evidence:
                counts["evidence_strings_total"] += 1
                if not isinstance(raw, str) or not raw.strip():
                    counts["evidence_strings_empty"] += 1
                    reasons.add("missing_evidence")
                    continue
                key = normalized_evidence(raw)
                matches = paragraph_ids.get(key, [])
                if len(matches) == 1:
                    gold.add(matches[0])
                    counts["evidence_strings_exact_paragraph"] += 1
                elif len(matches) > 1:
                    counts["evidence_strings_ambiguous"] += 1
                    reasons.add("ambiguous_paragraph")
                elif raw.startswith("FLOAT SELECTED:") or key in captions:
                    counts["evidence_strings_figure_table"] += 1
                    reasons.add("figure_table_evidence")
                elif key in section_headings:
                    counts["evidence_strings_section_heading"] += 1
                    reasons.add("section_heading_evidence")
                else:
                    counts["evidence_strings_unmatched"] += 1
                    reasons.add("unmatched_evidence")
            if gold:
                annotation_gold.append(gold)
        if len(annotation_gold) > 1 and any(gold != annotation_gold[0] for gold in annotation_gold[1:]):
            counts["questions_annotator_evidence_disagreement"] += 1
        for reason in reasons:
            counts[f"excluded_reason_{reason}"] += 1
        if reasons or not annotation_gold:
            counts["questions_excluded"] += 1
            continue
        question_id = str(qa["question_id"])
        if question_id in gold_by_query:
            raise ValueError(f"Duplicate question_id within paper: {question_id}")
        queries.append({"query_id": question_id, "text": qa["question"]})
        gold_by_query[question_id] = annotation_gold
        counts["questions_evaluable"] += 1
    return candidates, queries, gold_by_query, counts


def score_rankings(
    rankings: dict[str, list[dict[str, Any]]],
    gold_by_query: dict[str, list[set[str]]],
    *,
    candidate_ids: set[str],
) -> dict[str, Any]:
    """Question macro, with best complete human evidence set as the target."""

    totals = {str(k): {"hit": 0.0, "best_annotation_recall": 0.0, "complete_annotation": 0.0, "mrr": 0.0} for k in CUTOFFS}
    for query_id, annotation_sets in gold_by_query.items():
        ranked_ids = [str(row["chunk_id"]) for row in rankings.get(query_id, [])]
        if len(ranked_ids) != len(set(ranked_ids)) or any(item not in candidate_ids for item in ranked_ids):
            raise ValueError("Ranking contains duplicate or cross-paper paragraph IDs")
        for cutoff in CUTOFFS:
            top = ranked_ids[:cutoff]
            selected = set(top)
            recall = max(len(selected & gold) / len(gold) for gold in annotation_sets)
            first = next((index for index, item in enumerate(top, 1) if any(item in gold for gold in annotation_sets)), None)
            row = totals[str(cutoff)]
            row["hit"] += float(first is not None)
            row["best_annotation_recall"] += recall
            row["complete_annotation"] += float(any(gold <= selected for gold in annotation_sets))
            row["mrr"] += 1.0 / first if first is not None else 0.0
    denominator = len(gold_by_query)
    return {
        cutoff: {key: value / denominator for key, value in values.items()}
        for cutoff, values in totals.items()
    } if denominator else totals


def git_provenance() -> dict[str, Any]:
    """Record Git when available without making the standalone ZIP depend on it."""

    unavailable = {
        "available": False,
        "commit": None,
        "dirty": None,
        "status_sha256": None,
    }
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        )
        if commit.returncode != 0:
            return unavailable
        status = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
        )
        if status.returncode != 0:
            return unavailable
    except OSError:
        return unavailable
    return {
        "available": True,
        "commit": commit.stdout.strip(),
        "dirty": bool(status.stdout),
        "status_sha256": hashlib.sha256(status.stdout.encode("utf-8")).hexdigest(),
    }


def run_benchmark(
    *,
    input_path: Path,
    output_dir: Path,
    seed: int = 20261018,
    max_papers: int = 40,
    dense: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    input_sha = sha256_file(input_path)
    if input_sha != DEV_FILE_SHA256:
        raise ValueError(f"QASPER dev file SHA-256 mismatch: {input_sha}")
    dataset = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(dataset, dict):
        raise ValueError("QASPER dev input must be a paper-ID object")
    selected = select_papers(dataset, seed=seed, max_papers=max_papers)
    encoder = (
        SentenceTransformerEncoder(
            model=E5_MODEL,
            revision=E5_REVISION,
            device="cpu",
            batch_size=16,
            query_prefix="query: ",
            document_prefix="passage: ",
        )
        if dense else None
    )
    summary: Counter[str] = Counter()
    method_totals: dict[str, dict[str, dict[str, float]]] = {}
    selected_ids = []
    for paper_id, paper in selected:
        selected_ids.append(paper_id)
        candidates, queries, gold, paper_counts = prepare_paper(paper)
        summary.update(paper_counts)
        if queries:
            summary["papers_with_evaluable_questions"] += 1
        else:
            continue
        ids = {item["chunk_id"] for item in candidates}
        bm25_rankings = rank_bm25(candidates, queries, top_k=max(CUTOFFS))
        methods = {"bm25": bm25_rankings}
        if encoder is not None:
            dense_rankings = rank_dense(candidates, queries, encoder=encoder, top_k=max(CUTOFFS))
            methods["e5_dense"] = dense_rankings
            methods["bm25_e5_rrf"] = fuse_rrf(
                {"bm25": bm25_rankings, "e5_dense": dense_rankings},
                rrf_k=60,
                top_k=max(CUTOFFS),
            )
        for method, rankings in methods.items():
            scores = score_rankings(rankings, gold, candidate_ids=ids)
            method_rows = method_totals.setdefault(method, {})
            for cutoff, values in scores.items():
                totals = method_rows.setdefault(cutoff, {key: 0.0 for key in values})
                for key, value in values.items():
                    totals[key] += value * len(gold)
    denominator = summary["questions_evaluable"]
    if not denominator:
        raise ValueError("No questions have complete, unambiguous paragraph evidence")
    results = {
        "schema_version": 1,
        "result_classification": "PRELIMINARY_COMPONENT_DIAGNOSTIC",
        "task": "QASPER within-paper LOCAL paragraph evidence retrieval",
        "dataset": "QASPER v0.3 dev",
        "scope": {
            "papers_in_dev": len(dataset),
            "papers_selected": len(selected),
            "selection_seed": seed,
            "selection_rule": "smallest SHA256(seed:paper_id), with paper_id tie break",
            "selected_paper_ids_sha256": hashlib.sha256("\n".join(sorted(selected_ids)).encode("utf-8")).hexdigest(),
            "candidate_scope": "abstract and full_text paragraphs of own paper only; figure/table captions excluded",
            "gold_mapping": "NFKC+casefold+whitespace exact unique paragraph match; all answerable annotations complete",
            "cutoffs": list(CUTOFFS),
        },
        "coverage": dict(sorted(summary.items())),
        "methods": {
            method: {
                "question_count": denominator,
                "macro": {
                    cutoff: {name: value / denominator for name, value in values.items()}
                    for cutoff, values in cutoffs.items()
                },
            }
            for method, cutoffs in sorted(method_totals.items())
        },
        "interpretation": "Paragraph retrieval only. No answer generation, rubric scoring, GRAPH routing, or grading-validity claim.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.json"
    write_json(metrics_path, results)
    source_dir = Path(__file__).parent
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "result_classification": results["result_classification"],
        "governance": {
            "use": "User-requested internal research diagnostic",
            "team_dataset_approval": "NOT_RECORDED",
            "redistribution": "Raw corpus and per-query predictions excluded from output and submission",
            "official_license": "CC BY 4.0",
        },
        "source": {
            "dataset": "QASPER v0.3 dev",
            "version": "0.3",
            "split": "dev",
            "official_dataset_card": "https://huggingface.co/datasets/allenai/qasper",
            "official_archive_url": "https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz",
            "archive_sha256": ARCHIVE_SHA256,
            "extracted_dev_sha256": input_sha,
            "input_path": str(input_path),
        },
        "coverage": dict(sorted(summary.items())),
        "configuration": {
            "seed": seed,
            "max_papers": max_papers,
            "dense_enabled": dense,
            "bm25": {"k1": 1.2, "b": 0.75},
            "rrf_k": 60 if dense else None,
            "dense_model": encoder.metadata if encoder is not None else None,
        },
        "code_sha256": {
            name: sha256_file(path)
            for name, path in {
                "qasper_benchmark": source_dir / "benchmark.py",
                "bm25": source_dir.parent / "offline_retrieval" / "bm25.py",
                "dense": source_dir.parent / "offline_retrieval" / "dense.py",
                "rrf": source_dir.parent / "offline_retrieval" / "rrf.py",
            }.items()
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
        },
        "git": git_provenance(),
        "timing": {"total_wall_seconds": time.perf_counter() - started},
        "artifacts": {"metrics.json": {"sha256": sha256_file(metrics_path)}},
    }
    write_json(output_dir / "run_manifest.json", manifest)
    return results
