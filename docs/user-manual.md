# OTC user manual

This manual covers the public OTC command-line and Python surfaces. It is
written for callers that need a stable connector boundary, not for provider
internals.

## 1. Choose the right surface

| Need | Use | What it provides |
| --- | --- | --- |
| Inspect or move a table | `otc` CLI | Arrow-backed reads, local conversion, connector imports |
| Run a bounded temporal query in-process | `open_table_connector.timeseries` plus a provider executor | Typed plans, Polars/Arrow semantics, temporal receipts |
| Run OTC beside another process (for example OTS) | `open_table_connector.process` and `otc-process` | Framed control messages, Arrow artifacts, cancellation, credential references |

OTC's portable temporal lane is intentionally smaller than a native
time-series database. OTS sends a typed `PortableTemporalPlan` to OTC; OTC
does not parse Timescale Core SQL or accept arbitrary SQL as its portable
contract.

## 2. Install and run the CLI

From a checkout:

```console
uv sync --dev
uv run --package open-table-connector otc --help
```

The canonical entry points are `otc` and `open-table-connector`.
`open-connectors` remains a deprecated compatibility alias.

The CLI has five commands:

| Command | Purpose |
| --- | --- |
| `list` | List registered connectors, schemes, capabilities, and modes |
| `inspect` | Read metadata, columns, fingerprints, and row count |
| `read` | Read one endpoint and emit a selected format |
| `convert` | Read once and write to a local file or stdout |
| `import` | Read once and write to a writable connector |

Examples:

```console
uv run --package open-table-connector otc list
uv run --package open-table-connector otc inspect --from orders.csv --output-format json
uv run --package open-table-connector otc read --from orders.csv --output-format jsonl
uv run --package open-table-connector otc convert --from orders.csv --to orders.xlsx --to-format excel
uv run --package open-table-connector otc import --from orders.csv --to gsheets://ID/Orders --if-exists append
```

### CLI options

The shared options are:

| Option | Values or shape | Notes |
| --- | --- | --- |
| `--from` | endpoint | Required for every command except `list` |
| `--to` | endpoint | Required for `convert` and `import` |
| `--from-format` | `auto`, `csv`, `excel`, `json`, `jsonl`, `table` | Local input override |
| `--to-format` | same values | Local output override |
| `--output-format` | `csv`, `json`, `jsonl`, `table` | Defaults to `jsonl` |
| `--if-exists` | `error`, `append`, `replace` | Destination conflict policy |
| `--limit` | positive integer | Maximum rows returned from a read |
| `--timeout` | positive seconds | Connector request timeout |
| `--sheet` | sheet name | Excel or Google Sheets selection |
| `--range` | provider range | Google Sheets range |
| `--field-name` | repeatable field name | Feishu field projection |
| `--token` | secret value | Prefer an environment variable in automation |
| `--target` | provider target | MaybeSheet document/table target |

`convert` destinations must be local files or `-` (stdout). `import`
destinations must advertise `table.write`.

### Output and errors

Successful `inspect`, `read`, and pipeline summaries are emitted as the
requested format. A conversion to `-` owns stdout for the selected codec, so
the CLI does not append a JSON summary to that stream.

Errors are emitted as one safe JSON object on stderr. Provider secrets are not
included in the object. Automation should use the process exit code and the
stable error `code`, rather than matching human text.

## 3. Endpoint and URI rules

### Ordinary table CLI endpoints

| Endpoint | Meaning |
| --- | --- |
| `orders.csv` | Bare path; `local_files` probes the payload/suffix |
| `file:///absolute/path/orders.csv` | Compatibility local-file route |
| `csv:///absolute/path/orders.csv` | Explicit CSV connector |
| `excel:///absolute/path/orders.xlsx` | Explicit Excel connector; add `--sheet` when needed |
| `md:///absolute/path/orders.md` | Explicit Markdown pipe-table connector |
| `gsheets://SPREADSHEET_ID/Sheet` | Google Sheets connector |
| `feishu://APP_TOKEN/TABLE_ID` | Feishu Bitable connector |
| `maybe://DOCUMENT/TARGET` | MaybeSheet connector |

For CLI JSON and JSONL conversion, use a normal path (for example
`events.jsonl`) or pass `--from-format jsonl`; the CLI's default registry uses
the local compatibility route for those codecs.

### Temporal API endpoints

Temporal executors use `TableURI` values directly:

| Provider | URI schemes | Executor |
| --- | --- | --- |
| CSV | `csv://` and internal `managed+csv://` | `CsvTemporalExecutor` |
| JSON | `json://` | `JsonTemporalExecutor` |
| JSONL | `jsonl://` | `JsonTemporalExecutor` |
| Excel | `excel://`, `xlsx://`, and internal `managed+xlsx://` | `ExcelTemporalExecutor` |
| SQLite | `sqlite://` | `SQLiteTemporalExecutor` |
| PostgreSQL | `postgres://` | `PostgresTemporalExecutor` |
| MaybeSheet | `maybe://` | `MaybeSheetTemporalExecutor` |

JSON and JSONL always keep their normal schemes. Managed lifecycle state is
selected with an out-of-band snapshot reference; `managed+json://` and
`managed+jsonl://` are not valid targets.

Direct local temporal targets must be absolute regular files. A direct file
read is bounded before materialization and symlinked sources are rejected by
the local temporal providers.

## 4. Connector support matrix

| Provider | Ordinary table CLI | Portable temporal semantics | Managed lifecycle | Pushdown claim |
| --- | --- | --- | --- | --- |
| CSV | read/inspect/convert | scan, latest, as-of, aggregate, fill | stage, idempotent commit, snapshot readback, atomic visibility, abort | none |
| JSON | read through local codecs | same portable operations | same lifecycle | none |
| JSONL | read through local codecs | same portable operations | same lifecycle | none |
| Excel | read/inspect/convert | same portable operations | same lifecycle; worksheet-bound | none |
| SQLite | library/process binding | same typed operations with prepared SQL reads and Arrow/Polars semantics | full lifecycle | no separate pushdown capability is advertised |
| PostgreSQL | library/process binding | same typed operations with prepared SQL reads and Arrow/Polars semantics | full lifecycle | no separate pushdown capability is advertised |
| MaybeSheet | read/inspect/import | only after a live capability probe | only after complete live lifecycle proof | probe-dependent |
| Google Sheets | read/inspect/import | not a portable temporal backend | no | not applicable |
| Feishu Bitable | read/inspect/import | not a portable temporal backend | no | not applicable |
| Markdown | read/inspect/convert | no | no | not applicable |

Support is capability-based. A provider must not claim a capability merely
because an operation can be approximated locally. See
`open_table_connector.timeseries.capabilities` for the individual versioned
identities.

## 5. Portable time-series API

### Describe the table

Every temporal request binds to an immutable `TemporalTableDescriptor`:

```python
from open_table_connector.timeseries import (
    DuplicatePolicy,
    TemporalOrdering,
    TemporalTableDescriptor,
    TimestampPrecision,
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
```

The event-time field is required and non-null. Series keys define independent
series. Tags are filterable dimensions. Aggregate measures may use value
fields only. `replace-latest` requires a non-null ingestion-time field.

The descriptor hash includes the descriptor and normalized Arrow schema. It
does not include the physical URI or credentials.

Compute it from the exact schema returned by the source (the field types and
timestamp timezone/precision must match):

```python
from open_table_connector.timeseries import temporal_descriptor_hash

descriptor_hash = temporal_descriptor_hash(descriptor, source_schema)
```

### Build a typed plan

The v1 operation set is:

- `ScanRange`: projection and tag filters over `[start, end)`;
- `Latest`: latest row per series, optionally at or before a timestamp;
- `AsOf`: as-of row per series;
- `BucketAggregate`: fixed or calendar buckets with named measures; and
- `GapFill`: bucket aggregation followed by `null`, constant, LOCF, or linear
  fill.

Every plan carries a descriptor hash, logical relation token, required
capabilities, maximum rows/bytes/duration, deterministic output order, and an
optional result row limit. Plans reject unknown fields, duplicate projections,
non-UTC timestamps, unbounded ranges, and non-positive bounds.

Example scan plan:

```python
from open_table_connector.timeseries import (
    OrderDirection,
    OrderKey,
    PortableTemporalPlan,
    ResourceBounds,
    ScanRange,
)

plan = PortableTemporalPlan(
    schema_version="otc.portable-temporal-plan/v1",
    descriptor_hash=descriptor_hash,
    relation="ticks",
    required_capabilities=(),
    resource_bounds=ResourceBounds(100_000, 50_000_000, 10_000),
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
```

### Execute and inspect the receipt

All executors implement the same request/result seam:

```python
from open_table_connector.contract import TableURI
from open_table_connector.local_files import CsvTemporalExecutor
from open_table_connector.timeseries import TemporalExecutionRequest

request = TemporalExecutionRequest(
    target=TableURI("csv:///absolute/path/ticks.csv"),
    plan=plan,
    credential_reference=None,
    operation_id="scan-2026-08-29",
    snapshot_reference=None,
)
result = CsvTemporalExecutor(descriptor).execute(request)
assert result.table is not None
print(result.table)
print(result.receipt.to_wire())
```

`TemporalReceipt` records the descriptor and plan identities, requested and
observed ranges, output ordering, execution location, examined/returned rows
and bytes, elapsed time, and an optional snapshot reference.

## 6. Managed storage lifecycle

Providers that advertise lifecycle capabilities implement
`ManagedTemporalStore`:

```text
stage(Arrow artifact) -> commit(stage) -> readback(snapshot)
                              \-> abort(stage)
```

Stage is invisible. Commit is idempotent on the logical target, stage, and
idempotency key. Readback is an independent observation: its schema, content,
row, byte, and time-range facts are measured from the committed snapshot, not
copied from the staged request. Abort reports `removed`, `already_absent`, or
`already_committed`.

For JSON and JSONL, use `JsonManagedTemporalStore("json", ...)` or
`JsonManagedTemporalStore("jsonl", ...)`; the target remains `json://` or
`jsonl://`. CSV and Excel managed namespaces are provider-internal details and
are normally selected by an OTS/process binding rather than typed by a CLI
user.

## 7. Credentials, limits, and safety

- Put credentials in the caller's environment, resolver, or process secret
  store. Do not put secrets in URIs, plan documents, or artifact paths.
- `--token` is convenient for local experiments; environment variables or a
  deployment-owned credential resolver are safer for automation.
- Every temporal plan requires positive `max_rows`, `max_bytes`, and
  `max_duration_ms` bounds.
- Physical URIs and credential values are excluded from descriptor and plan
  hashes.
- Arrow artifacts are content-addressed and path-traversal checked.
- Process diagnostics and provider errors redact common token/password/API-key
  forms.

## 8. Local connector process

`otc-process` is a stdio supervisor for OTS or another caller that needs a
separate process. It requires two deployment-owned environment variables:

```console
export OTC_PROCESS_CONFIG=/absolute/path/otc-process.json
export OTC_ARTIFACT_ROOT=/absolute/path/otc-artifacts
uv run --package open-table-connector-process otc-process
```

The config is a closed, regular, non-symlink JSON file with no credentials.
Minimal CSV configuration:

```json
{
  "schema_version": "otc.process-bootstrap/v1",
  "provider": "csv",
  "descriptor": {
    "time_field": "ts",
    "timezone": "UTC",
    "precision": "nanosecond",
    "series_key_fields": ["symbol"],
    "tag_fields": ["venue"],
    "value_fields": ["price", "size"],
    "ingestion_time_field": "received_at",
    "duplicate_policy": "replace-latest",
    "ordering": "unspecified"
  },
  "target": "managed+csv:///absolute/path/ticks.csv",
  "managed": true
}
```

The process protocol negotiates connector and capability versions, carries
typed plan documents, exchanges Arrow IPC artifacts, supports cancellation,
and keeps credential references outside control payloads. It is a transport
for the temporal contract, not a second query language.

## 9. Troubleshooting

| Symptom | Check |
| --- | --- |
| `no connector advertises this endpoint scheme` | Use a supported URI scheme or a bare local path |
| `local destination format could not be inferred` | Add `--to-format` or use a recognized suffix |
| `connector sources do not support --from-format` | Remove the override for remote connectors |
| `snapshot_unavailable` | Use the snapshot reference returned by the same managed target |
| `protocol_invalid` | Recompute the descriptor hash from the exact Arrow schema |
| `resource_limit_exceeded` | Increase bounds deliberately or reduce the requested range/projection |
| MaybeSheet capability failure | Run its exact live command probe and inspect the advertised capabilities |

For normative behavior, see the [portable time-series design](superpowers/specs/2026-08-29-portable-time-series-storage-design.md)
and [time-series conformance suite](../specification/conformance/timeseries/README.md).
