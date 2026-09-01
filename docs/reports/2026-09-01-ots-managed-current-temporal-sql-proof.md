# OTC Managed Current and Temporal SQL Proof

This report records the exact upstream source used by OTS for managed current
snapshot recovery and the Temporal SQL Lite profile.

## Source identity

- Approved base: `272f7c2c1b45b738e4044211d5e8000e5841cebb`
- Conforming code commit immediately before this report: `2f858f7dea3ba5f07774510b43648b6109c9c929`
- Branch: `codex/ots-managed-current`
- Supported Python: `>=3.11,<3.15`
- PyArrow support: `>=14,<24`; lock-selected release: `23.0.1`
- Polars lock-selected release: `1.44.1`

The code commits add provider-neutral managed current recovery, real SQLite
recovery and validation, the closed four-operation Temporal SQL Lite profile,
duplicate-policy enforcement, Python 3.14 wheel-compatible dependency
metadata, public declared-schema attachment when reopening a table, precision-
correct bucket origins, and exact Decimal averages. This report refresh is the
next documentation commit after that code commit, so the code SHA above is
intentionally the report's final source SHA.

## Verification commands

The following commands were run from the repository root:

```text
uv run --frozen pytest packages/timeseries/tests/test_storage_protocols.py packages/sdk/tests/test_temporal_current.py -q
uv run --frozen pytest packages/sdk/tests/test_client.py -q
uv run --frozen pytest packages/sqlite/tests/test_temporal_current.py -q
uv run --frozen pytest packages/sdk/tests/test_temporal_sql_profile.py packages/timeseries/tests/test_sql_duplicate_policy.py packages/sqlite/tests/test_sdk_temporal_sql.py -q
uv lock --upgrade-package pyarrow
uv sync --python 3.14 --frozen
uv run --python 3.14 --frozen python -c 'import sys, pyarrow, polars; print(sys.version.split()[0]); print(pyarrow.__version__, polars.__version__)'
uv run --python 3.13 --frozen pytest packages/contract/tests packages/sdk/tests packages/timeseries/tests packages/local_files/tests packages/sqlite/tests -q
uv run --python 3.14 --frozen pytest packages/contract/tests packages/sdk/tests packages/timeseries/tests packages/local_files/tests packages/sqlite/tests -q
uv sync --frozen
uv run --frozen pytest -q
uv run --frozen ruff check packages/sdk packages/timeseries packages/sqlite
git diff --check
```

The focused SQL corpus passed 58 cases. The Python 3.13 and 3.14 package
matrix each passed 392 tests. The repository-wide OTC suite passed 1,050 tests
with 3 skips. Ruff passed for the SDK, time-series, and SQLite packages, and
the final diff check was clean. The Python 3.14 interpreter selected the
`cp314` PyArrow 23.0.1 wheel rather than an sdist.

## Public proof scope

The tests cover no-current, single-current, sequential, reopened, empty,
descriptor-mismatch, corrupt, missing-artifact, ambiguous-current, and
cross-target recovery. The SQL corpus covers bounded scans, equality and
`IN` filters, latest, all seven aggregates, fixed buckets, gap fill, `locf`,
and `interpolate`, plus rejection of general SQL, invalid parameters and
limits, incomplete ordering/grouping, unsupported `AsOf` SQL, and invalid
duplicate-policy combinations.

No provider metadata names, physical artifact paths, SQL parser objects, or
underscore-prefixed provider methods are part of the documented consumer
surface.

## Tree status

The source tree was clean after the code commit and before this documentation
commit; the only files added by the documentation commit are this report and
the three package README updates.
