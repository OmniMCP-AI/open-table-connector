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


def test_builtin_spreadsheet_mutation_commits_and_closes_session(tmp_path):
    from open_table_connector.local_files import LocalFilesConnector
    from open_table_connector.sdk import Client, ConnectorRegistry

    uri = (tmp_path / "dispatch.xlsx").as_uri()
    with Client(registry=ConnectorRegistry([LocalFilesConnector()])) as client:
        book = client.workbook.create(uri)
        book.worksheet.create("Report").range("A1").write([["before"]])
        book.write()
        result = execute_operation(
            client,
            OperationRequest(
                "spreadsheet",
                "range.write",
                "1.0",
                TargetSelector(uri, "Report"),
                {"address": "A1", "values": [["after"]]},
            ),
            ExecutionOptions(),
        )
        assert result.commit.value == "committed"
        reopened = client.workbook(uri)
        assert reopened.worksheet("Report").range("A1").read().require_value() == [["after"]]
        reopened.close()


def test_builtin_spreadsheet_dry_run_does_not_publish(tmp_path):
    from open_table_connector.local_files import LocalFilesConnector
    from open_table_connector.sdk import Client, ConnectorRegistry

    uri = (tmp_path / "dispatch-dry.xlsx").as_uri()
    with Client(registry=ConnectorRegistry([LocalFilesConnector()])) as client:
        book = client.workbook.create(uri)
        book.worksheet.create("Report").range("A1").write([["before"]])
        book.write()
        before = (tmp_path / "dispatch-dry.xlsx").read_bytes()
        result = execute_operation(
            client,
            OperationRequest(
                "spreadsheet",
                "range.write",
                "1.0",
                TargetSelector(uri, "Report"),
                {"address": "A1", "values": [["after"]]},
            ),
            ExecutionOptions(dry_run=True),
        )
        assert result.outcome.value == "planned"
        assert (tmp_path / "dispatch-dry.xlsx").read_bytes() == before
