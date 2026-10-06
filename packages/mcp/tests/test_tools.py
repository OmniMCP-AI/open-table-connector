from __future__ import annotations

from open_table_connector.contract import OperationRequest, TargetSelector


def test_discover_lazy_schema():
    from open_table_connector.mcp.tools import otc_discover

    payload = otc_discover({"namespace": "spreadsheet", "operation_id": "range.read"})
    assert payload["isError"] is False
    assert payload["structuredContent"]["operation_id"] == "range.read"


def test_inspect_refuses_write_effect():
    from open_table_connector.mcp.tools import otc_inspect

    request = OperationRequest("spreadsheet", "range.write", "1.0", TargetSelector("file:///tmp/book.xlsx", "Report"), {"address": "A1", "values": [[1]]})
    result = otc_inspect(request, object(), None)
    assert result["isError"] is True


def test_execute_no_shell_or_arbitrary_module():
    from open_table_connector.mcp.tools import otc_execute

    result = otc_execute({"namespace": "spreadsheet", "operation_id": "unknown", "version": "1.0", "target": None, "arguments": {}}, object(), None)
    assert result["isError"] is True


def test_unknown_and_partial_are_error_with_receipts():
    from open_table_connector.mcp.tools import result_payload
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
    payload = result_payload(result)
    assert payload["isError"] is True
    assert payload["structuredContent"]["receipts"]
