# Universal connector conformance

This directory contains the offline, framework-neutral conformance suite for
the supported connector families: `csv`, `excel`, `md`, `local_files`,
`google_sheets`, `feishu_bitable`, `maybe_sheet`, `sqlite`, `postgres`, and
`dbt`. Tests use deterministic fixture data and stable case IDs so the suite
can validate wire
contracts, discovery, table behavior, database behavior, dbt behavior, CLI
surfaces, and security invariants without requiring external services.

The local matrix keeps the concrete `csv`, `excel`, and `md` cases separate
from the `local_files` compatibility case. Explicit `csv://`, `excel://`, and
`md://` endpoints assert direct scheme routing, while bare paths and `file://`
URIs continue to exercise compatibility autodetection.

Each case owns its temporary files, database, recording transport, or process
client. The suite does not read credentials, call the network, invoke vendor
binaries, or share mutable databases.

From a fresh checkout, install every workspace package and the development
dependencies before running the suite:

```bash
uv sync --all-packages --group dev
```

The suite must maintain at least 120 collected test cases. Check the count
with:

```bash
uv run --frozen python -m pytest specification/conformance/universal --collect-only -q
```

Run the dedicated suite with:

```bash
uv run --frozen python -m pytest specification/conformance/universal -q
```

When adding coverage, prefer named behavior-focused tests in the relevant
module. Parametrized cases should use stable descriptive IDs.
