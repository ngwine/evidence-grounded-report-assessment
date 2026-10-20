# QASPER v0.3 dev — Pipeline 2 LOCAL evidence retrieval

**Run date:** 18/10/2026
**Result class:** preliminary component diagnostic on the full dev split
**Task:** rank evidence paragraphs inside the question's own paper

This run evaluates the LOCAL evidence retrieval component of Pipeline 2. It
does not evaluate rubric scoring, LOCAL versus GRAPH routing, answer generation,
or end-to-end grading of student reports.

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
