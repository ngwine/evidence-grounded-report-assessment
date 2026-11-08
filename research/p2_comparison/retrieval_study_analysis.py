"""Audit DEV retrieval inputs and exact proof locations, separately from meaning."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path
import random

from research.gold_annotation.assessment_evidence import compare_evidence, summarize_comparisons
from research.p2_comparison import retrieval_study as study
from research.p2_comparison import runner as base
from research.p2_comparison.single_reference_evidence import audit_item


def paired_report_interval(references, first, second, *, draws=5000, seed=20261108):
    """Descriptive, post-hoc paired report bootstrap, not annotation uncertainty."""
    if type(draws) is not int or draws < 2:
        raise ValueError("At least two bootstrap draws are required")
    ref = {row["item_id"]: row for row in references}
    left = {row["item_id"]: row for row in first}
    right = {row["item_id"]: row for row in second}
    if (not ref or len(ref) != len(references) or len(left) != len(first) or len(right) != len(second)
            or set(ref) != set(left) or set(ref) != set(right)):
        raise ValueError("Paired bootstrap needs all items once per method")
    grouped = {}
    for key, expected in ref.items():
        if left[key]["case_id"] != expected["case_id"] or right[key]["case_id"] != expected["case_id"]:
            raise ValueError("Paired bootstrap report identity differs")
        a = left[key]["accepted_label"] == expected["label"]
        b = right[key]["accepted_label"] == expected["label"]
        grouped.setdefault(expected["case_id"], []).append(int(b) - int(a))
    deltas = [sum(values) / len(values) for _, values in sorted(grouped.items())]
    rng = random.Random(seed)
    samples = sorted(sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(draws))
    def quantile(q):
        position = (len(samples) - 1) * q
        lower = int(position)
        upper = min(lower + 1, len(samples) - 1)
        return samples[lower] + (samples[upper] - samples[lower]) * (position - lower)
    return {"unit": "REPORT", "reports": len(deltas), "draws": draws, "seed": seed,
        "second_minus_first_report_mean_agreement": sum(deltas) / len(deltas),
        "percentile_95_interval": [quantile(0.025), quantile(0.975)],
        "quantile": "type-7", "post_hoc_descriptive_dev_analysis": True,
        "confirmatory_significance_claim": False,
        "limitations": "Conditional on the inspected reports and fixed single reference; does not capture annotation, cohort-construction or method-selection uncertainty."}


def retrieved_location_record(item, context):
    """Project retrieved raw ranges to the captured body without fake absence."""
    paragraphs = sorted(context["paragraphs"], key=lambda p: p["start"])
    starts = [p["start"] for p in paragraphs]
    spans = {}
    for entry in item["evidence_pack"]:
        chunk = entry["chunk"]
        if entry["record"]["source_spans"] != chunk["source_spans"]:
            raise ValueError("Retrieved source map differs from evidence record")
        for source in chunk["source_spans"]:
            offset = source["locator"]["document_raw_char_start"]
            left, right = offset + source["element_raw_char_start"], offset + source["element_raw_char_end"]
            index = bisect_right(starts, left) - 1
            paragraph = paragraphs[index] if index >= 0 else None
            if paragraph is None or not paragraph["start"] <= left < right <= paragraph["end"]:
                raise ValueError("Retrieved location is outside its captured paragraph")
            quote = context["report_text"][left:right]
            if not quote.strip():
                raise ValueError("Retrieved location has no source text")
            spans[(left, right)] = {"paragraph_id": paragraph["paragraph_id"],
                "start": left, "end": right, "quote": quote}
    if not spans:
        return None
    return {"schema_version": 1, "kind": "SPAN_SET",
        **{key: context[key] for key in ("report_id", "report_version", "body_sha256")},
        "spans": list(spans.values())}


def analyze(*, prepared_dir: Path, run_dir: Path, source_prepared_dir: Path, output_dir: Path):
    prepared = Path(prepared_dir).resolve(strict=True)
    source = Path(source_prepared_dir).resolve(strict=True)
    run = Path(run_dir).resolve(strict=True)
    manifest = study._validated_preparation(prepared)
    study._checked_source(source)
    if base._sha(source / "preparation-manifest.json") != manifest["source_preparation_sha256"]:
        raise ValueError("Original source preparation differs from this DEV study")
    identity = base._read_json(run / "execution-identity.json")
    if identity["preparation_manifest_sha256"] != base._sha(prepared / "preparation-manifest.json"):
        raise ValueError("Run belongs to another preparation")
    predictions = base._read_json(run / "all-methods-predictions.json")["methods"]
    references = base._read_json(prepared / "reference.json")
    refs = {r["item_id"]: r for r in references["rows"]}
    expected = set(refs)
    methods, audits = {}, {}
    for method in study.METHODS:
        rows = predictions[method]
        if len(rows) != len(expected) or {row["item_id"] for row in rows} != expected:
            raise ValueError("Incomplete or duplicate method results")
        items, retrieval_comparisons, proof_comparisons = [], [], []
        count = Counter()
        for row in rows:
            case = row["case_id"]
            ref = refs[row["item_id"]]
            context = base._read_json(source / "cases" / case / "reference-context.json")
            if row["metadata"] != ref["metadata"] or context["body_sha256"] != ref["metadata"]["body_sha256"]:
                raise ValueError("Prediction and reference identity differ")
            item = next(item for item in base._read_json(prepared / "cases" / case / (method + ".json"))["items"]
                        if item["checklist"]["checklist_id"] == row["checklist_id"])
            if row["method_pack_sha256"] != item["evidence_pack_sha256"]:
                raise ValueError("Prediction retrieval pack changed")
            audit = audit_item(row, ref, context, item)
            if audit["issues"]:
                raise ValueError("New prediction proof geometry failed: " + json.dumps(audit["issues"]))
            retrieval = compare_evidence(retrieved_location_record(item, context), ref["evidence"], context)
            retrieval_comparisons.append(retrieval)
            proof_comparisons.append({"status": "COMPARED", "span_evidence": audit["location_overlap"],
                                      "document_absence": audit["document_absence"]})
            count["proofs"] += audit["proof_count"]
            count["source_bound_proofs"] += audit["source_bound_proof_count"]
            count["retrieved_chunks"] += len(item["evidence_pack"])
            count["retrieved_chars"] += sum(len(entry["chunk"]["normalized_text"]) for entry in item["evidence_pack"])
            count["model_calls"] += row["model_calls_observed"] or 0
            count["prompt_tokens_known"] += row["token_usage"].get("prompt_tokens_known", 0) or 0
            count["output_tokens_known"] += row["token_usage"].get("generated_tokens_known", 0) or 0
            count["items_with_complete_token_telemetry"] += row["token_usage"].get("telemetry_complete") is True
            items.append({"item_id": row["item_id"], "case_id": case, "audit": audit, "retrieval_location": retrieval})
        retrieval_summary = summarize_comparisons(retrieval_comparisons)
        proof_summary = summarize_comparisons(proof_comparisons)
        methods[method] = {"items": len(rows), **dict(count),
            "retrieval_selected_reference_location_overlap": retrieval_summary,
            "proof_selected_reference_location_overlap": proof_summary,
            "mean_retrieved_chunks_per_checklist": count["retrieved_chunks"] / len(rows),
            "verification_elapsed_seconds_sum": sum(row["elapsed_seconds"] for row in rows),
            "semantic_support_rate": None, "human_semantic_review_complete": False}
        audits[method] = items
    result = {"schema_version": 1, "design": manifest["design"], "status": "DEV_GEOMETRY_AND_RETRIEVAL_AUDITED",
        "reports": len(manifest["cases"]), "items_per_method": len(refs), "methods": methods,
        "source_bound_does_not_certify_semantic_support": True,
        "teacher_score_agreement_evaluated": False, "independent_holdout_claim": False,
        "unavailable_methods": manifest["unavailable_methods"],
        "location_metric_limit": "Character overlap measures coverage of one annotator's selected ranges, not exhaustive relevance or semantic evidence precision. Full-report input is expected to have high reference coverage.",
        "paired_report_bootstrap_local_minus_no_retrieval": paired_report_interval(
            references["rows"], predictions["no-retrieval"], predictions["local-bm25"]),
        "performance_limit": "One DEV run, uncontrolled warm/cache effects; elapsed totals are not a latency comparison.",
        "input_receipts": {"preparation": base._sha(prepared / "preparation-manifest.json"),
            "predictions": base._sha(run / "all-methods-predictions.json"),
            "references": base._sha(prepared / "reference.json"),
            "source_preparation": base._sha(source / "preparation-manifest.json")},
        "analysis_code_sha256": base._sha(Path(__file__))}
    out = base._private_output(Path(output_dir))
    base._write(out / "evidence-and-retrieval-audit.json", result)
    base._write(out / "item-proof-audits.json", audits)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--source-prepared-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    result = analyze(**vars(parser.parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
