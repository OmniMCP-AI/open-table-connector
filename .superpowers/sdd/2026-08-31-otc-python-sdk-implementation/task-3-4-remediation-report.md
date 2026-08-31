# Task 3/4 remediation report

Date: 2026-08-31

## Scope

- Made `Query` bindings recursively immutable and gave relational and temporal
  portable plans canonical `sha256:` identities. Temporal operation details now
  participate through the existing `PortableTemporalPlan` wire identity.
- Added recursive Client-affinity preflight with
  `CLIENT_AFFINITY_MISMATCH` before any physical source read.
- Corrected SQLGlot `LEFT JOIN` lowering and added conservative relational
  source, total-input, intermediate, output, byte, and duration admission.
- Added execution evidence with effective limits, observed rows/bytes/duration,
  plan identity, and definition identity.
- Added explicit provider-native SQL through `Client.native_sql(target)`, with
  one-statement/read-only policy, unsafe-function rejection, bounded query
  evidence, mutation lifecycle/idempotency evidence, and unknown-outcome
  reconciliation. SQLite and PostgreSQL expose their existing read paths through
  `read_native_sql`; SQLite is exercised against a real database.
- Added the narrow temporal SQL lane on `TimeSeriesView.sql`: exact bounded
  scans, latest-per-series, fixed-bucket aggregate, and fixed-bucket gap fill
  lower to the existing typed temporal operations. Unsupported shapes reject;
  there is no SQL fallback, Polars SQLContext, or DuckDB dependency.
- Expanded temporal and managed-storage receipt evidence. Expired abort now
  returns a non-mutation evidence receipt rather than a receiptless success.

## Regression tests

- Query mapping/deep-parameter immutability and canonical identity.
- Mixed-client graph rejection before connector reads.
- Source/output resource admission and execution receipt evidence.
- LEFT JOIN unmatched-row preservation.
- Native query/execute policy, unsupported connectors, and real SQLite
  integration.
- Temporal plan identity, all four temporal SQL forms, unsupported/unbounded
  temporal SQL, and expired-abort evidence.

## Verification

- `uv run --frozen pytest packages/sdk/tests packages/sqlite/tests/test_reader.py packages/postgres/tests/test_reader.py packages/contract/tests -q`
  (`99 passed`)
- `uv run --frozen pytest packages/timeseries/tests --ignore=packages/timeseries/tests/test_performance_characterization.py --ignore=packages/timeseries/tests/test_storage_protocols.py -q`
  (`67 passed`)
- focused Ruff over all changed SDK sources and tests
- SDK `compileall`
- scoped `git diff --check`

The complete time-series test directory currently has two unrelated baseline
collection/assertion issues: the performance characterization cannot import
the top-level `benchmarks` package under this invocation, and the storage
protocol test's closed error-code set omits the already-present
`configuration` connector error. Neither is caused by this remediation; the
remaining time-series suite is run separately above.

A repository-wide `python -m pytest -q` run reached `926 passed, 3 skipped`
and `42 failed`. The failures are outside the Task 3/4 regression surface:
the concurrent CLI/provider refactor has not yet updated its conformance
fixtures, provider transport tests have unrelated baseline mismatches, the
PostgreSQL read-only transaction hardening changes legacy cursor-call
expectations, and the already-present `configuration` error code has not yet
been mirrored into the schema/closed-set assertions. The one repository policy
failure initially attributable to this patch (a repeated PostgreSQL dialect
literal) was corrected and its exact policy test now passes.
