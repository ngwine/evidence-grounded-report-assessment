"""Integration checks for deterministic PDF/DOCX element provenance."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.kltn_ai.integrations.indexing.chunking import chunk_elements  # noqa: E402
from src.kltn_ai.integrations.parsing.docx_parser import extract_docx_elements  # noqa: E402
from src.kltn_ai.integrations.parsing.pdf_parser import extract_pdf_elements  # noqa: E402


FIXTURES_DIR = Path(__file__).parent / "fixtures"
REQUIRED_ELEMENT_FIELDS = {
    "schema_version",
    "document_version_id",
    "element_key",
    "element_id",
    "order",
    "type",
    "element_type",
    "raw_text",
    "normalized_text",
    "text",
    "raw_text_sha256",
    "normalized_text_sha256",
    "section_path",
    "structure_path",
    "locator",
    "normalization_map",
    "parser_spec",
    "generation_key",
}


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _assert_element_schema(elements: list[dict], source_kind: str) -> None:
    assert elements
    assert [element["order"] for element in elements] == list(range(len(elements)))
    assert len({element["element_key"] for element in elements}) == len(elements)
    assert len({element["document_version_id"] for element in elements}) == 1
    assert len({element["generation_key"] for element in elements}) == 1

    for element in elements:
        assert REQUIRED_ELEMENT_FIELDS <= element.keys()
        assert element["schema_version"] == 2
        assert element["element_id"] == element["element_key"]
        assert element["element_key"].startswith("el_")
        assert element["text"] == element["normalized_text"]
        assert element["section_path"] == element["structure_path"]
        assert element["raw_text"]
        assert element["normalized_text"]

        locator = element["locator"]
        assert locator["locator_version"] == 1
        assert locator["source_kind"] == source_kind
        assert locator["offset_convention"] == "half_open"
        assert locator["raw_char_start"] == 0
        assert locator["raw_char_end"] == len(element["raw_text"])
        assert locator["section_path"] == element["section_path"]

        mapping = element["normalization_map"]
        assert mapping["version"] == 1
        assert mapping["coordinate_system"] == "unicode_code_point"
        assert mapping["offset_convention"] == "half_open"
        assert mapping["raw_length"] == len(element["raw_text"])
        assert mapping["normalized_length"] == len(element["normalized_text"])
        assert len(mapping["segments"]) == len(element["normalized_text"])
        for index, segment in enumerate(mapping["segments"]):
            assert segment["normalized_start"] == index
            assert segment["normalized_end"] == index + 1
            assert 0 <= segment["raw_start"] <= segment["raw_end"] <= len(element["raw_text"])


@pytest.mark.parametrize(
    ("filename", "extractor", "source_kind"),
    [
        ("sample_thesis.pdf", extract_pdf_elements, "pdf"),
        ("sample_thesis.docx", extract_docx_elements, "docx"),
    ],
)
def test_parser_and_chunker_output_is_deterministic(filename, extractor, source_kind):
    path = FIXTURES_DIR / filename

    first_elements = extractor(str(path))
    second_elements = extractor(str(path))
    _assert_element_schema(first_elements, source_kind)
    assert _canonical(first_elements) == _canonical(second_elements)

    first_chunks = chunk_elements(first_elements, max_tokens=20, min_tokens=0)
    second_chunks = chunk_elements(second_elements, max_tokens=20, min_tokens=0)
    assert _canonical(first_chunks) == _canonical(second_chunks)
    assert all(chunk["token_count"] <= 20 for chunk in first_chunks)


def test_pdf_locator_has_zero_based_page_bbox_and_line_fragments():
    elements = extract_pdf_elements(str(FIXTURES_DIR / "sample_thesis.pdf"))

    assert {element["locator"]["page_index"] for element in elements} == {0, 1}
    for element in elements:
        locator = element["locator"]
        assert locator["page_number"] == locator["page_index"] + 1
        assert locator["page_label"]
        assert len(locator["bbox"]) == 4
        assert locator["fragments"]
        assert all(
            0 <= fragment["raw_char_start"] < fragment["raw_char_end"] <= len(element["raw_text"])
            for fragment in locator["fragments"]
        )


def test_docx_table_preserves_raw_rows_and_normalized_row_boundaries():
    elements = extract_docx_elements(str(FIXTURES_DIR / "sample_thesis.docx"))
    [table] = [element for element in elements if element["type"] == "table"]

    assert table["raw_rows"] == [["Tiêu chí", "Trọng số"], ["Tính đầy đủ", "30%"]]
    assert table["rows"] == table["raw_rows"]
    assert table["raw_text"] == "Tiêu chí\tTrọng số\nTính đầy đủ\t30%"
    assert table["normalized_text"] == "Tiêu chí Trọng số\nTính đầy đủ 30%"
    assert table["locator"]["page_index"] is None
    assert table["locator"]["table_index"] == 0


def test_repeated_body_text_is_not_removed_as_header_or_footer(tmp_path):
    path = tmp_path / "repeated-body.pdf"
    document = pymupdf.open()
    for page_number in range(2):
        page = document.new_page(width=595, height=842)
        page.insert_text((72, 35), "REPEATED HEADER", fontsize=9)
        page.insert_text((72, 180), "Repeated body claim must remain.", fontsize=11)
        page.insert_text((72, 210), f"Unique body {page_number}.", fontsize=11)
    document.save(path)
    document.close()

    elements = extract_pdf_elements(str(path))
    combined = "\n".join(element["normalized_text"] for element in elements)

    assert "REPEATED HEADER" not in combined
    assert combined.count("Repeated body claim must remain.") == 2
    assert "Unique body 0." in combined
    assert "Unique body 1." in combined


def test_two_column_pdf_uses_column_major_reading_order(tmp_path):
    path = tmp_path / "two-column.pdf"
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((50, 60), "Chapter 1", fontsize=14)
    page.insert_text((50, 140), "LEFT ONE", fontsize=11)
    page.insert_text((50, 160), "LEFT TWO", fontsize=11)
    page.insert_text((330, 140), "RIGHT ONE", fontsize=11)
    page.insert_text((330, 160), "RIGHT TWO", fontsize=11)
    document.save(path)
    document.close()

    elements = extract_pdf_elements(str(path))
    paragraphs = [
        element["normalized_text"]
        for element in elements
        if element["type"] == "paragraph"
    ]

    assert paragraphs == ["LEFT ONE LEFT TWO", "RIGHT ONE RIGHT TWO"]
