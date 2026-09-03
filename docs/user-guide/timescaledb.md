# TimescaleDB and direct Python integration

OTC is not a TimescaleDB client and does not expose a Timescale-specific SQL
passthrough. Its `open_table_connector.postgres` package is a plain PostgreSQL
connector that implements the certified portable temporal contract through
prepared reads and Arrow/Polars semantics.

## Plain PostgreSQL through OTC

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

Use a deployment-owned credential resolver in production. The connector does
not claim Timescale hyperfunctions, retention, compression, continuous
aggregates, or native lifecycle features merely because it can read a
PostgreSQL table.

## If you need native TimescaleDB

Use the Open Time Series TimescaleDB binding for a direct, native
TimescaleDB path. Keep that integration in OTS; OTC remains the connector
boundary. The two systems share portable contracts where applicable, but an
OTC failure is not an automatic fallback and a native-only plan cannot be
lowered to OTC.

## Snapshot and safety boundary

Managed OTC reads use an explicit `snapshot_reference` returned by the same
managed target. Never infer a snapshot from the current table or from a
provider timestamp. Statements, credentials, and URIs remain separate from
plan and descriptor identities.
