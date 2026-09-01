from __future__ import annotations

import time
from dataclasses import replace

import pyarrow as pa
import pytest
from open_table_connector.timeseries import (
    PolarsTemporalExecutor,
    TemporalErrorCode,
    TemporalExecutionRequest,
    TemporalExtensionError,
)

from packages.timeseries.tests.fixtures import (
    TARGET,
    MemoryTemporalSource,
    bounds,
    scan,
    ticks_table,
)


class DelayedSource(MemoryTemporalSource):
    def read_bounded(self, target, projection, predicates, resource_bounds):
        time.sleep(0.02)
        return super().read_bounded(target, projection, predicates, resource_bounds)


class RowOverReturningSource(MemoryTemporalSource):
    def read_bounded(self, target, projection, predicates, resource_bounds):
        del target, predicates, resource_bounds
        table = ticks_table().select(projection)
        return pa.concat_tables([table, table, table])


def execute(source, resource_bounds):
    return PolarsTemporalExecutor(source).execute(
        TemporalExecutionRequest(
            target=TARGET,
            plan=scan(resource_bounds=resource_bounds),
            credential_reference=None,
            operation_id="bounds-test",
            snapshot_reference=None,
        )
    )


@pytest.mark.parametrize(
    ("source", "resource_bounds"),
    [
        (RowOverReturningSource(), bounds(max_rows=10)),
        (MemoryTemporalSource(), bounds(max_bytes=1)),
        (DelayedSource(), bounds(max_duration_ms=1)),
    ],
)
def test_source_and_result_bounds_fail_without_partial_receipts(source, resource_bounds) -> None:
    with pytest.raises(TemporalExtensionError) as raised:
        execute(source, resource_bounds)

    assert raised.value.code is TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED


def test_result_row_limit_is_applied_after_deterministic_sort() -> None:
    plan = replace(scan(), result_row_limit=2)
    result = PolarsTemporalExecutor(MemoryTemporalSource()).execute(
        TemporalExecutionRequest(TARGET, plan, None, "limit-test", None)
    )

    assert result.table.num_rows == 2
    assert result.table["symbol"].to_pylist() == ["AAPL", "AAPL"]
