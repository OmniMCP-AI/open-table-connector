# Python API

The public application surface is `open_table_connector.sdk`. The namespace
is Polars-first and returns normalized `OperationResult` values.

## Core types

```python
import open_table_connector.sdk as otc

client = otc.Client.from_config("/absolute/path/config.toml")
table = client.open("file:///absolute/path/orders.csv").require_value()
inspection = table.inspect().require_value()
frame = table.read().require_value()
client.close()
```

Use bare paths or canonical `file://` URLs for local CSV and workbook files.
CSV remains available as a format and codec, including conversion output, but
does not have a format-specific public connector route. MaybeSheet targets use
canonical `https://www.maybe.ai/docs/spreadsheets/d/DOCUMENT_ID` document URLs.

Main public types include:

- `Client` — routing, open, collect, materialize, SQL, and formula entry point;
- `Table` — connector-backed table handle owned by one client;
- `Query` — immutable deferred table-producing computation;
- `TableInspection` — schema, mode, revision, and optional row count;
- `OperationResult[T]` — value plus outcome, receipts, warnings, and errors;
- `ClientConfig` — provider configuration and credential bindings; and
- `TemporalTableDescriptor` and `TimeSeriesView` — typed temporal overlay.

## Table operations

```python
table.insert(frame)
table.update(frame, keys=("id",))
table.delete(where=otc.all_rows())
table.drop()
```

Use `table.transaction()` to group `insert`, keyed `update`, and
predicate-required `delete` calls. A `Table` is client-affine; reopen it on a
different client rather than passing the physical handle across clients.

## SQL operations

```python
result = client.sql(
    "SELECT orders.id, orders.total FROM orders WHERE orders.total > $1",
    sources={"orders": table},
    parameters={"1": 20},
).require_value()
```

Use `client.native_sql(target)` only for an explicitly provider-native,
read-only capability. Use `table.time_series(descriptor)` for portable temporal
queries.

## Temporal operations

The public temporal package exports `TemporalTableDescriptor`,
`PortableTemporalPlan`, `ScanRange`, `Latest`, `AsOf`, `BucketAggregate`,
`GapFill`, `TemporalExecutionRequest`, and resource-bound types. The executor
returns an Arrow/Polars result plus a `TemporalReceipt`.

## Formula operations

`Client.formulas(GridFormulaTarget(...))` and
`Client.formulas(FieldFormulaTarget(...))` return provider capability views.
Formula activation requires `FormulaExpression`; ordinary table writes are
value-only.

## Physical layout API

`Client.open(..., metadata_only=True)` creates a `Table` binding without
materializing rows. `table.layout()` returns `TableLayoutSession`, which is
client-affine and shares the provider's worksheet identity with the data Table.
Use `layout.range(address).style(...)`, `.format(...)`,
`layout.range(address).read_style(fields=None)`,
`layout.worksheet.config(...)` and
`layout.worksheet.read_config(rows=..., columns=..., view_fields=None)`.

Style writes are patches: omitted fields and border edges remain unchanged,
`False` is a real value, and `border: {"top": {"style": "none"}}` explicitly
clears one edge. `text_layout` maps to the provider's native wrapping flags;
unknown properties, unsupported modes and incompatible column units fail before
dispatch. `CellFormat` accepts complete Excel format codes or a built-in ID with
explicit locale/date-system context.

Read methods return `OperationResult` values containing a versioned physical
observation. Its coverage, source references, native dimensions and
`physical_hash` can be independently verified after closing and reopening the
workbook. A write acknowledgment never substitutes for readback. Providers
without verified read commands return `unsupported_capability` rather than
silently dropping a request.
