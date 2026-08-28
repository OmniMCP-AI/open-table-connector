# Universal connector conformance suite design

## Status

Approved direction: a dedicated, offline, universal test suite covering every
connector package in the workspace. The suite must contain at least 120 test
cases and must be deterministic in CI without credentials or network access.

## Scope

The suite covers the current connector packages:

- `local_files`
- `google_sheets`
- `feishu_bitable`
- `maybe_sheet`
- `sqlite`
- `postgres`
- `dbt`

The common suite tests behavior guaranteed by the neutral contract. Capability
specific tests are selected from each connector's declared capabilities. A
connector is never required to pass an assertion for a capability it does not
advertise; instead, the suite verifies that unsupported calls fail explicitly
and safely where the public API exposes that behavior.

## Test location and harness

Universal tests live under `specification/conformance/universal/`, separate
from provider implementation tests. A small harness defines a connector case
with:

- stable identity and expected contract version;
- capability and URI-scheme declarations;
- deterministic fixture construction and cleanup;
- read/inspect/write operations where supported;
- a recording transport, process client, or temporary local/database
  resource as appropriate.

Provider-specific fixture code is limited to setup and protocol assertions.
Shared assertions remain parametrized over connector cases. The harness must
not make network calls, read credentials from the environment, or depend on a
vendor CLI being installed.

## Coverage matrix

The dedicated suite will provide at least 120 collected tests, with the exact
count reported by a test-count check. The matrix will include:

1. identity, contract-version, capability, mode, and scheme discovery;
2. URI validation, credential-free values, and safe wire serialization;
3. capability-positive and capability-negative behavior;
4. deterministic reads and inspections for table-capable connectors;
5. Arrow/Polars parity where both capabilities are advertised;
6. row limits, timeout propagation, pagination, and bounded results;
7. schema/content fingerprints, receipts, source revisions, and row counts;
8. write request shape, append/replace/error policy behavior, and affected rows;
9. connector-owned fields and coordinate conventions;
10. provider/process failure mapping, authentication, conflict, timeout, and
    credential redaction;
11. CLI registry discovery, format conversion, JSONL summaries, table output,
    and local round trips through the same connector fixtures;
12. repeated-run determinism and fixture isolation.

Each matrix cell has a descriptive test name and tests one observable behavior.
The target is at least 120 collected tests, not merely 120 parametrized input
values hidden inside a single test function.

## Fixture rules

- Local files use temporary CSV, JSON, JSONL, Markdown-table, and spreadsheet
  fixtures.
- Google Sheets and Feishu use recording transports that assert request shape
  and return stable provider payloads.
- MaybeSheet uses a recording process client that captures argv, stdin, and
  credential-safe environment behavior.
- SQLite and Postgres use isolated temporary databases or recording database
  seams; no external database service is required.
- dbt uses a temporary project and recording runner/artifact boundary; no dbt
  executable or project outside the fixture is required.

## Failure policy

Failures must identify the connector case, capability, fixture, and expected
contract invariant. Error assertions must inspect stable error codes and safe
details, never raw provider payloads or credentials. Tests must not weaken
provider-specific tests or change production behavior merely to satisfy the
universal suite.

## Acceptance criteria

- Every current connector package is represented by a named case.
- The dedicated suite collects at least 120 tests.
- The suite passes offline with a fresh workspace setup.
- Full workspace tests continue to pass.
- No test requires credentials, network access, a vendor binary, or a shared
  mutable database.
- The suite documents how to run only universal tests and how its count is
  checked.
