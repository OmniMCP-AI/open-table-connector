from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest

from open_table_connector.contract import TableURI
from open_table_connector.local_files import (
    JsonManagedTemporalStore,
    JsonTemporalExecutor,
    encode_json_table,
    encode_jsonl_table,
)
from open_table_connector.timeseries import (
    AggregateFunction,
    AggregateMeasure,
    BucketAggregate,
    FixedBucket,
    ManagedCommitRequest,
    ManagedStageRequest,
    PolarsTemporalExecutor,
    TemporalErrorCode,
    TemporalExecutionRequest,
    TemporalExtensionError,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import MemoryTemporalSource, descriptor, portable, ticks_table

from .managed_fixtures import put_artifact
from .test_temporal_csv import operations


def uri(format_name: str, path: Path) -> TableURI:
    return TableURI(path.as_uri().replace("file://", f"{format_name}://", 1))


def write_direct(path: Path, format_name: str, table: pa.Table | None = None) -> None:
    value = table if table is not None else ticks_table()
    encoder = encode_json_table if format_name == "json" else encode_jsonl_table
    path.write_text(encoder(value), encoding="utf-8")


def stage(store, artifact_root: Path, target: TableURI, *, operation_id="stage-1", idem="idem-1"):
    table = ticks_table()
    return store.stage(
        ManagedStageRequest(
            operation_id=operation_id,
            artifact=put_artifact(artifact_root, table),
            descriptor_hash=temporal_descriptor_hash(descriptor(), table.schema),
            logical_target=target,
            physical_target=target,
            idempotency_key=idem,
            resource_bounds=operations()[0].resource_bounds,
        )
    )


def commit(store, staged, *, operation_id="commit-1"):
    return store.commit(
        ManagedCommitRequest(
            operation_id,
            staged.logical_target,
            staged.stage_id,
            staged.idempotency_key,
            operations()[0].resource_bounds,
        )
    )


@pytest.mark.parametrize("format_name", ("json", "jsonl"))
@pytest.mark.parametrize("plan", operations())
def test_direct_and_exact_snapshot_execution_match_portable_arrow(
    tmp_path: Path,
    format_name: str,
    plan,
) -> None:
    artifact_root = tmp_path / "artifacts"
    path = tmp_path / f"ticks.{format_name}"
    write_direct(path, format_name)
    target = uri(format_name, path)
    managed = JsonManagedTemporalStore(format_name, artifact_root, descriptor())
    staged = stage(managed, artifact_root, target)
    committed = commit(managed, staged)
    executor = JsonTemporalExecutor(descriptor(), managed)
    expected_request = TemporalExecutionRequest(target, plan, None, "expected", None)
    expected = PolarsTemporalExecutor(MemoryTemporalSource()).execute(expected_request).table

    direct = executor.execute(
        TemporalExecutionRequest(target, plan, None, "direct", None)
    ).table
    snapshot = executor.execute(
        TemporalExecutionRequest(
            target,
            plan,
            None,
            "snapshot",
            committed.snapshot_reference,
        )
    ).table
    assert direct.equals(expected)
    assert snapshot.equals(expected)
    assert target.scheme == format_name
    assert "managed+" not in target.value


@pytest.mark.parametrize("format_name", ("json", "jsonl"))
def test_snapshot_reference_is_bound_to_the_same_normal_target(
    tmp_path: Path,
    format_name: str,
) -> None:
    artifact_root = tmp_path / "artifacts"
    first_path = tmp_path / f"first.{format_name}"
    second_path = tmp_path / f"second.{format_name}"
    write_direct(first_path, format_name)
    write_direct(second_path, format_name)
    first = uri(format_name, first_path)
    second = uri(format_name, second_path)
    managed = JsonManagedTemporalStore(format_name, artifact_root, descriptor())
    committed = commit(managed, stage(managed, artifact_root, first))

    with pytest.raises(TemporalExtensionError) as raised:
        JsonTemporalExecutor(descriptor(), managed).execute(
            TemporalExecutionRequest(
                second,
                operations()[0],
                None,
                "cross-target",
                committed.snapshot_reference,
            )
        )
    assert raised.value.code is TemporalErrorCode.SNAPSHOT_UNAVAILABLE


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            '[{"ts":"2026-08-29T00:00:00Z","symbol":{"nested":1},'
            '"venue":"X","price":1,"size":1,"received_at":"2026-08-29T00:00:00Z"}]',
            "scalar",
        ),
        (
            '[{"ts":"2026-08-29T00:00:00Z","symbol":"A",'
            '"venue":"X","price":"bad","size":1,"received_at":"2026-08-29T00:00:00Z"}]',
            "numeric",
        ),
    ],
)
def test_temporal_roles_and_aggregate_inputs_are_type_checked(
    tmp_path: Path,
    document: str,
    message: str,
) -> None:
    path = tmp_path / "bad.json"
    path.write_text(document)
    target = uri("json", path)
    aggregate = portable(
        BucketAggregate(
            "2026-08-29T00:00:00.000000000Z",
            "2026-08-29T00:05:00.000000000Z",
            FixedBucket(300_000_000_000, "2026-08-29T00:00:00.000000000Z", 0),
            ("symbol",),
            (AggregateMeasure("avg_price", AggregateFunction.AVG, "price"),),
            (),
        )
    )
    with pytest.raises(TemporalExtensionError, match=message) as raised:
        JsonTemporalExecutor(descriptor()).execute(
            TemporalExecutionRequest(target, aggregate, None, "bad-types", None)
        )
    assert raised.value.code is TemporalErrorCode.PROTOCOL_INVALID
