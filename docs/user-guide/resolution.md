# Resolution and lookup behavior

OTC resolves temporal data through a descriptor-bound `TimeSeriesView`. The
portable operation set is closed and bounded:

- `ScanRange` returns projected rows in a half-open time range;
- `Latest` returns the latest row per series, optionally at a cutoff;
- `AsOf` returns the as-of row per series;
- `BucketAggregate` computes fixed or calendar buckets; and
- `GapFill` adds `null`, constant, LOCF, or linear fill rules.

## Lookup semantics

`Latest` and `AsOf` use descriptor series keys and deterministic ordering.
Ranges use `[start, end)`. Temporal timestamps are RFC 3339 UTC strings at the
descriptor precision. `LOCF` does not look before the requested range, and
linear interpolation requires observations on both sides inside that range.

## Build a typed lookup

```python
from open_table_connector.sdk import Client
from open_table_connector.timeseries import TemporalTableDescriptor

with Client.from_config("/absolute/path/config.toml") as client:
    table = client.open("csv:///absolute/path/ticks.csv").require_value()
    series = table.time_series(descriptor)
    latest = series.latest(at_or_before="2026-08-29T00:10:00.000000000Z")
    result = client.collect(latest).require_value()
```

The descriptor hash is computed from the descriptor and the exact Arrow schema.
It excludes the physical URI and credentials. A provider must reject a plan
whose descriptor hash does not match the opened table.

## Provider selection

Capability selection is explicit. CSV, JSON, JSONL, Excel, SQLite, and
PostgreSQL have certified portable operations with different lifecycle and
dependency boundaries. Google Sheets and Feishu Bitable are ordinary table
connectors, not portable temporal backends. A provider-specific failure is not
an instruction to retry through another provider.
