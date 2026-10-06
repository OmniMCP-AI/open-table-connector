from __future__ import annotations

from open_table_connector.contract import ExecutionOptions, OperationRequest, TargetSelector
from open_table_connector.sdk.discovery import OperationCatalog
from open_table_connector.sdk.operations import execute_operation, register_operation_handler
from open_table_connector.sdk.result import Outcome


def test_schema_examples_match_dispatch_validation() -> None:
    request = OperationRequest(
        "spreadsheet", "range.read", "1.0", TargetSelector("file:///tmp/book.xlsx", "Sheet1"), {"address": "A1"}
    )
    called: list[str] = []

    def handler(_client, _request, _options):
        called.append("handler")
        return "ok"

    register_operation_handler("spreadsheet", "range.read", "1.0", handler)
    result = execute_operation(object(), request, ExecutionOptions(), catalog=OperationCatalog.default())
    assert result.outcome is Outcome.SUCCEEDED
    assert called == ["handler"]


def test_unknown_operation_never_imports_arbitrary_module() -> None:
    request = OperationRequest("spreadsheet", "unknown.module", "1.0", None, {})
    result = execute_operation(object(), request, ExecutionOptions(), catalog=OperationCatalog.default())
    assert result.outcome is Outcome.REJECTED
    assert result.error is not None
    assert result.error.code.value in {"invalid_descriptor", "unsupported_capability"}
