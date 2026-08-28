# Task 2 Report: Concrete CSV, Excel, and Markdown Connectors

## Scope

Implemented the Task 2 concrete local-format connector seams inside
`packages/local_files`:

- added `CsvConnector`, `ExcelConnector`, and `MarkdownConnector`
- added format-specific request and option dataclasses
- added shared helpers for connector identities, manifests, inspections, and
  receipts
- added a shared private explicit-scheme local-path resolver for `csv://`,
  `excel://`, and `md://`
- preserved existing public `local_files` exports while extending
  `open_table_connector.local_files.__init__`

## TDD Trace

1. Added failing tests:
   - `packages/local_files/tests/test_csv_connector.py`
   - `packages/local_files/tests/test_excel_connector.py`
   - `packages/local_files/tests/test_markdown_connector.py`
2. Verified the red phase with:
   - `uv run python -m pytest packages/local_files/tests/test_csv_connector.py packages/local_files/tests/test_excel_connector.py packages/local_files/tests/test_markdown_connector.py -q`
   - initial result: 3 collection errors because the concrete connector modules
     did not exist
3. Implemented the minimal connector modules and shared helpers.
4. Re-ran the focused suite, fixed one over-escaped Markdown test fixture, then
   re-ran to green.

## Implementation Notes

- `identity.py` now exposes `connector_identity()` so the concrete connectors
  and the compatibility facade share versioned identity construction.
- `manifest.py` now exposes `capability_manifest()` so each concrete connector
  advertises the same read/inspect/resolve capability set with its own explicit
  URI scheme.
- `receipts.py` now supports connector-specific receipts while preserving the
  existing `local_files` default behavior.
- `inspection.py` now supports caller-specified `header_row` and conditional
  worksheet facts so concrete connectors can report format-appropriate
  inspection details without CLI imports.
- `resolver.py` now contains `_resolve_explicit_local_path()` for concrete
  scheme validation:
  - scheme must match exactly
  - query parameters are rejected
  - unsupported hosts are rejected
  - paths must be absolute regular files
  - byte limits are enforced
  - explicit schemes fail closed when the probed format does not match
- `__init__.py` now re-exports the new concrete connectors and request/option
  types without removing existing public imports.

## Verification

Focused connector suite:

- `uv run python -m pytest packages/local_files/tests/test_csv_connector.py packages/local_files/tests/test_excel_connector.py packages/local_files/tests/test_markdown_connector.py -q`
- result: `21 passed in 0.60s`

Affected package suite:

- `uv run python -m pytest packages/local_files/tests -q`
- result: `41 passed in 17.16s`

Full workspace suite:

- `uv run python -m pytest -q`
- result: `460 passed in 8.02s`

Formatting / diff checks:

- `git diff --check`
- result: no output

## Self-Review

- The diff stays inside the local-files distribution plus the requested task
  report and tests.
- Existing `local_files` public imports remain available.
- Explicit concrete schemes now fail closed on mismatched payloads and do not
  introduce any network or credential behavior.
- Arrow and Polars reads share one canonical Arrow materialization per
  connector, which keeps schema/content fingerprints identical across both
  read capabilities.

## Concerns

- None for Task 2 scope. The `local_files` compatibility facade still has its
  own follow-up delegation work in Task 3, but Task 2’s concrete connectors and
  their package-level regressions are green.
