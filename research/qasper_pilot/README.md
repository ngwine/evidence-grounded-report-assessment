# QASPER v0.3 dev: LOCAL paragraph evidence retrieval

This is a preliminary Pipeline 2 component diagnostic. A question ranks only
paragraphs from its own QASPER paper. It does not generate an answer, grade a
rubric, route to GRAPH, or evaluate Vietnamese student reports.

Source: [official QASPER dataset card](https://huggingface.co/datasets/allenai/qasper)
(CC BY 4.0). The official v0.3 train/dev archive is
`https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz`.
The archive SHA-256 is
`a28fdf966db827bcee3d873107d6b6669864fb7ca8fbf73a192f5e39191bdb5a`;
the extracted `qasper-dev-v0.3.json` SHA-256 is
`2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93`.
The file hash is checked before any run. The team's formal dataset approval is
not recorded; this run is internal research requested by the user.

## Protocol

- With `--max-papers 281`, use all 281 dev papers. Smaller runs select papers
  by ascending SHA-256 of `seed:paper_id`, with paper ID as tie break. The
  default seed is `20261018`.
- Candidate units are the abstract and non-empty `full_text` paragraphs of the
  question's own paper. Figure/table captions and section headings are not
  candidates. BM25 uses `k1=1.2`, `b=0.75`. Optional Dense is cached
  `intfloat/multilingual-e5-small` revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3` with E5 query/passage
  prefixes, CPU inference, and local files only. Fusion is equal-weight RRF
  with `k=60`.
- An evidence string maps to gold only if Unicode NFKC, case folding, and
  whitespace normalization give one exact paragraph match in the same paper.
  The official `FLOAT SELECTED:` evidence denotes a figure or table. It is
  counted and excluded from this paragraph-only run. Section-heading evidence,
  unmatched or duplicate paragraph text, missing evidence, and questions with
  mixed answerable/unanswerable annotations are counted and excluded. All
  answerable human annotations must map completely before a question is scored.
  `highlighted_evidence` is not used because it is an excerpt, not the whole
  paragraph unit.
- `hit@K` checks whether any acceptable human evidence paragraph is retrieved.
  `best_annotation_recall@K` takes the maximum paragraph-set recall across
  human annotations for that question. `complete_annotation@K` requires every
  paragraph of at least one annotation to be retrieved. `MRR@K` uses the first
  acceptable paragraph. Every metric is a question macro average; overlapping
  evidence strings or multiple annotations do not become independent queries.

## Run

From the repository root, with the official dev file at
`var/datasets/raw/qasper-v0.3/qasper-dev-v0.3.json` and the exact E5 revision
already cached under this example's `HF_HOME` (change that path to your own
cache when running elsewhere):

```bash
HF_HOME=var/models/hf-home HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  ./.venv-research/bin/python -m research.qasper_pilot \
  --dense --max-papers 281 \
  --output-dir research/results/rq2-qasper/local-paragraph-dev-v03-all281-s20261018
```

The command writes only aggregate `metrics.json` and `run_manifest.json` in
the ignored results directory. It never writes raw paper/question text, gold
IDs, or per-query predictions. The manifest records source, license,
governance status, checksums, code/config, hardware, timing, git state, and
coverage. Rerunning on the same file and code should reproduce `metrics.json`
byte for byte; timing and creation time in the manifest naturally differ.

This is a dev-set component diagnostic, not an untouched holdout or the
official QASPER answer/evidence F1 task. Complete Pipeline 2 validation still
requires an approved report–rubric dataset, rubric labels, and human scoring.
