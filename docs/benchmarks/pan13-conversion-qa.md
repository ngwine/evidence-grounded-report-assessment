# PAN13 pilot-pack conversion QA

Date: 2026-09-25
Scope: official PAN13 Text Alignment **training** split, conversion only

## Source verification

- Zenodo record: `3715980`;
- archive: `pan13-text-alignment-test-and-training.zip`;
- provider MD5: `fec7fca7a82193a97fbb97cde7781b63` — matched;
- independently computed archive SHA-256:
  `82b48527058ee2610e77360ff0d38d28fa54abfa7fa50e34d84673065524d223`.

The archive is open for download but its Zenodo metadata does not declare a
license identifier. This QA therefore keeps governance at `PENDING` and does
not index or run a scientific experiment.

## Conversion result

The converter was run twice from the same extracted training split with:

```text
dataset_version: zenodo-3715980-training-2013-01-21
split_name: official-training-derived
query_unit: annotated_suspicious_span
target_scope: span
chunker: paragraph-aware-v1
max_chunk_chars: 1200
```

| Artifact | Records | SHA-256 |
| --- | ---: | --- |
| `documents.jsonl` | 3,230 | `ddfbac4e82db69869158cd9990a078408812218416becff327e6393b373af3ab` |
| `chunks.jsonl` | 13,600 | `51d495f1afbac78d49bb0934616597b24db6d765ee30ca3f581543e4241a92a8` |
| `queries.jsonl` | 4,007 | `a9d9e083f42577da2fd47d91966e1055390776d34d3f1a2271ce1a7a4659642e` |
| `qrels.jsonl` | 4,007 | `8689552d2bee39337e0da6e6f5d9d92210ad71362901214c7ebd848babd7b73a` |
| `dataset-manifest.json` | 1 | `8e2b0dd1b3ce882929714b2d94548bb95d398589feedaa8b80c019602f06ffa2` |

Both conversions produced byte-identical artifacts. The input fingerprint was
`d13ba09d67a334c0e6ae34a977079eb7a4e3d586b3d2b334dd1f8de829583c7c`
over 10,242 XML/TXT files. The split contained 5,185 XML files; conversion found
4,007 positive plagiarism features and skipped 1,947 XML files without a
positive plagiarism feature.

## Gates verified

- all source documents under `src/` remain candidates, including documents not
  referenced by a positive qrel;
- query/source offsets are checked against exact unnormalized UTF-8 text;
- stable document/chunk/query/qrel IDs and output ordering are deterministic;
- output file checksums are recorded in the manifest;
- validator rejected the resulting manifest with
  `Dataset is not APPROVED; indexing/experiments are denied`.

## Interpretation boundary

This proves the conversion path on the official archive; it is not a retrieval
quality result. The derived pack is a positive span-retrieval diagnostic and
does not evaluate no-plagiarism false positives, pair-restricted alignment,
granularity or PlagDet. Those require a separate official PAN13 alignment
evaluator before any text-alignment claim is made.
