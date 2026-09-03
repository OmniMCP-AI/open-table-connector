# Temporal SQL

OTC exposes a constrained Temporal SQL Lite profile over a `TimeSeriesView`.
SQLGlot parses and validates the statement before it is lowered to the typed
portable operations. It is not TimescaleDB SQL passthrough.

## Supported shape

The profile supports bounded `SELECT` statements for range scans, latest
lookups, fixed/calendar bucket aggregates, and gap fill. It accepts typed
numbered parameters (`$1`, `$2`, ...), deterministic `ORDER BY`, and an
explicit `LIMIT`.

It rejects unbounded ranges, unknown fields, joins, CTEs, subqueries, DDL/DML,
provider settings, arbitrary functions, and untyped temporal bounds. Typed
`as_of()` remains a Python helper rather than a SQL operation.

```python
series = table.time_series(descriptor)
query = series.sql(
    """
    SELECT ts, symbol, price
    FROM series
    WHERE ts >= $1 AND ts < $2 AND symbol = $3
    ORDER BY symbol, ts
    LIMIT 100
    """,
    parameters={
        "1": "2026-08-29T00:00:00.000000000Z",
        "2": "2026-08-29T01:00:00.000000000Z",
        "3": "AAPL",
    },
    snapshot_reference=snapshot_reference,
)
result = client.collect(query).require_value()
```

## Relational and native SQL

`Client.sql(...)` is the portable relational lane over explicitly bound table
sources. `Client.native_sql(target)` is a separate provider-native lane with
read-only policy checks and no portable fallback. Use the temporal lane when
the query needs time-series semantics and the relational lane for joins across
ordinary in-memory or connector-backed tables.

All lanes enforce resource limits and return receipts. See [Python API](../reference/python-api.md)
for the public constructors and [TimescaleDB](timescaledb.md) for the direct
database boundary.
