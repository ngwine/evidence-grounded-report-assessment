# DEV1 controlled comparison: shorter Cross-Encoder inputs

Protocol version: `short-evidence-dev1-v1`, prepared 28/10/2026 before DEV1
model outputs are inspected. This is a development comparison for the faculty
paper, not a final holdout result. DEV0 results remain frozen.

## Question and primary contrast

Does deterministic, token-bounded input construction change source-document
ranking compared with A5's full query/support input and model truncation?
The primary contrast is **A6 minus A5**, using parent-balanced Recall@10.
A6 may improve, tie or degrade performance; all outcomes are retained.

A1–A5 remain the original baselines. A6 uses exactly the same candidate lists,
pre-rerank ordering, top-50 documents, per-view support passage IDs, checkpoint,
raw-logit output and maximum-support pooling as A5. It only changes the strings
visible to the Cross-Encoder within those fixed pairs. It never uses a gold
source span, qrel, relevance label or holdout result to construct an input.

## Locked configuration

- Dataset: new `pan-pc-11-dev1-v2-clean`, 30 parent annotations, 207 query
  windows and 200 candidate source documents; positive-only oracle-span task.
- Baselines: fixed-window BM25, structure-aware Dense, RRF, Dense+CE and RRF+CE.
- Dense: multilingual E5-small revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`, CPU, batch 16.
- CE: mMARCO mMiniLMv2 L12 H384 revision
  `1427fd652930e4ba29e8149678df786c240d8825`, CPU, batch 8, maximum length 512.
- BM25: k1=1.2, b=0.75; fixed view: 256 word tokens, stride 128.
- Candidate depth: 100 per view; RRF k=60; rerank top 50; preserve unscored tail.
- Input policy: `lexical_window_v1`, query prefix up to **192 model tokens**,
  one contiguous support-passage window up to **256 model tokens**.
- Seed: 20261012. No budget sweep, checkpoint search or DEV0 retuning is part
  of this comparison. Any later method change requires a new protocol/config.

The config is
[`pan-pc-11-short-evidence-dev1-v1.json`](../../configs/retrieval/pan-pc-11-short-evidence-dev1-v1.json).

## Input construction

1. Use the exact fast tokenizer belonging to the locked CE, with character
   offsets and no truncation, to inspect each existing query/support pair.
2. Preserve a query that fits; otherwise retain its earliest token-bounded
   prefix within the query budget.
3. From the visible query, take case-folded whole-word terms of at least two
   characters. Choose one passage token window maximizing the number of
   distinct matching whole query terms. Resolve ties at the earliest position.
   No additional model, reference answer or gold annotation is consulted.
4. Crop the original strings using tokenizer offsets, never decode token IDs
   into a replacement text. If re-tokenizing a boundary fragment exceeds a
   per-leg budget, shorten its end deterministically until it fits; record
   this repair. The passage start and chosen support ID remain fixed.
5. Tokenize the actual resulting pair again. Unsupported offsets or a pair
   still exceeding the configured budget fail the stage. No hidden fallback
   to a different policy is allowed.
6. Submit one pair per existing support and keep A5's maximum pooling. Store
   original/cropped hashes, relative character ranges, token counts, crop and
   repair flags, and actual model tokenization diagnostics.

This is one **input-construction policy** contrast. Query-prefix trimming and
lexical passage-window selection are both parts of that policy. A result
cannot isolate the causal effect of truncation alone or separately establish
which of those two transformations caused a ranking change.

Original source spans retain their meaning as candidate-passage provenance.
After cropping, they are not automatically labelled model-visible. Selected
character ranges are relative to pair strings; raw-document spans require a
separately verified mapping.

## Dataset preparation and execution gate

DEV1 and TEST0 were regenerated in a clean checkout of commit `d6cec84`, using
the committed converter with SHA
`0a60e6daec5b849fb5c460abe1828f16cc2438c8d004e691c5aa3124f26c0d13`.
Original packs and their manifests remain untouched. The new packs still need
explicit per-pack handling decisions before being marked approved; no identity,
PII decision or retention term is inferred from the earlier DEV0 approval.

Before a scientific run:

- Verify provider archive checksums, generated file hashes and split exclusion
  records. Check pairwise parent, suspicious-document and complete source-pool
  disjointness, using metadata only for TEST0.
- Complete the existing per-pack manifest fields and approval evidence with
  the actual responsible person's decision. The existing runner continues to
  reject `PENDING` manifests; no bypass flag is introduced.
- Freeze the implementation/config in an isolated clean commit. Record the
  exact config, model and input hashes with every run. Test doubles belong
  only in synthetic software checks and must never be reported as model results.

TEST0 remains sealed while DEV1 is used for method development. No TEST0
model inference or label inspection is authorized by this DEV1 protocol.
After DEV1 review, lock the final comparison and record a separate TEST0
execution decision. A negative/no-source cohort is needed only if the paper
extends its claims to precision, rejection or false positives.

## Metrics and reporting

Primary: parent-balanced Recall@10. Secondary: parent-balanced MRR@10 and
nDCG@10; candidate Recall@100; query-window macro metrics; actual truncation,
crop and input-repair rates. Resample parent annotations, not correlated query
windows, for paired intervals (10,000 draws, seed 20261028, 95% type-7 percentile).

The report must verify that A5/A6 candidate membership, pre-rerank positions,
head/tail partition and support IDs match. Candidate Recall@100 must therefore
remain identical. Report actual visible token counts and withheld raw-span
mappings rather than assuming the original full passage was scored.

Pair memoization is shared, so sequential A4/A5/A6 stage timings are not
independent cold-run latency measurements. Report actual inference/cache counts
and shared-stage wall time; a separate fixed cold/warm benchmark is needed for
latency claims. Do not reinterpret the historical DEV0 suspension interval as
runtime for this method.

## Reproduction after the gate passes

Run from the clean experiment checkout, using the existing research environment
and absolute paths for the approved pack and model cache:

```bash
HF_HOME=/Users/ngwii/KLTN/var/models/hf-home \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
/Users/ngwii/KLTN/.venv-research/bin/python -m research.offline_retrieval run \
  --dataset-manifest /Users/ngwii/KLTN/var/datasets/derived/similarity/pan-pc-11-dev1-v2-clean/dataset-manifest.json \
  --config research/configs/retrieval/pan-pc-11-short-evidence-dev1-v1.json \
  --output-dir /Users/ngwii/KLTN/var/paper/short-evidence-2026-10-28/dev1-run
```

Use a fresh output directory for each attempt. Raw corpus files stay under
ignored `var/`; the faculty paper receives derived tables and audited claims,
not redistributed PAN source text.
