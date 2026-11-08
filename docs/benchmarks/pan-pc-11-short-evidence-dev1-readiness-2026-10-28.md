# PAN-PC-11 short-evidence follow-up: preparation and execution record

Updated 28/10/2026. The controlled A5/A6 comparison completed and passed its
artifact audit. See [the result](pan-pc-11-short-evidence-dev1-result.md).

## Method snapshot

- Branch: `experiment/w7-2-short-evidence-dev1`.
- Local commit: `2a8c073072ba41af8f05c79e75124aeef833f0d3`.
- Isolated checkout: `var/worktrees/paper-followup-20261028`; clean at launch.
- [Protocol](../../research/protocols/rq1-similarity/short-evidence-dev1-v1.md)
  and [config](../../research/configs/retrieval/pan-pc-11-short-evidence-dev1-v1.json)
  were prepared before inspecting DEV1 model results.
- A1–A5 remain unchanged. A6 keeps A5's candidate pool, support IDs, rerank
  depth, checkpoint and max pooling. The changed factor is visible input
  construction: query prefix up to 192 model tokens and one lexical support
  window up to 256 tokens, verified with the exact tokenizer.
- Cropped strings retain relative character ranges and hashes. Full original
  raw spans are not relabelled as model-visible. Gold source spans are not
  available to input construction.

## New pack checks

The original DEV0, DEV1-v1 and TEST0-v1 packs remain intact. New v2 packs were
regenerated from clean converter commit `d6cec84`; converter SHA matches the
historical exclusion implementation.

| Pack | Parent annotations | Query windows | Candidate sources | Chunks | Current state |
|---|---:|---:|---:|---:|---|
| DEV1-v2-clean | 30 | 207 | 200 | 47,523 | Approved; model run and paired artifact audit completed |
| TEST0-v2-clean | 30 | 314 | 200 | 49,541 | Approved handling metadata; sealed, no model run |

All three pairs DEV0/DEV1, DEV0/TEST0 and DEV1/TEST0 have zero overlap in
parent annotations, suspicious-document references and the complete candidate
source pool. This was computed from an automated metadata-only projection;
TEST0 text, labels and model results were not inspected to choose a method.
Provider archive hashes, all generated file hashes and the exclusion chain
were checked. Exact hashes and local approval evidence remain under ignored
`var/paper/short-evidence-2026-10-28/`.

The user authorized the work and identified themself as the responsible
approver. The record names project owner Nguyễn Trần Ngọc Quý and retains
the actual conversation authorization. PII handling is conservative:
`contains_pii=true` denotes potentially identifying public-corpus content,
not a certified absence of PII. Derived packs are restricted to local research
and given a 30-day retention/review term; provider archives retain their
separate pre-existing policy. No automatic deletion job is claimed.

Both manifests passed from `PENDING` to `APPROVED` only after this decision
was recorded. Before that change, the unchanged runner gate rejected both
packs before loading models. The pre-approval manifests were preserved so
TEST0's derivation reference to the original DEV1 manifest remains auditable.

## Software and model checks

- Full root research/backend suite before the final report-test addition:
  **724 passed, 21 skipped**.
- Focused experiment snapshot, including report/parent-bootstrap audits:
  **77 passed** in the isolated checkout.
- Complete research suite from the same isolated clean snapshot:
  **332 passed**.
- Three synthetic English/Vietnamese pairs were scored with the actual locked
  Cross-Encoder. All prepared pairs used 452 tokens and were not truncated.
  These are software/model smoke checks, not retrieval-accuracy measurements.
- Test coverage verifies unchanged A1–A5 outputs, identical A5/A6 candidate and
  support budgets, fixed tails, independence from qrel offsets, valid crop
  provenance, deterministic parent-cluster resampling and checksum failures.

## Execution and result

DEV1 completed from the clean snapshot with offline model loading and host
sleep prevention. Raw logs/results are retained under
`var/paper/short-evidence-2026-10-28/`. No DEV0 tuning or TEST0 inference is part
of this run. A failed attempt must be preserved; the runner refuses nonempty
output directories.

The comparison module verified artifact hashes, identical candidates,
supports and tails, and actual tokenizer diagnostics. A5 parent Recall@10
is 0.772928; A6 is 0.738360. The paired difference is -0.034568 with 95%
interval [-0.102758, 0.036920]. A6 needs no additional model truncation,
versus 19,742/20,700 support requests for A5, but does not demonstrate better
retrieval. No method replacement or further budget search follows this run.
Shared model/cache timings are not independent cold-run latency.

TEST0 can only be evaluated after DEV1 review and a frozen final comparison.
This is development evidence, not an untouched-holdout conclusion.
