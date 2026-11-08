# QASPER v0.3 dev — within-paper evidence retrieval proxy

**Run date:** 18/10/2026
**Result class:** preliminary component diagnostic on the full dev split
**Task:** rank evidence paragraphs inside the question's own paper

This run evaluates paragraph evidence retrieval using BM25, Dense and RRF
utilities shared with Pipeline 2. It does not evaluate rubric scoring, LOCAL
versus GRAPH routing, answer generation, or end-to-end grading of student reports.

More precisely, the runner directly calls the shared BM25, Dense and RRF
utilities. It does not call `assessment._rank_local` or the complete assessment
pipeline. QASPER questions replace authored checklist queries, and the candidate
units are dataset paragraphs rather than the app's parser chunks. Report this
as a **within-paper retrieval proxy/component diagnostic**, not execution or
validation of the complete LOCAL assessment path, its reranker or rubric rules.

## Source and protocol

The source is [QASPER v0.3](https://huggingface.co/datasets/allenai/qasper),
dev split. The official dataset card lists CC BY 4.0. Its full dev file has
281 papers, 1,005 questions, and 1,764 human answer annotations. The archive
SHA-256 is `a28fdf966db827bcee3d873107d6b6669864fb7ca8fbf73a192f5e39191bdb5a`;
the extracted dev JSON SHA-256 is
`2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93`.
The repository checks the latter before running. Formal approval in the team's
dataset mapping has not been recorded; this is user-requested internal research.

The frozen run uses every dev paper, with seed `20261018`. Each question ranks
only its own paper's abstract and full-text paragraphs. BM25 has `k1=1.2`,
`b=0.75`; Dense uses cached `intfloat/multilingual-e5-small` revision
`614241f622f53c4eeff9890bdc4f31cfecc418b3`, E5 query/passage prefixes,
and CPU inference. Fusion is equal-weight RRF with `k=60`, using each method's
Top-10 list; candidate depth was not swept. All methods rank paragraphs to
depth 10. The verified rerun took 237.67 wall seconds on an arm64 Mac with
10 logical CPUs and Python 3.12.14.

Human evidence is matched only when Unicode normalization, case folding, and
whitespace normalization produce one exact paragraph in that paper. A question
is scored only when every answerable human annotation maps completely.
Figure/table (`FLOAT SELECTED:`) evidence, section headings, absent evidence,
duplicate-text ambiguity, and mixed answerability are counted and excluded.
This conservative rule avoids silently treating an unmapped evidence string as
a negative retrieval result. Human `highlighted_evidence` excerpts are not
used as whole-paragraph gold.

## Coverage

| Item | Count |
| --- | ---: |
| Papers in dev / papers with an evaluable question | 281 / 255 |
| Questions total / evaluable / excluded | 1,005 / 646 / 359 |
| Answer annotations / answerable / unanswerable | 1,764 / 1,601 / 163 |
| Candidate paragraphs | 13,547 |
| Evidence strings total / unique exact paragraph | 2,808 / 2,414 |
| Figure/table evidence strings | 253 |
| Section-heading evidence strings | 129 |
| Duplicate-paragraph ambiguous strings | 12 |
| Unmatched strings after these classifications | 0 |

Question-level exclusion reasons are overlapping: figure/table evidence 164,
section heading 45, missing evidence 39, mixed answerability 75,
unanswerable-only 60, and duplicate-paragraph ambiguity 6. They do not sum to
359. Across all questions, including excluded ones, 282 have differing mapped
human evidence sets. For scored questions, multiple complete annotations are
treated as alternative valid sets, not separate questions.

## Retrieval results

All values below are question macro averages over the same 646 evaluable
questions. `Hit@K` finds any paragraph from an acceptable human annotation.
`Best recall@K` takes the best paragraph-set recall across annotations.
`Complete@K` requires all paragraphs of at least one annotation. MRR uses the
first acceptable paragraph.

| Method | Hit@1 | Hit@5 | Hit@10 | Best recall@10 | Complete@10 | MRR@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.1873 | 0.5697 | 0.7693 | 0.6829 | 0.6176 | 0.3457 |
| E5-small Dense | 0.3019 | 0.7198 | 0.8669 | 0.7995 | 0.7430 | 0.4781 |
| BM25 + E5 RRF | 0.2616 | 0.6997 | 0.8715 | 0.7890 | 0.7245 | 0.4426 |

Dense improves every listed metric over BM25 in this descriptive dev run.
Fusion has the highest Hit@10 point estimate, while Dense has higher
best-annotation recall, complete-annotation rate, and MRR. The small fusion
Hit@10 difference is not a superiority claim; no confidence interval or
untouched holdout is reported here.

## Reproduction and boundaries

Run from the repository root with the official extracted file at
`var/datasets/raw/qasper-v0.3/qasper-dev-v0.3.json`:

```bash
HF_HOME=var/models/hf-home HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  ./.venv-research/bin/python -m research.qasper_pilot \
  --dense --max-papers 281 \
  --output-dir research/results/rq2-qasper/local-paragraph-dev-v03-reproduction
```

The aggregate `metrics.json` SHA-256 is
`e254444c3921a6a189caf7888f62e127a471fcd94a0132e2dbe63d9da4bff237`.
`run_manifest.json` records the archive and extracted-file hashes, source URLs,
license, coverage, code hashes, model revision, config, hardware, timing, and
git state. The output contains no corpus text, per-question predictions, or
gold paragraph IDs. The manifest's code hashes were checked against the
current source files after the run. A separate BM25-only whole-dev run produced
an identical BM25 metrics section.

This is the dev split, already used for diagnosis, and the output is a
paragraph-level retrieval metric. It is not the official QASPER answer or
evidence F1 score. Some long paragraphs may be truncated by E5's tokenizer;
the four paragraphs above 512 whitespace tokens are only a lower-bound warning,
not a tokenizer-level truncation audit. Pipeline 2 still needs an approved
report–rubric corpus, rubric labels, instructor scores, and a separate GRAPH
evaluation before making any claim about grading quality.

## Clean-code revalidation — 30 October 2026

The owner reran the same full-DEV diagnostic with actual cached E5 inference
from clean commit `9b9721d6b0d0eb9069b95b4d937635c2d9e3924e`. The launcher
completed with return code 0 and `CLI_SUCCEEDED`. Data/model/configuration,
selection, coverage and metric definitions match the reference above:
281 papers, 1,005 questions, 646 evaluable and 359 excluded.

Every aggregate metric at every recorded cutoff matches, and `metrics.json`
is byte-identical to the reference (SHA-256 `e254444c3921a6a189caf7888f62e127a471fcd94a0132e2dbe63d9da4bff237`).
The RRF source hash differs from the historical run; the other three recorded
code-component hashes match. This is aggregate revalidation on the current
frozen implementation, not exact historical-source replay. Equal aggregates
do not establish identical per-query rankings; these runs do not export them.

The new files are under
`var/results/rq2-qasper/local-paragraph-dev-v03-revalidation-20261030-v1/`.
[Comparison record](../../var/paper/p2-preparation-2026-10-30/qasper/new-run-comparison-v1.json)
checks artifact hashes and identical inputs, settings, scope and coverage.
Wall time was 371.11 seconds for this offline run; it is not end-to-end app latency.

The clean rerun resolves the code-snapshot concern for this revalidation.
The manifest still states `team_dataset_approval=NOT_RECORDED`; no approval
was added retroactively. The previously inspected DEV scope, paragraph-only
task and lack of rubric/verifier/GRAPH evaluation remain unchanged.

## Inclusion in the faculty-review manuscript — 1 November 2026

The manuscript now reports this experiment in §4.6 (protocol) and §5.6/Table 10
(results), separately from the PAN source-retrieval study. The table uses the
existing revalidated aggregate values, with the same 646 evaluable questions
out of 1,005 and 359 exclusions. No model inference or new result selection
was performed for this writing update.

The result supports a descriptive comparison of within-paper paragraph
retrievers. It is not the official QASPER QA/evidence F1 evaluation or a
validation of P2's rubric-to-score path. Both Hit@10 and evidence completeness
are reported so that the small RRF Hit@10 advantage is not presented as
overall superiority. DEV reuse, absent uncertainty/holdout evidence and
paragraph-mapping restrictions remain methodological limits. Separately, the
project's pack status remains `NOT_RECORDED`: manuscript inclusion does not
itself supply an approval decision or establish that a final publication
submission has met all project gates.
