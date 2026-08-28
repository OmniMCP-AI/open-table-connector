# Local Connector Types Design

## Status

Approved in chat on 2026-08-28. Implementation has not started.

## Context

The local connector currently exposes one `local_files` identity and uses
content probing to distinguish CSV and XLSX files. The CLI also understands
Markdown tables, but Markdown is currently implemented only in the CLI format
layer. This leaves discovery, URI routing, and direct connector usage unable to
name the concrete table formats.

## Goals

- Expose concrete connector identities for `csv`, `excel`, and `md`.
- Preserve the existing `local_files` identity as a compatibility facade.
- Preserve `file://` URIs and bare local paths through format autodetection.
- Add explicit URI schemes for direct format selection:
  `csv://`, `excel://`, and `md://`.
- Keep format-specific behavior behind small, testable connector interfaces.
- Keep neutral connector code independent of the CLI package.
- Preserve the existing CLI `--from`/`--to` conversion and import workflows.

## Non-goals

- Do not remove or rename the `MaybeSheet`, Google Sheets, Feishu, SQLite,
  PostgreSQL, or dbt connector identities.
- Do not require callers using `file://` or bare paths to add a format scheme.
- Do not add a new distribution for every local format in this change. The
  existing local-files distribution owns the concrete implementations and the
  compatibility facade.
- Do not change the public Python type names `MaybeSheetConnector` or other
  unrelated connector types.

## Connector identities and schemes

The local-files distribution will expose four connector identities:

| Identity | Explicit schemes | Compatibility behavior |
| --- | --- | --- |
| `csv` | `csv` | Reads CSV, TSV, and semicolon-delimited text according to CSV options. |
| `excel` | `excel` | Reads XLSX files and supports worksheet selection. |
| `md` | `md` | Reads Markdown pipe tables. |
| `local_files` | `file` | Probes the file and delegates to one of the three concrete connectors. |

`file://` remains the stable compatibility URI. A `file://` URI with a CSV,
XLSX, or Markdown payload is resolved by the facade. An explicit concrete URI
must resolve to its declared format and fail closed if the payload is not that
format.

The CLI registry will expose all four identities. Its routing rules are:

1. `csv://`, `excel://`, and `md://` select the matching concrete adapter.
2. `file://` and bare paths select the `local_files` facade adapter.
3. The facade probes the resource and delegates the operation to the concrete
   connector implementation.

## Module structure

The existing `packages/local_files` distribution remains the ownership seam.
Its implementation will be organized around format-specific modules:

- `csv_connector.py`: CSV identity, options, request, resolver, read, and
  inspection behavior.
- `excel_connector.py`: Excel identity, options, request, resolver, read, and
  inspection behavior.
- `markdown_connector.py`: Markdown identity, options, request, resolver, read,
  and inspection behavior.
- `local_files_connector.py`: format probing and delegation for the existing
  `local_files` identity.
- Existing low-level readers remain internal implementations where their
  behavior is already correct; the new modules own the public seams.

Each concrete connector will implement the existing contract interfaces for
URI resolution, Arrow reads, Polars reads, and inspection. Format-specific
options will not leak into unrelated connectors:

- CSV options cover delimiter and encoding.
- Excel options cover worksheet and header row.
- Markdown options cover encoding and the accepted pipe-table grammar.

The Markdown parser will move into the neutral local-files distribution. The
CLI format layer may reuse that implementation, but the neutral package will
not import the CLI package.

## Data flow

```text
explicit csv:// ───────> CsvAdapter ───────> CsvConnector
explicit excel:// ────> ExcelAdapter ─────> ExcelConnector
explicit md:// ────────> MdAdapter ────────> MarkdownConnector
file:// / bare path ──> LocalFilesAdapter ─> probe ─> concrete connector
```

Reads and inspections return the same Arrow/Polars result and receipt shapes
already defined by the contract package. Explicit concrete endpoints use the
concrete connector identity in receipts. Compatibility facade reads retain the
`local_files` identity in receipts, even when the facade delegates internally.

CLI writes and conversions continue to use the existing local format writers.
An explicit concrete destination selects its format directly; a local path
continues to use extension/format inference. No provider connector imports the
CLI package.

## Compatibility and errors

- Existing imports from `open_table_connector.local_files` remain available.
- Existing `LocalReadOptions`, `LocalTableReadRequest`, and
  `LocalFilesConnector` remain available during this migration.
- Unsupported format payloads produce the existing stable connector error code
  with safe path/suffix details only.
- Explicit concrete schemes reject a mismatched payload rather than silently
  falling back to another format.
- The facade preserves current content-probing behavior for `file://` inputs.
- No credentials or network access are introduced for local formats.

## Verification

The implementation is complete only when the following are covered:

- Each concrete connector has manifest, identity, URI resolution, Arrow/Polars
  parity, inspection, limits, and malformed-input tests.
- Markdown reads and CLI writes round-trip escaped cells, separator-looking
  rows, empty cells, and hyphen-only data rows.
- The facade continues to autodetect CSV and XLSX and now delegates Markdown.
- CLI discovery lists `csv`, `excel`, `md`, and `local_files` with their schemes.
- Explicit concrete schemes and compatibility `file://`/bare-path routing are
  tested, including mismatched-format failures.
- The full workspace test suite, compilation check, lock check, package build,
  and CLI smoke tests pass.
