from __future__ import annotations

import pyarrow as pa
import pytest
from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    FillMode,
    FillRule,
    FixedBucket,
    GapFill,
    PolarsTemporalExecutor,
    ResourceBounds,
    TemporalErrorCode,
    TemporalExecutionRequest,
    TemporalExtensionError,
)

from packages.timeseries.tests.fixtures import (
    TARGET,
    MemoryTemporalSource,
    descriptor,
    ns,
    portable,
)


def sparse_table() -> pa.Table:
    return pa.table(
        {
            "ts": pa.array(
                [ns(0), ns(10), ns(0)],
                type=pa.timestamp("ns", tz="UTC"),
            ),
            "symbol": ["AAPL", "AAPL", "MSFT"],
            "venue": ["XNAS", "XNAS", "XNYS"],
            "price": pa.array([0.0, 10.0, 100.0], type=pa.float64()),
            "size": pa.array([1, 1, 1], type=pa.int64()),
            "received_at": pa.array(
                [ns(0, 1), ns(10, 1), ns(0, 1)],
                type=pa.timestamp("ns", tz="UTC"),
            ),
        }
    )


def gap(fills, *, resource_bounds=None):
    return portable(
        GapFill(
            start="2026-08-29T00:00:00.000000000Z",
            end="2026-08-29T00:15:00.000000000Z",
            bucket=FixedBucket(
                300_000_000_000,
                "2026-08-29T00:00:00.000000000Z",
                0,
            ),
            group_by=("symbol",),
            measures=(
                AggregateMeasure("avg_price", AggregateFunction.AVG, "price"),
                AggregateMeasure("rows", AggregateFunction.COUNT, None),
            ),
            tag_predicates=(),
            fills=fills,
        ),
        resource_bounds=resource_bounds,
    )


def execute(plan):
    source = MemoryTemporalSource(table=sparse_table(), temporal_descriptor=descriptor())
    return PolarsTemporalExecutor(source).execute(
        TemporalExecutionRequest(TARGET, plan, None, "gap-test", None)
    ).table


def values_by_symbol(table, field):
    rows = table.to_pylist()
    return {
        symbol: [row[field] for row in rows if row["symbol"] == symbol]
        for symbol in ("AAPL", "MSFT")
    }


def test_null_constant_locf_and_linear_fill_stay_inside_each_series() -> None:
    table = execute(
        gap(
            (
                FillRule("avg_price", FillMode.LINEAR, None),
                FillRule("rows", FillMode.CONSTANT, 0),
            )
        )
    )
    assert values_by_symbol(table, "avg_price") == {
        "AAPL": [0.0, 5.0, 10.0],
        "MSFT": [100.0, None, None],
    }
    assert values_by_symbol(table, "rows") == {
        "AAPL": [1, 0, 1],
        "MSFT": [1, 0, 0],
    }

    locf = execute(
        gap(
            (
                FillRule("avg_price", FillMode.LOCF, None),
                FillRule("rows", FillMode.NULL, None),
            )
        )
    )
    assert values_by_symbol(locf, "avg_price") == {
        "AAPL": [0.0, 0.0, 10.0],
        "MSFT": [100.0, 100.0, 100.0],
    }


def test_gapfill_checks_cartesian_row_bound_before_materialization() -> None:
    constrained = ResourceBounds(max_rows=5, max_bytes=10_000_000, max_duration_ms=1_000)
    with pytest.raises(TemporalExtensionError) as raised:
        execute(gap((), resource_bounds=constrained))

    assert raised.value.code is TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED
