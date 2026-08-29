from __future__ import annotations

import hashlib
from pathlib import Path

import pyarrow as pa

from open_table_connector.contract import TableURI
from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ManagedCommitRequest,
    ManagedStageRequest,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import descriptor, ticks_table


def managed_uri(path: Path) -> TableURI:
    return TableURI(path.as_uri().replace("file://", "managed+csv://", 1))


def put_artifact(root: Path, table: pa.Table | None = None) -> ArrowArtifactReference:
    value = table if table is not None else ticks_table()
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, value.schema) as writer:
        writer.write_table(value)
    data = sink.getvalue().to_pybytes()
    digest = hashlib.sha256(data).hexdigest()
    relative = Path("sha256") / f"{digest}.arrow"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)
    return ArrowArtifactReference(relative.as_posix(), f"sha256:{digest}", len(data))


def stage_request(
    artifact_root: Path,
    logical_path: Path,
    *,
    operation_id: str = "stage-1",
    idempotency_key: str = "idem-1",
    table: pa.Table | None = None,
) -> ManagedStageRequest:
    value = table if table is not None else ticks_table()
    target = managed_uri(logical_path)
    return ManagedStageRequest(
        operation_id=operation_id,
        artifact=put_artifact(artifact_root, value),
        descriptor_hash=temporal_descriptor_hash(descriptor(), value.schema),
        logical_target=target,
        physical_target=target,
        idempotency_key=idempotency_key,
    )


def commit_request(stage, *, operation_id: str = "commit-1") -> ManagedCommitRequest:
    return ManagedCommitRequest(
        operation_id=operation_id,
        logical_target=stage.logical_target,
        stage_id=stage.stage_id,
        idempotency_key=stage.idempotency_key,
    )
