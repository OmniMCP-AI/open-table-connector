from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pytest
from open_table_connector.contract import ConnectorError, ConnectorErrorCode, TableURI
from open_table_connector.maybe_sheet import (
    MaybeSheetManagedTemporalStore,
    probe_temporal_capabilities,
)
from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ManagedAbortRequest,
    ManagedCommitRequest,
    ManagedReadbackRequest,
    ManagedStageRequest,
    ResourceBounds,
    temporal_descriptor_hash,
)
from open_table_connector.timeseries.capabilities import (
    STORAGE_ABORT,
    STORAGE_COMMIT_IDEMPOTENT,
    STORAGE_READBACK_VERIFY,
    STORAGE_SNAPSHOT_READ,
    STORAGE_STAGE,
    STORAGE_VISIBILITY_ATOMIC,
)

from packages.timeseries.tests.fixtures import descriptor, ticks_table

from .test_temporal_recording import FIXTURES, RecordingTemporalProcess

LIFECYCLE = {
    STORAGE_STAGE,
    STORAGE_COMMIT_IDEMPOTENT,
    STORAGE_SNAPSHOT_READ,
    STORAGE_READBACK_VERIFY,
    STORAGE_VISIBILITY_ATOMIC,
    STORAGE_ABORT,
}


def _artifact(root: Path):
    sink = pa.BufferOutputStream()
    table = ticks_table()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    data = sink.getvalue().to_pybytes()
    digest = hashlib.sha256(data).hexdigest()
    path = root / "sha256" / f"{digest}.arrow"
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    path.chmod(0o600)
    return data, ArrowArtifactReference(f"sha256/{digest}.arrow", f"sha256:{digest}", len(data))


class LifecycleProcess(RecordingTemporalProcess):
    def __init__(self, artifact_bytes: bytes):
        super().__init__()
        self.artifact_bytes = artifact_bytes
        self.stage_id = "stage:" + "c" * 64
        self.snapshot_id = "sha256:" + hashlib.sha256(artifact_bytes).hexdigest()
        self.snapshot_reference = "mbs-snapshot:" + self.snapshot_id[7:]

    def run(self, argv, *, credentials=None, stdin=None, timeout=None):
        if argv[2] in {"describe", "read"}:
            return super().run(
                argv, credentials=credentials, stdin=stdin, timeout=timeout
            )
        self.calls.append((argv, credentials, stdin, timeout))
        request = json.loads(stdin)
        target = request["logical_target"]
        now = "2026-08-29T01:02:03.000000000Z"
        if argv[2] == "stage":
            return {
                "receipt": {
                    "schema_version": "otc.managed-stage-receipt/v1",
                    "operation_id": request["operation_id"],
                    "logical_target": target,
                    "physical_target": request["physical_target"],
                    "stage_id": self.stage_id,
                    "idempotency_key": request["idempotency_key"],
                    "artifact_hash": request["artifact"]["sha256"],
                    "descriptor_hash": request["descriptor_hash"],
                    "staged_at": now,
                    "visible": False,
                }
            }
        if argv[2] == "commit":
            return {
                "receipt": {
                    "schema_version": "otc.managed-commit-receipt/v1",
                    "operation_id": request["operation_id"],
                    "logical_target": target,
                    "stage_id": request["stage_id"],
                    "idempotency_key": request["idempotency_key"],
                    "snapshot_id": self.snapshot_id,
                    "snapshot_reference": self.snapshot_reference,
                    "committed_at": now,
                    "visibility": "atomic",
                }
            }
        if argv[2] == "snapshot-read":
            import base64

            return {
                "schema_version": "mbs.temporal-snapshot-result/v1",
                "arrow_ipc_base64": base64.b64encode(self.artifact_bytes).decode(),
            }
        if argv[2] == "readback":
            table = ticks_table()
            arrow_hash = "sha256:" + hashlib.sha256(self.artifact_bytes).hexdigest()
            schema_hash = "sha256:" + hashlib.sha256(
                table.schema.serialize().to_pybytes()
            ).hexdigest()
            return {
                "receipt": {
                    "schema_version": "otc.managed-readback-receipt/v1",
                    "operation_id": request["operation_id"],
                    "snapshot_id": request["snapshot_id"],
                    "observed_at": now,
                    "observed_schema_hash": schema_hash,
                    "observed_content_hash": arrow_hash,
                    "observed_rows": table.num_rows,
                    "observed_bytes": len(self.artifact_bytes),
                    "observed_range": {
                        "start": "2026-08-29T00:00:00.000000000Z",
                        "end": "2026-08-29T00:10:00.000000000Z",
                    },
                }
            }
        if argv[2] == "abort":
            return {
                "receipt": {
                    "schema_version": "otc.managed-abort-receipt/v1",
                    "operation_id": request["operation_id"],
                    "logical_target": target,
                    "stage_id": request["stage_id"],
                    "disposition": "already_committed",
                    "aborted_at": now,
                }
            }
        raise AssertionError(argv)


@pytest.mark.parametrize("missing", ("stage", "commit", "snapshot-read", "readback", "abort"))
def test_lifecycle_capabilities_are_all_or_none(missing: str) -> None:
    description = json.loads((FIXTURES / "temporal-describe.json").read_text())
    full = probe_temporal_capabilities(RecordingTemporalProcess(copy.deepcopy(description)))
    assert LIFECYCLE.issubset(full)

    del description["commands"][missing]
    process = RecordingTemporalProcess(description)
    capabilities = probe_temporal_capabilities(process)
    assert LIFECYCLE.isdisjoint(capabilities)
    with pytest.raises(ConnectorError) as error:
        MaybeSheetManagedTemporalStore(process, Path("/unused"), descriptor())
    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert len(process.calls) == 1


def test_lifecycle_requires_explicit_atomic_visibility_evidence() -> None:
    description = json.loads((FIXTURES / "temporal-describe.json").read_text())
    description["visibility"] = {"guarantee": "best-effort", "evidence_schema": None}
    process = RecordingTemporalProcess(description)

    assert LIFECYCLE.isdisjoint(probe_temporal_capabilities(process))
    with pytest.raises(ConnectorError):
        MaybeSheetManagedTemporalStore(process, Path("/unused"), descriptor())
    assert len(process.calls) == 1


def test_recording_managed_store_uses_only_proven_receipts(tmp_path: Path) -> None:
    data, reference = _artifact(tmp_path / "artifacts")
    process = LifecycleProcess(data)
    store = MaybeSheetManagedTemporalStore(process, tmp_path / "artifacts", descriptor())
    target = TableURI("maybe://document/ticks")
    staged = store.stage(
        ManagedStageRequest(
            "mbs-stage",
            reference,
            temporal_descriptor_hash(descriptor(), ticks_table().schema),
            target,
            target,
            "mbs-idem",
            ResourceBounds(100, 10_000_000, 1_000),
        )
    )
    committed = store.commit(
        ManagedCommitRequest(
            "mbs-commit",
            target,
            staged.stage_id,
            staged.idempotency_key,
            ResourceBounds(100, 10_000_000, 1_000),
        )
    )
    result = store.readback(
        ManagedReadbackRequest(
            "mbs-readback",
            target,
            committed.snapshot_id,
            committed.snapshot_reference,
            ResourceBounds(100, 10_000_000, 1_000),
        )
    )
    aborted = store.abort(ManagedAbortRequest("mbs-abort", target, staged.stage_id))

    assert result.table is not None and result.table.equals(ticks_table())
    assert aborted.disposition.value == "already_committed"
    assert [call[0][2] for call in process.calls] == [
        "describe",
        "stage",
        "commit",
        "snapshot-read",
        "readback",
        "abort",
    ]
