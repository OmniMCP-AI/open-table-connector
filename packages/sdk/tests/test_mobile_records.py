from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import open_table_connector.sdk as otc
import pytest


def _result(
    outcome: otc.Outcome,
    *,
    value: otc.RecordUpdateValue | None = None,
    commit: otc.CommitState | None = None,
    verification: otc.VerificationState | None = None,
    code: otc.ErrorCode | None = None,
) -> otc.OperationResult[otc.RecordUpdateValue]:
    defaults = {
        otc.Outcome.SUCCEEDED: (otc.CommitState.COMMITTED, otc.VerificationState.PASSED),
        otc.Outcome.REJECTED: (otc.CommitState.NOT_STARTED, otc.VerificationState.SKIPPED),
        otc.Outcome.PARTIAL: (otc.CommitState.PARTIAL, otc.VerificationState.FAILED),
        otc.Outcome.UNKNOWN: (otc.CommitState.UNKNOWN, otc.VerificationState.UNAVAILABLE),
    }
    selected_commit, selected_verification = defaults[outcome]
    error = None
    if code is not None:
        error = otc.ErrorInfo(code, f"{outcome.value} mobile update")
    return otc.OperationResult(
        value=value,
        outcome=outcome,
        commit=commit or selected_commit,
        verification=verification or selected_verification,
        receipts=(),
        error=error,
    )


@dataclass
class RecordingUpdater:
    result: otc.OperationResult[otc.RecordUpdateValue]
    calls: list[tuple[otc.TableBinding, otc.RecordUpdateRequest]]

    def update_record(
        self, binding: otc.TableBinding, request: otc.RecordUpdateRequest
    ) -> otc.OperationResult[otc.RecordUpdateValue]:
        self.calls.append((binding, request))
        return self.result


def _table(fake_connector) -> tuple[otc.Table, Any]:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    return client.open("fake://warehouse/orders").require_value(), client


def test_table_update_record_delegates_revisions_and_idempotency_key(fake_connector) -> None:
    table, _client = _table(fake_connector)
    value = otc.RecordUpdateValue("rec_123", "record-2", "table-2", {"status": "Done"})
    updater = RecordingUpdater(_result(otc.Outcome.SUCCEEDED, value=value), [])
    fake_connector.update_record = updater.update_record

    result = table.update_record(
        "rec_123",
        {"status": "Done"},
        expected_table_revision="table-1",
        expected_record_revision="record-1",
        idempotency_key="mobile-edit-1",
    )

    assert result.value == value
    assert len(updater.calls) == 1
    binding, request = updater.calls[0]
    assert binding is table._binding
    assert request == otc.RecordUpdateRequest(
        record_id="rec_123",
        patch={"status": "Done"},
        expected_table_revision="table-1",
        expected_record_revision="record-1",
        idempotency_key="mobile-edit-1",
    )


def test_table_update_record_fails_closed_without_connector_io(fake_connector) -> None:
    table, _client = _table(fake_connector)

    result = table.update_record(
        "rec_123",
        {"status": "Done"},
        expected_table_revision="table-1",
        expected_record_revision="record-1",
        idempotency_key="mobile-edit-1",
    )

    assert result.outcome is otc.Outcome.REJECTED
    assert result.error is not None
    assert result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY
    assert not any(call[0] == "update_record" for call in fake_connector.calls)


@pytest.mark.parametrize(
    ("outcome", "code"),
    [
        (otc.Outcome.REJECTED, otc.ErrorCode.STALE_REVISION),
        (otc.Outcome.PARTIAL, otc.ErrorCode.PARTIAL_EFFECT),
        (otc.Outcome.UNKNOWN, otc.ErrorCode.UNCERTAIN_MUTATION),
    ],
)
def test_table_update_record_passes_through_non_success_states(fake_connector, outcome, code) -> None:
    table, _client = _table(fake_connector)
    updater = RecordingUpdater(_result(outcome, code=code), [])
    fake_connector.update_record = updater.update_record

    result = table.update_record(
        "rec_123",
        {"status": "Done"},
        expected_table_revision="table-1",
        expected_record_revision="record-1",
        idempotency_key="mobile-edit-1",
    )

    assert result.outcome is outcome
    assert result.error is not None
    assert result.error.code is code
