# PAN pilot runbook v1

Run one official split at a time. Raw archives, extracted text, generated JSONL,
model weights and experiment outputs stay under ignored `var/` or
`research/results/`; none belongs in Git.

## 1. Verify the source archive

PAN-PC-11 uses two RAR archives. Compare their MD5 values with
`pan-pc-11-source-retrieval-pilot-v1/dataset-manifest.template.json`, then
record local SHA-256. Point the converter only at the external-detection
corpus; intrinsic-detection data is outside this pilot.

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
  --input-root var/datasets/raw/pan-pc-11/v1/external-part1 \
  --output-dir var/datasets/derived/similarity/pan-pc-11-part1-pilot-v1 \
  --dataset-version zenodo-3250095-v1-external-part1 \
  --split-name derived-external-part1
```

PAN13 Text Alignment component diagnostic:

```bash
./.venv/bin/python -m research.pan_pilot \
  --dataset pan13 \
  --input-root var/datasets/raw/pan13-text-alignment/v1/training \
  --output-dir var/datasets/derived/similarity/pan13-training-component-v1 \
  --dataset-version zenodo-3715980-training-2013-01-21 \
  --split-name official-training-derived
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
  --dataset-manifest var/datasets/derived/similarity/pan-pc-11-part1-pilot-v1/dataset-manifest.json \
  --config research/configs/retrieval/pan-pc-11-pilot-v1.json

./.venv-research/bin/python -m research.offline_retrieval run \
  --dataset-manifest var/datasets/derived/similarity/pan-pc-11-part1-pilot-v1/dataset-manifest.json \
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
- two repeated runs produce byte-identical predictions/metrics;
- errors and limitations are written before selecting the final framework.
