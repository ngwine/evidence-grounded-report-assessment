# PAN-PC-11 BM25 chunking pilot — preliminary result

Date: 2026-09-27  
Result class: component diagnostic, not a full-corpus or official PAN score

## Question

With the same queries, candidate source documents and BM25 parameters, does
structure-aware chunking retrieve the gold source document better than a
fixed-token-window baseline?

This experiment covers the source-retrieval stage of Pipeline 1. It does not
evaluate text alignment, plagiarism classification or Pipeline 2 assessment.

## Locked protocol

- Source: PAN-PC-11 external-detection corpus, Zenodo record `3250095`.
- Rights basis: the provider permits free research use; redistribution is not
  assumed. The internal dataset review recorded in Dataset Mapping approved
  this retrieval experiment.
- Sampling seed: `20260923`.
- Positive annotations: 30, selected deterministically from 49,620 valid
  annotations.
- Candidate source documents: 200 = 30 relevant + 170 distractors.
- Query unit: annotated suspicious-span windows of at most 256 Unicode word
  tokens, stride 128.
- Evaluation units: 320 query windows from 30 parent annotations.
- Target: source document.
- BM25: `k1=1.2`, `b=0.75`.
- Fixed-window baseline: 256 tokens, stride 128; 62,430 candidate chunks.
- Structure-aware variant: paragraph-aware chunks, maximum 1,200 characters;
  49,152 candidate chunks.
- Cutoffs: 1, 5, 10, 20 and 100.

Configuration:
`research/configs/retrieval/pan-pc-11-bm25-chunking-pilot-v1.json`.

## Primary result: query-window level

| Method | Recall@1 | Recall@5 | Recall@10 | Recall@20 | Recall@100 | MRR@100 | nDCG@100 | Retrieval time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed-window BM25 | **0.5688** | **0.6531** | **0.6906** | **0.7375** | **0.8562** | **0.6112** | **0.6596** | 267.94 s |
| Structure-aware BM25 | 0.5094 | 0.5906 | 0.6406 | 0.6844 | 0.8250 | 0.5498 | 0.6027 | **161.02 s** |
| Fixed minus structure | +0.0594 | +0.0625 | +0.0500 | +0.0531 | +0.0312 | +0.0614 | +0.0569 | +106.92 s |

Fixed-window construction took an additional 2.24 seconds. Total run duration,
including validation, loading, evaluation and artifact writing, was 431.34
seconds on an Apple arm64 machine with 10 logical CPUs and 16 GiB RAM.

## Parent-annotation diagnostic

Overlapping windows from the same annotation are correlated, so the 320 query
windows must not be presented as 320 independent samples. As a secondary view,
the best gold-source rank across the windows of each of the 30 parent
annotations was calculated:

| Method | Any-window Recall@1 | Recall@5 | Recall@20 | Best-window MRR |
| --- | ---: | ---: | ---: | ---: |
| Fixed-window BM25 | **1.0000** | **1.0000** | 1.0000 | **1.0000** |
| Structure-aware BM25 | 0.8667 | 0.9667 | 1.0000 | 0.8976 |

Fixed-window BM25 achieved a better best rank for 4 annotations, a worse rank
for 0 and the same rank for 26. The four differences occurred on relatively
long annotated spans (2,714–21,501 characters). This any-window aggregation is
optimistic and is included only to avoid treating overlapping windows as
independent observations; it is not the primary metric.

## Interpretation

The preliminary result does **not** support the assumption that the current
structure-aware chunker improves lexical source retrieval. Fixed windows were
more accurate at every measured cutoff, while structure-aware BM25 was about
40% faster in the retrieval stage and used about 21% fewer candidate chunks.

A plausible explanation is protocol alignment: queries are themselves
256-token windows, and the fixed baseline uses the same window size with 50%
overlap. It therefore has a better chance of retaining a near-exact lexical
match. Paragraph-aware chunks are shorter on average (163 versus 256 tokens),
do not overlap and can split long matching passages across several chunks.
This is a hypothesis for error analysis, not yet a causal conclusion.

## Boundaries of the claim

- The experiment uses an oracle annotated suspicious span, not a full
  suspicious report. It is a controlled source-retrieval diagnostic.
- It uses only 30 annotations and 200 candidate documents, not all PAN-PC-11.
- It evaluates BM25 only; Dense retrieval and Hybrid RRF have not run yet.
- Query windows from one annotation overlap and are not statistically
  independent.
- It does not compute official PAN text-alignment or PlagDet measures.
- A realistic follow-up must query full suspicious documents or independently
  generated sliding windows and aggregate their rankings.

## Reproducibility record

- Git commit: `afeaac480f073f98ce110580e2741325becf09f8`.
- Dataset manifest SHA-256:
  `a167b4154a7205aa749d0e3a9bd99ac4685138d60f354dd5d7d00f11bfc0d875`.
- Config SHA-256:
  `49fa099e07f5b4f0584134de2247f407ebdf5dba979c9c808f75b6b9d6c4ed1c`.
- Metrics SHA-256:
  `ef54bcf0f2a302c14bbb322b8c2b2a4ac76f90d2955b84b8483954af032bdb9f`.
- Predictions SHA-256:
  `736a24a0533e78d9f97d0d51cbe139c2566107634e68421c956e4b1f5a000457`.
- Run-manifest SHA-256:
  `5788a0a5f892a28ff35d5a63b4a9a50200e57cc9a19ad4823aa221c479b3134b`.

The run manifest reports a clean tracked diff. Its generic `dirty` flag is true
only because unrelated, untracked local files existed in the worktree; their
content hash was recorded and they were not part of the experiment code.
