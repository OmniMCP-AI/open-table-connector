from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Barrier, Thread

import pytest
from open_table_connector.contract import ExecutionRequest
from open_table_connector.sqlite import SQLiteConnector, SQLiteManagedTemporalStore

from packages.timeseries.tests.fixtures import descriptor

from .temporal_fixtures import commit_request, sqlite_uri, stage_request


def test_explicit_transaction_handle_rolls_back_without_connector_global_connection(tmp_path: Path) -> None:
    path = tmp_path / "tx.db"
    uri = sqlite_uri(path)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE events (id INTEGER)")
    connection.commit()
    connection.close()
    connector = SQLiteConnector()

    transaction = connector.begin(uri)
    transaction.execute(ExecutionRequest(uri, "INSERT INTO events VALUES (?)", (1,)))
    transaction.abort()

    assert not hasattr(connector, "_transaction_connection")
    assert sqlite3.connect(path).execute("SELECT COUNT(*) FROM events").fetchone() == (0,)


def test_managed_commit_failure_rolls_back_and_two_instances_can_commit(tmp_path: Path) -> None:
    path = tmp_path / "managed.db"
    uri = sqlite_uri(path)
    artifact_root = tmp_path / "artifacts"

    def fail(event):
        if event == "before_pointer_update":
            raise RuntimeError("injected")

    crashing = SQLiteManagedTemporalStore(
        uri,
        artifact_root,
        descriptor(),
        fault_injector=fail,
    )
    staged = crashing.stage(stage_request(artifact_root, uri))
    with pytest.raises(RuntimeError, match="injected"):
        crashing.commit(commit_request(staged))
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM _otc_ts_snapshots").fetchone() == (0,)
    assert connection.execute("SELECT COUNT(*) FROM _otc_ts_commits").fetchone() == (0,)
    connection.close()

    first = SQLiteManagedTemporalStore(uri, artifact_root, descriptor())
    second = SQLiteManagedTemporalStore(uri, artifact_root, descriptor())
    staged_one = first.stage(stage_request(artifact_root, uri, operation="stage-a", idem="idem-a"))
    staged_two = second.stage(stage_request(artifact_root, uri, operation="stage-b", idem="idem-b"))
    barrier = Barrier(3)
    results = []

    def publish(store, staged, operation):
        barrier.wait()
        results.append(store.commit(commit_request(staged, operation=operation)))

    threads = [
        Thread(target=publish, args=(first, staged_one, "commit-a")),
        Thread(target=publish, args=(second, staged_two, "commit-b")),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert len(results) == 2
    assert not hasattr(first, "_transaction_connection")
    assert not hasattr(second, "_transaction_connection")
