# PAN13 span-retrieval component pilot v1

## Role

This pack converts each annotated suspicious span into an oracle query and uses
the annotated source span as its qrel. It tests whether the retrieval stack can
recover evidence spans under fixed-window, structure-aware BM25, Dense and
Hybrid+RRF configurations.

It **does not** implement the official PAN13 text-alignment task. Official
evaluation also requires pair-level alignment output, negative cases,
precision, recall, granularity and PlagDet. Numbers from this pack must be
reported only as component-diagnostic Recall/MRR/nDCG.

Keep data local:

```text
var/datasets/raw/pan13-text-alignment/v1/
var/datasets/derived/similarity/pan13-span-retrieval-oracle-pilot-v1/
```

The published outer archive contains separate training and test2 ZIP files.
After extraction, each split contains `src/`, `susp/`, a root `pairs` file and
category directories with per-pair XML. Convert one official split at a time;
do not merge training and test into one manifest. Empty no-plagiarism XML is
counted by conversion QA but excluded from this positive-qrel retrieval
diagnostic, because false-positive evaluation needs a separate protocol.

The template remains `PENDING` until rights, retention and approver/date are
confirmed. The official training/test partition must be preserved in separate
generated packs or recorded explicitly in the manifest.
