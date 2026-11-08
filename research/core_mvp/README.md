# Two-pipeline core MVP

This package is the smallest executable path that connects the thesis design
to real PDF/DOCX inputs. It runs offline and writes file-backed artifacts, so
MongoDB, the API and the UI are not prerequisites for a feasibility run.
It is a research prototype, not the integrated lecturer-facing application.

Current outputs must be reviewed by a person. In particular, the Pipeline 1
verbatim path requires a substantial, varied exact span; short or generic
matches stay provisional. Distinct exact spans in the same report chunk may
contribute to coverage, while overlapping token ranges are counted only once.
Pipeline 2 now abstains on nearby lexical negation and withholds a
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
→ exact-overlap check or unverified retrieval candidate (no semantic label)
→ exact spans and document-level aggregation
→ similarity-report.json
```

Dense and Cross-Encoder scores identify relevant passages, not proven reuse.
With policy `EXACT_EVIDENCE_OR_UNVERIFIED_RETRIEVAL_V1`, semantic candidates have
both `similarity_type` and `provisional_similarity_type` set to `null`, plus
`semantic_verification_status: NOT_RUN`. No `PARAPHRASE` or `SUMMARY` label is
inferred from embedding scores or relative text length. The old
`summary_length_ratio` config is accepted for compatibility but is unused.
The review gate retains its existing thresholds: this change does not claim
better retrieval precision or hide previously returned candidate pairs.

The compatible `PROVISIONAL_REVIEW_REQUIRED` status and `selected_for_manual_review`
flag still identify the review queue. Weak exact overlaps can retain provisional
`VERBATIM`; only substantial, varied, evidence-backed exact spans contribute to
confirmed coverage. `review_source_groups` groups the selected queue by source
chunk with every report chunk retained. Multiple report passages pointing to
one source passage trigger a diagnostic warning, not a hard cap: genuine reuse
of the same source in several places must remain detectable.

`provisional_review_passage_coverage_percentage` is a legacy field name for the
union of report tokens in chunks selected for review divided by the report token
union. With parser-v2 provenance, tokens are keyed by document version, element
and normalized offsets, so overlapping chunks count once. Legacy inputs without
coordinates explicitly disclose a chunk-local fallback. Exact-token coverage
uses the same denominator; source aggregation ranks by each source's exact-token
coverage weight. Review coverage measures workload, not confirmed similarity.
The report records the formula/version in `coverage_definitions`. Calibrated similarity stays
`null`. Similarity evidence is not a plagiarism verdict. A trained/evaluated
pairwise verifier and independently labelled examples are still needed to
distinguish actual paraphrases, summaries and same-topic hard negatives.

The W10 diagnostic config can opt into `candidate_selection: quota_union`:
reserve configurable BM25 and Dense candidates for the Cross-Encoder, then
fill remaining places in RRF order. Optional `evidence_budget_per_source`
limits candidate passages from one source for each report chunk; it does not
cap evidence across the whole report. The default remains RRF-only selection.
The report keeps the preselection rank and why a candidate entered the pool.
This is a diversity mechanism to test, not a demonstrated accuracy gain.

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

The optional `bm25-p2-llm-v1` profile adds a local Qwen3.5 4B requirement
verifier, separately from the phrase/context V4 baseline. A digest-locked
loopback Ollama service proposes relations and exact evidence quotations;
code checks proof and computes labels/scores. Invalid or unavailable model
responses abstain. See the [runtime and usage guide](../../docs/architecture/p2-local-llm-verifier.md).
Real-model synthetic smoke checks establish executable integration, not
independent rubric-grading accuracy.

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

Parsing in the runner uses a separate child process per input. Defaults are a
60-second wall timeout, 45 CPU seconds, 20 MiB input, 64 MiB parser output,
2 million extracted characters and 20,000 chunks. `documents.resource_limits`
can set a smaller explicit budget in a versioned config. Linux also enforces a
2 GiB address-space limit; macOS records that a memory cap is not enforced.
A failed or timed-out parser does not return a successful partial document.
Outputs use a private directory and a nonempty run directory cannot be reused.

`citation-context.json` stores numeric/author-year markers, bibliography-entry
candidates, original spans and unresolved/ambiguous states. It is included in
the run manifest hashes. These candidates do not validate a citation or change
the similarity/assessment score. JSON Schema validation and semantic runtime
checks both run before either pipeline report is written.

To reproduce the W10 Pipeline 1 technical slice without private files, use the
committed synthetic fixture and locked model revisions:

```bash
HF_HOME=var/models/hf-home TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 \
TOKENIZERS_PARALLELISM=false .venv-research/bin/python -m research.core_mvp \
  --report research/tests/fixtures/similarity_w10/report.md \
  --source research/tests/fixtures/similarity_w10/source-operation.md \
  --source research/tests/fixtures/similarity_w10/source-trials.md \
  --rubric research/tests/fixtures/core_mvp/rubric.json \
  --config research/configs/core-mvp-w10-synthetic-quota-union.json \
  --output-dir var/results/core-mvp/w10-reproducible-synthetic \
  --pipeline similarity
```

The additional [synthetic case pack](../tests/fixtures/similarity_w10/README.md)
checks quotation, generic overlap, no-source, same-topic hard-negative and
exact-span behavior. Neither fixture supplies adjudicated research labels.

## Outputs

- `similarity-report.json`: ranked candidates, evidence-backed exact labels,
  unverified semantic review candidates, source/report spans and per-source
  aggregation.
- `assessment-report.json`: compiled rubric, evidence packs, three-state
  verification, checklist outcomes and deterministic score proposal.
- `mvp-summary.json`: compact outcome and runtime summary.
- `run-manifest.json`: commit/worktree state, input hashes, locked model
  revisions, hardware, timing, truncation diagnostics and output checksums.

The output boundary is documented by the Draft 2020-12 schemas in
[`research/schemas`](../schemas/README.md) and enforced by runtime contract
checks before the runner writes either pipeline report.

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
safe abstention on missing evidence and the complete two-pipeline runner. They
also cover quota-union selection, per-source candidate budget and rejection of
out-of-scope Evidence Pack entries.
