# PAN pilot runbook v1

Run one official split at a time. Raw archives, extracted text, generated JSONL,
model weights and experiment outputs stay under ignored `var/` or
`research/results/`; none belongs in Git.

## 1. Verify the source archive

PAN-PC-11 uses a **single multipart RAR archive** split into `.part1.rar` and
`.part2.rar`; these are volumes, not two corpus splits. Put both files in the
same directory, compare both MD5 values with the manifest template, record
local SHA-256, then extract starting from `.part1.rar`. Point the converter at
the complete `external-detection-corpus`; intrinsic-detection data is outside
this pilot. Never convert a numbered archive volume or a single corpus
`partN` as though it were an independent candidate corpus: PAN references can
cross those directories.

PAN13 Text Alignment uses
`pan13-text-alignment-test-and-training.zip`. Verify provider MD5
`fec7fca7a82193a97fbb97cde7781b63` and compute SHA-256 locally. Extract the
outer ZIP and then its training/test2 ZIPs. Do not combine official partitions.

Example checksum commands on macOS:

```bash
md5 /path/to/archive
shasum -a 256 /path/to/archive
```

## 2. Convert one extracted split

PAN-PC-11:

```bash
./.venv/bin/python -m research.pan_pilot \
  --dataset pan-pc-11 \
  --input-root var/datasets/raw/pan-pc-11/v1/extracted-unar/pan-plagiarism-corpus-2011/external-detection-corpus \
  --output-dir var/datasets/derived/similarity/pan-pc-11-pilot-v1 \
  --dataset-version zenodo-3250095-v1-external-derived-pilot \
  --split-name hash-grouped-derived-pilot \
  --max-annotations 30 \
  --max-candidate-documents 200 \
  --seed 20260923 \
  --source-archive var/datasets/raw/pan-pc-11/v1/pan-plagiarism-corpus-2011.part1.rar \
  --source-archive var/datasets/raw/pan-pc-11/v1/pan-plagiarism-corpus-2011.part2.rar
```

This is a resource-bounded feasibility pilot for the 16 GB development
machine, not a full-corpus PAN-PC-11 score. The converter records the sampler,
seed, selected IDs/candidate pool and archive lineage. Full-corpus evaluation
requires a streaming/inverted BM25 index and batched vector index rather than
the in-memory reference runner.

### Derive leakage-safe DEV1 and sealed TEST0

Keep the existing 30-parent pack as `DEV0`. Derive `DEV1` with seed `20261012`
while excluding DEV0, then derive `TEST0` with seed `20261013` while excluding
both earlier manifests. The exclusion applies to parent annotations,
suspicious documents, positive source documents, and the complete prior
candidate pools (including distractors).

```bash
./.venv/bin/python -m research.pan_pilot \
  --dataset pan-pc-11 \
  --input-root var/datasets/raw/pan-pc-11/v1/extracted-unar/pan-plagiarism-corpus-2011/external-detection-corpus \
  --output-dir var/datasets/derived/similarity/pan-pc-11-dev1-v1 \
  --dataset-version zenodo-3250095-v1-external-derived-pilot \
  --split-name DEV1-leakage-safe \
  --max-positive-annotations 30 \
  --max-candidate-documents 200 \
  --seed 20261012 \
  --source-archive var/datasets/raw/pan-pc-11/v1/pan-plagiarism-corpus-2011.part1.rar \
  --source-archive var/datasets/raw/pan-pc-11/v1/pan-plagiarism-corpus-2011.part2.rar \
  --exclude-manifest var/datasets/derived/similarity/pan-pc-11-pilot-v1/dataset-manifest.json

./.venv/bin/python -m research.pan_pilot \
  --dataset pan-pc-11 \
  --input-root var/datasets/raw/pan-pc-11/v1/extracted-unar/pan-plagiarism-corpus-2011/external-detection-corpus \
  --output-dir var/datasets/derived/similarity/pan-pc-11-test0-v1 \
  --dataset-version zenodo-3250095-v1-external-derived-pilot \
  --split-name TEST0-leakage-safe \
  --max-positive-annotations 30 \
  --max-candidate-documents 200 \
  --seed 20261013 \
  --source-archive var/datasets/raw/pan-pc-11/v1/pan-plagiarism-corpus-2011.part1.rar \
  --source-archive var/datasets/raw/pan-pc-11/v1/pan-plagiarism-corpus-2011.part2.rar \
  --exclude-manifest var/datasets/derived/similarity/pan-pc-11-pilot-v1/dataset-manifest.json \
  --exclude-manifest var/datasets/derived/similarity/pan-pc-11-dev1-v1/dataset-manifest.json
```

Both new manifests intentionally remain `PENDING`; a real reviewer must finish
the governance gate before any runner invocation. TEST0 stays sealed until the
method and configuration have been frozen on DEV1. Current split audit evidence
is recorded in
`research/protocols/rq1-similarity/pan-pc-11-split-readiness.md`.

PAN13 Text Alignment component diagnostic:

```bash
./.venv/bin/python -m research.pan_pilot \
  --dataset pan13 \
  --input-root var/datasets/raw/pan13-text-alignment/v1/training \
  --output-dir var/datasets/derived/similarity/pan13-training-component-v1 \
  --dataset-version zenodo-3715980-training-2013-01-21 \
  --split-name official-training-derived \
  --source-archive var/datasets/raw/pan13-text-alignment/v1/pan13-text-alignment-test-and-training.zip
```

The command writes `documents.jsonl`, `chunks.jsonl`, `queries.jsonl`,
`qrels.jsonl` and `dataset-manifest.json`. Output is deterministic for identical
input, options and converter version.

## 3. Complete the governance gate

The generated manifest intentionally has `governance.status=PENDING`. Review
and record:

- archive provenance, provider checksum and local SHA-256;
- license/terms and allowed purpose;
- candidate/query split and leakage grouping;
- PII/classification and retention;
- approver and approval date.

Only a real reviewer may change the status to `APPROVED`. Never fill a fake
approver merely to make the validator pass.

## 4. Cache the locked Dense model

Create the separate Python 3.12 research environment described in the runner
README. Cache exactly this immutable Hugging Face revision:

```text
model: intfloat/multilingual-e5-small
revision: 614241f622f53c4eeff9890bdc4f31cfecc418b3
```

The runner uses `local_files_only=True` and will not silently download or move
to another revision during an experiment.

## 5. Validate, then run

PAN-PC-11:

```bash
./.venv-research/bin/python -m research.offline_retrieval validate \
  --dataset-manifest var/datasets/derived/similarity/pan-pc-11-pilot-v1/dataset-manifest.json \
  --config research/configs/retrieval/pan-pc-11-pilot-v1.json

./.venv-research/bin/python -m research.offline_retrieval run \
  --dataset-manifest var/datasets/derived/similarity/pan-pc-11-pilot-v1/dataset-manifest.json \
  --config research/configs/retrieval/pan-pc-11-pilot-v1.json \
  --output-dir research/results/rq1-pan-pc-11/run-001
```

For PAN13, use `pan13-component-pilot-v1.json`. Report its result only as a
positive span-retrieval component diagnostic. It excludes empty no-plagiarism
XML and does not compute official alignment Precision/Recall/Granularity/
PlagDet.

## 6. Acceptance checklist

- validator passes without bypass flags;
- manifest records clean commit, dataset/config/model versions and hardware;
- four methods run on the identical corpus/query/qrel split;
- prediction and metric artifact checksums are stored;
- PAN-PC-11 rankings contain unique source documents;
- manifest identifies the deterministic query/candidate sampling policy; no
  resource-bounded pilot number is called a full-corpus result;
- two repeated runs produce byte-identical predictions/metrics;
- errors and limitations are written before selecting the final framework.
