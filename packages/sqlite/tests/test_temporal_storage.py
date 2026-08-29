from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from open_table_connector.sqlite import SQLiteManagedTemporalStore, SQLiteTemporalExecutor
from open_table_connector.timeseries import (
    AbortDisposition,
    ManagedAbortRequest,
    ManagedReadbackRequest,
    PolarsTemporalExecutor,
    ResourceBounds,
    TemporalExecutionRequest,
)

from packages.local_files.tests.test_temporal_csv import operations
from packages.timeseries.tests.fixtures import MemoryTemporalSource, descriptor

from .temporal_fixtures import (
    commit_request,
    create_ticks,
    sqlite_uri,
    stage_request,
)


def test_sqlite_stage_commit_readback_and_abort_use_adapter_owned_tables(tmp_path: Path) -> None:
    path = tmp_path / "ticks.db"
    target = sqlite_uri(path)
    artifact_root = tmp_path / "artifacts"
    store = SQLiteManagedTemporalStore(target, artifact_root, descriptor())
    staged = store.stage(stage_request(artifact_root, target))

    connection = sqlite3.connect(path)
    assert connection.execute("SELECT committed FROM _otc_ts_stages").fetchall() == [(0,)]
    assert connection.execute("SELECT COUNT(*) FROM _otc_ts_commits").fetchone() == (0,)
    connection.close()

    committed = store.commit(commit_request(staged))
    assert store.commit(commit_request(staged, operation="commit-retry")) == committed
    readback = store.readback(
        ManagedReadbackRequest(
            "readback-1",
            target,
            committed.snapshot_id,
            committed.snapshot_reference,
            ResourceBounds(100, 10_000_000, 1000),
        )
    )
    assert readback.table is not None
    assert readback.table.num_rows == 7
    assert store.abort(
        ManagedAbortRequest("abort-1", target, staged.stage_id)
    ).disposition is AbortDisposition.ALREADY_COMMITTED


@pytest.mark.parametrize("plan", operations())
@pytest.mark.parametrize("snapshot", (False, True))
def test_sqlite_temporal_executor_matches_portable_semantics(
    tmp_path: Path,
    plan,
    snapshot: bool,
) -> None:
    path = tmp_path / "ticks.db"
    create_ticks(path)
    target = sqlite_uri(path)
    artifact_root = tmp_path / "artifacts"
    store = SQLiteManagedTemporalStore(target, artifact_root, descriptor())
    reference = None
    if snapshot:
        reference = store.commit(
            commit_request(store.stage(stage_request(artifact_root, target)))
        ).snapshot_reference
    request = TemporalExecutionRequest(target, plan, None, "sqlite-test", reference)
    actual = SQLiteTemporalExecutor(
        descriptor(),
        "ticks",
        managed_store=store,
    ).execute(request).table
    expected = PolarsTemporalExecutor(MemoryTemporalSource()).execute(request).table
    assert actual.equals(expected)
