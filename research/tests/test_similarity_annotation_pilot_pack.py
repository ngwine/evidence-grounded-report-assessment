"""Regression tests for the private Pipeline 1 annotation pack."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from research.similarity_annotation import pilot_pack


def _passage(chunk_id: str, document_id: str, text: str, page: int) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "normalized_start": 0,
        "normalized_end": len(text),
        "raw_start": 0,
        "raw_end": len(text),
        "text": text,
        "source_spans": [
            {
                "element_key": f"element-{chunk_id}",
                "chunk_normalized_char_start": 0,
                "chunk_normalized_char_end": len(text),
                "chunk_raw_char_start": 0,
                "chunk_raw_char_end": len(text),
                "element_normalized_char_start": 0,
                "element_normalized_char_end": len(text),
                "element_raw_char_start": 0,
                "element_raw_char_end": len(text),
                "matched_chunk_normalized_start": 0,
                "matched_chunk_normalized_end": len(text),
                "matched_chunk_raw_start": 0,
                "matched_chunk_raw_end": len(text),
                "matched_element_raw_start": 0,
                "matched_element_raw_end": len(text),
                "source_name": "must-not-copy-this.pdf",
                "locator": {
                    "source_kind": "pdf",
                    "block_id": f"block-{chunk_id}",
                    "page_index": page - 1,
                    "page_number": page,
                    "page_label": str(page),
                    "raw_char_start": 0,
                    "raw_char_end": len(text),
                    "section_path": ["Private Person"],
                },
            }
        ],
    }


def _inputs(tmp_path: Path, *, wrong_hash: bool = False) -> tuple[Path, Path]:
    reports = {
        "abstract": ("Abstract: Sudoku constraint encoding and search methods.", 1),
        "page-one-email": ("Private Person, person@example.test", 1),
        "ordinary-a": ("Constraint programming represents Sudoku with cell domains.", 2),
        "ordinary-b": ("The solver checks each row, column, and box.", 3),
        "contribution-tail": (
            "Sudoku requires exactly one value per cell. V. C ONTRIBUTIONS Private Person",
            4,
        ),
    }
    matches = []
    for report_id, (report_text, page) in reports.items():
        for rank in range(1, 4):
            source_id = f"source-{rank}"
            source_text = f"Source document {rank} gives a Sudoku constraint example."
            matches.append(
                {
                    "report_chunk_id": report_id,
                    "source_chunk_id": source_id,
                    "source_document_id": f"document-{rank}",
                    "source_name": f"Source{rank}.pdf",
                    "rank": rank,
                    "selected_for_manual_review": (
                        (report_id == "abstract" and rank == 1)
                        or (report_id == "contribution-tail" and rank == 2)
                    ),
                    "selected_for_document_coverage": False,
                    "similarity_type": None,
                    "provisional_similarity_type": "PARAPHRASE",
                    "classification_status": "PROVISIONAL_REVIEW_REQUIRED",
                    "heuristic_score": 0.42,
                    "classification_reasons": ["test-only"],
                    "features": {"token_jaccard": 0.12},
                    "alignment": {
                        "kind": "PASSAGE_LEVEL",
                        "report": _passage(report_id, "report-document", report_text, page),
                        "source": _passage(source_id, f"document-{rank}", source_text, rank),
                    },
                }
            )
    report_path = tmp_path / "similarity-report.json"
    report_path.write_text(
        json.dumps({"pipeline": "similarity-core-mvp-v0", "matches": matches}),
        encoding="utf-8",
    )
    report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "run-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "fixture-run",
                "outputs": {
                    "similarity_report": {
                        "sha256": "0" * 64 if wrong_hash else report_hash
                    }
                },
                "inputs": {
                    "report": {"sha256": "a" * 64},
                    "sources": [
                        {
                            "document_id": f"document-{rank}",
                            "source_name": f"Source{rank}.pdf",
                            "sha256": str(rank) * 64,
                        }
                        for rank in range(1, 4)
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return report_path, manifest_path


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_pack_is_blinded_private_deterministic_and_preserves_original_offsets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    var_root = tmp_path / "var"
    monkeypatch.setattr(pilot_pack, "_VAR_ROOT", var_root)
    report_path, manifest_path = _inputs(tmp_path)
    kwargs = {
        "similarity_report_path": report_path,
        "run_manifest_path": manifest_path,
        "target_pairs": 9,
        "safe_page_one_chunk_ids": ["abstract"],
    }
    first_dir, second_dir = var_root / "first", var_root / "second"
    first = pilot_pack.build_pilot_pack(output_dir=first_dir, **kwargs)
    second = pilot_pack.build_pilot_pack(output_dir=second_dir, **kwargs)

    assert first == second
    assert first["selected_pairs"] == 9
    assert first["selected_manual_review_pairs"] == 2
    assert first["selected_source_document_ids"] == [
        "document-1", "document-2", "document-3"
    ]
    assert first["governance"]["status"] == "PENDING"
    pairs = _jsonl(first_dir / "pairs.jsonl")
    predictions = _jsonl(first_dir / "model_predictions.jsonl")
    quy = _csv(first_dir / "annotations_quy.csv")
    yen = _csv(first_dir / "annotations_yen.csv")
    adjudication = _csv(first_dir / "adjudication.csv")
    assert len(pairs) == len(predictions) == len(quy) == len(yen) == len(adjudication) == 9
    assert len({row["pair_id"] for row in pairs}) == 9
    assert quy == yen
    assert {row["report_chunk_id"] for row in quy} == {
        "abstract", "ordinary-a", "ordinary-b", "contribution-tail"
    }
    assert {row["source_name"] for row in quy} == {
        "Source1.pdf", "Source2.pdf", "Source3.pdf"
    }
    assert all(
        not any(row[field] for field in (
            "label", "report_evidence_quote", "source_evidence_quote",
            "quote_or_citation", "confidence", "rationale",
        ))
        for row in quy
    )
    assert all(row["final_label"] == "" for row in adjudication)
    assert all(row["decision_by"] == "" and row["decided_at"] == "" for row in adjudication)
    assert all("heuristic_score" not in row for row in quy)
    assert all("heuristic_score" in row for row in predictions)
    tail = next(row for row in pairs if row["report_provenance"]["chunk_id"] == "contribution-tail")
    assert tail["report_text"] == "Sudoku requires exactly one value per cell."
    provenance = tail["report_provenance"]
    assert provenance["excerpt_policy"] == "TRIMMED_BEFORE_CONTRIBUTIONS"
    assert provenance["original_normalized_end"] > provenance["excerpt_normalized_end"]
    assert provenance["source_spans"][0]["locator"]["page_number"] == 4
    assert "source_name" not in provenance["source_spans"][0]
    assert "section_path" not in provenance["source_spans"][0]["locator"]
    assert "Private Person" not in (first_dir / "pairs.jsonl").read_text(encoding="utf-8")
    assert "person@example.test" not in (first_dir / "annotations_quy.csv").read_text(encoding="utf-8")
    assert all(path.stat().st_mode & 0o077 == 0 for path in first_dir.iterdir())
    for filename, info in first["artifacts"].items():
        assert hashlib.sha256((first_dir / filename).read_bytes()).hexdigest() == info["sha256"]


def test_pack_rejects_unignored_output_and_mismatched_run_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    var_root = tmp_path / "var"
    monkeypatch.setattr(pilot_pack, "_VAR_ROOT", var_root)
    report_path, manifest_path = _inputs(tmp_path, wrong_hash=True)
    with pytest.raises(ValueError, match="under the ignored repository var"):
        pilot_pack.build_pilot_pack(
            similarity_report_path=report_path,
            run_manifest_path=manifest_path,
            output_dir=tmp_path / "unsafe-pack",
            target_pairs=2,
        )
    with pytest.raises(ValueError, match="hash does not match"):
        pilot_pack.build_pilot_pack(
            similarity_report_path=report_path,
            run_manifest_path=manifest_path,
            output_dir=var_root / "bad-hash",
            target_pairs=2,
        )
    assert not (var_root / "bad-hash").exists()


def test_spreadsheet_text_cannot_start_a_formula() -> None:
    assert pilot_pack._spreadsheet_safe_text("=2+2") == "'=2+2"
    assert pilot_pack._spreadsheet_safe_text("  +SUM(A1)") == "'  +SUM(A1)"
    assert pilot_pack._spreadsheet_safe_text("ordinary text") == "ordinary text"
