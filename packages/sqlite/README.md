# open-table-connector-sqlite

SQLite reader, writer, temporal lowering, and managed snapshot storage.

Install with `pip install open-table-connector-sqlite`; import
`open_table_connector.sqlite`.

The SQLite connector exposes managed temporal recovery through the public SDK
only. Call `series.storage.current()` to recover the current
`ManagedSnapshotState`, then use `series.storage.readback(state.snapshot)` for
the immutable snapshot contents. Provider tables, metadata rows, and artifact
paths are implementation details.

It also executes the public Temporal SQL Lite profile: bounded scans, latest
lookups, bucket aggregates, and gap fill. SQL is validated by the SDK and
lowered to the portable temporal operations; typed `as_of()` remains separate
from the SQL profile.
