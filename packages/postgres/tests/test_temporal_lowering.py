from __future__ import annotations

from dataclasses import replace

import pytest

from open_table_connector.postgres import PostgresTemporalExecutor, lower_postgres
from open_table_connector.timeseries import CalendarBucket, CalendarUnit

from packages.local_files.tests.test_temporal_csv import operations
from packages.timeseries.tests.fixtures import descriptor, portable, scan


def test_postgres_range_is_quoted_parameterized_and_ignores_logical_relation_text() -> None:
    plan = replace(portable(scan().operation), relation='logical"; DROP TABLE x; --')
    prepared = lower_postgres(plan, descriptor(), "market.ticks")
    assert 'FROM "market"."ticks"' in prepared.statement
    assert '"ts" >= %s AND "ts" < %s' in prepared.statement
    assert "2026-08-29" not in prepared.statement
    assert "DROP TABLE" not in prepared.statement
    assert prepared.parameters[:2] == (plan.operation.start, plan.operation.end)
    assert prepared.residual_plan is None

    with pytest.raises(ValueError, match="physical_table"):
        lower_postgres(plan, descriptor(), 'ticks"; DROP TABLE x; --')


def test_postgres_covers_operations_without_claiming_timescale_gapfill() -> None:
    statements = [lower_postgres(plan, descriptor(), "ticks") for plan in operations()]
    assert statements[0].residual_plan is None
    assert statements[1].residual_plan is None
    assert statements[2].residual_plan is None
    assert "date_bin" in statements[3].statement
    assert statements[3].residual_plan is None
    assert statements[4].residual_plan == operations()[4]
    assert all("time_bucket_gapfill" not in item.statement for item in statements)

    fixed = operations()[3]
    calendar = replace(
        fixed,
        operation=replace(
            fixed.operation,
            bucket=CalendarBucket(
                1,
                CalendarUnit.DAY,
                "UTC",
                1,
                "2026-01-01T00:00:00.000000000Z",
                0,
            ),
        ),
    )
    assert "date_trunc" in lower_postgres(calendar, descriptor(), "ticks").statement
    assert not any("timescale" in item.casefold() for item in PostgresTemporalExecutor.CAPABILITIES)
