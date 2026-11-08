# Controlled A5/A6 short-evidence comparison

Run: `pan-pc-11-short-evidence-dev1-v1-20261028T094748124172Z-2d899392c5`; classification: `COMPONENT_DIAGNOSTIC`; role: `DEV1_CONTROLLED_INPUT_CONSTRUCTION`.

| Method | Parent Recall@10 [95% CI] | MRR@10 [95% CI] | nDCG@10 [95% CI] | Candidate R@100 |
|---|---|---|---|---|
| A5 | 0.772928 [0.658137, 0.881043] | 0.629272 [0.490790, 0.766427] | 0.662579 [0.532554, 0.791411] | 1.000000 |
| A6 | 0.738360 [0.625872, 0.844153] | 0.627040 [0.495319, 0.757329] | 0.653272 [0.529669, 0.775030] | 1.000000 |

A6 minus A5 (paired parent resampling):
- recall_at_10: -0.034568 [-0.102758, 0.036920]
- mrr_at_10: -0.002232 [-0.040760, 0.031261]
- ndcg_at_10: -0.009307 [-0.047053, 0.024747]

| Method | Scored support requests | Truncated | Policy query crop | Policy passage crop | Policy repair | Max visible tokens |
|---|---:|---:|---:|---:|---:|---:|
| A5 | 20700 | 19742 | 0 | 0 | 0 | 512 |
| A6 | 20700 | 0 | 19700 | 19359 | 1498 | 452 |

Counts are scored support requests, including exact-pair cache reuse. Policy crop/repair columns describe A6 preprocessing only; A5 zeros do not imply that longest-first model truncation preserved all query or passage tokens.

Shared model and exact-pair cache: sequential method times are not independent cold latency.

Input-construction comparison; cannot isolate truncation alone or establish end-to-end plagiarism/assessment accuracy.

## Interpretation

The shorter-input policy removed additional model truncation but did not improve early
source retrieval in this development comparison. Parent-balanced Recall@10
fell from 0.772928 to 0.738360, a difference of −3.4568 percentage points
(95% paired interval −10.2758 to +3.6920 points). The interval includes zero;
this sample establishes neither an improvement nor a reliable degradation.
MRR@10 and nDCG@10 also have lower point estimates, with intervals crossing
zero. There is no basis here to replace A5 with A6 as an improved method.

A6 combines query-prefix trimming and lexical passage-window selection.
Eliminating model truncation does not establish that more useful evidence
was retained. Further diagnosis must distinguish those transformations in a
new protocol rather than retune this reported run. Candidate Recall@100 stays
identical because the top-50 head is reordered and the complete tail is kept.
Neither method evaluates no-source rejection or end-to-end plagiarism accuracy.

## Protocol and audit

- [Frozen protocol](../../research/protocols/rq1-similarity/short-evidence-dev1-v1.md)
- [Locked config](../../research/configs/retrieval/pan-pc-11-short-evidence-dev1-v1.json)
- [Preparation record](pan-pc-11-short-evidence-dev1-readiness-2026-10-28.md)
- DEV1: 30 parents, 207 query windows, 200 source documents; disjoint from DEV0
  in parent, suspicious-document and complete candidate-source pools.
- TEST0 remains sealed and has not been scored or used to choose the policy.
- Actual model inference; no injected scorer/encoder. The run completed with
  a clean tracked and untracked Git state.
- Audit passed identical candidates, upstream ranks, scored-head/unscored-tail
  membership, support IDs and provenance. Input/artifact hashes were checked.
- Paired parent-cluster bootstrap: 10,000 draws, seed 20261028, type-7
  percentile 95% intervals. DEV1 is a development comparison, not holdout proof.
- Both methods use 20,700 support requests. A5 truncates 19,742 (95.37%); A6
  truncates 0, with maximum visible pair length 452 tokens (A5 maximum 512).

## Reproduction and artifact identity

Run the frozen config from the clean experiment checkout. Keep raw corpus
text and predictions under ignored local storage; this note reports aggregates.
From the frozen checkout, set `KLTN_ROOT` to the original workspace containing
the private `var/` artifacts. The comparison renderer consumes the completed
run and exact DEV1 queries:

```bash
KLTN_ROOT=/absolute/path/to/KLTN
python -m research.offline_retrieval.analysis.short_evidence_comparison \
  --run-dir "$KLTN_ROOT/var/paper/short-evidence-2026-10-28/dev1-run" \
  --queries "$KLTN_ROOT/var/datasets/derived/similarity/pan-pc-11-dev1-v2-clean/queries.jsonl" \
  --output "$KLTN_ROOT/var/paper/short-evidence-2026-10-28/short-evidence-dev1-comparison.md"
```

- Commit: `2a8c073072ba41af8f05c79e75124aeef833f0d3`
- Config SHA-256: `2d899392c5cf6399eb4b31756d06200574aa6ce17adb68091818b2d4e439ba52`
- Run manifest SHA-256: `d03cc88e8a03c1ebbc7dc533a99e90337f6522bbc5f63d5afcc8fc0a2b067f0b`
- Metrics SHA-256: `8d3b7947cbbcff966fdf94aff23a4a795fe8bd702557d17cfe24714f99e18180`
- Predictions SHA-256: `096f282cd7f673b71ad6d25ea9c4abd6dd499271492e17f71a3ced3766ade2bc`
- DEV1 manifest SHA-256: `75837eb9af004f8e4bb361fe42d7fbb3ccb69e9aeb4b8e604941a8d76c2b3010`
- Recorded duration: 4322.00s; shared Cross-Encoder stage: 2625.83s. These are execution records, not independent latency comparisons.
