from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pyarrow as pa
from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    BucketAggregate,
    FixedBucket,
    PolarsTemporalExecutor,
    TemporalExecutionRequest,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import (
    TARGET,
    MemoryTemporalSource,
    portable,
    ticks_table,
)


def test_average_of_decimal_values_stays_decimal() -> None:
    source_table = ticks_table()
    values = [
        None if value is None else Decimal(str(value)).quantize(Decimal("0.000000000000000001"))
        for value in source_table["price"].to_pylist()
    ]
    source_table = source_table.set_column(
        3,
        "price",
        pa.array(values, type=pa.decimal128(38, 18)),
    )
    source = MemoryTemporalSource(table=source_table)
    operation = BucketAggregate(
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:10:00.000000000Z",
        FixedBucket(300_000_000_000, "2026-08-29T00:00:00.000000000Z"),
        ("symbol",),
        (AggregateMeasure("average", AggregateFunction.AVG, "price"),),
        (),
    )
    plan = replace(
        portable(operation),
        descriptor_hash=temporal_descriptor_hash(source.descriptor, source.table.schema),
    )

    result = PolarsTemporalExecutor(source).execute(
        TemporalExecutionRequest(TARGET, plan, None, "decimal-average", None)
    )

    assert result.table.schema.field("average").type == pa.decimal128(38, 18)
