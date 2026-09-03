# First time series

OTC's portable time-series API is a typed Python interface. It accepts a
`PortableTemporalPlan`, not arbitrary SQL.

## Create a bounded source

```console
cat > ticks.csv <<'CSV'
ts,symbol,venue,price,size,received_at
2026-08-29T00:01:00.000000000Z,AAPL,XNAS,100.0,10,2026-08-29T00:01:01.000000000Z
2026-08-29T00:06:00.000000000Z,AAPL,XNAS,102.0,12,2026-08-29T00:06:01.000000000Z
2026-08-29T00:06:00.000000000Z,MSFT,XNYS,200.0,20,2026-08-29T00:06:01.000000000Z
CSV
```

## Describe and scan it

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
    TemporalTableDescriptor,
    TemporalOrdering,
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
    resource_bounds=ResourceBounds(10_000, 10_000_000, 5_000),
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
    target=TableURI(Path("ticks.csv").absolute().as_uri().replace("file://", "csv://", 1)),
    plan=plan,
    credential_reference=None,
    operation_id="first-scan",
    snapshot_reference=None,
)
result = CsvTemporalExecutor(descriptor).execute(request)
print(result.table)
print(result.receipt.to_wire())
```

Run it from the directory containing `ticks.csv` after installing the local
files and time-series packages. The range is half-open (`[start, end)`), and
all requests are bounded by rows, bytes, and duration.

## Next steps

- Use `Latest`, `AsOf`, `BucketAggregate`, or `GapFill` for other operations.
- Use [Temporal SQL](../user-guide/temporal-sql.md) when the closed SQL profile
  is more convenient.
- Use [Evidence and lineage](../user-guide/evidence-and-lineage.md) to inspect
  receipts and fingerprints.
