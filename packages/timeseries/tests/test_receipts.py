from __future__ import annotations

from copy import deepcopy

import pytest
from open_table_connector.contract import (
    BaseConvention,
    CapabilityIdentity,
    ConnectorIdentity,
    NeutralReceipt,
    TableMode,
    TableURI,
)
from open_table_connector.timeseries import (
    AbortDisposition,
    ExecutionLocation,
    ManagedAbortReceipt,
    ManagedCommitReceipt,
    ManagedReadbackReceipt,
    ManagedStageReceipt,
    OrderDirection,
    OrderKey,
    ResourceBounds,
    TemporalReceipt,
    TimeRange,
    VisibilityGuarantee,
)

START = "2026-08-29T00:00:00.000000000Z"
END = "2026-08-30T00:00:00.000000000Z"
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64


def neutral_receipt() -> NeutralReceipt:
    return NeutralReceipt(
        connector=ConnectorIdentity("local_files", "0.1.0", "1.0"),
        capability=CapabilityIdentity("timeseries.scan.range", "1.0"),
        operation_id="execute-1",
        safe_uri=TableURI("json:///data/ticks.json"),
        mode=TableMode.BASE,
        source_revision=HASH_A,
        schema_fingerprint=HASH_B,
        content_fingerprint=HASH_C,
        coordinate_convention=BaseConvention(key_fields=("symbol",)),
        row_count=2,
        batch_count=1,
    )


def test_temporal_receipt_round_trips_and_enforces_request_bounds() -> None:
    receipt = TemporalReceipt(
        schema_version="otc.temporal-receipt/v1",
        neutral_receipt=neutral_receipt(),
        descriptor_hash=HASH_A,
        requested_range=TimeRange(START, END),
        observed_range=TimeRange(START, END),
        output_order=(OrderKey("symbol", OrderDirection.ASC),),
        execution_location=ExecutionLocation.CONNECTOR,
        resource_bounds=ResourceBounds(10, 4096, 1000),
        examined_rows=3,
        examined_bytes=512,
        returned_rows=2,
        returned_bytes=256,
        elapsed_ms=25,
        snapshot_reference="sha256:" + "d" * 64,
        plan_schema_version="otc.portable-temporal-plan/v1",
        portable_plan_hash=HASH_B,
    )

    assert TemporalReceipt.from_wire(receipt.to_wire()) == receipt
    assert receipt.to_wire()["execution_location"] == "connector"

    with pytest.raises(ValueError, match="cannot exceed max_rows"):
        TemporalReceipt(
            **{
                **receipt.to_wire(),
                "neutral_receipt": neutral_receipt(),
                "requested_range": TimeRange(START, END),
                "observed_range": TimeRange(START, END),
                "output_order": (OrderKey("symbol", OrderDirection.ASC),),
                "execution_location": ExecutionLocation.CONNECTOR,
                "resource_bounds": ResourceBounds(1, 4096, 1000),
                "examined_rows": 3,
            }
        )


def test_receipt_wire_rejects_unknown_fields() -> None:
    receipt = ManagedReadbackReceipt(
        schema_version="otc.managed-readback-receipt/v1",
        operation_id="readback-1",
        snapshot_id=HASH_A,
        observed_at=END,
        observed_schema_hash=HASH_B,
        observed_content_hash=HASH_C,
        observed_rows=2,
        observed_bytes=128,
        observed_range=TimeRange(START, END),
    )
    wire = deepcopy(receipt.to_wire())
    wire["acceptance"] = "accepted"

    with pytest.raises(ValueError, match="unknown managed readback receipt fields"):
        ManagedReadbackReceipt.from_wire(wire)


def test_readback_requires_independent_observation() -> None:
    with pytest.raises(ValueError, match="observed_at"):
        ManagedReadbackReceipt(
            schema_version="otc.managed-readback-receipt/v1",
            operation_id="readback-1",
            snapshot_id=HASH_A,
            observed_at=None,
            observed_schema_hash=HASH_B,
            observed_content_hash=HASH_C,
            observed_rows=2,
            observed_bytes=128,
            observed_range=TimeRange(START, END),
        )


def test_managed_lifecycle_receipts_are_closed_and_round_trip() -> None:
    target = TableURI("json:///data/ticks.json")
    stage = ManagedStageReceipt(
        schema_version="otc.managed-stage-receipt/v1",
        operation_id="stage-1",
        logical_target=target,
        physical_target=target,
        stage_id="stage:" + "a" * 64,
        idempotency_key="idem-1",
        artifact_hash=HASH_A,
        descriptor_hash=HASH_B,
        staged_at=START,
        visible=False,
    )
    commit = ManagedCommitReceipt(
        schema_version="otc.managed-commit-receipt/v1",
        operation_id="commit-1",
        logical_target=target,
        stage_id=stage.stage_id,
        idempotency_key=stage.idempotency_key,
        snapshot_id=HASH_C,
        snapshot_reference="sha256:" + "d" * 64,
        committed_at=END,
        visibility=VisibilityGuarantee.ATOMIC,
    )
    abort = ManagedAbortReceipt(
        schema_version="otc.managed-abort-receipt/v1",
        operation_id="abort-1",
        logical_target=target,
        stage_id=stage.stage_id,
        disposition=AbortDisposition.ALREADY_COMMITTED,
        aborted_at=END,
    )

    assert ManagedStageReceipt.from_wire(stage.to_wire()) == stage
    assert ManagedCommitReceipt.from_wire(commit.to_wire()) == commit
    assert ManagedAbortReceipt.from_wire(abort.to_wire()) == abort
    assert stage.visible is False
    assert commit.visibility is VisibilityGuarantee.ATOMIC


@pytest.mark.parametrize("value", ("removed", "already_absent", "already_committed"))
def test_abort_dispositions_are_closed(value: str) -> None:
    assert AbortDisposition(value).value == value


@pytest.mark.parametrize("value", ("atomic", "non_atomic"))
def test_visibility_guarantees_are_closed(value: str) -> None:
    assert VisibilityGuarantee(value).value == value
