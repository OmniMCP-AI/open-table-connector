# Python API

The public application surface is `open_table_connector.sdk`. The namespace
is Polars-first and returns normalized `OperationResult` values.

## Core types

```python
import open_table_connector.sdk as otc

client = otc.Client.from_config("/absolute/path/config.toml")
table = client.open("csv:///absolute/path/orders.csv").require_value()
inspection = table.inspect().require_value()
frame = table.read().require_value()
client.close()
```

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
