# PAN pilot converter

Convert one already-extracted PAN split into the four JSONL files consumed by
the offline retrieval runner. Raw archives, extracted text and generated packs
remain local and must not be committed.

```bash
python -m research.pan_pilot \
  --dataset pan13 \
  --input-root var/datasets/raw/pan13-text-alignment/v1/test2 \
  --output-dir var/datasets/derived/similarity/pan13-test2-v1 \
  --dataset-version zenodo-3715980-test2 \
  --split-name test2 \
  --max-positive-annotations 30 \
  --max-candidate-documents 200 \
  --seed 20260923 \
  --source-archive var/datasets/raw/pan13-text-alignment/v1/pan13-text-alignment-test-and-training.zip
```

Use `--dataset pan-pc-11` for PAN-PC-11. The converter discovers XML/TXT
recursively, so the official PAN13 `src/`, `susp/` and category-directory
layout does not need to be flattened.

## Resource-bounded deterministic sampling

The converter defaults to at most 30 positive plagiarism annotations and
200 candidate source documents. These conservative defaults keep the first
end-to-end pilot repeatable on the 16 GB development machine;
`--max-positive-annotations` also accepts
the shorter compatibility alias `--max-annotations`. PAN-PC-11 never permits
an unbounded positive selection. The algorithm:

1. scans XML metadata without opening the corpus TXT files;
2. groups positives by XML parent directory, SHA-256-orders each stratum using
   `--seed`, then selects them round-robin across strata;
3. retains every source relevant to a selected positive;
4. fills the remaining candidate budget with SHA-256-selected source
   distractors; and
5. opens only selected candidate sources and selected suspicious documents.

If the relevant sources alone exceed `--max-candidate-documents`, conversion
fails instead of silently dropping a gold target. The manifest records the
policy, seed, full candidate counts, selected stable annotation IDs and hashes
of the selected IDs/paths. Therefore a bounded pilot must not be reported as a
full-corpus PAN result.

Official PAN releases contain XML for both suspicious and source documents.
Only XML whose root references a suspicious document (or is located under a
known suspicious-document directory) is eligible for positive sampling.

## Query windows

Each annotated suspicious span is split into windows containing at most 256
Unicode word tokens (`--max-query-word-tokens`), with a default stride of 128
(`--query-stride-word-tokens`). Every window has its own stable query ID but
retains a shared `parent_annotation_id`; each receives the same annotated
source qrel. The query records preserve both annotation-level and window-level
raw offsets and hashes.

## Source archive lineage

Pass `--source-archive` once for PAN13 or repeat it for both PAN-PC-11 RAR
volumes. The converter computes local MD5, SHA-256 and byte size. For these
official names it also verifies the provider MD5 and aborts on mismatch:

- `pan-plagiarism-corpus-2011.part1.rar`:
  `b2930f859497dd48ba5bb606d3f4a4f3`;
- `pan-plagiarism-corpus-2011.part2.rar`:
  `b23d86c17a47d2bfbdc4c314ea5810df`;
- `pan13-text-alignment-test-and-training.zip`:
  `fec7fca7a82193a97fbb97cde7781b63`.

Archive paths are not written to the manifest. It contains only the basename,
size, checksums and verification result. Transformation provenance also stores
the converter code SHA-256 plus Git commit/dirty state when Git is available.

The generated files are:

- `documents.jsonl`: exact source-document text and raw SHA-256;
- `chunks.jsonl`: stable paragraph-aware chunks with half-open raw spans;
- `queries.jsonl`: bounded suspicious-span windows with parent annotation,
  exact offsets and annotation provenance;
- `qrels.jsonl`: exact source spans, with `target_scope=document` for
  PAN-PC-11 and `target_scope=span` for PAN13;
- `dataset-manifest.json`: output checksums, metadata-only corpus inventory
  fingerprint, sampling policy/counts, archive lineage, transformation
  provenance, split and governance record.

The manifest always starts at `governance.status=PENDING`. Conversion does not
approve dataset rights, and the runner must continue to reject the pack until
the project records its rights basis, retention, approver and approval date.
Existing output files are not replaced unless `--overwrite` is explicitly
passed.
