# PAN-PC-11 multi-view Top-10 transition analysis

Date: 2026-09-30

Status: DEV0 diagnostic; no parameter selection or final method claim

## Question and evidence

This analysis explains the query-window Top-10 difference between
`structure_dense` and `multiview_hybrid_rrf` in the frozen PAN-PC-11 pilot.
It does not re-run retrieval or change any configuration.

- Frozen predictions:
  `research/results/rq1-pan-pc-11/multiview-hybrid-pilot-v1-02a3c4b/predictions.jsonl`
- Run manifest:
  `research/results/rq1-pan-pc-11/multiview-hybrid-pilot-v1-02a3c4b/run_manifest.json`
- Prediction SHA-256:
  `b9821b08590b1a51bd5bef2fd61c8947312ec2cc353645246dd204df3ae03970`
- Dataset pack:
  `var/datasets/derived/similarity/pan-pc-11-pilot-v1/`
- Reproducible audit script:
  `research/offline_retrieval/analysis/analyze_multiview_transitions.py`

The script verifies the prediction checksum against the run manifest before
analysing ranks. BM25 ranks above 100 are not guessed from the truncated
standalone baseline: they come from the `rrf_ranks` contribution recorded in
the fused prediction, for which candidate depth was 200.

The older directory `multiview-hybrid-pilot-v1/` contains byte-identical
predictions, but its manifest records the earlier `f3ca5af` working state.
Use the suffixed `multiview-hybrid-pilot-v1-02a3c4b/` directory as evidence:
its manifest binds the run to commit `02a3c4b` with no tracked modifications.

## Result

At Top-10, RRF changes the Dense outcome for 58 of 320 query windows:

| Transition | Windows | Parent annotations | Median BM25 rank | Median Dense rank | Median RRF rank |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense hit → RRF miss | 36 | 4 | 159 | 1 | 32 |
| Dense miss → RRF hit | 22 | 6 | 1 | 23.5 | 7 |

The net change is `22 - 36 = -14` window hits, exactly matching the frozen
result. These are not 58 independent plagiarism cases. The 36 losses come
from only four parent annotations, and 31 of them come from two long parents.
The 22 rescues come from six parents. Across both directions only eight of the
30 parents are affected.

This concentration explains why query-window Recall@10 decreases from 0.7563
to 0.7125 while parent-balanced Recall@10 slightly increases from 0.8219 to
0.8300. The two aggregation views answer different questions; neither should
be omitted.

## Mechanism taxonomy

This taxonomy describes observed rank mechanics, not PAN plagiarism types.

| Mechanism | Count | Observed ranks | Interpretation |
| --- | ---: | --- | --- |
| Severe BM25 disagreement | 27 | BM25 103–188; Dense 1–10; RRF 24–45 | Equal RRF heavily demotes a source that Dense strongly supports but BM25 almost rejects. |
| BM25 disagreement | 9 | BM25 21–98; Dense 1–9; RRF 11–24 | The same mechanism occurs closer to the cutoff. |
| BM25 Top-10 rescue | 20 | BM25 1–6; Dense 11–50; RRF 1–10 | Lexical retrieval supplies the missing early signal and fusion restores the source. |
| Moderate cross-view consensus rescue | 2 | `(BM25, Dense, RRF) = (13,13,8)` and `(25,14,9)` | Neither input is Top-10, but agreement across views promotes the source. |

As a descriptive proxy, the median fraction of unique query tokens also found
in the annotated source span is 0.086 for loss windows and 0.495 for rescue
windows. The severe-disagreement group has a median of 0.075. This supports
the explanation that BM25 helps most when lexical evidence is strong and can
damage early rank when it is weak. It must not be labelled "paraphrase",
"translation" or another obfuscation type because those labels were not
preserved in this derived pack.

## Parent-level effect

| Parent annotation | Windows | Dense hits | RRF hits | Loss | Rescue | RRF − Dense rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `55b920cd58c3f36e0fff4477` | 30 | 24 | 5 | 19 | 0 | −0.633 |
| `a4dcefc28a7dcaf054b85342` | 29 | 16 | 4 | 12 | 0 | −0.414 |
| `1cc4a4ae700218e73e659204` | 25 | 12 | 16 | 2 | 6 | +0.160 |
| `68a5d13eb9564b93f5a55917` | 27 | 6 | 14 | 0 | 8 | +0.296 |
| `fb9ea9b81a5652b060d73e5e` | 25 | 14 | 13 | 3 | 2 | −0.040 |
| `210134fadddac5f4ab936761` | 4 | 0 | 3 | 0 | 3 | +0.750 |
| `f11c4a83628ff146e635db81` | 24 | 19 | 21 | 0 | 2 | +0.083 |
| `6e3701548ba52812ecdec9a9` | 24 | 22 | 23 | 0 | 1 | +0.042 |

## Consequence for the next method

Equal-weight RRF should remain a reproducible candidate-fusion baseline, not
be presented as the final early-stage ranker. Re-tuning `rrf_k`, view weights
or chunk sizes on these same 30 parents would turn DEV0 into a hidden training
set. The next implementation should instead test whether a Cross-Encoder can
resolve the observed lexical/semantic disagreement on a new development set.

The proposed reranking path is:

```text
BM25 top-100 documents + Dense top-100 documents
→ union by source document
→ keep the best BM25 and Dense support passage for each document
→ RRF candidate ordering
→ Cross-Encoder scores at most 50 candidate documents
→ max Cross-Encoder passage score per source document
→ Top-K source documents with the winning passage as provenance
```

Implementation requirements:

1. Introduce a reranker interface separate from retrieval. Record backend,
   model identifier, immutable revision, batch size, device and maximum input
   length in the resolved config and run manifest.
2. Preserve both per-view support passages. A document may have a fixed-window
   BM25 passage and a different structure-aware Dense passage; score both and
   aggregate by `max`, retaining the winning passage and score.
3. Record pre-rerank rank, post-rerank rank, Cross-Encoder score, support span
   and support method for every returned source document.
4. Use deterministic batching and tie-breaking. Add an injected test reranker
   so unit tests do not download a model.
5. Report candidate Recall@100 before reranking separately from final
   Recall/MRR/nDCG. A reranker cannot recover a relevant document absent from
   its candidate pool.

Locked ablations for the new development split should be:

- A1: Fixed-window BM25;
- A2: Structure-aware Dense;
- A3: equal-weight RRF with `k=60`;
- A4: Dense candidates + Cross-Encoder;
- A5: multi-view RRF candidates + Cross-Encoder.

Use parent-balanced Recall@10 as the primary model-selection metric, with
query-window metrics retained as secondary diagnostics. Freeze the selected
configuration before opening the test split.

## Exact transition cases

IDs below omit the constant `annotation-` and `query-` prefixes. `Coverage` is
the unique-query-token coverage in the annotated source span; it is a
diagnostic proxy rather than a relevance score.

### Dense hit → RRF miss (36)

| Parent | Window | Query | BM25 | Dense | RRF | Coverage |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| `1cc4a4ae700218e73e659204` | 0 | `c607c19d9a0b8b6d1325b966` | 53 | 1 | 11 | 0.490 |
| `1cc4a4ae700218e73e659204` | 21 | `3596d6121fe8358425756222` | 64 | 4 | 19 | 0.463 |
| `55b920cd58c3f36e0fff4477` | 0 | `115c55b932ac5c6ad641f0fd` | 173 | 1 | 33 | 0.101 |
| `55b920cd58c3f36e0fff4477` | 1 | `04c750197ebf8626f1763e56` | 175 | 1 | 32 | 0.095 |
| `55b920cd58c3f36e0fff4477` | 2 | `9cdb067bb882743253539946` | 180 | 1 | 36 | 0.070 |
| `55b920cd58c3f36e0fff4477` | 4 | `85e69957edb7e086ee3e2e74` | 188 | 1 | 37 | 0.079 |
| `55b920cd58c3f36e0fff4477` | 7 | `11fe219f7398971fbbe171ec` | 183 | 1 | 35 | 0.075 |
| `55b920cd58c3f36e0fff4477` | 8 | `c556e39ef0329f5e0d0e8cff` | 187 | 1 | 32 | 0.063 |
| `55b920cd58c3f36e0fff4477` | 10 | `91f9b77e06f5117f55fa1c71` | 187 | 1 | 40 | 0.045 |
| `55b920cd58c3f36e0fff4477` | 11 | `bd1a93a01205fe43a8e96aff` | 162 | 1 | 31 | 0.099 |
| `55b920cd58c3f36e0fff4477` | 12 | `dc6029d793ed49941b2701f1` | 91 | 1 | 24 | 0.095 |
| `55b920cd58c3f36e0fff4477` | 13 | `b64d0f39d49d0cc25fcd12c0` | 157 | 1 | 34 | 0.090 |
| `55b920cd58c3f36e0fff4477` | 14 | `8c76542468505d147291060e` | 103 | 1 | 24 | 0.113 |
| `55b920cd58c3f36e0fff4477` | 15 | `e3ae78a516cbcc2c3a0f80aa` | 117 | 1 | 27 | 0.089 |
| `55b920cd58c3f36e0fff4477` | 17 | `e7164c7ad3e8ee230d84afc8` | 164 | 10 | 45 | 0.099 |
| `55b920cd58c3f36e0fff4477` | 18 | `517b504f0b364dea05134b71` | 154 | 1 | 31 | 0.065 |
| `55b920cd58c3f36e0fff4477` | 19 | `2f06b56999b207a7afd09868` | 98 | 1 | 24 | 0.089 |
| `55b920cd58c3f36e0fff4477` | 24 | `5515bbcdec59bb3b61180896` | 47 | 1 | 13 | 0.097 |
| `55b920cd58c3f36e0fff4477` | 25 | `02c8c15bdfabec4253a52eab` | 118 | 1 | 27 | 0.084 |
| `55b920cd58c3f36e0fff4477` | 28 | `a02f873c91a40dbbaf4b5f01` | 58 | 1 | 14 | 0.105 |
| `55b920cd58c3f36e0fff4477` | 29 | `c6d696795bdc1866a3ee4542` | 165 | 1 | 37 | 0.059 |
| `a4dcefc28a7dcaf054b85342` | 3 | `824e762d1bf24cf15ab2e098` | 155 | 1 | 29 | 0.086 |
| `a4dcefc28a7dcaf054b85342` | 6 | `1232680329058b0ffddec91e` | 114 | 4 | 35 | 0.062 |
| `a4dcefc28a7dcaf054b85342` | 9 | `bd5588f7c68bb63d1644f3b6` | 104 | 1 | 29 | 0.092 |
| `a4dcefc28a7dcaf054b85342` | 10 | `d4244c45b35e26b16425ed1c` | 163 | 1 | 34 | 0.085 |
| `a4dcefc28a7dcaf054b85342` | 11 | `b2ea5217cd85c3a86d6fc6db` | 186 | 1 | 34 | 0.075 |
| `a4dcefc28a7dcaf054b85342` | 13 | `57d9f2b527fd6234c5e22eee` | 185 | 1 | 35 | 0.075 |
| `a4dcefc28a7dcaf054b85342` | 14 | `9224679a9488d8fc58c307e3` | 184 | 1 | 39 | 0.065 |
| `a4dcefc28a7dcaf054b85342` | 15 | `47711a70c106e1844d1fa08a` | 134 | 1 | 32 | 0.067 |
| `a4dcefc28a7dcaf054b85342` | 16 | `284e109badce93a4764e4914` | 163 | 1 | 35 | 0.054 |
| `a4dcefc28a7dcaf054b85342` | 19 | `4c7a889fa937d1c2cfb26b68` | 168 | 1 | 37 | 0.069 |
| `a4dcefc28a7dcaf054b85342` | 20 | `6f01c27b192780acf94ad34b` | 162 | 1 | 32 | 0.068 |
| `a4dcefc28a7dcaf054b85342` | 23 | `8d9aebc10a73c24ac44e377d` | 161 | 7 | 42 | 0.064 |
| `fb9ea9b81a5652b060d73e5e` | 1 | `aef3f16fb5f31740f3d90152` | 46 | 8 | 16 | 0.517 |
| `fb9ea9b81a5652b060d73e5e` | 15 | `d86b934adfbb38d540fd22f5` | 30 | 8 | 13 | 0.553 |
| `fb9ea9b81a5652b060d73e5e` | 23 | `829b2ebd91c18e5d44bf679f` | 21 | 9 | 11 | 0.596 |

### Dense miss → RRF hit (22)

| Parent | Window | Query | BM25 | Dense | RRF | Coverage |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| `1cc4a4ae700218e73e659204` | 10 | `3c3a2dc379af7996337bacc6` | 1 | 17 | 4 | 0.485 |
| `1cc4a4ae700218e73e659204` | 11 | `50327082d2c71d13adaba7e6` | 1 | 14 | 2 | 0.509 |
| `1cc4a4ae700218e73e659204` | 13 | `0d98eb958030e8b27ef87981` | 4 | 28 | 7 | 0.487 |
| `1cc4a4ae700218e73e659204` | 14 | `29cc9c22c30b36b77bd834d9` | 3 | 18 | 7 | 0.494 |
| `1cc4a4ae700218e73e659204` | 18 | `660b94de235c6767ff3c7a51` | 1 | 14 | 4 | 0.484 |
| `1cc4a4ae700218e73e659204` | 20 | `3799ba944a42a1d825bad9db` | 1 | 20 | 4 | 0.464 |
| `210134fadddac5f4ab936761` | 0 | `0306182b5d6f1a390b8bdc03` | 6 | 31 | 10 | 0.416 |
| `210134fadddac5f4ab936761` | 1 | `04c17f72d792198f852605c1` | 4 | 19 | 7 | 0.453 |
| `210134fadddac5f4ab936761` | 3 | `a0f325f49564f6f74e78afe8` | 1 | 36 | 6 | 0.459 |
| `68a5d13eb9564b93f5a55917` | 14 | `2603e712ebe6732ea77813f0` | 3 | 19 | 2 | 0.481 |
| `68a5d13eb9564b93f5a55917` | 17 | `012cbeafd4401ab0f24141e8` | 1 | 43 | 7 | 0.545 |
| `68a5d13eb9564b93f5a55917` | 18 | `5f3475535e911c85f885bbd5` | 1 | 50 | 9 | 0.509 |
| `68a5d13eb9564b93f5a55917` | 19 | `ab8388fed78c03bb2806163b` | 1 | 38 | 8 | 0.429 |
| `68a5d13eb9564b93f5a55917` | 20 | `fd4879615db7f3009707032b` | 1 | 27 | 3 | 0.440 |
| `68a5d13eb9564b93f5a55917` | 22 | `23018efe378e9f114246701e` | 1 | 11 | 1 | 0.497 |
| `68a5d13eb9564b93f5a55917` | 23 | `e1a1a90a8b2a1d9362a9c4af` | 1 | 49 | 9 | 0.516 |
| `68a5d13eb9564b93f5a55917` | 24 | `7edaca754d80d465d42e3253` | 2 | 15 | 4 | 0.548 |
| `6e3701548ba52812ecdec9a9` | 1 | `6eb073fea310b2d3db111aef` | 1 | 35 | 6 | 0.497 |
| `f11c4a83628ff146e635db81` | 4 | `e7ee0ee99574e1c9ffb80101` | 3 | 28 | 7 | 0.613 |
| `f11c4a83628ff146e635db81` | 23 | `1f8f74fbedf96c46c40280f9` | 4 | 28 | 10 | 0.577 |
| `fb9ea9b81a5652b060d73e5e` | 9 | `1e7f4ae4abf0f5a753e6e6e8` | 25 | 14 | 9 | 0.503 |
| `fb9ea9b81a5652b060d73e5e` | 18 | `ae5002246b25b9c159e437fe` | 13 | 13 | 8 | 0.522 |

## Reproduction

```bash
python3 research/offline_retrieval/analysis/analyze_multiview_transitions.py \
  --predictions research/results/rq1-pan-pc-11/multiview-hybrid-pilot-v1-02a3c4b/predictions.jsonl \
  --run-manifest research/results/rq1-pan-pc-11/multiview-hybrid-pilot-v1-02a3c4b/run_manifest.json \
  --dataset-dir var/datasets/derived/similarity/pan-pc-11-pilot-v1 \
  --cutoff 10 --pretty
```
