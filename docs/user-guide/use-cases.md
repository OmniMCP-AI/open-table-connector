# OTC use cases

This page collects three complete OTC workflows. Each one starts with a
realistic input, shows the command or Python API call, and explains when the
workflow is a good fit.

## 1. Prepare a daily analyst export

Use this workflow when a local CSV needs to be checked, converted into a
portable machine-readable file, and delivered as an Excel workbook.

### Create the input

```console
cat > daily-orders.csv <<'CSV'
order_id,ordered_at,customer,total,status
1001,2026-09-01T09:15:00Z,ada,42.50,paid
1002,2026-09-01T10:30:00Z,grace,18.00,pending
1003,2026-09-01T11:45:00Z,linus,73.25,paid
CSV
```

### Inspect and convert it

```console
otc inspect \
  --from daily-orders.csv \
  --output-format json

otc convert \
  --from daily-orders.csv \
  --to daily-orders.jsonl \
  --output-format jsonl

otc convert \
  --from daily-orders.jsonl \
  --to daily-orders.xlsx \
  --output-format excel \
  --sheet Orders
```

Verify the portable output before sending it on:

```console
otc read --from daily-orders.jsonl --output-format table
otc inspect --from daily-orders.xlsx --output-format json
```

`inspect` provides the detected schema and source receipt. `convert` keeps the
workflow local and produces a new destination receipt. Use this path for
exports, hand-offs, and small data preparation jobs where a transactional
database is not required.

## 2. Import a local extract into a shared sheet

Use this workflow when a local extract is ready for a team-maintained Google
Sheet. Inspect the destination-shaped source first, then make the write with an
explicit conflict policy.

### Install the provider and configure credentials

Install the core package and the optional Google Sheets provider in the same
environment:

```console
python -m pip install open-table-connector open-table-connector-google-sheets
export GOOGLE_SHEETS_ACCESS_TOKEN='replace-with-a-short-lived-token'
```

Keep credentials in the environment or in an external secret manager. Do not
put a token in the endpoint or commit it to a project file.

### Inspect the source and import it

```console
otc inspect \
  --from daily-orders.csv \
  --output-format json

otc import \
  --from daily-orders.csv \
  --to gsheets://SPREADSHEET_ID/Orders \
  --if-exists append
```

Read back a bounded range to verify the shared result:

```console
otc read \
  --from gsheets://SPREADSHEET_ID/Orders \
  --range 'Orders!A1:E20' \
  --output-format table
```

Replace `append` with `replace` only when replacing the existing sheet is
intentional. Use `error` when an existing destination should stop the job.
`import` is the correct command for a writable remote connector; `convert` is
for local destinations or stdout.

## 3. Run a bounded time-series scan for a report

Use this workflow when a small local event file needs deterministic temporal
semantics and an auditable receipt, without requiring a database service.

### Create the time-series source

```console
cat > ticks.csv <<'CSV'
ts,symbol,venue,price,size,received_at
2026-09-01T09:00:00.000000000Z,AAPL,XNAS,100.0,10,2026-09-01T09:00:00.100000000Z
2026-09-01T09:05:00.000000000Z,AAPL,XNAS,101.0,11,2026-09-01T09:05:00.100000000Z
2026-09-01T09:10:00.000000000Z,AAPL,XNAS,103.0,13,2026-09-01T09:10:00.100000000Z
2026-09-01T09:05:00.000000000Z,MSFT,XNYS,200.0,20,2026-09-01T09:05:00.100000000Z
CSV
```

### Describe the contract and execute a scan

Save the following as `scan_ticks.py` in the same directory:

```python
from pathlib import Path

import pyarrow as pa
from open_table_connector.contract import TableURI
from open_table_connector.local_files import CsvTemporalExecutor
from open_table_connector.timeseries import (
    DuplicatePolicy,
    OrderDirection,
    OrderKey,
    PortableTemporalPlan,
    ResourceBounds,
    ScanRange,
    TemporalExecutionRequest,
    TemporalOrdering,
    TemporalTableDescriptor,
    TimestampPrecision,
    temporal_descriptor_hash,
)

descriptor = TemporalTableDescriptor(
    time_field="ts",
    timezone="UTC",
    precision=TimestampPrecision.NANOSECOND,
    series_key_fields=("symbol",),
    tag_fields=("venue",),
    value_fields=("price", "size"),
    ingestion_time_field="received_at",
    duplicate_policy=DuplicatePolicy.REPLACE_LATEST,
    ordering=TemporalOrdering.UNSPECIFIED,
)

schema = pa.schema([
    pa.field("ts", pa.timestamp("ns", tz="UTC")),
    pa.field("symbol", pa.string()),
    pa.field("venue", pa.string()),
    pa.field("price", pa.float64()),
    pa.field("size", pa.int64()),
    pa.field("received_at", pa.timestamp("ns", tz="UTC")),
])

plan = PortableTemporalPlan(
    schema_version="otc.portable-temporal-plan/v1",
    descriptor_hash=temporal_descriptor_hash(descriptor, schema),
    relation="ticks",
    required_capabilities=(),
    resource_bounds=ResourceBounds(
        max_rows=10_000,
        max_bytes=10_000_000,
        max_duration_ms=5_000,
    ),
    operation=ScanRange(
        start="2026-09-01T09:00:00.000000000Z",
        end="2026-09-01T09:11:00.000000000Z",
        projection=("ts", "symbol", "price"),
        tag_predicates=(),
    ),
    output_order=(
        OrderKey("symbol", OrderDirection.ASC),
        OrderKey("ts", OrderDirection.ASC),
    ),
    result_row_limit=None,
)

request = TemporalExecutionRequest(
    target=TableURI(
        Path("ticks.csv").absolute().as_uri().replace("file://", "csv://", 1)
    ),
    plan=plan,
    credential_reference=None,
    operation_id="daily-report-scan",
    snapshot_reference=None,
)

result = CsvTemporalExecutor(descriptor).execute(request)
print(result.table)
print(result.receipt.to_wire())
```

Run it with the local-file and temporal extras installed:

```console
python scan_ticks.py
```

The range is half-open (`[start, end)`), so the scan includes events at
09:00 through 09:10 and excludes events at 09:11 or later. The descriptor
defines the time field, key, tags, value types, duplicate policy, and precision;
the plan adds projection, ordering, and resource bounds. The returned receipt
records the execution facts needed to explain or verify the result.

To turn the same source into five-minute report buckets, replace `ScanRange`
with a typed `BucketAggregate` plan and optionally add `GapFill`; see
[Temporal SQL](temporal-sql.md) and [First time series](../getting-started/first-timeseries.md)
for the related operations.

## Choosing a workflow

| Need | Use |
| --- | --- |
| A portable file for a person or another tool | Daily analyst export |
| A controlled write to a shared remote table | Shared-sheet import |
| Deterministic time-range analysis with receipts | Bounded time-series scan |

These examples use OTC's ordinary table and portable temporal surfaces only.
They do not require a documentation-site dependency or a database service.
