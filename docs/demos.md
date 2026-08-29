# OTC demos and use cases

These examples are intentionally small. They show the boundary between
ordinary table movement, portable time-series execution, and a native OTS
backend.

## Demo 1: Convert a daily export for an analyst

Use a bare path when compatibility probing is helpful:

```console
uv run --package open-table-connector otc inspect --from daily-orders.csv --output-format json
uv run --package open-table-connector otc convert \
  --from daily-orders.csv \
  --to daily-orders.jsonl --to-format jsonl
uv run --package open-table-connector otc convert \
  --from daily-orders.jsonl \
  --to daily-orders.xlsx --to-format excel --sheet Orders
```

This path is appropriate for ad-hoc, non-trading work: the output is portable,
human-readable, and easy to attach to another workflow. It does not provide a
transactional time-series snapshot or native database retention/compression.

## Demo 2: Inspect a sheet before importing it

Google Sheets credentials stay out of the endpoint:

```console
export GOOGLE_SHEETS_ACCESS_TOKEN='…'

uv run --package open-table-connector otc inspect \
  --from gsheets://SPREADSHEET_ID/Orders \
  --range 'Orders!A1:F100' --output-format json

uv run --package open-table-connector otc convert \
  --from gsheets://SPREADSHEET_ID/Orders \
  --to orders.csv --to-format csv
```

Use `import` (instead of `convert`) when the destination is a remote writable
connector, and select an explicit `--if-exists` policy. Google Sheets and
Feishu Bitable are ordinary table connectors in OTC; they are not portable
temporal storage backends.

## Demo 3: Query a CSV time series with the portable evaluator

Create a source with an event time, series key, tag, value, and ingestion time:

```console
cat > ticks.csv <<'CSV'
ts,symbol,venue,price,size,received_at
2026-08-29T00:00:00.000000000Z,AAPL,XNAS,100.0,10,2026-08-29T00:00:00.100000000Z
2026-08-29T00:05:00.000000000Z,AAPL,XNAS,101.0,11,2026-08-29T00:05:00.100000000Z
2026-08-29T00:10:00.000000000Z,AAPL,XNAS,103.0,13,2026-08-29T00:10:00.100000000Z
2026-08-29T00:05:00.000000000Z,MSFT,XNYS,200.0,20,2026-08-29T00:05:00.100000000Z
CSV
```

Run the Python example from [Getting started](getting-started.md), changing
the end time to `2026-08-29T00:11:00.000000000Z`. A `ScanRange` returns the
projected rows in deterministic series/time order. A `Latest` plan returns one
row per symbol, and an `AsOf` plan applies the same selection at a requested
timestamp.

The evaluator reads Arrow, applies the typed operation in Polars, checks the
resource bounds, and returns a `TemporalReceipt`. No SQL parser is involved.

## Demo 4: Bucket and gap-fill for a dashboard

Build a five-minute aggregate and fill missing buckets with last observation
carried forward:

```python
from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    BucketAggregate,
    FillMode,
    FillRule,
    FixedBucket,
    GapFill,
)

bucket = FixedBucket(
    width_ns=5 * 60 * 1_000_000_000,
    origin="2026-08-29T00:00:00.000000000Z",
    offset_ns=0,
)
measure = AggregateMeasure("avg_price", AggregateFunction.AVG, "price")

aggregate = BucketAggregate(
    start="2026-08-29T00:00:00.000000000Z",
    end="2026-08-29T01:00:00.000000000Z",
    bucket=bucket,
    group_by=("symbol",),
    measures=(measure,),
    tag_predicates=(),
)

gap_fill = GapFill(
    start=aggregate.start,
    end=aggregate.end,
    bucket=bucket,
    group_by=aggregate.group_by,
    measures=aggregate.measures,
    tag_predicates=(),
    fills=(FillRule("avg_price", FillMode.LOCF, None),),
)
```

`LOCF` does not look before the requested range. Linear interpolation requires
observations on both sides inside the range. For calendar buckets, use
`CalendarBucket` with an explicit IANA timezone and week start so DST and
month boundaries are deterministic.

## Demo 5: Run the same plan against SQLite

SQLite is useful for a local, bounded development or research workflow. The
physical table name is validated as a simple identifier:

```python
from open_table_connector.contract import TableURI
from open_table_connector.sqlite import SQLiteTemporalExecutor
from open_table_connector.timeseries import TemporalExecutionRequest

request = TemporalExecutionRequest(
    target=TableURI("sqlite:///absolute/path/market.db"),
    plan=plan,
    credential_reference=None,
    operation_id="sqlite-scan",
    snapshot_reference=None,
)
result = SQLiteTemporalExecutor(descriptor, "ticks").execute(request)
print(result.table)
```

The SQLite adapter applies bounded prepared reads and then uses the same
portable Arrow/Polars semantics. Add a `SQLiteManagedTemporalStore` when a
caller needs stage/commit/readback/abort and snapshot addressing.

## Demo 6: Run against PostgreSQL

Plain PostgreSQL is also a portable OTC backend. It is not a TimescaleDB
identity and does not claim Timescale-specific hyperfunctions, retention, or
continuous aggregates:

```python
from open_table_connector.contract import TableURI
from open_table_connector.postgres import PostgresTemporalExecutor
from open_table_connector.timeseries import TemporalExecutionRequest

request = TemporalExecutionRequest(
    target=TableURI("postgres://db.example.test/market"),
    plan=plan,
    credential_reference="market-read",
    operation_id="postgres-scan",
    snapshot_reference=None,
    credential_values={"user": "ots_reader", "password": password},
)
result = PostgresTemporalExecutor(
    descriptor,
    "public.ticks",
    credentials={"user": "ots_reader", "password": password},
).execute(request)
```

In production, resolve `credential_reference` through a deployment-owned
resolver rather than placing passwords in source code. The adapter sets a
statement timeout from `max_duration_ms` and enforces row/byte bounds.

## Demo 7: Put OTC behind `otc-process`

Use the process adapter when OTS or another host should own orchestration and
OTC should own physical access. Create a private config file with mode `0600`
and set:

```console
export OTC_PROCESS_CONFIG=/absolute/path/otc-process.json
export OTC_ARTIFACT_ROOT=/absolute/path/otc-artifacts
uv run --package open-table-connector-process otc-process
```

The process handshake negotiates the connector version, portable plan version,
and capability versions. `execute` returns a verified Arrow artifact reference
and a temporal receipt. Managed operations use the same process with `stage`,
`commit`, `readback`, and `abort`. A cancel frame marks the session cancelled
and invokes the provider's cooperative abort hook when available.

## When to use a native OTS backend instead

Choose native TimescaleDB (or a future native ClickHouse/TDengine adapter) when
you need native time-series features, high ingest rates, continuous
aggregates, retention/compression policies, tiering, subscriptions, or
real-time trading workloads. Choose OTC when the workload is development,
non-trading, non-real-time, or an ad-hoc exchange where portability and a
small operational footprint matter more than native scale.
