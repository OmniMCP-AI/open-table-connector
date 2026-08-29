from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import pyarrow as pa

from open_table_connector.contract import TableURI
from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ManagedCommitRequest,
    ManagedStageRequest,
    ResourceBounds,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import descriptor, ticks_table

BOUNDS = ResourceBounds(10_000, 64 * 1024 * 1024, 30_000)


def sqlite_uri(path: Path) -> TableURI:
    return TableURI(f"sqlite://{path.as_posix()}")


def put_artifact(root: Path, table: pa.Table | None = None) -> ArrowArtifactReference:
    value = table if table is not None else ticks_table()
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, value.schema) as writer:
        writer.write_table(value)
    data = sink.getvalue().to_pybytes()
    digest = hashlib.sha256(data).hexdigest()
    path = root / "sha256" / f"{digest}.arrow"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)
    return ArrowArtifactReference(f"sha256/{digest}.arrow", f"sha256:{digest}", len(data))


def stage_request(root: Path, target: TableURI, *, operation="stage-1", idem="idem-1"):
    table = ticks_table()
    return ManagedStageRequest(
        operation,
        put_artifact(root, table),
        temporal_descriptor_hash(descriptor(), table.schema),
        target,
        target,
        idem,
        BOUNDS,
    )


def commit_request(stage, *, operation="commit-1"):
    return ManagedCommitRequest(
        operation,
        stage.logical_target,
        stage.stage_id,
        stage.idempotency_key,
        BOUNDS,
    )


def create_ticks(path: Path) -> None:
    table = ticks_table()
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE ticks (ts INTEGER, symbol TEXT, venue TEXT, price REAL, size INTEGER, received_at INTEGER)"
    )
    columns = [table[name].to_pylist() for name in ("symbol", "venue", "price", "size")]
    times = table["ts"].cast(pa.int64()).to_pylist()
    received = table["received_at"].cast(pa.int64()).to_pylist()
    rows = [
        (times[index], columns[0][index], columns[1][index], columns[2][index], columns[3][index], received[index])
        for index in range(table.num_rows)
    ]
    connection.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?, ?, ?)", rows)
    connection.commit()
    connection.close()
