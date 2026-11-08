# Experiment audit for the English paper

Audit date: 2026-11-08 (earlier dated entries retained as historical snapshots)

Immediate handoff: a complete manuscript for faculty/supervisor review, using
the existing template. See [the paper completion priorities](KE_HOACH_HOAN_THIEN_BAI_BAO.md).
A stronger empirical claim remains conditional on the experiment evidence below.

## What is supported by artifacts

- On 8 November, the context-bundle/prompt intervention and a separate DEV
  retrieval comparison completed 90 decisions on the previously inspected
  15 SEFORA essays. Full parsed-report input matched 35/45 references and
  LOCAL BM25 top-5 matched 32/45, versus the historical one-step result of
  37/45 and always-MET baseline of 42/45. Both new branches had zero technical
  abstentions; no new variant was promoted on these results. All 149 present
  proofs were source-bound, which does not certify semantic correctness.
  Report-cluster bootstrap was added as post-hoc descriptive analysis; it
  does not establish a reliable winner or incorporate annotation uncertainty.
  A method-masked human review packet covers all 73 conclusive decisions,
  with human fields blank and support rates unset. Semantic GRAPH remains
  explicitly NOT_IMPLEMENTED_NOT_RUN. The current paper tables are unchanged.
  The user chose SEFORA for the next assessment study; recovery of R1/R2 is
  not a prerequisite. New raw essays/grades do not automatically provide
  three-state checklist references. See [the DEV record](../benchmarks/sefora-p2-context-retrieval-dev-2026-11-08.md)
  and [data readiness](../benchmarks/p2-experiment-readiness-2026-11-08.md).

- On 7 November, the user-authorized single-reference exploratory comparison
  completed 15 SEFORA Class_2 essays × three text-only checklists × two
  verifier architectures. One-step matched 37/45 reference labels (82.22%);
  two-step matched 32/45 (71.11%); always-MET matched 42/45 (93.33%). Both
  methods had zero technical abstentions and predicted no UNMET despite
  three document-absence UNMET references. QUO001 agreement fell from 10/15
  to 6/15 with the two-step workflow; seven selections were empty. All 179
  present proofs map to original source coordinates, which does not establish
  semantic support. Inputs, labels, matched citation cap, model and code were
  frozen before execution, and references were not supplied to the verifier.
  This is a **single AI-assisted annotator reference**, not multi-rater gold
  or an approved independent holdout. It does not support a quality gain for
  the two-step method. The manuscript quality tables are unchanged. See
  [the completed run and limitations](../benchmarks/sefora-p2-single-reference-result-2026-11-07.md).

- On 3 November, a separate opt-in local LLM assessment verifier was
  implemented with a digest-locked Qwen3.5 4B Q4_K_M model, JSON/quotation
  validation, requirement-level decisions and unchanged deterministic
  scoring. Five author-written synthetic cases were executed using the real
  local model, including paraphrased support, direct contradiction, missing
  evidence, future-only evidence and a report-instruction case. This is
  software/protocol validation, not SEFORA accuracy or independent assessment
  gold. Historical PAN/QASPER metrics are unchanged. See the
  [implementation and smoke record](../architecture/p2-local-llm-verifier.md).

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
- On 30 October, the QASPER LOCAL diagnostic was revalidated with real cached
  E5 inference from clean commit `9b9721d`. All aggregate metrics on 646
  evaluable questions and the complete metrics-file bytes match the historical
  reference. RRF source hashes differ, so this confirms the current frozen
  implementation's aggregate results, not an identical historical-source or
  per-query replay. This remains a previously inspected DEV component result;
  team pack approval is still recorded as `NOT_RECORDED`. See the
  [QASPER report](../benchmarks/qasper-v03-local-evidence-dev-result.md).
  The QASPER runner calls shared retriever utilities directly, not P2's
  `_rank_local` or full checklist-to-score pipeline. It supports an auxiliary
  within-paper retrieval proxy result, not full LOCAL assessment validation.
  On 1 November, the faculty-review manuscript incorporates this experiment
  in §4.6 and §5.6/Table 10: 646 of 1,005 DEV questions are scored and 359
  excluded under the paragraph-mapping protocol. Inclusion reports the
  existing descriptive component evidence; it does not create pack approval,
  close G-05, or establish grading effectiveness.
- The bootstrap implementation has focused test coverage (`27 passed, 2
  skipped` in the relevant subset), and the locked PAN-PC-11 manifest/config
  pair passes the fail-closed validator.
- Leakage-safe split derivation has a repeatable prior-manifest exclusion
  mechanism. The earlier `71 passed` research-suite count belongs to the
  12 October snapshot, not the current full-project test count.
- The 25 October implementation snapshot includes a working authenticated
  Mongo/API/worker app and the scoped phrase-context P2 verifier V3. Its
  checks recorded `681 passed, 21 skipped` across research/backend tests,
  50 context/regression checks within that suite, six mocked browser contract
  checks, and real web BM25/Hybrid runs. These are software checks, not model
  accuracy or independently labelled experimental results.
- The separate 29 October application-quality cycle adds opt-in bidirectional
  NLI proposals for compared P1 sentence spans and the lexical/context P2
  verifier V4. It does not add results to the PAN tables. Its first candidate
  was frozen at `7aa249f` before the authored challenge was inspected:
  BM25 P1 decision agreement changed from 8/24 to 16/24, and RRF from 4/24
  to 16/24; both retained eight abstentions. P2 matched 11/12 challenge
  expectations before and after. These are assistant-authored development
  expectations, not independent human gold or general model accuracy.
- A later citation-number guard correction was frozen separately at `a2a3d885`.
  On a new 16-case component cohort, enabling bibliography-linked exclusion
  hints left decision agreement at 8/16 and recovered 0/4 linked positives;
  neither condition produced false equivalence on the ten semantic-negative
  cases. This negative result is retained without tuning on that cohort.
  It does not replace the first challenge result or establish improvement in
  citation handling. See [the application-quality record](../benchmarks/output-quality-development-2026-10-29.md).

## Integration status

- The local Git history contains the merged A1--A5 work through PR #13
  (`0323432`), parser golden benchmark through PR #10 (`7a1c1fa`), and API
  contract through PR #7 (`1262646`); all are ancestors of integrated `main`
  commit `3ba820e`. The earlier statement that those PRs were still open is
  obsolete. This is a history check, not a claim about current remote CI.
- The active working branch is `feat/demo-workspace-ui`, with uncommitted UI,
  verifier and documentation changes. The paper's historical DEV0 artifacts
  remain tied to their original run commit and checksums. A new experiment
  needs its own clean, reviewable code snapshot; do not relabel the old run
  as having used the latest implementation.
- The application-quality snapshots are isolated on `feat/w10-output-quality-v1`.
  MongoDB migrations 006/007 add immutable NLI v1/v2 profile identifiers.
  `bm25-nli-v2` and `rrf-nli-v2` require MPS for NLI; RRF adds E5 on CPU,
  without a relevance Cross-Encoder. P2 retains BM25 retrieval and V4 rules
  in both profiles. P1 semantic proposals do not add exact coverage, and
  SUMMARY classification remains unimplemented.
- The original DEV1/TEST0 packs retain their earlier PENDING metadata. New
  `*-v2-clean` packs were regenerated on 28 October from clean converter
  commit `d6cec84`; provider/generated checksums and all three pairwise leakage
  dimensions were checked. The owner decision and conservative handling
  metadata were recorded separately, and the new packs are APPROVED for the
  stated internal purpose. TEST0 remains sealed during method development.
  See [the follow-up preparation record](../benchmarks/pan-pc-11-short-evidence-dev1-readiness-2026-10-28.md).
- The short-input comparison is implemented in a separate clean experiment
  checkout at `2a8c073`. DEV1 completed with actual locked models and passed
  prediction/metric/query checksum and A5/A6 candidate/support/tail audits.
  On 30 different parents and 207 query windows, parent Recall@10 changes
  from 0.772928 to 0.738360; A6-minus-A5 is -0.034568 with paired 95% interval
  [-0.102758, 0.036920] (10,000 parent draws, seed 20261028).
  A6 needs no additional model truncation, versus 19,742/20,700 A5 support
  requests (95.37%). These are request counts including cache reuse;
  DEV0's 97.5% uses unique pairs and is not the same denominator.
  The result does not establish improvement or a clear degradation.
  [Audited DEV1 result](../benchmarks/pan-pc-11-short-evidence-dev1-result.md)
  is incorporated as Table 9 and §5.5 in the paper. The isolated research
  suite passed 332 tests; software tests are distinct from retrieval quality.
- The three disjointness dimensions remain parent annotation, suspicious
  document and the complete candidate-source pool, not only qrel positives.
- `quota_union` exists in the application passage-level P1 implementation,
  not in the offline source-document experiment runner used for the paper.
  A paper ablation of that policy requires a reviewed implementation and
  protocol rather than merely changing an existing app configuration.

## Claims that must remain preliminary

- The reported PAN-PC-11 run is resource bounded, positive only, and uses
  oracle suspicious-span queries. It is not an official PAN result.
- It evaluates source-document retrieval and reranking, not suspicious-span
  discovery, text alignment, similarity-type classification, or document-level
  plagiarism detection.
- `DEV0` has been inspected repeatedly and must not be used for further
  parameter tuning.
- Bootstrap intervals quantify conditional uncertainty across 30 parents
  per pack; they are development evidence on DEV0/DEV1, not a confirmatory
  significance test or substitute for an untouched holdout.

## Claims not yet supported

- Pipeline 2 now has an executable authored-checklist compiler, LOCAL/GRAPH
  structure-and-term retrieval, phrase/context verification, deterministic
  scoring and review integration. It has no completed approved, independently
  annotated in-domain end-to-end effectiveness study.
- The LIP V3 case matches 6/10 pre-run reference labels, versus 3/10 before the
  context fixes. A V4 replay on the same saved evidence matches 10/10, with
  6 MET, 3 UNMET and 1 CANNOT_ASSESS; a new BM25 web run reproduces these
  counts. The total remains null. The case was seen during development and
  used to diagnose the changes. It is not held-out accuracy, independent gold
  or evidence of general P2 effectiveness, and is not included in the paper
  quality tables.
- QASPER is now reported separately from PAN as an auxiliary within-paper
  paragraph-retrieval experiment in the faculty-review manuscript. Its
  previously inspected DEV questions, custom paragraph metrics, exclusions,
  lack of confidence intervals and untouched holdout, and missing team pack
  approval remain explicit. It does not validate the actual checklist query,
  parser-chunk retrieval, verifier, rubric scores, or GRAPH path of P2.
  The MMDocIR text pilot dated 18 October remains outside the paper's Results;
  its seven single-page-evidence questions and pre-gate pack history are not
  independent end-to-end assessment evidence.
- PAN13 conversion QA is not a retrieval-quality or official PlagDet result.
  PlagBench, HoVer and HARMOGEN-R do not contribute numbers to the present
  paper tables.
- A completed in-domain assessment study still needs its own approved
  manifest, independent annotation/adjudication and immutable split. Public
  component results do not establish end-to-end grading validity.
- SEFORA assessment evaluation is deferred to the following week at the
  owner's request on 1 November. On 2 November, both 60-row preparation
  sheets were returned and audited: Quy's sheet records AI-assisted human
  review; Yen's sheet retains 25 UNSURE items. The owner attests that neither
  saw the other's labels or P2 predictions before saving the separate
  sheets. Atomic mappings and evidence adjudication remain unfinished;
  these are not frozen gold labels. No SEFORA inference, label metric, or
  grading result is added to the manuscript. See the
  [returned-label review](../benchmarks/sefora-p2-return-review-2026-11-02.md).
- On 4 November, the revised Yen sheet has no UNSURE labels: 24 MET,
  10 UNMET and 26 CANNOT_ASSESS. There are 21 label differences from Quy;
  the new 60%/unknown-count aggregation rules are not adopted as rubric
  policy. A local P2 development diagnostic uses only the original CRIT001
  question on all ten essays, with annotations and teacher feedback excluded
  from inference. All ten CRIT001 reference labels are MET. This diagnostic
  is not an approved benchmark, adjudicated gold, three-class effectiveness
  evaluation, or teacher-score agreement study. It does not add SEFORA
  quality numbers to the manuscript; input/output receipts are under
  `var/paper/sefora-p2-diagnostic-2026-11-04/`.
  The completed LLM diagnostic matches 3/10 positive-only reference labels;
  seven outputs are CANNOT_ASSESS (two timeouts, three rejected quotations,
  two insufficient-evidence judgments). Failures are retained in the
  denominator. These observations identify development issues; they are
  not full-P2 accuracy or publication-strength grading evidence.
- The subsequent 4 November P2 development fix adds bounded all-parsed-chunk
  context for short reports, code-resolved source-unit citations, and separate
  evidence selection and selected-only verification calls. Its final replay
  matches 9/10 CRIT001 labels with no technical abstentions and 23 source-bound
  proofs, while one item remains CANNOT_ASSESS. Semantic citation quality is
  still uneven, including general statements in some otherwise matching MET
  items. A ten-case synthetic challenge passes nine expectations; a future-only
  outline is UNMET rather than the expected CANNOT_ASSESS. The intermediate
  all-MET run with weak citations is preserved and is not substituted for the
  final result. These are inspected development diagnostics, not a held-out
  grading study, and remain outside the manuscript's quality tables. Details:
  `var/paper/sefora-p2-diagnostic-2026-11-04/improvement/KET_QUA_SUA_P2.md`.

## Minimum work before a publication-strength claim

Preparation on 5 November adds returned-XLSX validation, typed whole-captured-
text absence records, and matched one-/two-step comparison tools. A single
author-written software case verifies shared upstream evidence, citation cap
three, and actual call accounting; it supplies no new grading metric. The new
15-essay annotation cohort is excluded from development comparisons. Sect. 3.3
and the generated Word manuscript now describe the optional local verifier;
the Experimental Design and subsequent Markdown sections and all Word table
contents are unchanged. See [P2 readiness](../benchmarks/p2-readiness-2026-11-05.md).

1. Retain the regenerated, approved DEV1/TEST0 snapshots and their clean
   converter provenance. The locked DEV1 comparison is completed and audited;
   review its evidence and freeze the final method before TEST0 is opened. Preserve
   unsuccessful attempts and report negative results as well as gains.
2. Freeze the method on DEV1, then evaluate the locked comparison on the
   untouched TEST0 under its approved protocol. A positive-only source-
   retrieval study must keep that scope explicit. Add a negative/no-source
   cohort and a suitable protocol before claiming precision, false-positive
   rate or rejection quality; the existing positive-only runner does not
   support those claims automatically.
3. Add text-alignment and similarity-type experiments before claiming complete
   Pipeline 1 performance.
4. Complete the approved in-domain rubric corpus, annotation/adjudication, and
   LOCAL-vs-GRAPH ablation before claiming Pipeline 2 effectiveness.
5. Retain parent-annotation clustering for all intervals and paired comparisons;
   use the independently frozen holdout for confirmatory reporting rather than
   upgrading the DEV0 bootstrap into a significance claim.
