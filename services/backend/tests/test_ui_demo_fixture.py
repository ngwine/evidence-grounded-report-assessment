"""Only self-authored fixture checks; not model-quality or governance approval."""
import fitz

from scripts.seed_ui_demo import SHARED, oid, pdf


def test_demo_pdf_bytes_are_deterministic_readable_and_explicitly_synthetic():
    first = pdf("Self-authored fixture", [("1. Method", SHARED)])
    assert first == pdf("Self-authored fixture", [("1. Method", SHARED)])
    with fitz.open(stream=first, filetype="pdf") as document:
        text = " ".join(document[0].get_text().split())
        assert "SELF-AUTHORED DEMO / NOT EMPIRICAL RESEARCH" in text
        assert SHARED in text
    assert oid("report-approval") == oid("report-approval")
    assert oid("report-approval") != oid("source-approval")
