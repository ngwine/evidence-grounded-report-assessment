# Exact vector index baseline — W5.2

`LocalExactVectorIndex` builds a private immutable generation from vectors,
parser/chunker/code versions, pinned model revision, source document versions,
hashes and provenance. Files are canonical JSON with a SHA-256 manifest. The
same input rebuild returns the same generation; changed content under the same
document-version ID and nondeterministic output under the same config fail.

`build()` requires ACTIVE/READY/APPROVED versions, declared purpose and rights
metadata. `search()` requires workspace, purpose and an explicit current allowlist
of document-version IDs. Filtering occurs before scoring. It returns stable
Top-K cosine results with chunk/version/source spans. The caller must fetch the
current allowlist from the authoritative repository each time; the stored
build-time approval is only a snapshot.

Use a private index directory under ignored `var/`. No model is loaded by this
adapter and no index is automatically activated. MongoDB generation activation,
concurrent run references, cleanup retention and a worker/retrieval integration
remain separate work. This exact search is suitable as a small-corpus baseline;
there is no approximate-search scalability claim.

```bash
.venv-research/bin/python -m pytest services/backend/tests/test_vector_index.py -q
```
