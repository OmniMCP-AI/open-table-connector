# SDK Manual

The generated [Python API inventory](../reference/api-inventory.md) lists every public export and declared signature. This manual gives the supported construction patterns and result semantics.

## Client and local tables

Construct a `Client` with an explicit `ConnectorRegistry`; applications that use configuration can call `Client.from_config(...)`.

```python
import polars as pl
from open_table_connector.sdk import Client, ConnectorRegistry
from open_table_connector.local_files import LocalFilesConnector

client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
orders = client.open("file:///absolute/path/orders.csv").require_value()
frame: pl.DataFrame = orders.read().require_value()
print(frame.shape)
client.close()
```

`OperationResult.require_value()` raises `OTCError` for rejected, failed, partial, or unknown operations. For automation that cannot raise, inspect `outcome`, `commit`, `verification`, `receipts`, and `error` directly.

## Workbook sessions

Workbook sessions are buffered and exclusive. Queue reads or mutations through worksheet and range handles, then call `write()` once. Context management closes the session on every path.

```python
from open_table_connector.sdk import Client, ConnectorRegistry
from open_table_connector.local_files import LocalFilesConnector

client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
uri = "file:///absolute/path/report.xlsx"
with client.workbook.create(uri, profile="rich-artifact/1.0") as book:
    book.worksheet.create("Report")
    book.worksheet("Report").range("A1:B2").write([["Name", "Total"], ["Ada", 42]])
    result = book.write(idempotency_key="report-initial-v1")
assert result.commit.value == "committed"
```

Use `dry_run=True` for validation without publication, `expected_revision` for optimistic concurrency, and `allow_partial=True` only when the caller handles partial receipts. A commit of `unknown` must be reconciled with `book.reconcile()` before any retry.

Range styles, formats, worksheet changes, formulas, and rich image operations all use the same session lifecycle. Rich XLSX is existing Excelize capability only; OfficeCLI is not imported by the workbook writer.

```python
with client.workbook(uri) as book:
    book.worksheet("Report").range("A1:B1").style(bold=True)
    book.worksheet("Report").range("B2:B20").format(pattern="$#,##0.00")
    result = book.write()
```

## Discovery and typed operations

`OperationCatalog.default()` describes static schemas. `resolve_capabilities(client, target)` binds those schemas to a target and reports provider evidence. Static discovery is not proof that a provider can execute an operation.

```python
from open_table_connector.contract import TargetSelector
from open_table_connector.sdk import OperationCatalog, resolve_capabilities

descriptor = OperationCatalog.default().get("spreadsheet", "range.write", "1.0")
observation = resolve_capabilities(
    client, TargetSelector("file:///absolute/path/report.xlsx", "Report")
).require_value()
```

For MCP or another typed boundary, use the closed wire form:

```python
request = {
    "namespace": "spreadsheet",
    "operation_id": "range.read",
    "version": "1.0",
    "target": {"uri": uri, "sheet": "Report", "object_id": None},
    "arguments": {"address": "A1:B2"},
}
```

## Recipes and snapshots

`export_recipe()` observes a fresh target and emits layout-only operations. `apply_recipe()` validates requirements again and closes its session after commit or failure.

```python
from open_table_connector.sdk.recipes import export_recipe, apply_recipe

recipe = export_recipe(client, uri, selectors).require_value()
applied = apply_recipe(client, uri, recipe, options).require_value()
```

`capture_workbook_snapshot()` returns a hash and consistency classification. Use it before renderer work and verify the source hash again afterward.

## Artifacts and previews

```python
from open_table_connector.artifacts import ViewRequest, WatchRequest
from open_table_connector.contract import TargetSelector

view = client.artifacts().view(ViewRequest(TargetSelector(uri), "html"))
watch = client.artifacts().watch(WatchRequest("start", TargetSelector(uri)))
```

View and watch operate on owned disposable copies. If OfficeCLI or a browser is missing, the result is `unsupported_capability`; no synthetic HTML, PNG, or running URL is returned. Watch records preserve session identity, source/snapshot hashes, loopback URL, editability (`preview_copy_only`), discard persistence, and process state (`running`, `crashed`, `orphaned`, or `stopped`).

## Optional MCP host

```python
from open_table_connector.mcp.server import MCPHost, create_server

server = create_server(host=MCPHost(client))
```

The server registers exactly three tools. Policy authorization occurs before dispatch. Shell commands, arbitrary module names, credentials, and undeclared fields are rejected.
