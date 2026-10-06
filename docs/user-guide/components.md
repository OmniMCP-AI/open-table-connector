# Components Manual

This manual explains package ownership, installation, dependency direction,
provider capabilities, and integration boundaries. Use the generated [API
inventory](../reference/api-inventory.md) for every public name and signature,
the [CLI manual](cli-manual.md) for command behavior, and the [SDK manual](sdk-manual.md)
for application workflows.

The layout follows patterns that work well in mature open-source projects:
DuckDB separates client/CLI concerns, csvkit separates input/processing/output
tools, Polars separates concepts from its API index, and Excelize documents
each workbook object family independently. OTC keeps those boundaries explicit
so optional providers do not leak into core imports.

## 1. Dependency layers

```text
contract
   |
   +--> spreadsheets --> local_files / remote sheet providers
   |
   +--> sdk ----------> cli
   |
   +--> artifacts ----> officecli
   |
   +--> mcp ----------> explicit SDK host
```

| Package | Owns | May depend on | Must not own |
| --- | --- | --- | --- |
| `contract` | closed identity, URI, receipt, error, and operation wire contracts | stdlib | providers, frameworks, OfficeCLI |
| `sdk` | `Client`, `Table`, `Query`, results, workbook facade, SQL | contract, optional protocols | provider-specific hidden fallback |
| `cli` | argparse, output codecs, exit mapping, shortcuts | SDK and installed adapters | a second mutation engine |
| `spreadsheets` | workbook operation schemas, rich qualification, snapshots, recipes | contract | provider imports, OfficeCLI |
| `local_files` | local CSV/JSON/JSONL/Markdown/XLSX routes and Excelize provider | contract, spreadsheets | remote credentials |
| `artifacts` | neutral export/view/watch models | contract | subprocesses, browser assumptions |
| `officecli` | optional DOCX/PPTX writer, view renderer, watch process | artifacts, contract | authoritative XLSX writes |
| `mcp` | official MCP stdio tools and policy boundary | SDK, contract | shell/module/credential injection |
| `formulas` | provider-neutral formula targets and expressions | contract | formula evaluation engine |
| `timeseries` | typed temporal descriptors/plans/evaluators | contract | provider-specific transport |
| provider packages | URI routing, credentials, physical I/O, provider evidence | contract/SDK protocols | framework publication policy |

The package boundary checks in CI enforce this direction. Optional package
absence must not make `import open_table_connector.sdk` fail.

## 2. Installation profiles

| Profile | Install | Enables |
| --- | --- | --- |
| Core SDK | `open-table-connector-sdk` | client, tables, query/result contracts |
| CLI | `open-table-connector` | `otc`, local routing, discovery |
| Local workbooks | `open-table-connector-local-files` | CSV/JSON/JSONL/XLSX/Markdown, Excelize |
| Spreadsheet contracts | `open-table-connector-spreadsheets` | operation catalog, sessions, recipes |
| Google Sheets | `open-table-connector-google-sheets` | configured remote sheet connector |
| MaybeSheet | `open-table-connector-maybe-sheet` | canonical HTTPS document connector |
| Feishu | `open-table-connector-feishu-bitable` | base-mode Bitable connector |
| SQL | `open-table-connector-sqlite` / `...-postgres` | database connectors |
| Artifacts | `open-table-connector-artifacts` | neutral DOCX/PPTX/view/watch contracts |
| OfficeCLI | `open-table-connector-officecli` | optional document adapter/process |
| MCP | `open-table-connector-mcp` | official typed MCP stdio server |
| Temporal | `open-table-connector-timeseries` | descriptors, plans, SQL Lite |

Install a narrow profile in production and all packages only in a development
workspace. Provider entry points are discovered lazily and can be disabled in
configuration.

## 3. `contract`: the stable boundary

The contract package defines `TableURI`, connector identities, canonical route
names, `OperationResult`, `Receipt`, `ErrorInfo`, `OTCError`, and closed
operation structures such as `TargetSelector`, `OperationRequest`,
`ExecutionOptions`, and `OperationDescriptor`.

Use contract types at process/API boundaries. Do not serialize ad hoc dicts
when a closed model exists:

```python
from open_table_connector.contract import OperationRequest, TargetSelector

request = OperationRequest(
    "spreadsheet", "range.read", "1.0",
    TargetSelector("file:///absolute/report.xlsx", "Report", None),
    {"address": "A1:B2"},
)
wire = request.to_wire()
```

`TargetSelector.to_wire()` always emits `uri`, `sheet`, and `object_id`.
`from_wire()` rejects unknown or missing keys. This strictness prevents MCP,
CLI, and SDK callers from drifting into incompatible request shapes.

## 4. `sdk`: application facade

The SDK owns routing and normalized result semantics. Its major components are:

| Module | Public surface |
| --- | --- |
| `sdk.client` | `Client`, config construction, materialization, SQL, formulas |
| `sdk.table` | `Table`, bindings, read/page/insert/update/delete/drop |
| `sdk.query` | `Query`, lanes, resource limits, plan hashes |
| `sdk.workbook` | workbook/session/worksheet/range/formula handles |
| `sdk.discovery` | operation catalog and target capability observation |
| `sdk.operations` | generic typed dispatch |
| `sdk.recipes` | observation-backed export/apply |
| `sdk.snapshots` | bounded local/remote workbook snapshots |
| `sdk.artifacts` | optional export/view/watch facade |
| `sdk.preview_sessions` | owned disposable runtime records |
| `sdk.result` | result, receipt, error, reconciliation types |

The [SDK manual](sdk-manual.md) includes examples for every workflow family;
the [API inventory](../reference/api-inventory.md) includes inherited public
members and enum wire values.

## 5. `cli`: thin executable layer

The CLI parses arguments, resolves credentials, builds the provider registry,
calls SDK functions, and maps result/error states to output and exit codes. It
does not implement an independent workbook writer or remote retry policy.

```text
argv -> argparse -> endpoint/config -> SDK/adapter -> result -> output/exit
```

CLI options are generated from the parser by `scripts/generate_reference_manuals.py`.
Run `scripts/check_cli_reference.py` when changing a parser command, and keep
examples in [cli-manual.md](cli-manual.md) aligned with that parser.

## 6. `spreadsheets`: workbook contract and Excelize reuse

This package is provider-neutral. It owns operation schemas for:

- workbook inspect/write/verify/reconcile/copy;
- worksheet list/create/delete/rename/move/config/config-read;
- range read/write/clear/sort/merge/unmerge;
- style, format, alignment, border, and text-layout read/write;
- formula set;
- image insert/list/read/delete; and
- observed layout recipe and rich qualification envelopes.

The operation catalog is exhaustive in [spreadsheet-schemas.md](../reference/spreadsheet-schemas.md).
The package does not import Excelize or OfficeCLI. Local provider support is
qualified by independent save/reopen evidence; unsupported object families
fail closed.

## 7. `local_files`: local codecs and workbook provider

`local_files` owns bare-path and `file://` routing for CSV, JSON, JSONL,
Markdown, and XLSX. CSV remains a format/codec, not a public `csv://` route.
The workbook provider uses the existing Excelize-backed implementation.

Use `rich-artifact/1.0` only for the currently qualified image subset:

```python
book = client.workbook.create(
    "file:///absolute/report.xlsx",
    profile="rich-artifact/1.0",
)
```

OfficeCLI is never imported by this authoring path. This preserves workbook
objects that the Excelize provider already supports and avoids a renderer
becoming an accidental spreadsheet writer.

## 8. Remote providers

| Provider | Target form | Mode | Credential binding | Evidence caveat |
| --- | --- | --- | --- | --- |
| Google Sheets | `gsheets://SPREADSHEET/SHEET` | sheet-mode | access token reference | provider revision/readback |
| MaybeSheet | `https://www.maybe.ai/docs/spreadsheets/d/DOC` | base/sheet | access token reference | live target and operation evidence |
| Feishu Bitable | `feishu://APP/TABLE` | base-mode | tenant token reference | field/record identity |
| SQLite | `sqlite:///absolute/path.db` | base-mode | local config | transaction/readback |
| PostgreSQL | `postgresql://...` without secrets in committed files | base-mode | external binding | server transaction/visibility |

Providers own URI parsing, credential leases, physical retries, API limits,
and provider receipts. OTC owns neutral semantics, policy, and result
classification. A provider may advertise ordinary table reads but not workbook,
formula, temporal, or rich-object operations.

## 9. `formulas`: explicit provider-native formulas

`GridFormulaTarget` binds a sheet-mode worksheet; `FieldFormulaTarget` binds an
existing base-mode formula field. `FormulaExpression` requires a dialect and
is the only way to activate formula intent. Ordinary writes keep formula-like
strings literal.

| Provider | Grid dialect | Field dialect | Recalculation |
| --- | --- | --- | --- |
| Local Excel | `excel-a1` | none in qualified surface | range/worksheet/workbook |
| Google Sheets | `google-sheets-a1` | none | provider-dynamic values |
| MaybeSheet | `maybe-sheet-a1` | `maybe-base` | explicit provider scopes |
| Feishu | none | `feishu-bitable` | provider behavior |

## 10. `timeseries`: bounded temporal execution

Temporal components define descriptor schema, precision/timezone, series keys,
duplicate policy, ordering, resource bounds, typed plans, and receipts. They do
not own a remote transport. Use a provider/executor that advertises the
required capability. Half-open ranges and deterministic ordering are part of
the portable contract.

## 11. `artifacts` and `officecli`

`artifacts` is a neutral contract package. It defines `ExportRequest`,
`ViewRequest`, `WatchRequest`, `ArtifactValue`, `ViewValue`, and `WatchValue`
without importing a subprocess or browser.

`officecli` is an optional physical adapter. It can create DOCX/PPTX native
table snapshots and render disposable HTML/PNG/text/outline/stats/issues views.
It qualifies the pinned OfficeCLI version, uses argv-only bounded execution,
disables auto-update/resident behavior, rejects unsafe asset paths, and carries
source hashes. Watch uses owned loopback processes and discard persistence.

Required boundaries:

1. authoritative XLSX is written by the existing Excelize provider only;
2. OfficeCLI receives disposable snapshots, never remote credentials;
3. missing binary/browser returns `unsupported_capability`;
4. preview edits cannot publish back to the workbook; and
5. legacy `.doc`, `.ppt`, and `.xls` conversion is not implied.

## 12. `mcp`: typed agent boundary

The MCP package uses the official MCP stdio transport and registers exactly
`otc_discover`, `otc_inspect`, and `otc_execute`. An embedding deployment
supplies `MCPHost(client)` and optionally an `AccessPolicy`.

No-host inspect/execute fails closed. The boundary accepts only closed typed
operation requests and never accepts shell commands, arbitrary import names,
credentials, or undeclared wire fields. Policy authorization happens before
catalog dispatch.

## 13. Operational deployment patterns

### Minimal local batch

Install CLI + local-files, use `file://`, retain JSON results, and run
`generate_reference_manuals.py --check` in CI.

### Shared-sheet service

Install CLI/SDK + one provider, bind credentials by environment reference,
use `capabilities` before writes, and retain receipts/readbacks.

### Workbook automation

Install SDK + local-files + spreadsheets. Use sessions, profiles, revision
checks, idempotency keys, and independent verify/reconcile.

### Artifact pipeline

Install artifacts + OfficeCLI only in the rendering worker. Publish the
authoritative workbook first, copy to disposable storage, render, hash outputs,
and discard the preview session.

### Agent/MCP deployment

Install MCP in a host process, require an absolute policy file, inject the SDK
client explicitly, and expose only the three typed tools.

## 14. Documentation and maintenance checklist

When adding a component or public option:

1. add the closed contract and provider capability;
2. add a focused test for success, rejection, and readback/evidence;
3. add the public export to the generated inventory through `__all__`;
4. add beginner and advanced examples to the relevant manual;
5. update the package README and component matrix;
6. run `generate_reference_manuals.py`, `--check`, CLI parity, link checks,
   package boundaries, and the full test suite; and
7. record unavailable live prerequisites as explicit gates.

## 15. External documentation references

These projects informed the manual structure and example progression:

- [DuckDB CLI overview](https://duckdb.org/docs/stable/clients/cli/overview)
  and [arguments](https://duckdb.org/docs/current/clients/cli/arguments):
  separate startup/options from command semantics.
- [DuckDB dot commands](https://duckdb.org/docs/current/clients/cli/dot_commands):
  document interactive/advanced controls independently.
- [csvkit CLI guide](https://csvkit.readthedocs.io/en/latest/cli.html) and
  [csvkit tutorial](https://github.com/wireservice/csvkit/blob/master/docs/tutorial/1_getting_started.rst):
  group common workflows and show composable shell pipelines.
- [Polars concepts](https://docs.pola.rs/user-guide/concepts/) and
  [lazy API](https://docs.pola.rs/user-guide/concepts/lazy-api/):
  teach execution concepts before the API inventory.
- [Excelize introduction](https://xuri.me/excelize/en/) and
  [Excelize API](https://pkg.go.dev/github.com/xuri/excelize/v2):
  document workbook objects and capability boundaries independently.
