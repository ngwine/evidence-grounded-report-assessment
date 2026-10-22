"""Conservative citation marker ↔ bibliography candidate provenance tests."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.kltn_ai.integrations.indexing.chunking import chunk_elements  # noqa: E402
from src.kltn_ai.integrations.parsing.citation_markers import (  # noqa: E402
    extract_citation_candidates,
)
from src.kltn_ai.integrations.parsing.docx_parser import extract_docx_elements  # noqa: E402
from src.kltn_ai.integrations.parsing.text_normalization import (  # noqa: E402
    normalize_with_mapping,
)


def _element(raw: str, key: str, *, path: list[str], page: int = 0) -> dict:
    normalized = normalize_with_mapping(raw)
    return {
        "schema_version": 2,
        "document_version_id": "version-test-1",
        "generation_key": "parser-generation-test-1",
        "element_key": key,
        "type": "paragraph",
        "raw_text": raw,
        "normalized_text": normalized.text,
        "normalization_map": normalized.normalization_map,
        "structure_path": path,
        "locator": {
            "locator_version": 1,
            "source_kind": "pdf",
            "offset_convention": "half_open",
            "page_index": page,
            "page_label": str(page + 1),
            "bbox": [1, 2, 3, 4],
            "block_id": key,
            "section_path": path,
        },
    }


def _chunks(*elements: dict) -> list[dict]:
    return chunk_elements(elements, max_tokens=400, min_tokens=0)


def _by_text(items: list[dict], text: str) -> dict:
    return next(item for item in items if item["normalized_text"] == text)


def test_numeric_and_author_year_candidates_keep_exact_parser_spans():
    report = (
        "Kết quả trong [1, 2–3] và (Oﬃce, 2020) cần kiểm chứng. "
        "Một đoạn khác nhắc Smith (2021)."
    )
    elements = [
        _element(report, "body", path=["Nội dung"], page=1),
        _element("[1] A source.", "ref1", path=["TÀI LIỆU THAM KHẢO"], page=2),
        _element("[2] B source.", "ref2", path=["TÀI LIỆU THAM KHẢO"], page=2),
        _element("[3] Office, J. (2020). C source.", "ref3", path=["TÀI LIỆU THAM KHẢO"], page=3),
        _element("Smith, A. (2021). D source.", "ref4", path=["TÀI LIỆU THAM KHẢO"], page=3),
    ]
    output = extract_citation_candidates(_chunks(*elements))
    assert len(output["markers"]) == 3
    assert len(output["bibliography_entries"]) == 4

    numeric = _by_text(output["markers"], "[1, 2–3]")
    assert numeric["keys"] == ["numeric:1", "numeric:2", "numeric:3"]
    assert numeric["link_status"] == "CANDIDATE_LINK"
    assert len(numeric["candidate_entry_ids"]) == 3
    assert numeric["verification_status"] == "UNKNOWN"
    assert numeric["span"]["element_key"] == "body"
    assert numeric["span"]["locator"]["page_index"] == 1
    assert numeric["span"]["locator"]["bbox"] == [1, 2, 3, 4]
    raw_start = numeric["span"]["element_raw_char_start"]
    raw_end = numeric["span"]["element_raw_char_end"]
    assert report[raw_start:raw_end] == numeric["raw_text"] == "[1, 2–3]"

    unicode_citation = _by_text(output["markers"], "(Office, 2020)")
    assert unicode_citation["raw_text"] == "(Oﬃce, 2020)"
    assert unicode_citation["link_status"] == "CANDIDATE_LINK"
    assert unicode_citation["keys"] == ["author-year:office:2020"]
    raw_start = unicode_citation["span"]["element_raw_char_start"]
    raw_end = unicode_citation["span"]["element_raw_char_end"]
    assert report[raw_start:raw_end] == "(Oﬃce, 2020)"

    narrative = _by_text(output["markers"], "Smith (2021)")
    assert narrative["link_status"] == "CANDIDATE_LINK"
    assert narrative["span"]["element_key"] == "body"
    assert all(entry["verification_status"] == "UNKNOWN" for entry in output["bibliography_entries"])


def test_unknown_duplicate_and_unsupported_keys_do_not_become_verified():
    elements = [
        _element("Xem [1], [9], [1-], [2-60] và (Smith, 2020).", "body", path=["Nội dung"]),
        _element("[1] Smith, J. (2020). First.", "ref1", path=["References"]),
        _element("[1] Smith, A. (2020). Duplicate.", "ref2", path=["References"]),
    ]
    result = extract_citation_candidates(_chunks(*elements))
    markers = result["markers"]
    assert _by_text(markers, "[1]")["link_status"] == "UNRESOLVED_AMBIGUOUS"
    assert len(_by_text(markers, "[1]")["ambiguous_entry_ids"]) == 2
    assert _by_text(markers, "[9]")["link_status"] == "UNRESOLVED_NOT_FOUND"
    assert _by_text(markers, "[1-]")["link_status"] == "UNRESOLVED_UNSUPPORTED_FORMAT"
    assert _by_text(markers, "[2-60]")["link_status"] == "UNRESOLVED_UNSUPPORTED_FORMAT"
    assert _by_text(markers, "(Smith, 2020)")["link_status"] == "UNRESOLVED_AMBIGUOUS"
    assert all(item["verification_status"] == "UNKNOWN" for item in markers)
    assert all(item["confidence_calibrated"] is False for item in markers)


def test_reference_section_is_explicit_and_no_bibliography_stays_unresolved():
    elements = [
        _element("As stated in [7].", "body", path=["Methods"]),
        _element("[7] Looks like a reference but remains body text.", "not-ref", path=["Results"]),
    ]
    result = extract_citation_candidates(_chunks(*elements))
    assert result["bibliography_entries"] == []
    assert all(marker["link_status"] == "UNRESOLVED_NO_BIBLIOGRAPHY" for marker in result["markers"])


def test_joined_chunk_keeps_element_not_synthetic_joiner_offsets():
    first = _element("First paragraph with [1].", "body-a", path=["Methods"])
    second = _element("Second paragraph with [2].", "body-b", path=["Methods"])
    reference = _element("[1] Source A.", "ref-a", path=["References"])
    chunks = _chunks(first, second, reference)
    assert any(len(chunk["source_spans"]) == 2 for chunk in chunks)
    result = extract_citation_candidates(chunks)
    marker = _by_text(result["markers"], "[2]")
    assert marker["span"]["element_key"] == "body-b"
    a, b = marker["span"]["element_raw_char_start"], marker["span"]["element_raw_char_end"]
    assert second["raw_text"][a:b] == "[2]"
    assert marker["link_status"] == "UNRESOLVED_NOT_FOUND"


def test_result_is_deterministic_when_chunk_iteration_order_changes():
    chunks = _chunks(
        _element("See [1].", "body", path=["Methods"]),
        _element("[1] Source A.", "ref", path=["References"]),
    )
    forward = extract_citation_candidates(chunks)
    backward = extract_citation_candidates(reversed(chunks))
    assert json.dumps(forward, sort_keys=True) == json.dumps(backward, sort_keys=True)


@pytest.mark.parametrize("damage", ["mixed_version", "missing_map", "duplicate_chunk"])
def test_malformed_or_mixed_provenance_fails_closed(damage):
    chunks = _chunks(
        _element("See [1].", "body", path=["Methods"]),
        _element("[1] Source A.", "ref", path=["References"]),
    )
    if damage == "mixed_version":
        chunks[-1]["document_version_id"] = "another-version"
    elif damage == "missing_map":
        chunks[0]["normalization_map"] = {}
    else:
        chunks.append(chunks[0])
    with pytest.raises(ValueError):
        extract_citation_candidates(chunks)


def test_real_docx_parser_output_roundtrips_citation_provenance(tmp_path):
    from docx import Document

    path = tmp_path / "citations.docx"
    document = Document()
    document.add_heading("Background", level=1)
    document.add_paragraph("Smith (2020) reports a result [1].")
    document.add_heading("References", level=1)
    document.add_paragraph("[1] Smith, J. (2020). Title.")
    document.save(path)

    elements = extract_docx_elements(path)
    result = extract_citation_candidates(chunk_elements(elements))
    assert len(result["bibliography_entries"]) == 1
    assert {item["normalized_text"] for item in result["markers"]} == {"Smith (2020)", "[1]"}
    assert all(item["link_status"] == "CANDIDATE_LINK" for item in result["markers"])
    for marker in result["markers"]:
        assert marker["span"]["locator"]["source_kind"] == "docx"
        assert marker["span"]["locator"]["page_index"] is None
