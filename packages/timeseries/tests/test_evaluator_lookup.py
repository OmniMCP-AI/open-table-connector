from __future__ import annotations

from dataclasses import replace

import pytest
from open_table_connector.timeseries import (
    DuplicatePolicy,
    PolarsTemporalExecutor,
    TagOperator,
    TagPredicate,
    TemporalExecutionRequest,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import (
    TARGET,
    MemoryTemporalSource,
    as_of,
    latest,
    scan,
    with_policy,
)


def execute(source: MemoryTemporalSource, plan):
    plan = replace(
        plan,
        descriptor_hash=temporal_descriptor_hash(source.descriptor, source.table.schema),
    )
    return PolarsTemporalExecutor(source).execute(
        TemporalExecutionRequest(
            target=TARGET,
            plan=plan,
            credential_reference=None,
            operation_id="lookup-test",
            snapshot_reference=None,
        )
    )


def test_scan_is_half_open_projected_and_deterministically_ordered() -> None:
    source = MemoryTemporalSource()
    result = execute(source, scan())

    assert result.table.column_names == ["ts", "symbol", "venue", "price"]
    assert result.table.num_rows == 4
    assert result.table["symbol"].to_pylist() == ["AAPL", "AAPL", "MSFT", "MSFT"]
    assert result.table["price"].to_pylist() == [100.0, 102.0, 200.0, 202.0]
    assert 103.0 not in result.table["price"].to_pylist()
    assert result.receipt.returned_rows == 4
    assert result.receipt.execution_location.value == "connector"
    assert {"received_at", "ts", "symbol", "venue", "price"}.issubset(
        set(source.last_projection)
    )


def test_tag_equality_and_in_are_applied_even_when_the_source_only_projects() -> None:
    predicates = (
        TagPredicate("venue", TagOperator.EQ, ("XNAS",)),
        TagPredicate("symbol", TagOperator.IN, ("AAPL", "MISSING")),
    )
    result = execute(MemoryTemporalSource(), scan(predicates=predicates))

    assert result.table["symbol"].to_pylist() == ["AAPL", "AAPL"]
    assert result.table["venue"].to_pylist() == ["XNAS", "XNAS"]


@pytest.mark.parametrize(
    ("policy", "expected_prices"),
    [
        (DuplicatePolicy.PRESERVE, [101.0, 102.0, None, 202.0]),
        (DuplicatePolicy.REPLACE_LATEST, [102.0, 202.0]),
    ],
)
def test_latest_ties_follow_duplicate_policy(policy, expected_prices) -> None:
    source = with_policy(MemoryTemporalSource(), policy)
    result = execute(source, latest())

    assert result.table["price"].to_pylist() == expected_prices


def test_reject_policy_fails_on_latest_exact_timestamp_ties() -> None:
    source = with_policy(MemoryTemporalSource(), DuplicatePolicy.REJECT)

    with pytest.raises(ValueError, match="duplicate event timestamp"):
        execute(source, latest())


def test_as_of_uses_nanosecond_precision_and_returns_missing_series_cleanly() -> None:
    result = execute(MemoryTemporalSource(), as_of())
    assert result.table["price"].to_pylist() == [100.0, 200.0]

    no_match = scan(
        predicates=(TagPredicate("symbol", TagOperator.EQ, ("MISSING",)),)
    )
    empty = execute(MemoryTemporalSource(), no_match)
    assert empty.table.num_rows == 0
    assert empty.table.column_names == ["ts", "symbol", "venue", "price"]
    assert empty.receipt.returned_rows == 0
