from __future__ import annotations

from dataclasses import replace

import open_table_connector.sdk as otc
import pytest
from open_table_connector.timeseries import (
    BucketAggregate,
    GapFill,
    Latest,
    ScanRange,
    TimestampPrecision,
)

from packages.timeseries.tests.fixtures import descriptor

from .temporal_sql_cases import ACCEPTED_CASES, REJECTED_CASES


@pytest.fixture
def series(fake_connector):
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    return client.open("fake://warehouse/orders").require_value().time_series(descriptor())


@pytest.mark.parametrize("case", ACCEPTED_CASES, ids=lambda case: case.name)
def test_complete_temporal_sql_profile_accepts_public_cases(series, case) -> None:
    query = series.sql(case.statement, parameters=case.parameters)
    operation = query._definition.plan.operation

    assert type(operation) is case.operation_type
    if isinstance(operation, (ScanRange, Latest)):
        fields = operation.projection
    elif isinstance(operation, (BucketAggregate, GapFill)):
        fields = (
            *operation.group_by,
            "bucket",
            *(item.output_field for item in operation.measures),
        )
    else:  # pragma: no cover - the accepted corpus is a closed union
        raise AssertionError(type(operation))
    assert fields == case.output_fields


@pytest.mark.parametrize("case", REJECTED_CASES, ids=lambda case: case.name)
def test_complete_temporal_sql_profile_rejects_unsupported_cases(series, case) -> None:
    with pytest.raises(otc.OTCError) as raised:
        series.sql(case.statement, parameters=case.parameters)

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.INVALID_SQL


@pytest.mark.parametrize(
    ("precision", "origin"),
    (
        (TimestampPrecision.SECOND, "1970-01-01T00:00:00Z"),
        (TimestampPrecision.MILLISECOND, "1970-01-01T00:00:00.000Z"),
        (TimestampPrecision.MICROSECOND, "1970-01-01T00:00:00.000000Z"),
        (TimestampPrecision.NANOSECOND, "1970-01-01T00:00:00.000000000Z"),
    ),
)
def test_temporal_sql_bucket_origin_matches_descriptor_precision(fake_connector, precision, origin) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    descriptor_for_precision = replace(descriptor(), precision=precision)
    series = client.open("fake://warehouse/orders").require_value().time_series(descriptor_for_precision)

    query = series.sql(
        "SELECT time_bucket('5 minutes', ts) AS bucket, symbol, avg(price) AS value "
        "FROM series WHERE ts >= $1 AND ts < $2 GROUP BY bucket, symbol "
        "ORDER BY symbol, bucket LIMIT 100",
        parameters={"1": "2026-08-29T00:00:00.000000000Z", "2": "2026-08-29T00:10:00.000000000Z"},
    )

    assert query._definition.plan.operation.bucket.origin == origin
