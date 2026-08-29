from __future__ import annotations

from open_table_connector.process import (
    ArtifactStore,
    ConnectorProcessEnvelope,
    ConnectorProcessRegistry,
    ConnectorProcessServer,
    CredentialResolver,
    ProcessOperation,
    TemporalProcessHandler,
    temporal_registration,
)
from open_table_connector.contract import TableURI
from open_table_connector.local_files import CsvManagedTemporalStore, CsvTemporalExecutor
from open_table_connector.timeseries import PolarsTemporalExecutor
from packages.timeseries.tests.fixtures import MemoryTemporalSource, descriptor

from .conftest import lifecycle_case


def envelope(*, operation, message_id, payload, artifacts=(), connector_id="json"):
    return ConnectorProcessEnvelope(
        protocol="otc.connector-process/v1",
        message_id=message_id,
        session_id="conformance-session",
        operation=operation,
        connector={"id": connector_id, "version": "0.1.0", "contract_version": "1.0"},
        capability_version="1.0",
        resource_limits={"max_rows": 100, "max_bytes": 10_000_000, "max_duration_ms": 1000},
        credential_reference=None,
        payload=payload,
        artifact_references=artifacts,
    )


def test_ots_shaped_hello_and_execute_return_verified_arrow(tmp_path, semantic_case) -> None:
    handler = TemporalProcessHandler(
        executor=PolarsTemporalExecutor(MemoryTemporalSource()), store=None
    )
    registry = ConnectorProcessRegistry((temporal_registration("json", handler),))
    artifacts = ArtifactStore(tmp_path / "artifacts")
    server = ConnectorProcessServer(registry, artifacts, CredentialResolver())
    hello = envelope(
        operation=ProcessOperation.HELLO,
        message_id="hello",
        payload={
            "portable_plan_version": "otc.portable-temporal-plan/v1",
            "capability_versions": {"timeseries.scan.range": "1.0"},
        },
    )
    hello_response = server.handle(hello)
    assert hello_response.payload["result"]["process_protocol"] == "otc.connector-process/v1"

    execution = semantic_case.request
    execute = envelope(
        operation=ProcessOperation.EXECUTE,
        message_id="execute",
        payload={
            "target": execution.target.value,
            "portable_plan": execution.plan.to_wire(),
            "snapshot_reference": None,
        },
    )
    response = server.handle(execute)
    assert response.payload["ok"] is True
    assert len(response.artifact_references) == 1
    actual = artifacts.get_arrow(response.artifact_references[0], execute.resource_limits)
    assert actual.equals(semantic_case.expected)
    assert response.payload["result"]["receipt"]["schema_version"] == "otc.temporal-receipt/v1"


def test_ots_shaped_stage_commit_readback_and_abort(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifacts = ArtifactStore(artifact_root)
    target = TableURI(
        (tmp_path / "ticks").as_uri().replace("file://", "managed+csv://", 1)
    )
    case = lifecycle_case(artifact_root, target)
    store = CsvManagedTemporalStore(artifact_root, descriptor())
    handler = TemporalProcessHandler(
        executor=CsvTemporalExecutor(descriptor(), store), store=store
    )
    registry = ConnectorProcessRegistry((temporal_registration("csv", handler),))
    server = ConnectorProcessServer(registry, artifacts, CredentialResolver())

    def request(operation, message_id, payload, refs=()):
        value = envelope(
            operation=operation,
            message_id=message_id,
            payload=payload,
            artifacts=refs,
            connector_id="csv",
        )
        return value

    server.handle(
        request(
            ProcessOperation.HELLO,
            "lifecycle-hello",
            {
                "portable_plan_version": "otc.portable-temporal-plan/v1",
                "capability_versions": {"storage.stage": "1.0"},
            },
        )
    )
    staged = server.handle(
        request(
            ProcessOperation.STAGE,
            "lifecycle-stage",
            {
                "operation_id": case.stage_request.operation_id,
                "descriptor_hash": case.stage_request.descriptor_hash,
                "logical_target": target.value,
                "physical_target": target.value,
                "idempotency_key": case.stage_request.idempotency_key,
            },
            (case.stage_request.artifact,),
        )
    ).payload["result"]
    committed = server.handle(
        request(
            ProcessOperation.COMMIT,
            "lifecycle-commit",
            {
                "operation_id": case.commit_operation_id,
                "logical_target": target.value,
                "stage_id": staged["stage_id"],
                "idempotency_key": staged["idempotency_key"],
            },
        )
    ).payload["result"]
    readback = server.handle(
        request(
            ProcessOperation.READBACK,
            "lifecycle-readback",
            {
                "operation_id": case.readback_operation_id,
                "logical_target": target.value,
                "snapshot_id": committed["snapshot_id"],
                "snapshot_reference": committed["snapshot_reference"],
            },
        )
    )
    assert readback.payload["result"]["snapshot_id"] == committed["snapshot_id"]
    assert len(readback.artifact_references) == 1
    aborted = server.handle(
        request(
            ProcessOperation.ABORT,
            "lifecycle-abort",
            {
                "operation_id": case.abort_operation_id,
                "logical_target": target.value,
                "stage_id": staged["stage_id"],
            },
        )
    ).payload["result"]
    assert aborted["disposition"] == "already_committed"
