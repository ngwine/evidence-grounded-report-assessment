# W3.1 — CI quality/security gate scope

The workflow in `.github/workflows/ci.yml` now runs unit/integration fixtures,
OpenAPI parsing, frontend type-check/build, and these blocking quality gates:

Separate jobs also run the synthetic Chromium E2E and an authenticated MongoDB
replica set. The latter executes six live validator/role/queue/transaction tests,
restart recovery and two idempotent bootstrap runs; private generated secrets
are not uploaded. Optional tests still skip in the dependency-heavy unit job,
but their MongoDB cases must run in `mongo-integration` before CI is green.
Mongo integration uses the explicitly declared `ubuntu-22.04` hosted target,
logs kernel/runner image identity and the locked Mongo image, and leaves the
upstream kernel startup guard enabled. OS label is not a frozen kernel version;
passing this job does not prove support for arbitrary newer Linux kernels.

| Gate | Enforced scope | Failure policy |
|---|---|---|
| Ruff `E4,E7,E9,F` | Backend source and offline retrieval/core MVP/Evidence Graph Python source | Any selected finding fails; this is not full style coverage |
| Mypy | MongoDB schema/migration/roles/queue package and citation-marker adapter | Any typing error fails; other legacy/experimental modules are not yet covered |
| Bandit `-ll` | All backend source | Medium/high severity findings fail; no project-level skip or baseline |
| `pip-audit --strict` | Actual resolved Python environment installed by CI (research, backend and quality dependencies) | Any known advisory or audit-resolution failure fails; no ignored advisory IDs |
| npm audit wrapper (`scripts/audit_web_dependencies.py`) | The locked web dependency tree, explicitly including dev dependencies | High/critical advisories fail immediately; recognized transport errors retry at most three times; unresolved audit failures still block |
| Gitleaks v8.30.1 container digest | Checked-out repository files in a separate job | Any detected secret fails; output redacted; inline `gitleaks:allow` comments ignored |

All tool versions are pinned in `services/backend/requirements-quality.txt`;
Gitleaks uses the [official GHCR image](https://github.com/gitleaks/gitleaks/pkgs/container/gitleaks)
with an immutable digest. The scan does **not** inspect every historical Git
commit, non-default branch, ignored private `var/` file, or external data
source. It is not a data-rights/PII approval gate. A genuine false positive
must be triaged with the reviewer and an explicit, narrow, dated decision;
never add an arbitrary ignore rule merely to make CI green.

Local rerun after installing the quality requirements:

```bash
.venv-research/bin/python -m pip install -r services/backend/requirements-quality.txt
.venv-research/bin/ruff check --select E4,E7,E9,F services/backend/src research/offline_retrieval research/core_mvp research/evidence_graph
.venv-research/bin/mypy --check-untyped-defs --show-error-codes --follow-imports=silent services/backend/src/kltn_ai/db services/backend/src/kltn_ai/integrations/parsing/citation_markers.py
.venv-research/bin/bandit -q -r services/backend/src -ll
.venv-research/bin/python -m pip_audit --strict --progress-spinner off
.venv-research/bin/python scripts/audit_web_dependencies.py
```

The dependency audits query external advisory services and therefore cannot
be reproduced offline. Passing these checks means no findings **under the
declared scanners, scopes and advisory snapshot**; it does not establish
production readiness, complete RBAC, secured MongoDB, or absence of security
issues outside these tools.

## Audit-service reliability check, 23/10/2026

GitHub Actions run `39740629863`, web job `119696714938`, installed the lockfile
and completed TypeScript/Vite build successfully. Its web failure was the npm
advisory service returning HTTP 503, not a reported dependency advisory. A fresh
local read-only audit returned zero vulnerabilities.

The wrapper checks findings before retry and never waives an advisory. Only
recognized HTTP 5xx/network failures or an 18-second process timeout retry, at
most three attempts with 1- and 2-second delays (57 seconds maximum waiting).
Internal npm retries are disabled; each fetch is limited to five seconds.
HTTP 401/403/429, configuration errors, invalid JSON and unexplained nonzero
exits fail without retry. Exhausted retries still fail CI. Logs contain only
safe error codes/counts, not raw registry URLs or npm output. Offline unit tests
exercise these decisions, including JSON shapes observed from actual npm HTTP
503 and connection-refused invocations against local fixtures.

The final wrapper preflight passed **34 offline tests**, Ruff on the wrapper
and its tests, and a live invocation with **high=0, critical=0, moderate=0,
low=0**. These checks did not modify the dependency lockfile or suppress any
advisory, and do not substitute for the next clean-checkout GitHub CI result.

That clean-checkout result is now available for code commit `37c6277`:
[run `39834435765`](https://github.com/ngwine/evidence-grounded-report-assessment/actions/runs/39834435765)
passed **all five jobs** on 23/10/2026 (local timezone). Mongo's job records
Linux 6.8.0-1064-azure, Ubuntu runner image20261012.322.1 and locked Mongo8.0.34
digest, plus six live tests/restart/reapply. This records those exact targets,
not an assurance for every kernel or future advisory snapshot.

## Local preflight, 22/10/2026

- Ruff on the declared core scope: pass, after removing one unused import in
  `research/core_mvp/assessment.py`.
- Mypy on the MongoDB package plus citation adapter: pass. Extending the same invocation
  to `research/evidence_graph/contract.py` currently reports 16 type errors;
  graph is therefore **not** covered by the type gate yet.
- Bandit backend source at medium/high severity: pass.
- `npm audit --audit-level=high` on the existing web lockfile: no advisories.
- `pip-audit --strict` first found `PYSEC-2026-4320` in certifi 2026.7.22
  and `PYSEC-2026-1845` in pytest 8.4.2. The backend dependency floor was
  raised to certifi 2026.10.19 and pytest 9.0.3; after upgrading the local
  environment to certifi 2026.10.19 and pytest 9.1.1, the audit passed with
  **no known vulnerabilities found**. No advisory was ignored or waived.
  A fresh CI resolution still requires its own audit result.
- Gitleaks v8.30.1 was run with the pinned image/digest and the same `dir`
  flags as CI against a temporary snapshot of the **current** Git-tracked
  files plus non-ignored new files (294 files, about 2.14 MB): **no leaks
  found**. The snapshot contained only `var/.gitignore` from `var/`, not
  private datasets or ignored virtual environments. An earlier commit-only
  scan had flagged index-design prose in `docs/architecture/data-dictionary.md`
  as `generic-api-key`; the prose was reworded before this clean worktree-file
  scan. No Gitleaks allowlist or suppression was added. This does not clear the
  historical commit that contains the old wording, or unscanned private files.
- The final local rerun after the MongoDB schema/migration/role additions
  passed Ruff on the declared core scope, Mypy on its two declared modules,
  Bandit over **all** backend source, and 26 focused citation/MongoDB tests.
  The full `research/tests services/backend/tests` suite then finished with
  **299 passed, 7 skipped**; those skips remain outside this gate's coverage.
  `pip-audit --strict` again reported no known vulnerabilities; `npm audit
  --audit-level=high` again reported zero vulnerabilities. These local results
  are not a substitute for a fresh GitHub CI run on a clean checkout.
