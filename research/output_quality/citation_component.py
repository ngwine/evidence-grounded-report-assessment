"""Frozen synthetic component comparison for bibliography-linked numeric guards.

This evaluates the semantic component only. It does not validate an app's
citation resolver, source retrieval, document coverage, or independent gold.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


_MARKER = re.compile(r"\[[0-9]+\]\Z")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_component_pack(pack: Mapping[str, Any]) -> None:
    """Check explicit hint evidence; never infer citation status from brackets."""
    if pack.get("schema_version") != 1 or pack.get("classification") != "SYNTHETIC_AUTHORED_COMPONENT_DIAGNOSTIC":
        raise ValueError("Unsupported citation-component pack")
    if pack.get("label_status") != "ASSISTANT_AUTHORED_EXPECTATIONS" or pack.get("independent_human_gold") is not False:
        raise ValueError("Component expectations cannot claim independent human gold")
    cases = pack.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Nonempty component cases required")
    identifiers: set[str] = set()
    for case in cases:
        identifier = case.get("case_id")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("Unique component case IDs required")
        identifiers.add(identifier)
        if case.get("expected_relation") not in {"PARAPHRASE", "NONE", None}:
            raise ValueError("Invalid expected component relation")
        if case.get("expected_semantic_relation") not in {"PARAPHRASE", "NONE"}:
            raise ValueError("Semantic expectation must remain separate from policy abstention")
        hints = case.get("number_exclusion_ranges")
        if not isinstance(hints, Mapping) or set(hints) != {"report", "source"}:
            raise ValueError("Both explicit hint legs are required")
        expected_proofs: set[tuple[str, int, int]] = set()
        for leg in ("report", "source"):
            text = case.get(f"{leg}_text")
            if not isinstance(text, str) or not text.strip() or not isinstance(hints[leg], list):
                raise ValueError("Component inputs require nonempty text and explicit ranges")
            previous_end = -1
            for span in hints[leg]:
                start, end = span.get("start"), span.get("end")
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text) or start < previous_end:
                    raise ValueError("Invalid or overlapping citation-component range")
                if _MARKER.fullmatch(text[start:end]) is None:
                    raise ValueError("Only explicit ASCII bibliography markers may be excluded")
                expected_proofs.add((leg, start, end))
                previous_end = end
        proofs = case.get("exclusion_proofs")
        if not isinstance(proofs, list):
            raise ValueError("Explicit bibliography proofs required")
        actual_proofs: set[tuple[str, int, int]] = set()
        for proof in proofs:
            coordinate = proof.get("leg"), proof.get("start"), proof.get("end")
            if coordinate not in expected_proofs or coordinate in actual_proofs:
                raise ValueError("Unmatched or duplicate bibliography proof")
            leg, start, end = coordinate
            if (proof.get("resolution_status") != "UNIQUELY_LINKED_BIBLIOGRAPHY"
                    or not proof.get("reference_id") or not proof.get("bibliography_entry_text")
                    or proof.get("marker") != case[f"{leg}_text"][start:end]):
                raise ValueError("Bibliography proof is incomplete")
            actual_proofs.add(coordinate)
        if actual_proofs != expected_proofs:
            raise ValueError("Every excluded marker needs its own explicit proof")


def evaluate_component(
    pack_path: Path, output_dir: Path, verifier: Any, *,
    apply_exclusion_hints: bool, expected_sha256: str,
) -> dict[str, Any]:
    """Score exactly the frozen strings; only the numeric-guard hints vary."""
    actual_hash = _sha(pack_path.read_bytes())
    if actual_hash != expected_sha256:
        raise ValueError("Frozen citation-component pack checksum mismatch")
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    validate_component_pack(pack)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Use a fresh component output directory")
    pairs = [(case["report_text"], case["source_text"]) for case in pack["cases"]]
    kwargs = {"number_exclusion_ranges": [deepcopy(case["number_exclusion_ranges"]) for case in pack["cases"]]} if apply_exclusion_hints else {}
    results = verifier.verify_pairs(pairs, **kwargs)
    if len(results) != len(pairs):
        raise ValueError("Component verifier returned the wrong number of results")
    rows: list[dict[str, Any]] = []
    for case, result, pair in zip(pack["cases"], results, pairs, strict=True):
        predicted = result.get("similarity_type")
        if predicted not in {"PARAPHRASE", "NONE", None}:
            raise ValueError("Component verifier returned an invalid relation")
        text_hashes = {leg: _sha(text.encode("utf-8")) for leg, text in zip(("report", "source"), pair, strict=True)}
        for leg, digest in text_hashes.items():
            if result.get(f"{leg}_text_sha256", digest) != digest:
                raise ValueError("Component scorer did not preserve the frozen input string")
        linked = any(case["number_exclusion_ranges"].values())
        rows.append({"case_id": case["case_id"], "language": case["language"], "category": case["category"],
                     "expected_relation": case["expected_relation"], "expected_semantic_relation": case["expected_semantic_relation"],
                     "predicted_relation": predicted, "expected_decision_matches": predicted == case["expected_relation"],
                     "has_linked_citation_hints": linked, "input_text_sha256": text_hashes,
                     "number_exclusion_ranges": deepcopy(case["number_exclusion_ranges"]), "prediction": result})
    positives = [row for row in rows if row["expected_relation"] == "PARAPHRASE"]
    semantic_negatives = [row for row in rows if row["expected_semantic_relation"] == "NONE"]
    untrusted = [row for row in rows if not row["has_linked_citation_hints"] and row["expected_relation"] is None]
    summary = {"cases": len(rows), "expected_decision_matches": sum(row["expected_decision_matches"] for row in rows),
               "linked_positive_cases": len(positives),
               "linked_positives_recognized": sum(row["predicted_relation"] == "PARAPHRASE" for row in positives),
               "semantic_negative_cases": len(semantic_negatives),
               "negative_false_equivalence": sum(row["predicted_relation"] == "PARAPHRASE" for row in semantic_negatives),
               "untrusted_cases": len(untrusted),
               "untrusted_correctly_abstained": sum(row["predicted_relation"] is None for row in untrusted),
               "untrusted_false_equivalence": sum(row["predicted_relation"] == "PARAPHRASE" for row in untrusted),
               "abstained": sum(row["predicted_relation"] is None for row in rows)}
    module = sys.modules.get(type(verifier).__module__)
    module_file = getattr(module, "__file__", None)
    output = {"schema_version": 1, "pack_id": pack["pack_id"], "pack_sha256": actual_hash,
              "created_at": datetime.now(timezone.utc).isoformat(), "apply_exclusion_hints": apply_exclusion_hints,
              "independent_human_gold": False, "label_status": pack["label_status"],
              "semantic_module_sha256": _sha(Path(module_file).read_bytes()) if module_file else None,
              "verifier_metadata": deepcopy(getattr(verifier, "metadata", {})),
              "summary": summary, "cases": rows,
              "claim_limit": "Synthetic semantic-component diagnostic only; does not validate the real app citation resolver, whole-report plagiarism, or independent human gold."}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def compare_component(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    if before["pack_sha256"] != after["pack_sha256"]:
        raise ValueError("Component comparison needs the same frozen input pack")
    if before["verifier_metadata"] != after["verifier_metadata"]:
        raise ValueError("Component comparison must hold model and policy fixed")
    old = {row["case_id"]: row for row in before["cases"]}
    new = {row["case_id"]: row for row in after["cases"]}
    if set(old) != set(new):
        raise ValueError("Component comparison case identities differ")
    for identifier, first in old.items():
        last = new[identifier]
        if any(first[key] != last[key] for key in ("input_text_sha256", "expected_relation", "expected_semantic_relation", "number_exclusion_ranges")):
            raise ValueError("Component comparison input strings, hints or expectations changed")
    return {"schema_version": 1, "pack_id": before["pack_id"], "pack_sha256": before["pack_sha256"],
            "independent_human_gold": False, "before": before["summary"], "after": after["summary"],
            "same_model_and_policy": True, "same_input_strings": True,
            "before_hints_enabled": before["apply_exclusion_hints"], "after_hints_enabled": after["apply_exclusion_hints"],
            "claim_limit": after["claim_limit"]}
