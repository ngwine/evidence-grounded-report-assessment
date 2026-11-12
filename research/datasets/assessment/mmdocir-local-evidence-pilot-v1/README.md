# MMDocIR text-only LOCAL pilot pack

This template preserves the exact five-PDF selection used by
`research/mmdocir_pilot.py`. The SHA-256 values come from the workbook's
`Dataset mapping!G6` and the earlier local pilot; rehash both files before
approving a new run. The workbook's `J6` records Yến's dataset selection but
does not supply a dated approval for a frozen local pack.

To prepare a run, copy the template as
`var/datasets/raw/mmdocir-eval/dataset-manifest.json`, verify the source license,
file hashes, PII decision and retention, then record the real reviewer/date and
approval evidence. Set a fixed `dataset_version` and `governance.status` to
`APPROVED` only after that review. The executable gate is:

```sh
python -m research.governance check \
  var/datasets/raw/mmdocir-eval/dataset-manifest.json \
  --purpose EVIDENCE_RETRIEVAL_EXPERIMENT
python -m research.mmdocir_pilot \
  --dataset-manifest var/datasets/raw/mmdocir-eval/dataset-manifest.json
```

The pilot runner verifies the manifest before reading the raw annotation file
or extracting the PDF archive, and checks that the selected document names
still match the frozen list. It writes a hash of the manifest into its run
record. The old October 18 run record predates this gate and is not changed.
