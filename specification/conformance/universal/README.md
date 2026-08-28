# Universal connector conformance

This directory contains the offline, framework-neutral conformance suite for
the supported connector families: `local_files`, `google_sheets`,
`feishu_bitable`, `maybesheet`, `sqlite`, `postgres`, and `dbt`. Tests use
deterministic fixture data and stable case IDs so the suite can validate wire
contracts, discovery, table behavior, database behavior, dbt behavior, CLI
surfaces, and security invariants without requiring external services.

Each case owns its temporary files, database, recording transport, or process
client. The suite does not read credentials, call the network, invoke vendor
binaries, or share mutable databases.

The suite must maintain at least 120 collected test cases. Check the count
with:

```bash
uv run python -m pytest specification/conformance/universal --collect-only -q
```

Run the dedicated suite with:

```bash
uv run python -m pytest specification/conformance/universal -q
```

When adding coverage, prefer named behavior-focused tests in the relevant
module. Parametrized cases should use stable descriptive IDs.
