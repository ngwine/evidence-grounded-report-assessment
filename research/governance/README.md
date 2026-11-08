# Dataset mapping and per-pack approval

[`dataset_registry.json`](dataset_registry.json) transcribes only the selected
dataset decisions and rights/checksum notes from the team's `-4.xlsx` workbook,
sheet `Dataset mapping`. Cells `J6:J8` mark MMDocIR, HoVer and HARMOGEN-R as
"Dùng", reviewer Yến; their corresponding license notes are in `D6:D8`.
The workbook has no approval date for those rows. The registry records that
fact as `approved_at: null`. The workbook is external to Git; the cell
references are audit pointers, not a copy of private documents.

PAN-PC-11 is selected for research use, but its workbook rights cell `D4`
still calls for a rights review. The existing local DEV0 pack has its own
separately approved manifest. That approval does not cover DEV1, TEST0 or a
new derivation. PAN13 rights remain unresolved (`D5`, `J5`). Student reports
need documented consent or authority, PII review, anonymization and retention
before an in-domain experiment.

An experiment uses a particular frozen pack. Its manifest must state the
dataset version, allowed purpose, rights basis, approval evidence/person/date,
PII decision, retention, split identifiers and SHA-256 for each input file.
Private report packs also need a consent/authority evidence reference. The
validator also requires an explicit `pii_review` decision, reviewer, date and
private evidence reference; filling a `contains_pii` boolean alone is not a
PII review. It verifies all declared input files and checks declared source hashes
against the registry. Historical checksum values in Excel do not prove that
today's local copy still matches; rehash source files when preparing a pack.

```sh
python -m research.governance list
python -m research.governance check path/to/dataset-manifest.json \
  --purpose RETRIEVAL_EXPERIMENT
```

`check` exits with `DENIED` for a pending or incomplete manifest. A data
mapping decision never changes that gate. The existing offline retrieval runner
has its own manifest gate; this validator also covers candidate P2 pack
manifests before their component runners are connected to the shared gate.

Known local issue: `var/datasets/raw/hover-v1.1/` currently has a
`wiki_wo_links.checksum-mismatch.db`. The expected SHA-256 from the workbook
must match a clean wiki database before a HoVer run is approved.
