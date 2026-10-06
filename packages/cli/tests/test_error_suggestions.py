from __future__ import annotations

import io
import json

from open_table_connector.cli.discovery_commands import suggest_argument
from open_table_connector.cli.output import emit_error
from open_table_connector.contract import ConnectorError, ConnectorErrorCode, OperationDescriptor


def _descriptor():
    return OperationDescriptor(
        schema="otc.operation/1.0",
        operation_id="range.style",
        version="1.0",
        target_kind="range",
        arguments_schema={"type": "object", "properties": {"bold": {"type": "boolean"}, "token": {"type": "string"}}, "additionalProperties": False},
        capability="spreadsheet.range.style/1.0",
        effects=("buffered_write",),
    )


def test_suggestion_does_not_dispatch_or_correct():
    assert suggest_argument("blod", _descriptor()) == ("bold",)


def test_suggestion_redacts_secret_value():
    assert "secret" not in str(suggest_argument("token=secret", _descriptor()))


def test_spreadsheet_otc_error_remains_exit_five():
    error = ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "provider failed", {})
    err = io.StringIO()
    assert emit_error(error, err) == 5
    assert json.loads(err.getvalue())["code"] == "execution_failed"


def test_partial_result_keeps_receipts():
    from open_table_connector.sdk.result import (
        CommitState,
        ErrorCode,
        ErrorInfo,
        OperationResult,
        Outcome,
        Receipt,
        VerificationState,
    )

    result = OperationResult(None, Outcome.PARTIAL, CommitState.PARTIAL, VerificationState.FAILED, (Receipt("spreadsheet", "range.write"),), error=ErrorInfo(ErrorCode.PARTIAL_EFFECT, "partial"))
    assert result.to_wire()["receipts"]
