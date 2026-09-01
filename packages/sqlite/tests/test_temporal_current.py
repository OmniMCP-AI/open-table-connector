from __future__ import annotations

import sqlite3
from pathlib import Path

import pyarrow as pa
import pytest
from open_table_connector.contract import TableURI
from open_table_connector.sqlite import SQLiteManagedTemporalStore
from open_table_connector.timeseries import (
    ManagedCommitRequest,
    ManagedCurrentRequest,
    ManagedStageRequest,
    ResourceBounds,
    TemporalErrorCode,
    TemporalExtensionError,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import descriptor, ticks_table

from .temporal_fixtures import put_artifact, sqlite_uri

BOUNDS = ResourceBounds(10_000, 64 * 1024 * 1024, 30_000)


def _stage_and_commit(
    store: SQLiteManagedTemporalStore,
    root: Path,
    target: TableURI,
    *,
    key: str,
    table: pa.Table | None = None,
):
    value = ticks_table() if table is None else table
    stage = store.stage(
        ManagedStageRequest(
            operation_id=f"stage-{key}",
            artifact=put_artifact(root, value),
            descriptor_hash=temporal_descriptor_hash(descriptor(), value.schema),
            logical_target=target,
            physical_target=target,
            idempotency_key=key,
            resource_bounds=BOUNDS,
        )
    )
    return store.commit(
        ManagedCommitRequest(
            operation_id=f"commit-{key}",
            logical_target=target,
            stage_id=stage.stage_id,
            idempotency_key=key,
            resource_bounds=BOUNDS,
        )
    )


def _current(store: SQLiteManagedTemporalStore, target: TableURI):
    return store.current(
        ManagedCurrentRequest(
            target,
            temporal_descriptor_hash(descriptor(), ticks_table().schema),
        )
    )


def test_current_returns_none_before_first_commit(tmp_path: Path) -> None:
    target = sqlite_uri(tmp_path / "ticks.db")
    store = SQLiteManagedTemporalStore(target, tmp_path / "artifacts", descriptor())

    assert _current(store, target) is None


def test_current_recovers_latest_snapshot_and_schema(tmp_path: Path) -> None:
    target = sqlite_uri(tmp_path / "ticks.db")
    root = tmp_path / "artifacts"
    store = SQLiteManagedTemporalStore(target, root, descriptor())
    committed = _stage_and_commit(store, root, target, key="batch-1")

    current = _current(store, target)

    assert current is not None
    assert current.snapshot_id == committed.snapshot_id
    assert current.snapshot_reference == committed.snapshot_reference
    assert current.schema == ticks_table().schema


def test_current_moves_across_sequential_commits_and_reopen(tmp_path: Path) -> None:
    target = sqlite_uri(tmp_path / "ticks.db")
    root = tmp_path / "artifacts"
    store = SQLiteManagedTemporalStore(target, root, descriptor())
    first = _stage_and_commit(store, root, target, key="batch-1")
    second_table = ticks_table().set_column(
        3,
        "price",
        pa.array([104.0, 100.0, 101.0, 102.0, 200.0, None, 202.0]),
    )
    second = _stage_and_commit(store, root, target, key="batch-2", table=second_table)

    assert _current(store, target).snapshot_id == second.snapshot_id  # type: ignore[union-attr]
    reopened = SQLiteManagedTemporalStore(target, root, descriptor())
    recovered = _current(reopened, target)
    assert recovered is not None
    assert recovered.snapshot_reference == second.snapshot_reference
    assert recovered.snapshot_reference != first.snapshot_reference


def test_current_recovers_an_empty_typed_snapshot(tmp_path: Path) -> None:
    target = sqlite_uri(tmp_path / "ticks.db")
    root = tmp_path / "artifacts"
    empty = ticks_table().slice(0, 0)
    store = SQLiteManagedTemporalStore(target, root, descriptor())
    _stage_and_commit(store, root, target, key="empty", table=empty)

    current = _current(store, target)

    assert current is not None
    assert current.schema == empty.schema
    assert current.schema.field("ts").type == pa.timestamp("ns", tz="UTC")


def test_current_rejects_descriptor_mismatch(tmp_path: Path) -> None:
    target = sqlite_uri(tmp_path / "ticks.db")
    root = tmp_path / "artifacts"
    store = SQLiteManagedTemporalStore(target, root, descriptor())
    _stage_and_commit(store, root, target, key="batch-1")

    with pytest.raises(TemporalExtensionError) as raised:
        store.current(ManagedCurrentRequest(target, "sha256:" + "b" * 64))
    assert raised.value.code is TemporalErrorCode.PROTOCOL_INVALID


@pytest.mark.parametrize("mutation", ("corrupt_blob", "missing_snapshot"))
def test_current_rejects_corrupt_or_missing_snapshot_artifact(
    tmp_path: Path, mutation: str
) -> None:
    target = sqlite_uri(tmp_path / "ticks.db")
    root = tmp_path / "artifacts"
    store = SQLiteManagedTemporalStore(target, root, descriptor())
    committed = _stage_and_commit(store, root, target, key="batch-1")
    connection = sqlite3.connect(tmp_path / "ticks.db")
    if mutation == "corrupt_blob":
        connection.execute(
            "UPDATE _otc_ts_snapshots SET arrow_blob = ? WHERE snapshot_id = ?",
            (b"corrupt", committed.snapshot_id),
        )
    else:
        connection.execute(
            "DELETE FROM _otc_ts_snapshots WHERE snapshot_id = ?",
            (committed.snapshot_id,),
        )
    connection.commit()
    connection.close()

    with pytest.raises(TemporalExtensionError) as raised:
        _current(store, target)
    assert raised.value.code is TemporalErrorCode.SNAPSHOT_UNAVAILABLE


def test_current_rejects_multiple_current_rows(tmp_path: Path) -> None:
    target = sqlite_uri(tmp_path / "ticks.db")
    root = tmp_path / "artifacts"
    store = SQLiteManagedTemporalStore(target, root, descriptor())
    _stage_and_commit(store, root, target, key="batch-1")
    _stage_and_commit(store, root, target, key="batch-2")
    connection = sqlite3.connect(tmp_path / "ticks.db")
    connection.execute("UPDATE _otc_ts_commits SET current = 1")
    connection.commit()
    connection.close()

    with pytest.raises(TemporalExtensionError) as raised:
        _current(store, target)
    assert raised.value.code is TemporalErrorCode.PROTOCOL_INVALID


def test_current_is_scoped_to_the_logical_target(tmp_path: Path) -> None:
    target = sqlite_uri(tmp_path / "ticks.db")
    other = TableURI(f"{target.value}#other")
    root = tmp_path / "artifacts"
    store = SQLiteManagedTemporalStore(target, root, descriptor())
    _stage_and_commit(store, root, target, key="batch-1")

    assert _current(store, other) is None
