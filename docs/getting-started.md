# Getting started with OTC

Open Table Connector (OTC) provides two complementary surfaces:

- the `otc` command for inspecting, moving, and converting ordinary tables; and
- Python packages for bounded portable time-series operations over Arrow and
  Polars.

OTC is a connector layer. It owns URI parsing, physical I/O, provider
  credentials supplied by the caller, resource limits, and neutral receipts.
  Open Time Series (OTS) owns logical time-series plans and can select OTC as a
  reduced-capability backend. Native TimescaleDB, ClickHouse, and TDengine
  remain native OTS backends.

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Git, if you are working from a checkout

## Install from a checkout

```console
git clone https://github.com/OmniMCP-AI/open-table-connector.git
cd open-table-connector
uv sync --dev
source .venv/bin/activate
otc --help
```

For a released build, install the CLI as a `uv` tool:

```console
uv tool install open-table-connector
otc --help
```

`uv sync` installs the workspace packages into one environment. Activating
`.venv` puts the `otc` entry point on `PATH` for the current shell.

## First table read

Create a small CSV file:

```console
cat > orders.csv <<'CSV'
order_id,customer,total
1001,ada,42.50
1002,grace,18.00
1003,linus,73.25
CSV
```

Inspect its schema and row count:

```console
otc inspect \
  --from orders.csv --output-format json
```

Read it as a Markdown table:

```console
otc read \
  --from csv://$(pwd)/orders.csv --output-format table
```

Convert it to JSONL, then read the converted file:

```console
otc convert \
  --from orders.csv --to orders.jsonl --output-format jsonl

otc read \
  --from orders.jsonl --output-format json
```

The default `read` output is JSONL. Use `--output-format csv`, `json`,
`jsonl`, or `table` when another representation is more convenient.

## Read a remote table

Credentials are supplied separately from the URI. For Google Sheets, set an
access token in the environment (or pass `--token`):

```console
GOOGLE_SHEETS_ACCESS_TOKEN="$TOKEN" \
  otc read \
    --from gsheets://SPREADSHEET_ID/Orders \
    --range 'A1:C100' --output-format jsonl
```

For a write-capable destination, use `import` and choose an explicit conflict
policy:

```console
otc import \
  --from orders.csv \
  --to gsheets://SPREADSHEET_ID/Orders \
  --if-exists append
```

## Try a portable time-series query

The time-series API is a Python interface. It accepts a typed
`PortableTemporalPlan`; it does not accept arbitrary SQL. The following
example reads a CSV directly and returns an Arrow table:

```python
from pathlib import Path

import pyarrow as pa

from open_table_connector.contract import TableURI
from open_table_connector.local_files import CsvTemporalExecutor
from open_table_connector.timeseries import (
    OrderDirection,
    OrderKey,
    PortableTemporalPlan,
    ResourceBounds,
    ScanRange,
    TemporalExecutionRequest,
    TemporalTableDescriptor,
    TimestampPrecision,
    DuplicatePolicy,
    TemporalOrdering,
    temporal_descriptor_hash,
)

csv_path = Path("ticks.csv").absolute()
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

# This schema must match the decoded source schema.
schema = pa.schema(
    [
        pa.field("ts", pa.timestamp("ns", tz="UTC")),
        pa.field("symbol", pa.string()),
        pa.field("venue", pa.string()),
        pa.field("price", pa.float64()),
        pa.field("size", pa.int64()),
        pa.field("received_at", pa.timestamp("ns", tz="UTC")),
    ]
)

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
        start="2026-08-29T00:00:00.000000000Z",
        end="2026-08-29T01:00:00.000000000Z",
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
    target=TableURI(csv_path.as_uri().replace("file://", "csv://", 1)),
    plan=plan,
    credential_reference=None,
    operation_id="getting-started-scan",
    snapshot_reference=None,
)
result = CsvTemporalExecutor(descriptor).execute(request)
print(result.table)
print(result.receipt.to_wire())
```

Time-series timestamps are RFC 3339 UTC strings at the descriptor precision.
Ranges are half-open (`[start, end)`). Every request is bounded by maximum
rows, bytes, and duration.

## Where to go next

- [User manual](user-manual.md) — complete CLI, URI, credential, and
  time-series API reference.
- [Demos and use cases](demos.md) — copy/paste examples for files, SQLite,
  PostgreSQL, and the connector process.
- [Portable time-series specification](superpowers/specs/2026-08-29-portable-time-series-storage-design.md)
  — normative plan, receipt, and capability details.
- [Conformance suite](../specification/conformance/timeseries/README.md) —
  provider-level semantic and lifecycle evidence.
