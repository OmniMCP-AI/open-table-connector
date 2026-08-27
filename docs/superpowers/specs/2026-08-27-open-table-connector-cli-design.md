# Open Table Connector CLI design

## Status

Approved direction: agent-first command line interface, with a human-readable
mode and a capability-driven import pipeline. The repository and project name
will become `open-table-connector`; the short executable name is `otc`.

## Goals

- Give agents one command vocabulary for every connector.
- Accept local CSV, JSON, JSONL, and human-readable table input.
- Convert between local formats and connector-backed tables without pairwise
  integrations.
- Support imports such as CSV to Google Sheets and Google Sheets to MaybeSheet.
- Keep credentials out of URIs, output, receipts, and persistent config files.
- Preserve the existing framework-neutral connector contracts.

## Non-goals for v1

- A persistent credential store or profile manager.
- Provider-specific formula calculation or formatting semantics.
- Schema migration, column mapping, or conflict-free multi-writer
  synchronization.
- A general-purpose SQL or transformation language.

## Command interface

The long-form command is `open-table-connector`; `otc` is the primary short
name. `open-connectors` remains a deprecated compatibility alias for the
command, but is not the new repository or package name.

```text
otc list
otc inspect SOURCE
otc read SOURCE [--output-format jsonl|json|csv|table]
otc convert SOURCE --to json|jsonl|csv --output FILE
otc import SOURCE DESTINATION [--if-exists append|replace|error]
```

`SOURCE` and `DESTINATION` can be connector URIs or local paths. Connector
selection is inferred from the URI scheme. Local format selection is inferred
from file extensions and can be overridden with `--input-format` or
`--output-format`.

The default output is JSONL. A read emits row events followed by one summary
event:

```json
{"event":"row","row":{"id":"a","amount":1}}
{"event":"summary","status":"completed","rows":1,"receipt":{}}
```

An import emits one completion event containing source and destination
receipts, row counts, and status. Errors are one credential-safe JSON object
on stderr and a nonzero exit code.

## Architecture

The CLI is a deep module over a small internal seam. The command layer does
not know provider request paths or provider payload shapes. It asks a registry
for an adapter, calls the existing contract roles, and routes Arrow tables to
format codecs or another writer.

```text
CLI parser
    |
    v
Command dispatcher ---- Format codecs (CSV/JSON/JSONL/table)
    |
    v
Connector registry
    |
    +--> local file reader/writer
    +--> Google Sheets adapter
    +--> Feishu Bitable adapter
    +--> MaybeSheet adapter
```

### Registry seam

`ConnectorRegistry` maps URI schemes to adapters and exposes capability lookup.
The registry is the only place where the CLI discovers connectors. A
destination that lacks `table.write` fails before any source rows are sent,
with `unsupported_capability` and the destination scheme in safe details.

### Table pipeline

1. Parse and validate the source address.
2. Select a source adapter or local format codec.
3. Read into an Arrow table, honoring row and timeout limits.
4. Emit or write through the selected destination codec/adapter.
5. Emit a summary with both receipts and counts.

The v1 implementation may materialize one Arrow table for simplicity, but the
pipeline interface should use batches internally so streaming JSONL and future
large-table implementations do not change the command contract.

### Format codecs

- CSV: first row is the header; empty fields are null.
- JSON: array of objects; object keys form the union of columns.
- JSONL: one object per non-empty line.
- table: aligned human-readable output and Markdown pipe tables as input. A
  Markdown separator row is optional when `--input-format table` is explicit.

Values that cannot be represented natively in a flat table are serialized as
JSON strings. Codec failures use `execution_failed` with the input path and
line/column information, never raw credential-bearing content.

## Connector-specific behavior

### Google Sheets

The existing Google Sheets adapter remains responsible for URI parsing,
Google Sheets API requests, sheet ranges, and write semantics. The CLI passes
generic `--range`/`--sheet` options only when supported by the adapter.

### Feishu Bitable

The existing Feishu adapter remains responsible for record pagination, field
selection, record IDs, and append writes. The CLI treats `_record_id` as a
connector-owned identity column and does not invent provider updates.

### MaybeSheet

Add `table.write` through the current `ProcessClient` seam. Extend that seam
with an optional stdin payload and make the writer invoke
`mbs <base-or-sheet-command> write --uri URI --target TARGET --input -`, sending
newline-delimited JSON records on stdin. The process client passes credentials
through its existing credential-safe environment mechanism and returns the
process JSON response as a neutral receipt. The CLI can therefore route Google
Sheets reads to MaybeSheet writes without knowing MaybeSheet’s subprocess
details.

MaybeSheet `replace` semantics must be rejected unless the process protocol
provides an explicit replace operation; `append` and `error` must have
deterministic meanings and tests.

## Configuration and security

- Google Sheets token: `GOOGLE_SHEETS_ACCESS_TOKEN`.
- Feishu token: `FEISHU_TENANT_ACCESS_TOKEN`.
- MaybeSheet credentials: the existing process-client environment mapping.
- Explicit flags override environment values.
- No credential values are printed in JSONL, tables, errors, or receipts.
- No persistent config file is read or written in v1.

## Exit codes

- `0`: completed.
- `2`: usage or input-format error.
- `3`: unsupported connector or capability.
- `4`: authentication failure.
- `5`: provider or local execution failure.
- `6`: conflict or invalid write policy.

## Testing strategy

Tests cross the public CLI seam with fake registry adapters, fake transports,
and in-memory streams. They cover:

- command dispatch and URI-based connector selection;
- JSONL default output and human table output;
- CSV/JSON/JSONL conversion round trips;
- row limits and summary receipts;
- CSV to Google Sheets and Google Sheets to MaybeSheet pipelines;
- capability and exit-code failures;
- credential redaction;
- MaybeSheet write argument construction and process errors.

Provider API calls remain covered by the existing injected transport tests;
the CLI test suite does not require network credentials.
