# Evidence Graph v1 — local contract and store

This package implements a small, versioned Evidence Graph slice for W11.1–W11.5.
It is separate from `research/core_mvp/graph.py`, which ranks chunks using
structure, shared terms and PageRank. This package represents **explicit**
claims, results and relations; it does not extract or verify their meaning.

## Input and provenance

`validate_snapshot()` accepts one immutable generation with:

- `scope`: `workspace_id`, `report_id`, `report_version_id`, `graph_version`,
  `analysis_run_id`;
- `input_versions`: exactly one matching report version and any source versions,
  each with `rights_state=APPROVED`;
- `chunks`: references projected from parser v2 output with
  `make_chunk_reference()`, including stable `chunk_id`, content SHA-256 and
  authoritative `source_spans`;
- `spans`: built by `make_span()` from a chunk and `source_span_index`. Each
  copies the parser's element-local and chunk-local raw/normalized ranges and
  original PDF/DOCX locator exactly;
- `nodes`: `CLAIM`, `CONCEPT`, `METHOD`, `RESULT`, `CONCLUSION`, `SOURCE`, or
  `EVIDENCE_SPAN`, built with `make_node()`. Each has an evidence span, extractor,
  model/rule version, confidence, and fixed UTC creation time. `CLAIM` requires
  `claim_kind` and `polarity` attributes;
- `edges`: typed relations built with `make_edge()`. Each carries evidence
  spans, extractor/version/confidence and a review state. Reviewed edges also
  require reviewer ID and UTC review time.

[`schema-v1.json`](schema-v1.json) documents the JSON shape. The Python
validator additionally checks references, stable identities, scope and parser
span equality, which JSON Schema cannot express by itself.

IDs are SHA-256 hashes of canonical scope, content and provenance, independent
of insertion order. Parser source spans are copied as a unit. Narrower claim
highlights need a future extractor plus a verified raw–normalized subspan
mapping; this adapter never guesses those offsets.

The validator rejects dangling references, unapproved or mismatched source
versions, cross-report/version nodes and edges, altered locators, duplicate IDs,
invalid relation endpoints and missing review provenance. It validates
**structure and traceability**, not whether a claimed semantic relation is
correct. `SUPPORTS` and `CONTRADICTS` therefore need separate human or
evaluated verifier review before an assessment consumes them.

## Local persistence and query

`LocalGraphStore(path)` uses SQLite with foreign keys and scoped indexes.
For a file-backed store, it creates a private `0700` immediate directory and
`0600` database file, or rejects an existing world-readable file/directory or
symlink. `:memory:` is available for tests.
`save(snapshot)` creates a generation or returns `UNCHANGED` for the same
canonical content. Changed extraction, model/config or review requires a new
`graph_version`; trying to reuse a version fails. Writes are transactional.

`graph_info(scope)`, `list_nodes(scope)`, `get_node(scope, node_id)` and
`outgoing_paths(scope, node_id)` require the entire scope. Node and path queries
return the source spans needed to open the original document/version/chunk.
`outgoing_paths` defaults to `accepted_only=True`; unreviewed or rejected
semantic edges are visible only when explicitly requested for QA.

`tombstone_document_version(workspace_id, version_id)` deletes every local
generation derived from that source or report version, cascading to nodes,
edges and spans. The tombstone prevents a later rebuild from reintroducing it.

Run focused tests from the repository root:

```bash
./.venv-research/bin/python -m pytest research/tests/test_evidence_graph_contract.py -q
```

## What remains

The fixture in tests uses manually authored nodes and relations. There is no
automatic claim/entity extraction, semantic contradiction verifier, gold-set
precision result, production MongoDB adapter, build worker or authenticated
HTTP graph API yet. The caller must enforce authorization before invoking this
local store; passing a scope is isolation of records, not user authentication.
