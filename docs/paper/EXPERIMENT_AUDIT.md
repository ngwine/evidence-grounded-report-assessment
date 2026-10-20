# Experiment audit for the English paper

Audit date: 2026-10-12

## What is supported by artifacts

- A frozen PAN-PC-11 `DEV0` component diagnostic exists for Pipeline 1.
- It contains 30 parent annotations, 320 correlated query windows, and 200
  candidate source documents.
- A1--A5 results are backed by predictions, metrics, a run manifest, immutable
  model revisions, dataset checksums, hardware/package metadata, and artifact
  checksums.
- The error analysis covers Dense-to-RRF Top-10 transitions, Cross-Encoder
  transitions, support-passage overlap, and token truncation.
- Parent-cluster paired bootstrap intervals are available for the parent-balanced
  Recall@10, MRR@10, and nDCG@10 estimates and for four prespecified method
  contrasts (10,000 resamples; 30 parent annotations; fixed seed 20261012).
- The parser/chunker implementation preserves stable identifiers, source spans,
  locators, and raw--normalized mappings.
- The bootstrap implementation has focused test coverage (`27 passed, 2
  skipped` in the relevant subset), and the locked PAN-PC-11 manifest/config
  pair passes the fail-closed validator.
- Leakage-safe split derivation now has a repeatable prior-manifest exclusion
  mechanism. The complete research suite passes (`71 passed`) after the
  bootstrap and split/exclusion changes.

## Integration status

- The A1--A5 implementation and report are on
  `experiment/w7-2-cross-encoder-ablation` at `bb1838f`.
- PR #13 is open and mergeable but has no review or CI check; the work is not
  yet on `main`.
- The parser golden benchmark (PR #10) and API contract (PR #7) are also still
  open. Their existence must not be presented as a merged release.
- Local DEV1 and TEST0 packs have been derived with zero pairwise overlap in
  parent annotation, suspicious document, and the entire candidate-source
  pool. They remain ignored local artifacts with governance `PENDING`; no
  model experiment has been run on either pack.
- Their manifests correctly record a dirty converter working tree. After the
  converter is reviewed and committed, both packs must be regenerated before
  governance approval or use by the fail-closed runner.

## Claims that must remain preliminary

- The reported PAN-PC-11 run is resource bounded, positive only, and uses
  oracle suspicious-span queries. It is not an official PAN result.
- It evaluates source-document retrieval and reranking, not suspicious-span
  discovery, text alignment, similarity-type classification, or document-level
  plagiarism detection.
- `DEV0` has been inspected repeatedly and must not be used for further
  parameter tuning.
- Bootstrap intervals quantify conditional uncertainty across the 30 parent
  annotations; they are descriptive DEV0 evidence, not a confirmatory
  significance test or substitute for an untouched holdout.

## Claims not yet supported

- Pipeline 2 has no completed retrieval, verification, scoring, or human-review
  experiment.
- The in-domain reports do not yet have a repository-backed approved manifest,
  locked annotation guideline, double annotation/adjudication, and immutable
  experimental split.
- PAN13 conversion QA is not a retrieval-quality or official PlagDet result.
- PlagBench, MMDocIR, HoVer, QASPER, and HARMOGEN-R have been mapped to roles but
  have not contributed numbers to the current paper.

## Minimum work before a publication-strength claim

1. Review and commit the split/exclusion implementation, regenerate `DEV1` and
   `TEST0` from the clean commit, verify zero overlap again, and obtain a real
   governance approval. Use `DEV1` for the evidence-centred reranker design
   only; keep `TEST0` sealed.
2. Run the selected configuration once on the untouched holdout containing
   positive and no-source queries.
3. Add text-alignment and similarity-type experiments before claiming complete
   Pipeline 1 performance.
4. Complete the approved in-domain rubric corpus, annotation/adjudication, and
   LOCAL-vs-GRAPH ablation before claiming Pipeline 2 effectiveness.
5. Retain parent-annotation clustering for all intervals and paired comparisons;
   use the independently frozen holdout for confirmatory reporting rather than
   upgrading the DEV0 bootstrap into a significance claim.
