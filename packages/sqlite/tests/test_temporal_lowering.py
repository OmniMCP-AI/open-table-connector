from __future__ import annotations

from dataclasses import replace

import pytest
from open_table_connector.sqlite import lower_sqlite
from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    CalendarBucket,
    CalendarUnit,
    PreparedTemporalQuery,
)

from packages.local_files.tests.test_temporal_csv import operations
from packages.timeseries.tests.fixtures import descriptor, portable, scan


def test_range_lowering_quotes_authorized_identifiers_and_parameterizes_every_value() -> None:
    plan = replace(scan().operation, tag_predicates=())
    portable_plan = replace(
        portable(plan),
        relation='logical"; DROP TABLE ticks; --',
    )
    lowered = lower_sqlite(portable_plan, descriptor(), "main.ticks")

    assert isinstance(lowered, PreparedTemporalQuery)
    assert 'FROM "main"."ticks"' in lowered.statement
    assert '"ts" >= ? AND "ts" < ?' in lowered.statement
    assert 'ORDER BY "symbol" ASC, "ts" ASC' in lowered.statement
    assert "2026-08-29" not in lowered.statement
    assert "DROP TABLE" not in lowered.statement
    assert lowered.parameters[:2] == (
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:10:00.000000000Z",
    )
    assert lowered.residual_plan is None


def test_invalid_physical_identifier_never_becomes_sql() -> None:
    with pytest.raises(ValueError, match="physical_table"):
        lower_sqlite(scan(), descriptor(), 'ticks"; DROP TABLE x; --')


def test_fixed_aggregate_pushes_matching_functions_but_calendar_and_gap_are_residual() -> None:
    fixed = operations()[3]
    pushed = lower_sqlite(fixed, descriptor(), "ticks")
    assert "GROUP BY" in pushed.statement
    assert "AVG(" in pushed.statement
    assert pushed.residual_plan is None
    assert all(str(value) not in pushed.statement for value in pushed.parameters)

    operation = fixed.operation
    calendar = replace(
        fixed,
        operation=replace(
            operation,
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
    assert lower_sqlite(calendar, descriptor(), "ticks").residual_plan == calendar
    assert lower_sqlite(operations()[4], descriptor(), "ticks").residual_plan == operations()[4]

    first = replace(
        fixed,
        operation=replace(
            operation,
            measures=(AggregateMeasure("first_price", AggregateFunction.FIRST, "price"),),
        ),
    )
    assert lower_sqlite(first, descriptor(), "ticks").residual_plan == first
