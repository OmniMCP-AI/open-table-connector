from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import pyarrow as pa
import pytest

from open_table_connector.local_files import CsvManagedTemporalStore
from open_table_connector.timeseries import (
    AbortDisposition,
    ManagedAbortRequest,
    ManagedReadbackRequest,
    ResourceBounds,
    TemporalErrorCode,
    TemporalExtensionError,
    TimestampPrecision,
    VisibilityGuarantee,
)

from packages.timeseries.tests.fixtures import descriptor, ticks_table

from .managed_fixtures import commit_request, stage_request


@pytest.mark.parametrize(
    ("unit", "precision", "scale"),
    [
        ("s", TimestampPrecision.SECOND, 1),
        ("ms", TimestampPrecision.MILLISECOND, 1_000),
        ("us", TimestampPrecision.MICROSECOND, 1_000_000),
        ("ns", TimestampPrecision.NANOSECOND, 1_000_000_000),
    ],
)
def test_observed_range_normalizes_every_arrow_timestamp_unit(
    tmp_path: Path,
    unit: str,
    precision: TimestampPrecision,
    scale: int,
) -> None:
    temporal_descriptor = replace(descriptor(), precision=precision)
    store = CsvManagedTemporalStore(tmp_path / unit, temporal_descriptor)
    table = pa.table(
        {
            "ts": pa.array(
                [1_000_000_000 * scale, 1_000_000_001 * scale],
                type=pa.timestamp(unit, tz="UTC"),
            )
        }
    )

    observed = store.snapshots._observed_range(table)
    assert observed is not None
    assert observed.start == "2001-09-09T01:46:40.000000000Z"
    assert observed.end == "2001-09-09T01:46:41.000000000Z"


def test_stage_is_invisible_and_commit_publishes_immutable_csv(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    logical = tmp_path / "ticks"
    store = CsvManagedTemporalStore(artifact_root, descriptor())
    stage = store.stage(stage_request(artifact_root, logical))
    layout = logical.with_name("ticks.otc")

    assert stage.visible is False
    assert not (layout / "current.json").exists()
    assert (layout / "stages" / f"{stage.stage_id[6:]}.arrow").is_file()

    committed = store.commit(commit_request(stage))
    snapshot = layout / committed.snapshot_reference
    assert committed.visibility is VisibilityGuarantee.ATOMIC
    assert snapshot.is_file()
    before = snapshot.read_bytes()
    assert store.commit(commit_request(stage, operation_id="commit-retry")) == committed
    assert snapshot.read_bytes() == before


def test_stage_idempotency_conflict_and_abort_dispositions(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    logical = tmp_path / "ticks"
    store = CsvManagedTemporalStore(artifact_root, descriptor())
    request = stage_request(artifact_root, logical)
    stage = store.stage(request)
    assert store.stage(replace(request, operation_id="retry")) == stage

    changed = ticks_table().set_column(
        ticks_table().schema.get_field_index("price"),
        "price",
        pa.array([999.0] * ticks_table().num_rows),
    )
    conflicting = stage_request(
        artifact_root,
        logical,
        operation_id="stage-conflict",
        idempotency_key=request.idempotency_key,
        table=changed,
    )
    with pytest.raises(TemporalExtensionError) as raised:
        store.stage(conflicting)
    assert raised.value.code is TemporalErrorCode.IDEMPOTENCY_CONFLICT

    removed = store.abort(ManagedAbortRequest("abort-1", stage.logical_target, stage.stage_id))
    absent = store.abort(ManagedAbortRequest("abort-2", stage.logical_target, stage.stage_id))
    assert removed.disposition is AbortDisposition.REMOVED
    assert absent.disposition is AbortDisposition.ALREADY_ABSENT

    committed_stage = store.stage(
        stage_request(artifact_root, logical, operation_id="stage-2", idempotency_key="idem-2")
    )
    store.commit(commit_request(committed_stage, operation_id="commit-2"))
    committed_abort = store.abort(
        ManagedAbortRequest("abort-3", committed_stage.logical_target, committed_stage.stage_id)
    )
    assert committed_abort.disposition is AbortDisposition.ALREADY_COMMITTED


def test_readback_reopens_and_independently_hashes_committed_snapshot(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    logical = tmp_path / "ticks"
    store = CsvManagedTemporalStore(artifact_root, descriptor())
    stage = store.stage(stage_request(artifact_root, logical))
    committed = store.commit(commit_request(stage))
    request = ManagedReadbackRequest(
        operation_id="readback-1",
        logical_target=stage.logical_target,
        snapshot_id=committed.snapshot_id,
        snapshot_reference=committed.snapshot_reference,
        resource_bounds=ResourceBounds(100, 10_000_000, 1000),
    )

    result = store.readback(request)
    assert result.table is not None
    assert result.table.num_rows == ticks_table().num_rows
    assert result.receipt.observed_rows == ticks_table().num_rows
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, result.table.schema) as writer:
        writer.write_table(result.table)
    independently_observed = "sha256:" + hashlib.sha256(
        sink.getvalue().to_pybytes()
    ).hexdigest()
    assert result.receipt.observed_content_hash == independently_observed
    assert result.receipt.observed_range is not None

    snapshot = logical.with_name("ticks.otc") / committed.snapshot_reference
    snapshot.write_bytes(snapshot.read_bytes() + b"tamper")
    with pytest.raises(TemporalExtensionError) as raised:
        store.readback(replace(request, operation_id="readback-tampered"))
    assert raised.value.code is TemporalErrorCode.SNAPSHOT_UNAVAILABLE
