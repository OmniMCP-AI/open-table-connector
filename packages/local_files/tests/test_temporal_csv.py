from __future__ import annotations

from pathlib import Path

import pytest

from open_table_connector.local_files import CsvManagedTemporalStore, CsvTemporalExecutor
from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    BucketAggregate,
    FillMode,
    FillRule,
    FixedBucket,
    GapFill,
    PolarsTemporalExecutor,
    TemporalExecutionRequest,
)

from packages.timeseries.tests.fixtures import (
    MemoryTemporalSource,
    as_of,
    descriptor,
    latest,
    portable,
    scan,
)

from .managed_fixtures import commit_request, stage_request


def operations():
    bucket = FixedBucket(300_000_000_000, "2026-08-29T00:00:00.000000000Z", 0)
    aggregate = BucketAggregate(
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:10:00.000000000Z",
        bucket,
        ("symbol",),
        (AggregateMeasure("avg_price", AggregateFunction.AVG, "price"),),
        (),
    )
    gap = GapFill(
        "2026-08-29T00:00:00.000000000Z",
        "2026-08-29T00:10:00.000000000Z",
        bucket,
        ("symbol",),
        (AggregateMeasure("avg_price", AggregateFunction.AVG, "price"),),
        (),
        (FillRule("avg_price", FillMode.LOCF, None),),
    )
    return (scan(), latest(), as_of(), portable(aggregate), portable(gap))


@pytest.mark.parametrize("plan", operations())
def test_committed_csv_matches_portable_arrow_evaluation(tmp_path: Path, plan) -> None:
    artifact_root = tmp_path / "artifacts"
    logical = tmp_path / "ticks"
    managed = CsvManagedTemporalStore(artifact_root, descriptor())
    stage = managed.stage(stage_request(artifact_root, logical))
    committed = managed.commit(commit_request(stage))
    request = TemporalExecutionRequest(
        stage.logical_target,
        plan,
        None,
        f"csv-{type(plan.operation).__name__}",
        committed.snapshot_reference,
    )

    actual = CsvTemporalExecutor(descriptor(), managed).execute(request).table
    expected = PolarsTemporalExecutor(MemoryTemporalSource()).execute(request).table
    assert actual.equals(expected)


def test_csv_advertises_semantics_without_false_pushdown_claims() -> None:
    capabilities = set(CsvTemporalExecutor.CAPABILITIES)
    assert {
        "timeseries.scan.range/1.0",
        "timeseries.lookup.latest/1.0",
        "timeseries.lookup.asof/1.0",
        "timeseries.aggregate.window/1.0",
        "timeseries.fill/1.0",
    }.issubset(capabilities)
    assert not any("pushdown" in item for item in capabilities)
