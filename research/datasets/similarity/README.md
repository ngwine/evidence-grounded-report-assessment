# Similarity pilot datasets

Raw archives and derived corpus text are local artifacts under `var/datasets/`
and are never committed. This directory stores only protocol, manifest templates
and provenance needed to reproduce an approved conversion.

Two PAN packs are intentionally separate:

- `pan-pc-11-source-retrieval-pilot-v1`: core source-retrieval diagnostic;
- `pan13-span-retrieval-oracle-pilot-v1`: span-retrieval component diagnostic,
  not the official PAN13 text-alignment evaluation.

Both templates remain `PENDING` until rights/access, local archive checksum,
retention and an actual approver/date are recorded. The offline runner must
reject them while that gate is open.
