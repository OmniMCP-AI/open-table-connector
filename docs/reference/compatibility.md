# Compatibility

## Runtime

| Component | Supported boundary |
| --- | --- |
| Python | `>=3.11,<3.15` |
| Polars | `>=1,<2` |
| PyArrow | `>=14,<24` |
| SQLGlot | `>=30,<31` in the SDK |
| Package release line | `0.1.x` |

The workspace is tested as a coordinated release line, while provider wheels
remain independently packaged. Check the installed provider descriptor and
capabilities rather than assuming every package is present.

## Capability boundaries

- CSV, JSON, JSONL, Excel, SQLite, and PostgreSQL expose certified portable
  temporal surfaces with provider-specific lifecycle limits.
- Google Sheets, Feishu Bitable, and MaybeSheet expose ordinary table APIs;
  formula and temporal capabilities are selected independently.
- PostgreSQL is not a TimescaleDB identity in OTC.
- DuckDB is not a current dependency or execution backend.
- Native provider SQL has no portable semantics or automatic fallback.

## Versioning

Plan, descriptor, process, receipt, and capability identities are versioned.
Consumers should pin compatible package ranges and reject unknown schema or
capability versions rather than guessing.
