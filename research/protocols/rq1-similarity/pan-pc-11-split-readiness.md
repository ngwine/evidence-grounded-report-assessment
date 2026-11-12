# PAN-PC-11 derived split readiness record

Date: 2026-10-12

## Scope

This record covers dataset derivation only. No governance decision was made and
no retrieval, reranking, classification, or model-selection experiment was run
on DEV1 or TEST0.

The existing 30-parent pilot is retained as DEV0. DEV1 and TEST0 were derived
from the same verified PAN-PC-11 external-detection extraction with explicit
prior-manifest exclusions. Generated JSONL packs remain under ignored `var/`;
this document records only counts and cryptographic evidence, not corpus text,
labels, IDs, or document paths.

## Frozen split policy

- DEV0 seed: `20260923` (existing diagnostic split).
- DEV1 seed: `20261012`; excludes DEV0.
- TEST0 seed: `20261013`; excludes DEV0 and DEV1.
- Per split budget: 30 parent annotations and 200 source candidates.
- Exclusion policy: `prior-derived-split-disjoint-v1`.
- Leakage groups: parent annotation ID, suspicious-document reference, and
  every source-document reference in earlier candidate pools.
- TEST0 is sealed: it must not be used to choose a model, threshold, fusion
  weight, candidate depth, chunking strategy, or prompt.

Before applying exclusions, the converter verifies that every prior manifest
belongs to the same dataset and metadata inventory. It also verifies the
declared SHA-256 and record count of the prior `documents.jsonl` and
`queries.jsonl`. Any mismatch aborts conversion.

## Derived artifact inventory

| Split | Local ignored pack | Parents | Query windows | Candidate sources | Chunks | Governance |
|---|---|---:|---:|---:|---:|---|
| DEV0 | `var/datasets/derived/similarity/pan-pc-11-pilot-v1` | 30 | 320 | 200 | 49,152 | APPROVED (pre-existing) |
| DEV1 | `var/datasets/derived/similarity/pan-pc-11-dev1-v1` | 30 | 207 | 200 | 47,523 | PENDING |
| TEST0 | `var/datasets/derived/similarity/pan-pc-11-test0-v1` | 30 | 314 | 200 | 49,541 | PENDING |

The query-window totals differ because parent annotations have different
lengths. The sampling unit remains the parent annotation, not an individual
window.

Manifest SHA-256 at derivation time:

- DEV0: `a167b4154a7205aa749d0e3a9bd99ac4685138d60f354dd5d7d00f11bfc0d875`
- DEV1: `6c1153ae9575cc5800c9a2596827fd216040f794d4adb0e6a2598a8621203d06`
- TEST0: `416f12734d35ece6e03e1aad04daf30c22dfde8a035515e78c76bce258d0002a`

## Exclusion accounting

DEV1 loaded one prior manifest: 30 parent IDs, 30 suspicious documents, and
200 candidate source documents. From 49,620 available positive annotations,
1,591 matched at least one prior leakage group, leaving 48,029 eligible before
the seeded 30-parent selection. All 200 prior candidate sources were removed
from the new candidate pool.

TEST0 loaded two prior manifests: 60 parent IDs, 60 suspicious documents, and
400 candidate source documents. From 49,620 available positive annotations,
2,842 matched at least one prior leakage group, leaving 46,778 eligible before
the seeded 30-parent selection. All 400 prior candidate sources were removed
from the new candidate pool.

Reason-specific annotation counts overlap and therefore do not sum to the
unique excluded total. Exact per-rule counts and union checksums are stored in
each ignored `dataset-manifest.json`.

## Pairwise disjointness check

| Split pair | Parent-ID overlap | Suspicious-document overlap | Candidate-source overlap |
|---|---:|---:|---:|
| DEV0 / DEV1 | 0 | 0 | 0 |
| DEV0 / TEST0 | 0 | 0 | 0 |
| DEV1 / TEST0 | 0 | 0 | 0 |

This is stronger than checking qrel source documents alone: distractors from an
earlier candidate pool also cannot reappear in a later candidate pool.

## Implementation and verification status

- Converter content SHA-256:
  `0a60e6daec5b849fb5c460abe1828f16cc2438c8d004e691c5aa3124f26c0d13`.
- Base commit recorded during derivation:
  `bb1838f6958caef4958a625ee9aed45dfb7d2a62`.
- Focused converter tests: 14 passed, including deterministic three-way split,
  pairwise leakage checks, repeatable CLI exclusions, checksum tamper failure,
  and corpus-fingerprint mismatch failure.
- Complete research test suite in `.venv-research`: 71 passed.

The derivation manifests honestly record `converter_provenance.git_dirty=true`
because the exclusion implementation had not yet been committed. After this
implementation is merged, regenerate DEV1 and TEST0 with `--overwrite`, rerun
the disjointness check, and update the manifest hashes above before treating
them as experiment inputs.

DEV1 and TEST0 are currently ready for governance review, not for model runs.
A real reviewer must record rights basis, classification/PII decision,
retention, approver, and approval date. The offline runner must continue to
fail closed while either manifest is `PENDING`.
