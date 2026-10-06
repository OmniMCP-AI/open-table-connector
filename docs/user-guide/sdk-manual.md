# SDK Manual

The OTC SDK is the application surface behind the CLI. This manual is a
progressive guide: construct a client, read a table, publish a table, use
bounded SQL, edit workbooks, then add formulas, temporal plans, artifacts, and
MCP. The generated [Python API inventory](../reference/api-inventory.md) is the
exhaustive export/signature reference and deliberately includes every public
class, function, enum, field, and method.

The structure follows Polars' documentation pattern of explaining concepts and
execution modes before listing the API. Read the [Polars concepts guide](https://docs.pola.rs/user-guide/concepts/)
and [Python API reference](https://docs.pola.rs/api/python/stable/reference/index.html)
alongside the OTC inventory when you need lower-level Polars behavior.

## 1. Install and choose a client

Install only the providers needed by an application:

```console
python -m pip install open-table-connector open-table-connector-local-files
```

Construct a client with explicit connectors in tests, or use `Client.from_config`
for installed entry-point providers in an application:

```python
from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import Client, ConnectorRegistry

client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
try:
    ...
finally:
    client.close()
```

```python
from open_table_connector.sdk import Client

client = Client.from_config("otc.toml")
```

`Client.from_config` resolves provider descriptors, enabled/disabled state,
credential references, environment bindings, and optional transports. Literal
credentials do not belong in a config file or a target URI. See [configuration](../reference/configuration.md)
for the closed TOML shape.

## 2. The result and error contract

Every SDK operation returns `OperationResult[T]` or raises `OTCError` at a
convenience boundary. A result contains:

| Field | Use |
| --- | --- |
| `value` | typed value when available |
| `outcome` | `succeeded`, `planned`, `rejected`, `failed`, `partial`, or `unknown` |
| `commit` | `committed`, `not_started`, `planned`, `partial`, `unknown`, or `not_applicable` |
| `verification` | `passed`, `failed`, `skipped`, or `unavailable` |
| `receipts` | safe target, connector, capability, and execution evidence |
| `warnings` | explicit omissions or non-fatal limitations |
| `error` | stable code, safe message/details, and reconciliation reference |

Use `.require_value()` when failure should raise:

```python
result = client.open("file:///absolute/orders.csv").require_value()
```

Use explicit inspection at service boundaries:

```python
result = client.open("file:///absolute/orders.csv")
if result.outcome.value != "succeeded":
    logger.error("open failed", extra={"code": result.error.code.value})
else:
    table = result.value
```

Never treat `unknown` as a clean failure. Reconcile or perform an independent
readback before retrying. Stable error codes are listed in [error-codes.md](../reference/error-codes.md).

## 3. Tables: open, read, and publish

### Open and read

```python
orders = client.open("file:///absolute/orders.csv").require_value()
frame = orders.read().require_value()
print(frame.schema)
print(frame.head())
```

The public physical handle is `Table`; a `Query` is deferred and does not
materialize rows until evaluated. Local CSV/workbook resources use `file://`;
MaybeSheet uses canonical HTTPS document URLs.

### Materialize a new table

Materialization is create-only. Choose a destination model explicitly:

```python
import polars as pl
from open_table_connector.sdk import DirectDestination

frame = pl.DataFrame({"order_id": [1001], "total": [42.5]})
created = client.materialize(
    frame,
    to=DirectDestination("file:///absolute/orders.json"),
).require_value()
```

An existing destination is not silently replaced. Use an explicit provider
operation or a conflict policy in the CLI when replacement is intentional.

### Mutate an existing table

```python
orders.insert(pl.DataFrame({"order_id": [1002], "total": [18.0]})).require_value()
orders.update(
    pl.DataFrame({"order_id": [1002], "total": [19.0]}),
    keys=("order_id",),
).require_value()
orders.delete(where="order_id = $1", parameters={"1": 1002}).require_value()
orders.drop().require_value()
```

`delete` requires a predicate. There is no generic `clear`, `replace`, or
unbounded delete operation. Provider implementations may expose a smaller
capability set; unsupported operations fail before dispatch.

### Paging and bounded reads

Use `read_page(limit=..., continuation=...)` for a stable bounded read where
the provider supports continuation tokens:

```python
page = orders.read_page(limit=500).require_value()
while page.continuation:
    page = orders.read_page(limit=500, continuation=page.continuation).require_value()
```

Keep source-row, input-byte, output-row, and duration limits explicit for
large or remote workflows. Do not assume a local test's unbounded memory is a
provider guarantee.

## 4. Queries and SQL lanes

OTC exposes separate relational, temporal, and provider-native SQL lanes.
Portable relational SQL is parsed and mapped to bounded Polars execution; it
does not silently fall back to a database engine. The `Query` object stores a
canonical plan hash and definition hash for reproducibility.

```python
query = client.sql(
    "SELECT customer, sum(total) AS revenue FROM orders "
    "GROUP BY customer ORDER BY revenue DESC LIMIT 20",
    sources={"orders": orders},
)
result = query.collect().require_value()
```

Use `SqlResourceLimits` to bound source rows/bytes, intermediate rows/bytes,
output rows/bytes, and duration:

```python
from open_table_connector.sdk import SqlResourceLimits

limits = SqlResourceLimits(max_output_rows=10_000, max_duration_ms=5_000)
result = client.sql("SELECT * FROM orders", sources={"orders": orders}, limits=limits).collect()
```

Provider-native SQL is explicit and provider-owned. Invalid SQL, resource
limits, unsupported functions, and unsafe external access produce stable
errors rather than a different execution lane.

## 5. Workbook sessions

Workbook sessions are the correct API for local XLSX edits and MaybeSheet
sheet-mode. They are buffered, exclusive, and closed on every path. Queue
operations through handles and call `write()` once.

```python
uri = "file:///absolute/report.xlsx"
with client.workbook.create(uri, profile="general/1.0") as book:
    book.worksheet.create("Report")
    book.worksheet("Report").range("A1:B2").write(
        [["Name", "Total"], ["Ada", 42]]
    )
    committed = book.write(idempotency_key="report-v1")
assert committed.commit.value == "committed"
```

Session entry points:

| Method | Use |
| --- | --- |
| `client.workbook.create(uri, profile=...)` | create a workbook |
| `client.workbook.open(uri, profile=...)` | edit an existing workbook |
| `client.workbook(uri)` | concise existing-workbook form |
| `client.workbook.copy(source, to=..., title=...)` | provider-qualified copy |
| `book.worksheet(name)` | bind a worksheet handle |
| `book.worksheet.create(name)` | queue worksheet creation |
| `book.write(...)` | validate, publish, and verify queued changes |
| `book.verify(expected)` | independent observation/intent check |
| `book.reconcile()` | recover a prior unknown outcome |
| `book.inspect()` | observe workbook metadata |

`write` accepts `dry_run`, `allow_partial`, `expected_revision`,
`idempotency_key`, `layout_expectation`, and provider/session limits. A dry run
does not change bytes. An unknown commit must be reconciled before retrying.

### Worksheet and range operations

```python
with client.workbook(uri) as book:
    report = book.worksheet("Report")
    report.range("A1:D20").read().require_value()
    report.range("A1:D1").style(bold=True)
    report.range("B2:B20").format(pattern="$#,##0.00")
    report.range("A1:D20").sort(key_column=4, reverse=True)
    report.range("A1:B2").merge()
    report.range("A1:B2").unmerge()
    result = book.write()
```

Available workbook handles cover range read/write, table read/write,
style/format/alignment/border/text-layout observation and writes, clear, sort,
merge/unmerge, worksheet create/delete/rename/move/config, workbook inspect,
verify, reconcile, and copy. The [generated spreadsheet schemas](../reference/spreadsheet-schemas.md)
provide exact argument properties, required fields, effects, limits, and result
schemas for each operation.

### Rich XLSX with existing Excelize capabilities

Use `rich-artifact/1.0` only when the workflow requires a qualified rich
object. The current local qualification is PNG/JPEG image insertion,
observation, and deletion with independent serialized readback.

```python
from open_table_connector.spreadsheets import ImageSpec

with client.workbook.create(uri, profile="rich-artifact/1.0") as book:
    book.worksheet("Report").image(
        ImageSpec(content=png_bytes, mime_type="image/png", anchor="B2")
    )
    inserted = book.write()
    images = book.worksheet("Report").images()
```

Use `book.capabilities` or `resolve_capabilities` before relying on charts,
shapes, tables, pivots, comments, validation, or other object families. An
unsupported object must fail closed. OfficeCLI never writes or resaves the
authoritative XLSX. MaybeSheet sheet-mode reuses the operation contract but
requires separate live evidence.

## 6. Operation discovery and generic dispatch

Static catalog discovery and target-bound capability resolution are separate:

```python
from open_table_connector.contract import TargetSelector
from open_table_connector.sdk import OperationCatalog, resolve_capabilities

descriptor = OperationCatalog.default().get("spreadsheet", "range.write", "1.0")
observation = resolve_capabilities(
    client, TargetSelector(uri, "Report")
).require_value()
```

`OperationCatalog` answers "what is registered?"; the result of
`resolve_capabilities` answers "what can this target prove now?". Never invent
an observation from request text.

The generic dispatcher accepts a closed `OperationRequest` and
`ExecutionOptions`:

```python
from open_table_connector.contract import ExecutionOptions, OperationRequest, TargetSelector
from open_table_connector.sdk import execute_operation

request = OperationRequest(
    "spreadsheet", "range.read", "1.0",
    TargetSelector(uri, "Report", None),
    {"address": "A1:B2"},
)
result = execute_operation(client, request, ExecutionOptions())
```

Wire serialization is closed: `TargetSelector` includes `uri`, `sheet`, and
`object_id`, even when optional values are `null`. Unknown keys are rejected.

## 7. Formulas

Formula activation is explicit and provider-native. Ordinary table/workbook
writes remain value-only; a string beginning with `=` is not automatically a
formula.

### Grid formulas

```python
from open_table_connector import otc

grid = client.formulas(
    otc.GridFormulaTarget(
        "file:///absolute/model.xlsx",
        otc.WorksheetRef(name="Model"),
    )
).require_value()
grid.set("D2:F4", otc.FormulaExpression("=B2+$C$1", "excel-a1")).require_value()
values = grid.read_values("D2:F4").require_value()
```

Grid `set` uses top-left copy-fill. Relative references translate per target;
absolute and mixed `$` references remain anchored. Formula text is preserved
with the required dialect (`excel-a1`, `google-sheets-a1`, or
`maybe-sheet-a1`). Recalculation is an explicit provider capability.

### Field formulas

```python
from open_table_connector.formulas import FieldFormulaTarget, FieldRef, FormulaExpression

orders = client.open("feishu://APP/TABLE").require_value()
margin = client.formulas(
    FieldFormulaTarget(orders, FieldRef(name="gross_margin"))
).require_value()
margin.set(FormulaExpression("revenue - cost", "feishu-bitable")).require_value()
```

Field formulas bind an existing provider formula field. OTC does not create or
convert fields in this surface. Calculated-value reads remain provider-dynamic
observations, not OTC-evaluated values.

## 8. Temporal and time-series workflows

Temporal plans are typed, hashed, bounded, and evaluated by the selected
provider/executor. Use `ScanRange`, `AsOf`, `Latest`, `BucketAggregate`, and
`GapFill` helpers rather than assembling arbitrary SQL strings when the
workflow needs deterministic temporal semantics.

```python
from open_table_connector.sdk import sql

query = sql(
    "SELECT * FROM ticks WHERE ts >= $1 AND ts < $2 LIMIT 10000",
    sources={"ticks": ticks},
)
result = query.collect().require_value()
```

Define timestamp precision, timezone, series keys, duplicate policy,
ingestion-time field, deterministic ordering, and resource bounds. Half-open
time ranges (`[start, end)`) avoid double counting adjacent windows. See the
[temporal SQL guide](temporal-sql.md), [time-series use case](use-cases.md),
and generated `timeseries` API section.

## 9. Recipes, snapshots, and artifacts

### Layout recipes

```python
from open_table_connector.sdk.recipes import apply_recipe, export_recipe

recipe = export_recipe(client, uri, selectors).require_value()
result = apply_recipe(client, uri, recipe, options).require_value()
```

Recipe export observes a fresh target. It emits layout operations only and
never values, formulas, or image bytes. Apply revalidates requirements and
closes its session after committed, rejected, or unknown outcomes.

### Snapshots and views

```python
from open_table_connector.artifacts import ViewRequest, WatchRequest
from open_table_connector.contract import TargetSelector

target = TargetSelector(uri)
view = client.artifacts().view(ViewRequest(target, "html"))
watch = client.artifacts().watch(WatchRequest("start", target))
```

Views copy a committed source into disposable storage and carry source hash,
snapshot hash, renderer/browser evidence, and output media type. Watch stores
owned process identity, loopback URL, refresh replacement, crash/orphaned
state, preview-copy-only editability, and discard persistence. Missing
OfficeCLI/browser prerequisites return `unsupported_capability`; no synthetic
HTML, PNG, or URL is produced.

## 10. MCP host integration

```python
from open_table_connector.mcp.server import MCPHost, create_server

server = create_server(host=MCPHost(client), policy=policy)
```

The official server registers exactly three tools. `otc_discover` is static;
`otc_inspect` allows read-only effects; `otc_execute` dispatches the typed
request through the same catalog and SDK host. Policy authorization runs before
dispatch. Shell commands, arbitrary imports, credentials, and undeclared wire
keys are rejected.

## 11. Provider and deployment matrix

| Provider/layer | Local | Remote | Typical use |
| --- | --- | --- | --- |
| `local_files` | CSV/JSON/JSONL/XLSX/Markdown, `file://` | no | tests, batch exports, Excelize workbooks |
| Google Sheets | no | `gsheets://` with configured credential | shared-sheet publication |
| MaybeSheet | no | HTTPS document URL | base-mode tables and sheet-mode grids |
| Feishu Bitable | no | `feishu://` | base-mode records and field formulas |
| SQLite/Postgres | local/service | connector URI | relational tables and SQL |
| OfficeCLI | optional process | no credential forwarding | DOCX/PPTX artifacts and views |
| MCP | optional stdio | host-controlled | typed agent tool boundary |

Capability declarations are evidence gates, not feature marketing. A provider
may be installed and still reject an operation for target, profile, mode,
credentials, limits, or missing live evidence.

## 12. Use-case index

| Use case | Primary API | Supporting API |
| --- | --- | --- |
| local CSV inspection | `client.open().read()` | snapshots, receipts |
| CSV/JSON/Excel conversion | `client.materialize()` or CLI `convert` | conflict policy |
| append/update/delete table | `Table.insert/update/delete` | keys, predicates, receipts |
| bounded relational query | `client.sql()` | `Query`, `SqlResourceLimits` |
| workbook layout edit | `client.workbook()` | style/format/config operations |
| rich XLSX image workflow | `profile="rich-artifact/1.0"` | `ImageSpec`, readback |
| explicit formulas | `client.formulas()` | dialect, recalculation |
| temporal report | typed temporal plan | descriptor hash, bounds |
| layout reuse | `export_recipe/apply_recipe` | fresh observation |
| visual QA | `artifacts().view/watch()` | disposable snapshot |
| agent tool boundary | `MCPHost` | policy, typed request |

## 13. Troubleshooting and advanced practices

1. Confirm the package and provider are installed with `otc list`.
2. Confirm the operation schema with `otc help` or `OperationCatalog`.
3. Resolve target evidence before dispatch with `resolve_capabilities`.
4. Bound sources and queries with limits before testing remote behavior.
5. Persist operation results and receipts as audit artifacts.
6. Reconcile every `unknown`, `partial`, or failed-verification result.
7. Use an idempotency key for retryable publication jobs.
8. Keep authoritative workbook writes and disposable rendering in separate steps.
9. Keep provider credentials in configuration references and environment bindings.
10. Pin package/provider versions for reproducible operation catalogs.

For every public name and signature, use the [generated API inventory](../reference/api-inventory.md).
For ownership and optional dependency boundaries, use the [components manual](components.md).
