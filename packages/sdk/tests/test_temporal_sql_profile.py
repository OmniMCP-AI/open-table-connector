from __future__ import annotations

import open_table_connector.sdk as otc
import pytest
from open_table_connector.timeseries import (
    BucketAggregate,
    GapFill,
    Latest,
    ScanRange,
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
