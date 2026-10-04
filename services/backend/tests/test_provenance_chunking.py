"""Regression tests for parser/chunker provenance schema v2."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.kltn_ai.integrations.indexing.chunking import (  # noqa: E402
    approx_token_count,
    chunk_elements,
)
from src.kltn_ai.integrations.parsing.text_normalization import (  # noqa: E402
    normalize_with_mapping,
    sha256_text,
    stable_element_key,
)


def _element(
    raw_text: str,
    *,
    block_index: int,
    element_type: str = "paragraph",
    section_path: list[str] | None = None,
    document_version_id: str = "doc-version-1",
    preserve_newlines: bool = False,
) -> dict:
    normalized = normalize_with_mapping(
        raw_text,
        preserve_newlines=preserve_newlines,
    )
    locator = {
        "locator_version": 1,
        "source_kind": "synthetic",
        "coordinate_system": {"text": "unicode_code_point", "bbox": None},
        "offset_convention": "half_open",
        "page_index": 0,
        "page_number": 1,
        "page_label": "1",
        "bbox": None,
        "section_path": list(section_path or []),
        "block_id": f"block-{block_index}",
        "block_index": block_index,
        "raw_char_start": 0,
        "raw_char_end": len(raw_text),
    }
    element_key = stable_element_key(
        document_version_id=document_version_id,
        element_type=element_type,
        raw_text_sha256=sha256_text(raw_text),
        locator=locator,
    )
    return {
        "schema_version": 2,
        "document_version_id": document_version_id,
        "generation_key": "parse-generation-1",
        "element_key": element_key,
        "order": block_index,
        "type": element_type,
        "raw_text": raw_text,
        "normalized_text": normalized.text,
        "text": normalized.text,
        "raw_text_sha256": sha256_text(raw_text),
        "normalized_text_sha256": sha256_text(normalized.text),
        "section_path": list(section_path or []),
        "structure_path": list(section_path or []),
        "locator": locator,
        "normalization_map": normalized.normalization_map,
    }


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_normalization_map_is_exact_for_nfkc_zero_width_and_whitespace():
    raw = "oﬃce\u200b   A"
    normalized = normalize_with_mapping(raw)

    assert normalized.text == "office A"
    segments = normalized.normalization_map["segments"]
    assert len(segments) == len(normalized.text)

    ligature_spans = [
        (segment["raw_start"], segment["raw_end"])
        for segment in segments[1:4]
    ]
    assert ligature_spans == [(1, 2), (1, 2), (1, 2)]
    assert raw[1:2] == "ﬃ"

    space_segment = segments[6]
    assert normalized.text[space_segment["normalized_start"]] == " "
    assert raw[space_segment["raw_start"] : space_segment["raw_end"]] == "   "


def test_chunks_are_byte_deterministic_and_use_stable_non_ordinal_ids():
    elements = [
        _element("Đoạn thứ nhất có đủ nội dung.", block_index=1, section_path=["A"]),
        _element("Đoạn thứ hai có thêm bằng chứng.", block_index=2, section_path=["A"]),
    ]

    first = chunk_elements(elements, max_tokens=40, min_tokens=0)
    second = chunk_elements(deepcopy(elements), max_tokens=40, min_tokens=0)

    assert _canonical(first) == _canonical(second)
    assert all(chunk["chunk_id"] == chunk["chunk_key"] for chunk in first)
    assert all(chunk["chunk_id"].startswith("chk-") for chunk in first)
    assert [chunk["order"] for chunk in first] == list(range(len(first)))

    reordered_metadata = deepcopy(elements)
    reordered_metadata[0]["order"] = 99
    reordered_metadata[1]["order"] = 100
    assert [chunk["chunk_key"] for chunk in chunk_elements(
        reordered_metadata, max_tokens=40, min_tokens=0
    )] == [chunk["chunk_key"] for chunk in first]

    ignored_heading = _element(
        "Phần không đóng góp nội dung chunk",
        block_index=0,
        element_type="heading",
        section_path=[],
    )
    with_preceding_heading = chunk_elements(
        [ignored_heading, *elements], max_tokens=40, min_tokens=0
    )
    assert [chunk["chunk_key"] for chunk in with_preceding_heading] == [
        chunk["chunk_key"] for chunk in first
    ]


def test_duplicate_text_at_distinct_locators_has_distinct_identity():
    text = "Nội dung giống nhau nhưng nằm ở hai vị trí khác nhau."
    elements = [
        _element(text, block_index=10, section_path=["A"]),
        _element(text, block_index=20, section_path=["B"]),
    ]

    chunks = chunk_elements(elements, max_tokens=100, min_tokens=0)

    assert len(chunks) == 2
    assert chunks[0]["normalized_text"] == chunks[1]["normalized_text"]
    assert chunks[0]["element_ids"] != chunks[1]["element_ids"]
    assert chunks[0]["chunk_key"] != chunks[1]["chunk_key"]


def test_long_paragraph_is_split_with_exact_half_open_source_spans():
    raw = "  " + " ".join(f"từ{i}" for i in range(120)) + "  "
    element = _element(raw, block_index=1, section_path=["Long"])

    chunks = chunk_elements([element], max_tokens=12, min_tokens=0)

    assert len(chunks) > 1
    assert all(chunk["token_count"] <= 12 for chunk in chunks)
    assert all(approx_token_count(chunk["normalized_text"]) <= 12 for chunk in chunks)
    assert all(len(chunk["source_spans"]) == 1 for chunk in chunks)

    previous_normalized_end = 0
    previous_raw_end = 0
    rebuilt_normalized = ""
    for chunk in chunks:
        span = chunk["source_spans"][0]
        assert span["element_normalized_char_start"] == previous_normalized_end
        assert span["element_raw_char_start"] >= previous_raw_end
        assert span["element_normalized_char_start"] < span["element_normalized_char_end"]
        assert span["element_raw_char_start"] < span["element_raw_char_end"]
        assert chunk["raw_text"] == raw[
            span["element_raw_char_start"] : span["element_raw_char_end"]
        ]
        rebuilt_normalized += chunk["normalized_text"]
        previous_normalized_end = span["element_normalized_char_end"]
        previous_raw_end = span["element_raw_char_end"]

    assert rebuilt_normalized.replace(" ", "") == element["normalized_text"].replace(" ", "")
    assert previous_normalized_end == len(element["normalized_text"])


def test_long_table_and_single_long_row_are_split_and_remain_table_chunks():
    rows = [
        "\t".join([f"hàng{i}", " ".join(f"giá_trị_{i}_{j}" for j in range(18))])
        for i in range(12)
    ]
    element = _element(
        "\n".join(rows),
        block_index=4,
        element_type="table",
        section_path=["Bảng"],
        preserve_newlines=True,
    )

    chunks = chunk_elements([element], max_tokens=15, min_tokens=0)

    assert len(chunks) > len(rows)
    assert all(chunk["type"] == "table" for chunk in chunks)
    assert all(chunk["token_count"] <= 15 for chunk in chunks)
    assert all(chunk["source_spans"][0]["element_key"] == element["element_key"] for chunk in chunks)


def test_chunk_normalization_map_and_source_spans_resolve_to_raw_text():
    element = _element(
        "oﬃce\u200b   A và nội dung tiếp theo",
        block_index=7,
        section_path=["Unicode"],
    )
    [chunk] = chunk_elements([element], max_tokens=100, min_tokens=0)

    char_map = chunk["normalization_map"]["normalized_char_to_raw_span"]
    assert len(char_map) == len(chunk["normalized_text"])
    for normalized_index, (raw_start, raw_end) in enumerate(char_map):
        assert 0 <= raw_start <= raw_end <= len(chunk["raw_text"])
        assert chunk["raw_text"][raw_start:raw_end]
        if chunk["normalized_text"][normalized_index] == " ":
            assert chunk["raw_text"][raw_start:raw_end].isspace()

    [source_span] = chunk["source_spans"]
    assert source_span["element_raw_char_start"] == 0
    assert source_span["element_raw_char_end"] == len(element["raw_text"])
    assert source_span["element_normalized_char_start"] == 0
    assert source_span["element_normalized_char_end"] == len(element["normalized_text"])


def test_legacy_elements_remain_supported_without_claiming_precise_page_index():
    elements = [
        {
            "type": "paragraph",
            "text": "Đầu vào legacy vẫn phải chạy.",
            "para_index": 3,
            "page": 8,
            "section_path": ["Legacy"],
        }
    ]

    [chunk] = chunk_elements(elements, max_tokens=100, min_tokens=0)

    assert chunk["document_version_id"].startswith("legacy:sha256:")
    assert chunk["locator"]["page_index"] is None
    assert chunk["source_spans"][0]["locator"]["legacy_page"] == 8
    assert chunk["source_refs"] == [3]


def test_invalid_config_mixed_versions_and_duplicate_element_keys_fail_closed():
    one = _element("Một", block_index=1, document_version_id="v1")
    two = _element("Hai", block_index=2, document_version_id="v2")

    with pytest.raises(ValueError, match="max_tokens"):
        chunk_elements([one], max_tokens=0)
    with pytest.raises(ValueError, match="min_tokens"):
        chunk_elements([one], min_tokens=-1)
    with pytest.raises(ValueError, match="mixed document_version_id"):
        chunk_elements([one, two])

    duplicate = deepcopy(one)
    duplicate["locator"]["block_index"] = 99
    with pytest.raises(ValueError, match="element_key values must be unique"):
        chunk_elements([one, duplicate])
