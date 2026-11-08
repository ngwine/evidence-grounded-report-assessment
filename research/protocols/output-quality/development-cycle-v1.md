# Output-quality development cycle, 29 October 2026

## Scope and frozen inputs

This cycle evaluates application outputs, separately from the frozen PAN
source-document ranking study. LIP is an already-seen development case.
The authored DEV pack has 12 P1 pairs and 6 P2 checks; the private challenge
has 24 P1 pairs and 12 P2 checks. Text, expected labels and Unicode evidence
offsets were hashed before candidate inference. All expectations are
assistant-authored synthetic development material, not independent human gold.

DEV SHA-256: `0bcc7ef8996b622fea0ebc41973907c997d0795427b993c65813e15d23cc2020`.
Challenge SHA-256: `4264cdad155b6f5f199351a534ce1bd26e8a73b6232c06a47a39f527f5c9619b`.

Baseline modules and their hashes are preserved under ignored
`var/quality/output-improvement-2026-10-29/before/`. Every candidate attempt
uses a fresh output directory. Candidate code, checkpoint and policy must be
frozen before implementation agents inspect challenge results. Once inspected,
the challenge is development evidence and cannot be reused as an unseen test
for later fixes.

## Candidate selected on DEV

P1 keeps exact-span coverage separate from semantic proposals. Its exact
evidence floor uses character length, token count and distinct alphabetic
tokens, avoiding an English-specific requirement for long whitespace words.
Semantic verification uses a local sequence-classification NLI model in both
directions, never E5 cosine or relevance Cross-Encoder scores as equivalence
probabilities.

- Checkpoint: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, revision
  `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`, CPU float32, batch8.
- Mutual entailment threshold0.65; rejection threshold0.85; margin0.20.
- Contiguous windows of1–2 sentences, at least5 words per leg; at most12
  selected window pairs per retrieved pair. Exact original offsets are retained.
- Token limit512, no model truncation. Overlength/unsupported inputs abstain.
- Character, sentence, batch and directional-pair caps are explicit in model
  metadata. Budget overflow abstains rather than quietly dropping comparisons.
- Identical segments defer to the exact policy. Changed explicit numbers or
  same-token reordered roles/attributes veto semantic positives. These guards
  do not implement general entity, quantity or role resolution.
- A positive proposes equivalence only for the compared spans and requires
  review. It contributes neither exact coverage nor a plagiarism percentage.
  SUMMARY is unsupported. Incomplete/uncertain comparisons remain null.

The model and threshold are **DEV-selected, not calibrated or prespecified
scientific estimates**. Attempts with MiniLM and with mDeBERTa at0.85 are
retained, including missed paraphrases and high-confidence role errors. On
the visible DEV cases, mDeBERTa at0.65 recognizes both expected paraphrases
without a reuse label on the eight negative target pairs; two role cases
still abstain. This small observation does not establish general accuracy.

P2 V4 keeps retrieval, rubric and score rules fixed while distinguishing
completed work from plans, pending tables and tool availability; scoped
negative preservation/limitation statements can support the corresponding
authored requirement. Real unresolved conflicts still abstain. The same
stored LIP evidence is replayed before full application execution.

## Comparisons and outcomes

Run BM25 baseline versus BM25 plus the candidate verifier on the identical
packs. Also compare RRF without relevance reranking, holding the verifier
fixed. New web profiles `bm25-nli-v1` and `rrf-nli-v1` preserve the previous
two profiles. P2 retrieval stays BM25 in both new profiles. Historical PAN
DEV0/DEV1 artifacts and original web results are never overwritten.

Report separately:

1. Positive source retrieval at ranks1/3 and expected anchor containment.
2. Target relation agreement with abstention/missing predictions explicit.
3. False reuse on negative cases and non-target distractors; false exact
   document coverage; per-class confusion and model-decision coverage.
4. P2 outcome agreement, false MET and correctly retained CANNOT_ASSESS.
5. Actual web/API/Mongo/worker run IDs, immutable input locks, compared spans,
   code/model hashes and failures. Producing a total score is not a success
   criterion.

Keep both successful and unsuccessful outcomes. Do not change challenge
labels, rubric, thresholds or model after inspecting its predictions to
improve the reported first-candidate result. Later defects require new
regression cases and a fresh unseen cohort.

PAN TEST0 stays sealed: its source-document qrels cannot validate paraphrase
relations or rubric outcomes. It belongs to a separately frozen source-ranking
evaluation. Authored application diagnostics do not become paper accuracy
tables or independent holdout evidence.

## Subsequent citation-guard correction

The first frozen challenge is retained unchanged. A subsequent replay of the
already-seen LIP case revealed that reference markers `[4]` and `[5]` were
counted as factual quantities and vetoed a model-supported sentence pair.
This correction is a new revision, not a retuned first-challenge result.

Only parser-provenance single numeric markers with a unique printed-key
bibliography candidate can become explicit exclusion hints for the numeric
guard. Index/array adjacency, quantitative contexts, units, intervals, missing
and ambiguous bibliography links do not provide hints. Original NLI strings,
model checkpoint, thresholds, windows and source spans remain unchanged.
The parser link and this numeric hint do not verify citation validity.

A separate 16-case citation-component cohort was authored and hash-locked
before implementers viewed its texts or labels. It compares the same model
with/without explicit numeric-exclusion hints. Its SHA-256 is
`e5f1e58e6cd43b1b7b58cf4ee7440268706441d31e2b50899934065ec1489a71`.
Record positive recovery, factual false equivalence and retained abstention
separately. Pipeline tests additionally check DOCX parsing, bibliography
linking, original offsets and the unchanged exact-coverage rule. This cohort
remains assistant-authored component evidence, separate from application
gold and the original challenge.

Candidate `a2a3d885` was frozen before opening that component cohort. Actual
MPS inference found no gain: decision agreement remained8/16, linked-positive
recovery0/4, false equivalence0/10 semantic negatives, and10 abstentions.
No threshold, text or expectation was changed after inspecting this result.
The application LIP replay recovered the P128 pair but not P131. These are
different cohorts and scopes; the LIP gain cannot replace the negative
component result. See the [development report](../../../docs/benchmarks/output-quality-development-2026-10-29.md)
for the complete comparisons and preserved application attempts.
