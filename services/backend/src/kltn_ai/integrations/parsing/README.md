# Citation/reference candidate adapter (`W4.5` baseline)

`citation_markers.extract_citation_candidates(chunks)` consumes the existing
provenance-v2 output of `chunk_elements()`. It recognises numeric markers such
as `[1]` and `[1, 2–3]`, narrow author–year forms such as `(Smith, 2020)` and
`Smith (2020)`, and bibliography-entry candidates under an explicit
References/Bibliography/Tài liệu tham khảo heading. A parser element explicitly
typed `reference` also qualifies as an entry candidate.

Each candidate keeps the exact raw and normalized text, zero-based half-open
offsets in the chunk **and** original parser element, plus the parser locator
(page/bbox for PDF when available; DOCX does not invent page numbers). A unique
printed key gives `CANDIDATE_LINK`, *not* a verified source or valid citation.
Missing/duplicate/unsupported keys remain `UNRESOLVED_*`; every marker and
entry has `verification_status: UNKNOWN`. `parse_confidence` and
`link_confidence` are uncalibrated heuristic indicators, never probabilities of
academic correctness or plagiarism.

The adapter deliberately does not infer whether a source exists, supports the
report's claim, was cited correctly, or constitutes plagiarism. It does not
handle every citation style, OCR-damaged text, bibliography entries spanning
multiple parser elements, or GROBID-level metadata extraction. Ambiguous cases
must be reviewed using the retained source spans. Do not use a candidate link
to suppress a similarity finding automatically.

Run the synthetic/real-parser contract tests with:

```bash
.venv-research/bin/python -m pytest services/backend/tests/test_citation_markers.py -q
```
