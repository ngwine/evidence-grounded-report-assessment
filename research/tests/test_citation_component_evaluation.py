"""Verify component-cohort input controls, not model quality."""

from copy import deepcopy
import hashlib
import json

import pytest

from research.output_quality.citation_component import (
    compare_component, evaluate_component, validate_component_pack,
)


def fixture_pack():
    report = "The panel broadcasts an alarm if its temperature crosses the maximum [4]."
    source = "An alarm is broadcast by the panel when its temperature exceeds the maximum [7]."
    hints = {"report": [{"start": report.index("[4]"), "end": report.index("[4]") + 3}],
             "source": [{"start": source.index("[7]"), "end": source.index("[7]") + 3}]}
    proofs = [{"leg": leg, **span, "marker": text[span["start"]:span["end"]],
               "reference_id": f"fictional-{leg}", "bibliography_entry_text": "Fictional authored reference.",
               "resolution_status": "UNIQUELY_LINKED_BIBLIOGRAPHY"}
              for leg, text in (("report", report), ("source", source)) for span in hints[leg]]
    return {"schema_version": 1, "pack_id": "software-fixture", "classification": "SYNTHETIC_AUTHORED_COMPONENT_DIAGNOSTIC",
            "label_status": "ASSISTANT_AUTHORED_EXPECTATIONS", "independent_human_gold": False,
            "cases": [{"case_id": "fixture-one", "language": "en", "category": "linked-reference",
                       "report_text": report, "source_text": source, "number_exclusion_ranges": hints,
                       "exclusion_proofs": proofs, "expected_relation": "PARAPHRASE",
                       "expected_semantic_relation": "PARAPHRASE"}]}


@pytest.mark.parametrize("mutation", ["missing_proof", "wrong_marker", "out_of_range", "fake_gold"])
def test_component_pack_rejects_unproven_or_invalid_exclusions(mutation):
    pack = fixture_pack()
    if mutation == "missing_proof":
        pack["cases"][0]["exclusion_proofs"].pop()
    elif mutation == "wrong_marker":
        pack["cases"][0]["number_exclusion_ranges"]["report"][0] = {"start": 0, "end": 3}
    elif mutation == "out_of_range":
        pack["cases"][0]["number_exclusion_ranges"]["report"][0]["end"] = 999
    else:
        pack["independent_human_gold"] = True
    with pytest.raises(ValueError):
        validate_component_pack(pack)


def test_component_comparison_only_changes_explicit_guard_hints(tmp_path):
    pack = fixture_pack()
    validate_component_pack(pack)
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    original = pack["cases"][0]

    class SoftwareOnlyVerifier:
        metadata = {"backend": "injected_test", "threshold": 0.65}

        def verify_pairs(self, pairs, **kwargs):
            assert pairs == [(original["report_text"], original["source_text"])]
            if kwargs:
                assert kwargs["number_exclusion_ranges"] == [original["number_exclusion_ranges"]]
            return [{"similarity_type": "PARAPHRASE" if kwargs else None,
                     "decision": "PARAPHRASE_SUPPORTED" if kwargs else "ABSTAIN"}]

    before = evaluate_component(path, tmp_path / "before", SoftwareOnlyVerifier(),
                                apply_exclusion_hints=False, expected_sha256=digest)
    after = evaluate_component(path, tmp_path / "after", SoftwareOnlyVerifier(),
                               apply_exclusion_hints=True, expected_sha256=digest)
    compared = compare_component(before, after)
    assert compared["same_input_strings"] and compared["same_model_and_policy"]
    assert compared["before"]["linked_positives_recognized"] == 0
    assert compared["after"]["linked_positives_recognized"] == 1
    changed = deepcopy(after)
    changed["verifier_metadata"]["threshold"] = 0.5
    with pytest.raises(ValueError, match="hold model and policy fixed"):
        compare_component(before, changed)
    changed = deepcopy(after)
    changed["cases"][0]["input_text_sha256"]["report"] = "changed"
    with pytest.raises(ValueError, match="input strings"):
        compare_component(before, changed)


def test_component_checksum_guard_runs_before_model(tmp_path):
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(fixture_pack()))
    with pytest.raises(ValueError, match="checksum mismatch"):
        evaluate_component(path, tmp_path / "out", object(), apply_exclusion_hints=False,
                           expected_sha256="0" * 64)
    assert not (tmp_path / "out").exists()
