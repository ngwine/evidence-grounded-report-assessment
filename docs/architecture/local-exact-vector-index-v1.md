# W5.2 local exact-vector index baseline

`services/backend/src/kltn_ai/integrations/indexing/vector_index.py` provides a
small, dependency-free **local artifact adapter**, not the production vector
service. It expects vectors already computed by a locked embedding model; it
never downloads or infers a model. The index contains no raw report text.

## Build contract

`LocalExactVectorIndex(private_root).build(...)` receives one workspace and
purpose; immutable document-version snapshots; locked model name/revision;
parser, chunker and code versions in config; and chunk IDs, content hashes,
authoritative `source_spans` and equal-dimensional finite vectors. Every input
version must be `ACTIVE`, `READY`, `APPROVED`, purpose-allowed and not tombstoned.
The caller obtains these facts from the authoritative registry immediately
before build; a JSON snapshot cannot grant rights by itself.

The adapter sorts version/chunk records, checks duplicate IDs and lineage,
rejects zero/non-finite vectors, and computes a generation ID from canonical
corpus/version/model/config/vector/provenance bytes. A private `0700` generation
directory stores `vectors.json` and its checksummed `manifest.json` as `0600`
files. Identical rebuild is idempotent. Reusing an immutable version ID with
different content, or the same corpus/model/config with different vectors,
fails closed. Existing generations are never overwritten; a malformed or
tampered generation blocks later rebuilds until an operator investigates.

## Query contract

`search(generation_id, vector, workspace_id=..., purpose=...,
allowed_document_version_ids=[...], top_k=...)` validates scope and requires an
**explicit current allowlist**. It filters by version *before* exact cosine
scoring, then sorts by score descending and chunk ID ascending. Output retains
generation ID, chunk/document/version IDs, score and `source_spans`. Empty
allowlist returns no candidate. The caller must obtain the allowlist from
current RBAC, governance and tombstones; the adapter cannot detect a revocation
after its own build snapshot. Do not expose this local API directly to a user.

## Limits and promotion gate

Search scans allowed vectors exactly; it is useful for small controlled tests,
not a scalable approximate nearest-neighbour service. It has no MongoDB
`index_generations` registry, activation transaction, revocation watcher,
cross-service authorization, deletion cascade, concurrency-safe index reader
leases or backup/restore workflow. Therefore it does **not** close the full
production `W5.2` DoD. Promotion requires integration with the authoritative
MongoDB generation registry and role-scope checks described in ADR-001, plus
resource/security benchmark and reviewer acceptance.

Run the deterministic contract tests:

```bash
.venv-research/bin/python -m pytest -q services/backend/tests/test_vector_index.py
```
