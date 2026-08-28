# Task 4 Report

Date: 2026-08-28

## Implementation Commit

`a47ad178282a03a7f137bfdf30d046f56f319fc9` —
`test: add universal database connector conformance`

## Files Changed

- `specification/conformance/universal/cases.py`
- `specification/conformance/universal/fixtures.py`
- `specification/conformance/universal/test_database_connectors.py`

No production connector implementation was changed.

## TDD Evidence

### Red

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_database_connectors.py -q
```

Result:

```text
18 failed, 19 passed in 0.81s
```

The expected failures covered the missing Postgres fixture handle, absent
connection/cursor lifecycle recordings, non-filtering SQL responses, missing
authentication/execution failure injection, permissive unexpected SQL, and
the recording seam's lack of existing-table behavior for `if_exists="error"`.

The red run also showed that SQLite's public `inspect()` path intentionally
uses its default read request without carrying the supplied row limit. The
inspection agreement test was corrected to compare the connector's unbounded
public inspect and read results, while bounded reads remain covered separately.

### Green

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_database_connectors.py -q
```

Result:

```text
37 passed in 0.64s
```

## Coverage Added

- Capability-filtered SQLite and Postgres cases for URI resolution, bounded
  Arrow reads, Arrow/Polars parity, and inspect/read agreement.
- Table-option and query-option selection with exact Postgres statements and
  parameters plus real SQLite query results.
- Append, replace, existing-table error, and invalid write policies with exact
  SQL, affected rows, and receipt assertions.
- Execute, commit, abort, conflict, transaction deferral, rollback, and close
  state across a real temporary SQLite database and recording Postgres DB-API
  connections.
- Safe read/write receipts, credential locality, stable Postgres
  authentication/execution errors, and stable SQLite execution errors.
- A fail-closed Postgres factory/cursor that records `execute`, `fetchmany`,
  `description`, `rowcount`, `executemany`, `commit`, `rollback`, and `close`,
  rejects unexpected SQL, and refuses non-fixture hosts.

## Verification

- Focused database suite:
  `uv run python -m pytest specification/conformance/universal/test_database_connectors.py -q`
  — `37 passed in 0.64s`.
- All universal tests:
  `uv run python -m pytest specification/conformance/universal -q`
  — `165 passed in 1.95s`.
- SQLite, Postgres, and dbt regressions:
  `uv run python -m pytest packages/sqlite/tests packages/postgres/tests packages/dbt/tests -q`
  — `7 passed in 0.66s`.
- Full workspace suite: `uv run python -m pytest` —
  `352 passed in 5.47s`.
- `uv run python -m compileall -q packages specification/conformance/universal`
  — passed.
- `git diff --check` — passed.

## Concerns

- SQLite's public `inspect()` implementation does not propagate the caller's
  `ResourceLimits` and reads its default `main.table`. The universal fixture
  preserves that production behavior; bounded-read coverage is asserted on
  `read_arrow`/`read_polars` instead.
- Postgres production error mapping preserves `str(exc)` in safe details. The
  deterministic failure fixtures therefore use credential-free provider
  diagnostics and separately prove that request credentials stay out of URIs,
  receipts, and serialized errors; production redaction behavior was not
  changed in this test-only task.
- The Postgres recorder intentionally whitelists the exact SQL emitted by the
  current connector and refuses unknown hosts/statements. A deliberate future
  SQL-shape change will require updating the fixture and its conformance
  assertions together.
