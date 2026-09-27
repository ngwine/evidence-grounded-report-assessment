# PAN-PC-11 source-retrieval pilot v1

## Role

This pack uses every annotated suspicious span as one query and retrieves its
source document from a candidate corpus. Chunk rankings are collapsed to unique
source documents before RRF and Recall/MRR/nDCG. It is a controlled diagnostic
for the thesis retrieval pipeline, not a reproduction of an official PAN task.

On the 16 GB development machine, v1 is explicitly a deterministic bounded
pilot: annotations and distractor source documents are hash-selected with a
locked seed, while every relevant source for a selected query is retained. The
manifest must record the sampler and candidate-pool composition. It must not be
reported as a full PAN-PC-11 corpus score.

The official corpus source is Webis/PAN-PC-11, archived as Zenodo record
`3250095`. The record states that the corpus may be used free of charge for
research purposes, but it does not declare an SPDX/Creative Commons license.
The pilot therefore records a research-use statement and does not assume
redistribution rights. The two provider MD5 values are locked in the manifest
template; conversion must additionally record local SHA-256. Do not commit the archive,
extracted text or derived JSONL. Store them below:

```text
var/datasets/raw/pan-pc-11/v1/
var/datasets/derived/similarity/pan-pc-11-source-retrieval-pilot-v1/
```

## Required gate

Before conversion results may run:

1. verify download provenance and local SHA-256;
2. document the applicable research-use terms/license;
3. record the derived split and leakage grouping;
4. record retention, approver and approval date;
5. change `governance.status` only through review.

`dataset-manifest.template.json` deliberately remains `PENDING`. The converter
generates the same state with real file checksums, document/query IDs and
conversion lineage.
