"""Compare before/after diagnostic artifacts with matching cases and retrieval."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping


def compare_evaluations(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    if before["pack_sha256"] != after["pack_sha256"] or before["pack_id"] != after["pack_id"]:
        raise ValueError("Before/after must use the same frozen pack")
    if before["profile"] != after["profile"]:
        raise ValueError("Use the same retrieval profile for a verifier comparison")
    configs = [{key: value for key, value in item["configuration"].items() if key != "semantic_verification"}
               for item in (before, after)]
    if configs[0] != configs[1]:
        raise ValueError("Retrieval configuration changed")
    old = {row["case_id"]: row for row in before["cases"]}
    new = {row["case_id"]: row for row in after["cases"]}
    if set(old) != set(new) or len(old) != len(before["cases"]) or len(new) != len(after["cases"]):
        raise ValueError("Before/after case identities differ or are duplicated")
    transitions: Counter[str] = Counter()
    groups: dict[str, dict[str, int]] = {}
    for identifier, first in old.items():
        last = new[identifier]
        task = first["task"]
        expected = "expected_relation" if task == "SIMILARITY" else "expected_outcome"
        correctness = "relation_correct" if task == "SIMILARITY" else "outcome_correct"
        if first[expected] != last[expected] or first["task"] != last["task"]:
            raise ValueError("Before/after expectations or task changed")
        group = f"{task}/{first['language']}/{first['category']}"
        values = groups.setdefault(group, {"cases": 0, "before_correct": 0, "after_correct": 0})
        values["cases"] += 1
        values["before_correct"] += int(first[correctness])
        values["after_correct"] += int(last[correctness])
        transitions[f"{task}:{'correct' if first[correctness] else 'incorrect'}->{'correct' if last[correctness] else 'incorrect'}"] += 1
    return {"schema_version": 1, "pack_id": before["pack_id"], "pack_sha256": before["pack_sha256"],
            "split": before["split"], "profile": before["profile"],
            "independent_human_gold": False, "label_status": "ASSISTANT_AUTHORED_EXPECTATIONS",
            "before": before["summary"], "after": after["summary"],
            "transitions": dict(sorted(transitions.items())), "groups": dict(sorted(groups.items())),
            "claim_limit": "Small assistant-authored development diagnostic, not independent human gold or PAN TEST0."}


def render_comparison(result: Mapping[str, Any]) -> str:
    lines = ["# Output-quality before/after diagnostic", "",
             f"Pack: `{result['pack_id']}`; split: `{result['split']}`; retrieval: `{result['profile']}`.", "",
             "Labels are assistant-authored expectations, not independently annotated human gold.", "",
             "| Observation | Before | After |", "|---|---:|---:|"]
    for task, field, label in [
        ("similarity", "relation_correct", "P1 relation agreement"),
        ("similarity", "decided_cases", "P1 decided cases"),
        ("similarity", "positive_target_retrieved_at_1", "P1 positive target retrieved at1"),
        ("similarity", "negative_false_reuse_labels", "P1 negative false reuse labels"),
        ("similarity", "negative_cases_any_source_false_reuse", "P1 negative cases with false reuse from any source"),
        ("similarity", "non_target_false_reuse_labels", "P1 false reuse labels on distractor sources"),
        ("similarity", "negative_false_exact_document_coverage", "P1 negative false exact coverage"),
        ("assessment", "outcome_correct", "P2 outcome agreement"),
        ("assessment", "false_met", "P2 false MET"),
        ("assessment", "unknown_kept_unknown", "P2 expected unknown retained")]:
        lines.append(f"| {label} | {result['before'][task][field]} | {result['after'][task][field]} |")
    lines += ["", "Missing predictions and abstentions are not converted to correct NONE labels.", "",
              "| Group | Cases | Before correct | After correct |", "|---|---:|---:|---:|"]
    for name, values in result["groups"].items():
        lines.append(f"| {name} | {values['cases']} | {values['before_correct']} | {values['after_correct']} |")
    lines += ["", result["claim_limit"], ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_evaluations(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_comparison(result), encoding="utf-8")
    args.output.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
