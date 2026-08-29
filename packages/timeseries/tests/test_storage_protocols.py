from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pyarrow as pa
import pytest

from open_table_connector.contract import TableURI
from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ManagedAbortRequest,
    ManagedCommitRequest,
    ManagedReadbackRequest,
    ManagedStageRequest,
    ManagedTemporalStore,
    PortableTemporalExecutor,
    ResourceBounds,
    TemporalErrorCode,
    TemporalExtensionError,
    TemporalExecutionRequest,
    TemporalExecutionResult,
    plan_from_wire,
    portable_plan_hash,
    validate_stage_retry,
)


ROOT = Path(__file__).parents[3]
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def portable_plan():
    fixture = json.loads(
        (ROOT / "specification/fixtures/timeseries/v1/scan-range.json").read_text(
            encoding="utf-8"
        )
    )
    return plan_from_wire(fixture["plan"])


def test_snapshot_reference_is_request_metadata_not_plan_identity() -> None:
    plan = portable_plan()
    direct = TemporalExecutionRequest(
        target=TableURI("json:///data/ticks.json"),
        plan=plan,
        credential_reference=None,
        operation_id="execute-direct",
        snapshot_reference=None,
    )
    committed = TemporalExecutionRequest(
        target=direct.target,
        plan=plan,
        credential_reference=None,
        operation_id="execute-committed",
        snapshot_reference=HASH_A,
    )

    assert portable_plan_hash(direct.plan) == portable_plan_hash(committed.plan)
    assert "snapshot_reference" not in direct.plan.to_wire()


def test_temporal_execution_result_requires_exactly_one_arrow_carrier() -> None:
    table = pa.table({"value": [1]})
    artifact = ArrowArtifactReference(
        relative_path="sha256/" + "a" * 64 + ".arrow",
        sha256=HASH_A,
        size_bytes=128,
    )

    with pytest.raises(ValueError, match="exactly one"):
        TemporalExecutionResult(table=table, artifact=artifact, receipt=None)
    with pytest.raises(ValueError, match="exactly one"):
        TemporalExecutionResult(table=None, artifact=None, receipt=None)
    with pytest.raises(ValueError, match="receipt"):
        TemporalExecutionResult(table=table, artifact=None, receipt=None)


def test_artifact_reference_rejects_absolute_and_traversal_paths() -> None:
    with pytest.raises(ValueError, match="relative"):
        ArrowArtifactReference("/tmp/data.arrow", HASH_A, 1)
    with pytest.raises(ValueError, match="traversal"):
        ArrowArtifactReference("../data.arrow", HASH_A, 1)


def test_managed_requests_bind_target_stage_snapshot_and_idempotency() -> None:
    target = TableURI("json:///data/ticks.json")
    artifact = ArrowArtifactReference("sha256/data.arrow", HASH_A, 128)
    stage = ManagedStageRequest(
        operation_id="stage-1",
        artifact=artifact,
        descriptor_hash=HASH_B,
        logical_target=target,
        physical_target=target,
        idempotency_key="idem-1",
        resource_bounds=ResourceBounds(10, 1024, 1000),
    )
    commit = ManagedCommitRequest(
        operation_id="commit-1",
        logical_target=target,
        stage_id="stage:" + "a" * 64,
        idempotency_key=stage.idempotency_key,
        resource_bounds=ResourceBounds(10, 1024, 1000),
    )
    readback = ManagedReadbackRequest(
        operation_id="readback-1",
        logical_target=target,
        snapshot_id=HASH_A,
        snapshot_reference=HASH_B,
        resource_bounds=ResourceBounds(10, 1024, 1000),
    )
    abort = ManagedAbortRequest(
        operation_id="abort-1",
        logical_target=target,
        stage_id=commit.stage_id,
    )

    assert stage.idempotency_key == commit.idempotency_key
    assert readback.snapshot_reference == HASH_B
    assert abort.stage_id == commit.stage_id


def test_stage_retry_rejects_same_key_with_different_content() -> None:
    from open_table_connector.timeseries import ManagedStageReceipt

    target = TableURI("json:///data/ticks.json")
    artifact = ArrowArtifactReference("sha256/data.arrow", HASH_A, 128)
    request = ManagedStageRequest(
        operation_id="stage-1",
        artifact=artifact,
        descriptor_hash=HASH_B,
        logical_target=target,
        physical_target=target,
        idempotency_key="idem-1",
        resource_bounds=ResourceBounds(10, 1024, 1000),
    )
    existing = ManagedStageReceipt(
        schema_version="otc.managed-stage-receipt/v1",
        operation_id="stage-original",
        logical_target=target,
        physical_target=target,
        stage_id="stage:" + "a" * 64,
        idempotency_key="idem-1",
        artifact_hash=HASH_A,
        descriptor_hash=HASH_B,
        staged_at="2026-08-29T00:00:00.000000000Z",
        visible=False,
    )

    assert validate_stage_retry(existing, request) == existing
    conflicting = replace(
        request,
        artifact=ArrowArtifactReference("sha256/other.arrow", "sha256:" + "c" * 64, 128),
    )
    with pytest.raises(TemporalExtensionError) as raised:
        validate_stage_retry(existing, conflicting)
    assert raised.value.code is TemporalErrorCode.IDEMPOTENCY_CONFLICT


def test_protocols_are_runtime_checkable_and_error_codes_are_extension_local() -> None:
    class Executor:
        def execute(self, request):
            raise AssertionError(request)

    class Store:
        def stage(self, request):
            raise AssertionError(request)

        def commit(self, request):
            raise AssertionError(request)

        def readback(self, request):
            raise AssertionError(request)

        def abort(self, request):
            raise AssertionError(request)

    assert isinstance(Executor(), PortableTemporalExecutor)
    assert isinstance(Store(), ManagedTemporalStore)
    assert {item.value for item in TemporalErrorCode} == {
        "protocol_invalid",
        "protocol_version_unsupported",
        "resource_limit_exceeded",
        "snapshot_unavailable",
        "idempotency_conflict",
        "visibility_incomplete",
    }
