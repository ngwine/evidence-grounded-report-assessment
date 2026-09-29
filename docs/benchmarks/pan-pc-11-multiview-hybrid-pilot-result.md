# PAN-PC-11 multi-view retrieval pilot — frozen result

Date: 2026-09-29
Result class: component diagnostic, not a full-corpus or official PAN score

## Research question

For Pipeline 1 source retrieval, does document-level Reciprocal Rank Fusion
(RRF) between fixed-window BM25 and structure-aware Dense retrieval improve
over either component alone?

The tested path is:

`query window → fixed-window BM25 + structure-aware E5 → per-view document aggregation → RRF(k=60) → Top-K source documents`

This experiment does not evaluate text alignment, plagiarism classification,
negative/no-match rejection or document-level plagiarism decisions.

## Locked protocol

- Dataset: PAN-PC-11 external-detection corpus, bounded deterministic pilot.
- Dataset version: `zenodo-3250095-v1-external-derived-pilot`.
- Seed: `20260923`.
- Evaluation set: 320 overlapping query windows from 30 positive parent
  annotations.
- Candidate corpus: 200 source documents.
- Candidate/final depth: 200/100 source documents.
- Fixed windows: 256 Unicode word tokens, stride 128.
- BM25: `k1=1.2`, `b=0.75`.
- Dense model: `intfloat/multilingual-e5-small`, immutable revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Dense prefixes: `query: ` and `passage: `.
- Fusion: unweighted RRF with `k=60`, after each view has retained its
  highest-scoring chunk per source document.
- Configuration:
  `research/configs/retrieval/pan-pc-11-multiview-hybrid-pilot-v1.json`.

## Query-window macro

Every query window has equal weight in this view.

| Method | R@1 | R@5 | R@10 | R@20 | R@100 | MRR@100 | nDCG@100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed-window BM25 | **0.5688** | 0.6531 | 0.6906 | 0.7375 | 0.8563 | **0.6112** | 0.6596 |
| Structure-aware Dense | 0.5406 | **0.6563** | **0.7563** | **0.8438** | 0.9750 | 0.6036 | **0.6784** |
| Multi-view RRF | 0.5469 | 0.6375 | 0.7125 | 0.7969 | **0.9844** | 0.6005 | 0.6748 |

Against Dense at Top-10, multi-view RRF rescued 22 queries but lost 36, for a
net loss of 14 hits. At Top-100 it rescued 7 and lost 4, for a net gain of 3.
The fusion therefore improved deep candidate coverage but did not improve
early ranking.

## Parent-balanced macro

The 30 parent annotations generate between 1 and 30 query windows; the five
largest parents account for 43.75% of all windows. To prevent those parents
from dominating the result, metrics were first averaged within each parent
and then averaged equally across parents.

| Method | R@1 | R@5 | R@10 | R@20 | R@100 | MRR@100 | nDCG@100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed-window BM25 | **0.7938** | **0.8369** | **0.8594** | 0.8793 | 0.9280 | **0.8147** | **0.8375** |
| Structure-aware Dense | 0.6218 | 0.7601 | 0.8219 | 0.8647 | **0.9902** | 0.6799 | 0.7422 |
| Multi-view RRF | 0.7073 | 0.7776 | 0.8300 | **0.9042** | 0.9843 | 0.7509 | 0.7973 |

The ordering changes under parent-balanced evaluation. This confirms that the
320 overlapping windows are not 320 independent cases and that model selection
must not rely on the query-window macro alone.

## Interpretation

Unweighted RRF improves deep coverage in the query-window macro, but that gain
does not hold in the parent-balanced macro and the current result does not
support selecting it as the final early-stage ranker. It improves query-window
Recall@100 over Dense by 0.0094, while reducing Recall@10 by 0.0438 and slightly
reducing MRR/nDCG. Under equal parent weight, fixed-window BM25 is strongest at
early cutoffs and Dense is strongest at Recall@100.

The next experiment should therefore expand and lock the parent-level holdout,
then analyse the Dense Top-10 losses before considering weighted fusion or a
reranker. RRF parameters must not be tuned repeatedly on these same 30 parent
annotations.

## Runtime

The frozen cold run took 1,826.87 seconds on an Apple M4 machine with 10 logical
CPUs and 16 GiB RAM:

- fixed-window construction: 2.92 s;
- fixed-window BM25: 308.73 s;
- structure-aware Dense: 1,509.41 s;
- RRF: 1.30 s.

## Reproducibility record

- Git commit: `02a3c4b42bffa8d49478c0dd7e6ee274fa2a524c`.
- Tracked Git state at run start: clean (`tracked_dirty=false`).
- Dataset manifest SHA-256:
  `a167b4154a7205aa749d0e3a9bd99ac4685138d60f354dd5d7d00f11bfc0d875`.
- Canonical resolved-config SHA-256:
  `82e38ad2679d3b47751d3331463f348c2958cdeaf1e54c22ab92c75928421715`.
- Config file SHA-256:
  `4c164fb39f4a154bf2100d1ebbb127751f3e2ee246ae4b39cc8bf084759793fd`.
- Predictions SHA-256:
  `b9821b08590b1a51bd5bef2fd61c8947312ec2cc353645246dd204df3ae03970`.
- Metrics SHA-256:
  `b9cba513e111d82b9b0df4d37820eff1792c58750e5e3cb7378e876f8c6c4162`.
- Run-manifest SHA-256:
  `74c5e3dc109aef1aea02f494c70101f622ca37285e6a5400fe850e15bb8ca23f`.
- Run ID:
  `pan-pc-11-multiview-hybrid-pilot-v1-20260929T060629041746Z-82e38ad267`.

The generic Git `dirty` flag is true only because unrelated local files were
untracked. The tracked diff hash is the SHA-256 of empty content, and the run
manifest records the untracked-content hash separately. A second run reproduced
the predictions byte-for-byte.
