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
  --split-name test2
```

Use `--dataset pan-pc-11` for PAN-PC-11. The converter discovers XML/TXT
recursively, so the official PAN13 `src/`, `susp/` and category-directory
layout does not need to be flattened.

The generated files are:

- `documents.jsonl`: exact source-document text and raw SHA-256;
- `chunks.jsonl`: stable paragraph-aware chunks with half-open raw spans;
- `queries.jsonl`: exact annotated suspicious spans and annotation provenance;
- `qrels.jsonl`: exact source spans, with `target_scope=document` for
  PAN-PC-11 and `target_scope=span` for PAN13;
- `dataset-manifest.json`: output checksums, input fingerprint, split and
  governance record.

The manifest always starts at `governance.status=PENDING`. Conversion does not
approve dataset rights, and the runner must continue to reject the pack until
the project records its rights basis, retention, approver and approval date.
Existing output files are not replaced unless `--overwrite` is explicitly
passed.
