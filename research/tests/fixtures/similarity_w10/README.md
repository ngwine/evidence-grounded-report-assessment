# Synthetic Pipeline 1 diagnostic pack

`cases.json` contains six entirely fictional report–source pairs for W10
software diagnostics. `report.md` and the two `source-*.md` files contain the
same scenarios as complete input documents for the one-command pipeline run:
distinctive copying, an attributed quotation, a
same-topic polarity conflict, no relevant source, a generic stock sentence,
and a semantic rewrite. Each case can be parsed as a separate report and source
file. The only machine-checkable expected outcome here is whether an exact,
distinctive span may contribute to automatic `VERBATIM` coverage.

Run the fixture test with:

```bash
.venv-research/bin/python -m pytest -q research/tests/test_week10_similarity_cases.py
```

The `kind` and `notes` fields describe a human-authored scenario, **not**
adjudicated research labels. In particular, the quotation case should remain a
similarity match while its attribution is for lecturer review; the system does
not currently detect citation validity. The no-source case only verifies that
unrelated text is not counted as exact reuse; it does not establish calibrated
open-set rejection. These six synthetic examples must not be used to report
precision, recall, F1, or to pass the thesis dataset/evaluation gates.
