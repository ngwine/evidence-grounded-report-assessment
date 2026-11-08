# Output-quality development diagnostics

This pack separates source/evidence retrieval from the decision made after
retrieval. It is not the PAN source-ranking experiment and does not open
PAN TEST0. All text and labels are newly authored synthetic expectations.
They have not been independently annotated or adjudicated by humans.

The public `fixtures/dev-v1.json` contains 12 similarity pairs and six rubric
checks in English and Vietnamese. Similarity cases cover exact reuse,
equivalent rewrites, opposite polarity, changed quantities, changed actors,
and related topics with different claims. Each case includes a target source
and two distractors. Expected evidence uses exact Unicode half-open ranges
and is checked against the frozen strings.

The private challenge contains 24 similarity pairs and 12 rubric checks.
Its bytes, expectations and lock record live under ignored
`var/quality/output-improvement-2026-10-29/case-pack/`. The first candidate
implementation and model/policy settings must be frozen before its texts,
labels or detailed results are opened to the implementation agents. Once
opened, it remains a development challenge; further fixes need a new unseen
cohort. It must never be presented as independent human gold or as PAN TEST0.

## Reproduce the preserved baseline

From the project root with the research environment:

```bash
.venv-research/bin/python -m research.output_quality.evaluation \
  --pack research/output_quality/fixtures/dev-v1.json \
  --expected-sha256 0bcc7ef8996b622fea0ebc41973907c997d0795427b993c65813e15d23cc2020 \
  --core-snapshot var/quality/output-improvement-2026-10-29/before \
  --output-dir var/quality/output-improvement-2026-10-29/new-baseline-attempt
```

Use a fresh output directory. Snapshot loading replaces Python module entries
and must run in a separate process, never inside the API, worker, or a process
that alternates baseline and candidate runs. Omitting `--core-snapshot` uses
the current working code. Source hashes, pack hash and configuration are
recorded in `evaluation.json`; full synthetic input/output artifacts remain
in the specified run directory.

Compare two completed runs only when their frozen pack, expectations and
retrieval settings match:

```bash
.venv-research/bin/python -m research.output_quality.comparison \
  --before var/quality/output-improvement-2026-10-29/case-pack/baseline-dev-bm25-v3/evaluation.json \
  --after var/quality/output-improvement-2026-10-29/candidate-dev-bm25/evaluation.json \
  --output var/quality/output-improvement-2026-10-29/dev-comparison.md
```

`evaluate_pack` also accepts actual encoder, reranker and semantic-verifier
adapters, with profiles `bm25`, `rrf` and `rrf-rerank`. The semantic-verifier
argument explicitly enables `pipeline1.semantic_verification.enabled` while
keeping retrieval settings fixed. Injected test doubles are software tests,
not actual model measurements. Retain all attempts and their model metadata.

## Read the results

- Positive target-source retrieval at ranks 1 and 3 is separate from relation
  agreement. Three short source documents make this a bounded diagnosis,
  not a realistic large-corpus retrieval benchmark.
- Full anchor containment checks the span in the returned alignment. A
  retrieved source document with a different visible passage does not pass
  automatically.
- Missing predictions and abstentions stay explicit. They are never converted
  to correct NONE labels. `negative_false_reuse_labels` refers to the target
  pair only. `negative_cases_any_source_false_reuse` flags a negative case if
  any retrieved source gets VERBATIM or PARAPHRASE. All non-target sources
  are distractors under the predeclared construction, so
  `non_target_false_reuse_labels` counts their positive labels across every
  case, including positive-target cases. False exact-document coverage is
  reported separately. An apparently correct target label must not conceal
  a false positive from another source in the same output.
- P2 reports checklist outcomes, false MET decisions and correctly retained
  CANNOT_ASSESS cases. Producing a non-null total is not the quality target.
- Counts are small, authored development observations. Report failures as
  well as gains; no general accuracy or statistical superiority follows.
