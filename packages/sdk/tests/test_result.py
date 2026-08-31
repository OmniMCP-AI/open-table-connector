from __future__ import annotations

import open_table_connector.sdk as otc
import pytest
from open_table_connector.contract import TableURI


def physical_receipt() -> object:
    return otc.Receipt(
        kind="physical",
        operation="table.read",
        connector_id="sqlite",
        capability="table.read.arrow/1.0",
        safe_target=TableURI("sqlite:///tmp/orders.db"),
        mode=otc.TableMode.BASE_MODE,
        details={"row_count": 2, "access_token": "hidden"},
    )


def test_operation_result_round_trips_with_receipts_and_safe_error_details() -> None:
    receipt = physical_receipt()
    result = otc.OperationResult(
        value=2,
        outcome=otc.Outcome.SUCCEEDED,
        commit=otc.CommitState.COMMITTED,
        verification=otc.VerificationState.PASSED,
        receipts=(receipt,),
        warnings=(
            otc.OperationWarning(
                code="truncated-preview",
                message="preview rows were capped",
                safe_details={"rows": 10},
            ),
        ),
    )

    restored = otc.OperationResult.from_wire(result.to_wire())
    assert restored == result
    assert "access_token" not in repr(result.to_wire())


def test_require_value_raises_typed_otc_error_and_preserves_result() -> None:
    failed = otc.OperationResult(
        value=None,
        outcome=otc.Outcome.UNKNOWN,
        commit=otc.CommitState.UNKNOWN,
        verification=otc.VerificationState.UNAVAILABLE,
        receipts=(physical_receipt(),),
        error=otc.ErrorInfo(
            code=otc.ErrorCode.UNCERTAIN_MUTATION,
            message="commit acknowledgement was lost",
            safe_details={"retry_after_seconds": 30, "token": "hidden"},
            reconciliation=otc.ReconciliationReference(
                operation_id="write-42",
                idempotency_key="run-42",
                connector_id="sqlite",
            ),
        ),
    )

    with pytest.raises(otc.OTCError) as raised:
        failed.require_value()

    assert raised.value.result == failed
    assert "token" not in repr(failed.to_wire())


def test_operation_result_rejects_invalid_state_combinations() -> None:
    with pytest.raises(ValueError, match="requires committed or not_applicable"):
        otc.OperationResult(
            value=1,
            outcome=otc.Outcome.SUCCEEDED,
            commit=otc.CommitState.NOT_STARTED,
            verification=otc.VerificationState.PASSED,
            receipts=(),
        )

    with pytest.raises(ValueError, match="requires an error"):
        otc.OperationResult(
            value=None,
            outcome=otc.Outcome.REJECTED,
            commit=otc.CommitState.NOT_STARTED,
            verification=otc.VerificationState.SKIPPED,
            receipts=(),
        )
