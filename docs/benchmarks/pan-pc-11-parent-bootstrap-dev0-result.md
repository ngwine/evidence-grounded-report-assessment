# PAN-PC-11 DEV0 parent-cluster paired bootstrap

## Scope

This analysis adds uncertainty intervals to the **frozen DEV0** A1--A5 retrieval/reranking results. The 320 overlapping query windows are not treated as independent observations. Each metric is first averaged within its originating plagiarism annotation, and the 30 parent annotations are then sampled with replacement. The same parent draw is used for all methods and paired deltas.

This is a descriptive diagnostic on a development set, not a final holdout evaluation or a confirmatory significance test.

## Reproduction

```bash
python3 -m research.offline_retrieval.analysis.bootstrap_parent_metrics \
  --metrics research/results/rq1-pan-pc-11/cross-encoder-dev0-v1-27f11cf/metrics.json \
  --queries var/datasets/derived/similarity/pan-pc-11-pilot-v1/queries.jsonl \
  --repetitions 10000 --seed 20261012 \
  --output docs/benchmarks/pan-pc-11-parent-bootstrap-dev0-result.md
```

- Bootstrap repetitions: `10,000`
- Seed: `20261012`
- Confidence interval: `95.0%` percentile interval (Hyndman--Fan type 7 interpolation)
- Resampling unit: `parent_annotation`; parents: `30`; query windows: `320`
- Query windows per parent: `1`--`30`
- `metrics.json` SHA-256: `a7a3bbcce697cfb28ebd3d5c3f920f4135461b60a4b3e200babfec9fdb4b3b5b`
- `queries.jsonl` SHA-256: `23588a796caa67f388aaed7f968d5b152e67325e80fcb31fe9d7d858b0c82e19`

## Parent-balanced estimates

Each cell is `estimate [95% CI]`.

| ID | Method | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---:|---:|---:|
| A1 | `fixed_window_bm25` | 0.859448 [0.752672, 0.948444] | 0.811961 [0.689425, 0.916198] | 0.823249 [0.705860, 0.923481] |
| A2 | `structure_dense` | 0.821854 [0.703651, 0.924038] | 0.674234 [0.538614, 0.801623] | 0.709064 [0.580798, 0.828163] |
| A3 | `multiview_hybrid_rrf` | 0.829993 [0.715816, 0.927389] | 0.744346 [0.607105, 0.867774] | 0.764545 [0.634987, 0.880216] |
| A4 | `dense_cross_encoder` | 0.659673 [0.525184, 0.791495] | 0.442333 [0.315887, 0.572799] | 0.493598 [0.369729, 0.619265] |
| A5 | `multiview_hybrid_cross_encoder` | 0.755820 [0.625314, 0.871782] | 0.654963 [0.513021, 0.786845] | 0.679427 [0.541358, 0.805441] |

## Paired deltas

A positive value favors the method on the left. Each bootstrap draw uses the same sampled parent annotations for both methods.

| Contrast | Recall@10 | MRR@10 | nDCG@10 |
|---|---:|---:|---:|
| A2-A1 | -0.037595 [-0.153356, 0.067496] | -0.137728 [-0.255199, -0.023067] | -0.114184 [-0.224733, -0.006246] |
| A3-A2 | 0.008139 [-0.064445, 0.083056] | 0.070112 [-0.009824, 0.148847] | 0.055481 [-0.017223, 0.122706] |
| A4-A2 | -0.162181 [-0.284754, -0.047633] | -0.231900 [-0.338676, -0.130721] | -0.215467 [-0.320485, -0.115100] |
| A5-A3 | -0.074173 [-0.185462, 0.039556] | -0.089383 [-0.211145, 0.037474] | -0.085118 [-0.200945, 0.035713] |

## Interpretation

- A1 has the highest point estimate on all three parent-balanced Top-10 metrics in this DEV0 sample.
- A3 versus A2 has a small positive point delta, while A4 versus A2 and A5 versus A3 are negative. These intervals quantify the uncertainty among the 30 observed parent annotations; they do not turn the diagnostic into a final model-selection result.
- The paired construction preserves each parent annotation's method-by-method comparison. Resampling 320 windows independently would give long annotations excessive weight and understate dependence caused by overlap.

## Caveats

- DEV0 was used for diagnosis and must not be reused indefinitely for parameter tuning. An independently frozen DEV1/holdout is still required for confirmatory comparison.
- A percentile interval that excludes zero is **not reported as a significance claim** here. The experiment was not preregistered for hypothesis testing, no multiple-comparison correction is applied, and only 30 parent annotations are observed.
- Bootstrap uncertainty is conditional on this derived, resource-bounded positive-query sample. It does not capture corpus construction, model selection, or annotation uncertainty.
- The pilot contains queries with a known relevant source. It does not measure false positives, no-source cases, plagiarism-type classification, final span alignment, or document-level similarity percentages.
- A1 and A2 differ in both retrieval algorithm and chunk view, so their delta is not a single-factor causal estimate.
