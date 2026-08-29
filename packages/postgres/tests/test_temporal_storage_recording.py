from __future__ import annotations

import hashlib
from pathlib import Path

import pyarrow as pa

from open_table_connector.contract import TableURI
from open_table_connector.postgres import PostgresManagedTemporalStore
from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ManagedAbortRequest,
    ManagedCommitRequest,
    ManagedReadbackRequest,
    ManagedStageRequest,
    ResourceBounds,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import descriptor, ticks_table


class RecordingCursor:
    description = ()
    rowcount = 1

    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=()):
        self.connection.statements.append((statement, tuple(parameters)))

    def fetchone(self):
        return self.connection.responses.pop(0) if self.connection.responses else None

    def fetchmany(self, size):
        del size
        return []

    def close(self):
        self.connection.cursor_closed = True


class RecordingConnection:
    def __init__(self, responses, *, commit_error=None):
        self.responses = list(responses)
        self.commit_error = commit_error
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.cursor_closed = False

    def cursor(self, *args, **kwargs):
        del args, kwargs
        return RecordingCursor(self)

    def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class RecordingFactory:
    def __init__(self, response_sets):
        self.response_sets = list(response_sets)
        self.connections = []

    def __call__(self, **kwargs):
        del kwargs
        connection = RecordingConnection(
            self.response_sets.pop(0) if self.response_sets else []
        )
        self.connections.append(connection)
        return connection


def artifact(root: Path):
    table = ticks_table()
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    data = sink.getvalue().to_pybytes()
    digest = hashlib.sha256(data).hexdigest()
    path = root / "sha256" / f"{digest}.arrow"
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    path.chmod(0o600)
    return table, data, ArrowArtifactReference(
        f"sha256/{digest}.arrow", f"sha256:{digest}", len(data)
    )


def test_recording_lifecycle_uses_advisory_lock_upsert_timeout_and_fresh_connections(tmp_path) -> None:
    target = TableURI("postgres://localhost/analytics")
    table, data, reference = artifact(tmp_path / "artifacts")
    artifact_hash = reference.sha256
    stage_id = "stage:" + "a" * 64
    snapshot_id = artifact_hash
    snapshot_reference = "postgres-snapshot:" + artifact_hash[7:]
    factory = RecordingFactory(
        [
            [None],
            [None, ("idem-1", data, artifact_hash)],
            [(snapshot_id, data)],
            [(1,)],
        ]
    )
    store = PostgresManagedTemporalStore(
        target,
        tmp_path / "artifacts",
        descriptor(),
        connection_factory=factory,
        stage_id_factory=lambda request: stage_id,
    )
    staged = store.stage(
        ManagedStageRequest(
            "stage-1",
            reference,
            temporal_descriptor_hash(descriptor(), table.schema),
            target,
            target,
            "idem-1",
        )
    )
    committed = store.commit(
        ManagedCommitRequest("commit-1", target, staged.stage_id, "idem-1")
    )
    readback = store.readback(
        ManagedReadbackRequest(
            "readback-1",
            target,
            committed.snapshot_id,
            committed.snapshot_reference,
            ResourceBounds(100, 10_000_000, 500),
        )
    )
    store.abort(ManagedAbortRequest("abort-1", target, staged.stage_id))

    assert readback.table is not None and readback.table.num_rows == 7
    statements = "\n".join(
        statement for connection in factory.connections for statement, _ in connection.statements
    )
    assert "pg_advisory_xact_lock" in statements
    assert "ON CONFLICT" in statements
    assert "SET LOCAL statement_timeout" in statements
    assert all(connection.closed for connection in factory.connections)
    assert all(connection.commits == 1 for connection in factory.connections)


def test_ambiguous_commit_is_reconciled_without_replaying_the_write(tmp_path) -> None:
    target = TableURI("postgres://localhost/analytics")
    table, data, reference = artifact(tmp_path / "artifacts")
    stage_id = "stage:" + "b" * 64
    snapshot_id = reference.sha256
    snapshot_reference = "postgres-snapshot:" + snapshot_id[7:]
    committed_at = "2026-08-29T01:02:03.000000000Z"

    class AmbiguousFactory:
        def __init__(self):
            self.connections = []

        def __call__(self, **kwargs):
            del kwargs
            if not self.connections:
                connection = RecordingConnection(
                    [None, ("idem-2", data, reference.sha256)],
                    commit_error=OSError("connection lost after commit"),
                )
            else:
                connection = RecordingConnection(
                    [("commit-2", stage_id, snapshot_id, snapshot_reference, committed_at)]
                )
            self.connections.append(connection)
            return connection

    factory = AmbiguousFactory()
    store = PostgresManagedTemporalStore(
        target,
        tmp_path / "artifacts",
        descriptor(),
        connection_factory=factory,
    )
    result = store.commit(ManagedCommitRequest("commit-2", target, stage_id, "idem-2"))

    assert result.snapshot_id == snapshot_id
    assert len(factory.connections) == 2
    first_statements = "\n".join(item[0] for item in factory.connections[0].statements)
    second_statements = "\n".join(item[0] for item in factory.connections[1].statements)
    assert "INSERT INTO" in first_statements
    assert "INSERT INTO" not in second_statements
    assert all(connection.closed for connection in factory.connections)
