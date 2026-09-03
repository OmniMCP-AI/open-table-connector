# Ingestion workflow

OTC ingestion has two forms: ordinary table movement through the CLI/SDK and
typed temporal ingestion through a provider's `TemporalConnectorExtension`.

## Ordinary table movement

The CLI reads a source into Arrow, carries the source receipt, and either
writes a local destination (`convert`) or materializes into a writable
connector (`import`). The destination policy is explicit:

```console
otc import --from orders.csv \
  --to gsheets://SPREADSHEET_ID/Orders \
  --if-exists append
```

`convert` accepts only local files or stdout. `import` accepts only writable
connector destinations. Provider-owned fields may be removed by the
destination adapter; other columns and source evidence are preserved.

## SDK materialization and mutation

```python
import polars as pl
from open_table_connector.sdk import BaseModeDestination, Client

with Client.from_config("/absolute/path/config.toml") as client:
    created = client.materialize(
        pl.DataFrame({"id": [1], "value": ["first"]}),
        to=BaseModeDestination("sqlite:///absolute/path/data.db", "events"),
    ).require_value()
    created.transaction().insert(
        pl.DataFrame({"id": [2], "value": ["second"]})
    ).commit()
```

Materialization is create-only. Use `TableTransaction` for grouped insert,
keyed update, and predicate-required delete operations.

## Temporal storage lifecycle

Providers that advertise managed temporal capabilities implement the lifecycle:

```text
stage -> commit -> readback
  \-> abort
```

Stage is invisible. Commit is idempotent for the logical target, stage, and
idempotency key. Readback independently measures the committed snapshot's
schema, content, row count, bytes, and time range. An uncertain mutation is
reconciled from its operation identity; it is not blindly repeated.

See [Resolution](resolution.md) for reading a committed snapshot and
[Evidence and lineage](evidence-and-lineage.md) for receipt interpretation.
