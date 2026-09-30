# PAN-PC-11 DEV0 — A1–A5 retrieval and Cross-Encoder ablation

**Run date:** 2026-09-30

**Analysis date:** 2026-10-01

**Result class:** component diagnostic on frozen `DEV0`; not a final model-selection result

## 1. Experimental question

This experiment tests one concrete part of Pipeline 1: after lexical and
semantic retrieval have produced source-document candidates, does an
off-the-shelf multilingual Cross-Encoder improve the early ranking?

The locked path is:

```text
Fixed-window BM25 Top-100 + structure-aware Dense Top-100
→ union by source document
→ equal-weight RRF (k = 60)
→ Cross-Encoder reranks the first 50 source documents
→ max score across the retained support passages of a source document
→ Top-K source documents with winning passage provenance
```

The 30 parent annotations previously used for diagnosis are frozen as
`DEV0`. No RRF weight, chunk size, candidate depth, or decision threshold was
changed after viewing these results.

## 2. Data and locked protocol

| Item | Value |
| --- | --- |
| Dataset | PAN-PC-11 derived source-retrieval pilot |
| Corpus in this resource-bounded pilot | 200 source documents |
| Gold units | 30 parent plagiarism annotations |
| Query windows | 320; windows from the same parent are not independent cases |
| Retrieval target | Source document |
| Candidate depth | Top-100 per retrieval view |
| RRF | Equal weight, `k = 60` |
| Cross-Encoder depth | Top-50 source documents |
| Passage-to-document aggregation | Maximum Cross-Encoder support score |
| Primary diagnostic metric | Parent-balanced Recall@10 |
| Secondary metrics | Query-window Recall, MRR, nDCG and candidate Recall@100 |
| Parameter selection on this set | Prohibited |

The ablation is:

| ID | Method |
| --- | --- |
| A1 | Fixed-window BM25 |
| A2 | Structure-aware Dense retrieval using multilingual E5-small |
| A3 | A1 + A2 with equal-weight RRF |
| A4 | A2 candidates + Cross-Encoder reranking |
| A5 | A3 candidates + Cross-Encoder reranking |

Locked models:

- Dense encoder: `intfloat/multilingual-e5-small`, revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Cross-Encoder: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision
  `1427fd652930e4ba29e8149678df786c240d8825`.
- Cross-Encoder maximum input length: 512 tokens; CPU batch size: 8.

The run used Python 3.12.14 on Apple Silicon with 16 GB RAM. Total wall time
was 3,300.65 seconds. Stage timings are diagnostic only: A5 reused exact pair
scores cached during A4, so A4 and A5 latency must not be compared as two
independent cold runs.

## 3. Main result

### 3.1 Query-window macro metrics

| Ablation | Recall@1 | Recall@5 | Recall@10 | Recall@20 | Recall@100 | MRR@10 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 BM25 | **0.5688** | 0.6531 | 0.6906 | 0.7375 | 0.8563 | **0.6046** | 0.6252 |
| A2 Dense | 0.5406 | **0.6563** | **0.7563** | **0.8438** | 0.9750 | 0.5941 | **0.6317** |
| A3 RRF | 0.5469 | 0.6375 | 0.7125 | 0.7969 | **0.9875** | 0.5899 | 0.6185 |
| A4 Dense + CE | 0.2781 | 0.4344 | 0.5344 | 0.6219 | 0.9750 | 0.3447 | 0.3894 |
| A5 Multi-view + RRF + CE | 0.3406 | 0.4469 | 0.5000 | 0.5625 | **0.9875** | 0.3871 | 0.4139 |

### 3.2 Parent-balanced macro metrics

| Ablation | Recall@1 | Recall@5 | Recall@10 | Recall@20 | Recall@100 | MRR@10 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 BM25 | **0.7938** | **0.8369** | **0.8594** | 0.8793 | 0.9280 | **0.8120** | **0.8232** |
| A2 Dense | 0.6218 | 0.7601 | 0.8219 | 0.8647 | **0.9902** | 0.6742 | 0.7091 |
| A3 RRF | 0.7073 | 0.7776 | 0.8300 | **0.9042** | 0.9854 | 0.7443 | 0.7645 |
| A4 Dense + CE | 0.3659 | 0.5474 | 0.6597 | 0.7500 | **0.9902** | 0.4423 | 0.4936 |
| A5 Multi-view + RRF + CE | 0.6072 | 0.7236 | 0.7558 | 0.7924 | 0.9854 | 0.6550 | 0.6794 |

The configured Cross-Encoder does **not** improve this pilot. Relative to its
own candidate baseline:

- A4 reduces query-window Recall@10 by 22.19 percentage points and
  parent-balanced Recall@10 by 16.22 points compared with A2.
- A5 reduces query-window Recall@10 by 21.25 points and parent-balanced
  Recall@10 by 7.42 points compared with A3.
- Recall@100 is unchanged within each pair because only the first 50 sources
  are reranked and the candidate tail is preserved. The failure is therefore
  in early reranking, not candidate availability at depth 100.

BM25 has the strongest parent-balanced result, while Dense has the strongest
query-window Recall@10. The disagreement is expected because several long
parent annotations produce many correlated query windows. Both reporting
units are retained; the 320 windows are not treated as 320 independent
plagiarism cases.

## 4. What happened to the two previously identified groups?

### 4.1 The 36 Dense Top-10 hits demoted by RRF

| Method | Top-10 hits within the 36 windows | Median relevant-source rank |
| --- | ---: | ---: |
| A1 BM25 | 0/36 | 53 |
| A2 Dense | 36/36 | 1.0 |
| A3 RRF | 0/36 | 57.5 |
| A4 Dense + CE | 31/36 | 1.5 |
| A5 RRF + CE | 4/36 | 57.5 |

A4 retains most of the semantic-only successes. A5 cannot repair this group:
RRF places the relevant source at a median rank of 57.5, while the
Cross-Encoder is allowed to inspect only the first 50 sources. This exposes a
structural problem in using the RRF order as a hard gate for reranking. A
source strongly supported by Dense can be removed before the stronger
pairwise model sees it.

### 4.2 The 22 windows rescued by multi-view RRF

| Method | Top-10 hits within the 22 windows | Median relevant-source rank |
| --- | ---: | ---: |
| A1 BM25 | 20/22 | 1.0 |
| A2 Dense | 0/22 | 23.5 |
| A3 RRF | 22/22 | 7.0 |
| A4 Dense + CE | 7/22 | 21.0 |
| A5 RRF + CE | 12/22 | 6.5 |

A5 keeps only 12 of the 22 RRF rescues. It therefore does not reliably retain
the lexical signal that made fusion useful.

Across all 320 windows, A2→A4 produces 22 new Top-10 hits but loses 93 existing
hits, for a net change of −71. A3→A5 produces 13 new hits and loses 81, for a
net change of −68.

## 5. Evidence-passage diagnosis

The reranker scores passages, but evaluation is performed at source-document
level. Finding the correct document does not guarantee that the selected
support passage overlaps the annotated plagiarised span.

| Diagnostic | A4 | A5 |
| --- | ---: | ---: |
| Relevant sources entering the Top-50 rerank stage | 300 | 266 |
| At least one scored support overlaps the gold source span | 199 (66.3%) | 233 (87.6%) |
| No scored support overlaps the gold source span | 101 (33.7%) | 33 (12.4%) |
| Winning support overlaps the gold source span | 199 (66.3%) | 217 (81.6%) |
| Top-10 misses despite an overlapping support | 44 | 77 |

This separates two failure modes:

1. **Support-selection failure.** In A4, one third of the relevant source
   documents are represented by a passage that does not overlap the gold
   evidence. The Cross-Encoder is being asked to score the wrong part of the
   correct source document.
2. **Reranker/model-input failure.** Even when an overlapping support exists,
   the reranker still pushes 44 A4 and 77 A5 cases outside Top-10. The current
   run uses long 256-word query windows and passages under a 512-subword-token
   model limit, so truncation is a plausible factor. Exact truncation metadata
   must be recorded before attributing all of this loss to the model itself.

## 6. Decision from DEV0

The current off-the-shelf Cross-Encoder configuration is rejected as the
default reranker. The negative result is retained because it rules out the
unsupported assumption that adding a generic multilingual reranker after RRF
automatically improves the pipeline.

The next experiment must be specified on a new development split rather than
tuned against these 30 parents. It should isolate three changes:

1. build the rerank pool with a fixed quota from both retrieval views, so a
   strong candidate from one view cannot be removed solely by RRF ordering;
2. retain multiple evidence passages per source document and measure passage
   overlap before document-level reranking;
3. record tokenizer lengths and truncation, then compare shorter evidence
   queries or evidence-centred sub-passages under a locked protocol.

Only after that protocol is frozen should the chosen variant be evaluated on
an untouched parent/document-disjoint holdout. `DEV0` remains a diagnostic
set and will not be used for further parameter search.

## 7. Reproduction and evidence

Run configuration:

`research/configs/retrieval/pan-pc-11-cross-encoder-dev0-v1.json`

Run command:

```bash
HF_HOME=var/models/hf-home HF_HUB_OFFLINE=1 \
  ./.venv-research/bin/python -m research.offline_retrieval run \
  --dataset-manifest \
    var/datasets/derived/similarity/pan-pc-11-pilot-v1/dataset-manifest.json \
  --config \
    research/configs/retrieval/pan-pc-11-cross-encoder-dev0-v1.json \
  --output-dir \
    research/results/rq1-pan-pc-11/cross-encoder-dev0-v1-0b8e326
```

Reproducible result audit:

```bash
python3 \
  research/offline_retrieval/analysis/analyze_cross_encoder_ablation.py \
  --predictions \
    research/results/rq1-pan-pc-11/cross-encoder-dev0-v1-0b8e326/predictions.jsonl \
  --metrics \
    research/results/rq1-pan-pc-11/cross-encoder-dev0-v1-0b8e326/metrics.json \
  --run-manifest \
    research/results/rq1-pan-pc-11/cross-encoder-dev0-v1-0b8e326/run_manifest.json \
  --dataset-dir var/datasets/derived/similarity/pan-pc-11-pilot-v1 \
  --cutoff 10 --pretty
```

The run manifest binds the result to commit
`0b8e32608226283b8cc1b4964da336fbf323c2a5`, with no tracked working-tree
changes. The working tree was marked dirty only because unrelated untracked
local report files existed.

Artifact SHA-256 values:

- `metrics.json`:
  `a7a3bbcce697cfb28ebd3d5c3f920f4135461b60a4b3e200babfec9fdb4b3b5b`
- `predictions.jsonl`:
  `8f757fc21a42b2a77cb74f29a16b1dcc09584953801c00361d6d64bbb63d466a`

Raw predictions remain local because research outputs are intentionally
ignored by Git. The tracked config, audit script, report, immutable model
revisions, and artifact checksums provide the reproducible evidence trail.

## 8. Limits on interpretation

- This is a 30-parent, resource-bounded diagnostic, not an official PAN result.
- It contains positive source-retrieval queries only; it does not evaluate
  no-source rejection or false-positive rate.
- A1 and A2 differ in both retrieval algorithm and chunking view, so their
  difference cannot be attributed solely to BM25 versus Dense retrieval.
- The run evaluates source retrieval and reranking, not final plagiarism
  classification, span alignment, or document-level plagiarism percentage.
- No statistical superiority or publication claim is made from `DEV0`.
