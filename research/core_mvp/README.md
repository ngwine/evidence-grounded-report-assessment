# Two-pipeline core MVP

This package is the smallest executable path that connects the thesis design
to real PDF/DOCX inputs. It runs offline and writes file-backed artifacts, so
MongoDB, the API and the UI are not prerequisites for a feasibility run.
It is a research prototype, not the integrated lecturer-facing application.

Current outputs must be reviewed by a person. In particular, the Pipeline 1
verbatim path requires a substantial, varied exact span; short or generic
matches stay provisional, and only one span per report chunk contributes to
coverage. Pipeline 2 now abstains on nearby lexical negation and withholds a
score whenever evidence is unresolved, but it is not a semantic contradiction
checker. Both paths need labelled evaluation before use for real plagiarism
decisions or grades.

## Executed flow

### Pipeline 1 — similarity

```text
report PDF/DOCX
→ provenance-preserving parser and section-aware chunker
→ BM25 + multilingual-e5-small
→ RRF
→ mMARCO Cross-Encoder reranking
→ transparent VERBATIM/PARAPHRASE/SUMMARY/NONE baseline
→ exact spans and document-level aggregation
→ similarity-report.json
```

The type classifier is deliberately marked uncalibrated. Dense and Cross-Encoder
scores identify relevant passages, not proven reuse. `PARAPHRASE`/`SUMMARY`
hypotheses remain in `provisional_similarity_type` as manual-review candidates,
while their final `similarity_type` is `null`;
they do not contribute to flagged-passage coverage. Only evidence-backed
`VERBATIM` matches do so in this baseline. The MVP also reports the separate
provisional-review passage coverage and exact-match coverage, but leaves
calibrated similarity percentage as `null` until a frozen labelled set is
available. Similarity evidence is not a plagiarism verdict.

### Pipeline 2 — evidence-grounded assessment

```text
versioned rubric JSON
→ deterministic rubric compiler
→ LOCAL or GRAPH routing
→ evidence retrieval
→ SUPPORTED / CONTRADICTED / INSUFFICIENT
→ MET / UNMET / CANNOT_ASSESS
→ deterministic score rule
→ assessment-report.json
```

LOCAL uses BM25 + Dense + RRF + Cross-Encoder. GRAPH v0 uses requirement-wise
BM25 seeds and deterministic Personalized PageRank over adjacency and shared-
term edges. It is a testable structure-and-term graph baseline, not a claim of
implementing full HippoRAG. Verification v0 matches explicit evidence
requirements authored in the rubric; semantic entailment and automatic rubric
decomposition still require separate evaluation. Any `CANNOT_ASSESS` checklist
withholds its criterion and total proposed score; `assessable_subtotal` is only
a diagnostic for the parts that could be assessed.

## Run

Install the research dependencies in the Python 3.12 environment, then point
the Hugging Face cache at the locked local model revisions:

```bash
python -m pip install -r research/requirements-research.txt

HF_HOME=var/models/hf-home \
TRANSFORMERS_OFFLINE=1 \
HF_HUB_OFFLINE=1 \
TOKENIZERS_PARALLELISM=false \
.venv-research/bin/python -m research.core_mvp \
  --report path/to/report.docx \
  --source path/to/source-1.pdf \
  --source path/to/source-2.docx \
  --rubric research/configs/core-mvp-weekly-progress-rubric-v0.json \
  --config research/configs/core-mvp-v0.json \
  --output-dir var/results/core-mvp/run-001 \
  --pipeline both
```

`--source` can be repeated. Supported document formats are PDF, DOCX, UTF-8
TXT and Markdown.

## Outputs

- `similarity-report.json`: ranked evidence, source/report spans, heuristic
  similarity types and per-source aggregation.
- `assessment-report.json`: compiled rubric, evidence packs, three-state
  verification, checklist outcomes and deterministic score proposal.
- `mvp-summary.json`: compact outcome and runtime summary.
- `run-manifest.json`: commit/worktree state, input hashes, locked model
  revisions, hardware, timing, truncation diagnostics and output checksums.

The runner rejects self-comparison, duplicate source content, changed inputs
during a run, unsupported document types and inconsistent rubric/config data.
Its local-input governance marker does not grant permission to index or publish
any dataset.

## Verification

```bash
.venv-research/bin/python -m pytest -q research/tests/test_core_mvp.py
.venv-research/bin/python -m pytest -q research/tests
```

The focused tests cover deterministic ingestion, stable provenance, verbatim
alignment, LOCAL evidence, multi-chunk GRAPH evidence, explicit contradiction,
safe abstention on missing evidence and the complete two-pipeline runner.
