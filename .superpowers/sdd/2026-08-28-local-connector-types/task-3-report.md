# Task 3 Report: Preserve `local_files` Compatibility Facade

## Outcome

Implemented the `local_files` compatibility facade as a delegating wrapper
around the concrete CSV, Excel, and Markdown connectors while preserving the
public `LocalReadOptions`, `LocalTableReadRequest`, `LocalFilesConnector`,
`LocalURIResolver`, and `local_files` receipt identity for `file://` reads.

## Changes

- Added
  [packages/local_files/src/open_table_connector/local_files/local_files_connector.py](/Users/admin/Code/GitHub/open-table-connector/packages/local_files/src/open_table_connector/local_files/local_files_connector.py)
  as the compatibility facade implementation.
- Turned
  [packages/local_files/src/open_table_connector/local_files/reader.py](/Users/admin/Code/GitHub/open-table-connector/packages/local_files/src/open_table_connector/local_files/reader.py)
  into a stable compatibility re-export for the existing public imports.
- Updated
  [packages/local_files/src/open_table_connector/local_files/__init__.py](/Users/admin/Code/GitHub/open-table-connector/packages/local_files/src/open_table_connector/local_files/__init__.py)
  to export the facade from its new home.
- Adjusted
  [packages/local_files/src/open_table_connector/local_files/probe.py](/Users/admin/Code/GitHub/open-table-connector/packages/local_files/src/open_table_connector/local_files/probe.py)
  so single-column `.csv` and `.tsv` files still autodetect through the
  compatibility `file://` path while Markdown continues to be identified by
  pipe-table structure.
- Added
  [packages/local_files/tests/test_local_files_connector.py](/Users/admin/Code/GitHub/open-table-connector/packages/local_files/tests/test_local_files_connector.py)
  to cover Markdown delegation, compatibility receipts, Excel preservation,
  and rejection of sheet selection for non-Excel formats.

## TDD Notes

Started with failing compatibility tests:

```bash
uv run python -m pytest packages/local_files/tests/test_local_files_connector.py packages/local_files/tests/test_resolver.py packages/local_files/tests/test_conformance.py -q
```

Observed failures:

- Markdown `file://` reads fell into the Excel branch and raised workbook-open
  errors.
- Single-column `.csv` content was not detected by the local format probe.
- Markdown sheet-selection errors surfaced as Excel execution failures instead
  of compatibility URI validation errors.

Implemented the facade/probe changes, then reran focused compatibility tests:

```bash
uv run python -m pytest packages/local_files/tests/test_local_files_connector.py packages/local_files/tests/test_resolver.py packages/local_files/tests/test_conformance.py packages/local_files/tests/test_csv_reader.py packages/local_files/tests/test_excel_reader.py packages/local_files/tests/test_probe.py -q
```

Result: `22 passed in 0.62s`

## Full Verification

Ran the full workspace test suite once before commit:

```bash
uv run python -m pytest -q
```

Result: `465 passed in 8.98s`

## Self-Review

Reviewed the diff with `git diff -- packages/local_files/src/open_table_connector/local_files packages/local_files/tests`.

Checked for:

- Stable public import paths from `open_table_connector.local_files` and
  `open_table_connector.local_files.reader`.
- `local_files` receipt identity preservation for compatibility reads.
- Excel-only sheet selection semantics.
- No impact on existing focused CSV/XLSX compatibility tests.

No additional issues found in self-review.

## Concerns

None at hand. The facade currently delegates by building concrete connector
requests and reusing the concrete connectors' internal canonical read paths,
which keeps the compatibility surface thin while preserving `file://` receipts.

## Review Fix Round 1: Preserve Facade Options During Inspection

### Finding and root cause

`LocalFilesConnector.inspect()` rebuilt a `LocalTableReadRequest` from only the
URI and resource limits. Because `InspectRequest` has no format-specific
options, an option-bearing compatibility request lost its `separator`,
`encoding`, `sheet`, and `header_row` values before delegation. Inspection
could therefore disagree with the corresponding compatibility read.

### Fix

- `inspect()` now accepts the existing `InspectRequest` form and the public
  `LocalTableReadRequest` form. It reuses the latter directly so all facade
  options reach the concrete connector.
- Inspection metadata now receives the facade request's `header_row`.
- Replaced the facade's `tuple[Any, Any]` helper return type with an explicit
  union of concrete connector/request pairs.

### TDD regression coverage

Added these focused tests in
`packages/local_files/tests/test_local_files_connector.py`:

- `test_local_files_facade_inspection_honors_csv_read_options` verifies a
  semicolon-delimited Latin-1 CSV is inspected with the requested separator
  and encoding.
- `test_local_files_facade_inspection_honors_excel_read_options` verifies
  worksheet selection, header-row selection, columns, and coordinate metadata
  during inspection.

The new tests were first run against the unfixed implementation:

```bash
uv run python -m pytest packages/local_files/tests/test_local_files_connector.py -q
```

Observed output: `2 failed, 5 passed in 15.84s`. The failures were the
expected default UTF-8/comma CSV decode and default Excel header-row behavior.

After the fix, the covering compatibility tests were run with:

```bash
uv run python -m pytest packages/local_files/tests/test_local_files_connector.py packages/local_files/tests/test_resolver.py packages/local_files/tests/test_conformance.py packages/local_files/tests/test_csv_reader.py packages/local_files/tests/test_excel_reader.py packages/local_files/tests/test_probe.py -q
```

Output: `24 passed in 0.60s`.

The full workspace suite was then run with:

```bash
uv run python -m pytest -q
```

Output: `467 passed in 6.91s`.

`git diff --check` also completed successfully with no output. The round-1
fix was committed in the follow-up fix commit after the original Task 3
implementation commit `aa098c2`.
