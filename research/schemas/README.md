# Core MVP output contracts

The three Draft 2020-12 JSON Schemas describe the stable boundary between the
offline pipelines, backend/worker and lecturer-facing UI:

- `similarity-report-v1.schema.json`: Pipeline 1 retrieval, review candidates,
  exact evidence and document-level coverage;
- `assessment-report-v1.schema.json`: Pipeline 2 checklist decisions, rationale,
  criterion scores and abstention;
- `evidence-v1.schema.json`: traceable Evidence Pack item.

`research.core_mvp.contracts` enforces the safety-critical subset at runtime.
It rejects untraceable evidence, inconsistent relation/outcome pairs and any
match counted in confirmed coverage without an exact report/source span. The
schemas remain forward-compatible so diagnostic fields can be added without a
breaking format change.

`research.schema_validation.validate_json_schema` runs the checked-in schemas
with the official `jsonschema` Draft 2020-12 validator and resolves the evidence
`$ref` from an in-memory registry, without fetching remote schemas. Run it on
the generated similarity report, assessment report, or an Evidence Pack entry
with `kind="similarity"`, `"assessment"`, or `"evidence"`. Schema validation
checks shape and types; keep the runtime cross-field/provenance checks as well.
