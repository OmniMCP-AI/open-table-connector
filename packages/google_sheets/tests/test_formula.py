from __future__ import annotations

from copy import deepcopy
from typing import Any

import open_table_connector.formulas as otf
from open_table_connector.contract import ConnectorError, ConnectorErrorCode, TableURI
from open_table_connector.google_sheets.connector import GoogleSheetsConnector
from open_table_connector.google_sheets.formula import GoogleSheetsFormulaExtension


class RecordingTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = [deepcopy(response) for response in responses]
        self.calls: list[dict[str, Any]] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": deepcopy(body),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected provider request")
        return deepcopy(self.responses.pop(0))


def _metadata() -> dict[str, Any]:
    return {
        "sheets": [
            {
                "properties": {
                    "sheetId": 17,
                    "title": "Model",
                    "gridProperties": {"rowCount": 100, "columnCount": 20},
                }
            }
        ]
    }


def _bound_target() -> otf.BoundGridFormulaTarget:
    return otf.BoundGridFormulaTarget(
        "gsheets://book-123/Model",
        otf.WorksheetRef(worksheet_id="17"),
    )


def test_bind_grid_requires_one_exact_worksheet_match_and_binds_metadata() -> None:
    transport = RecordingTransport([_metadata()])
    extension = GoogleSheetsFormulaExtension(
        GoogleSheetsConnector(transport=transport, access_token="configured-token", timeout=9)
    )

    result = extension.bind_grid(
        otf.GridFormulaBindRequest(
                otf.GridFormulaTarget(
                "gsheets://book-123/Model",
                otf.WorksheetRef(name="Model"),
            )
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.target.grid == TableURI("gsheets://book-123/Model")
    assert result.value.target.worksheet == otf.WorksheetRef(worksheet_id="17")
    assert result.value.capabilities.details.dialects == (otf.GOOGLE_SHEETS_A1,)
    assert result.value.capabilities.details.max_cells_per_operation == 10_000
    assert result.value.capabilities.details.max_expression_bytes == 50_000
    assert result.value.capabilities.details.recalculation_scopes == ()
    assert result.value.capabilities.details.calculation_states == (otf.CalculationState.PROVIDER_CURRENT,)
    assert {item.to_reference() for item in result.value.capabilities.capabilities} == {
        "formula.grid.read/1.0",
        "formula.grid.set/1.0",
        "formula.grid.values.read/1.0",
    }
    assert result.value.observed_revision.startswith("sha256:")
    assert transport.calls[0]["method"] == "GET"
    assert transport.calls[0]["url"] == (
        "https://sheets.googleapis.com/v4/spreadsheets/book-123?"
        "fields=sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))"
    )
    assert transport.calls[0]["headers"] == {"Authorization": "Bearer configured-token"}
    assert transport.calls[0]["timeout"] == 9


def test_read_grid_uses_native_formula_value_and_one_bounded_grid_request() -> None:
    transport = RecordingTransport(
        [
            _metadata(),
            {
                "sheets": [
                    {
                        "properties": {"sheetId": 17, "title": "Model"},
                        "data": [
                            {
                                "startRow": 1,
                                "startColumn": 4,
                                "rowData": [
                                    {
                                        "values": [
                                            {
                                                "userEnteredValue": {"formulaValue": "=B2+$C$1"},
                                                "effectiveValue": {"numberValue": 7},
                                                "effectiveFormat": {
                                                    "numberFormat": {"type": "NUMBER", "pattern": "0.00"}
                                                },
                                            },
                                            {
                                                "userEnteredValue": {"stringValue": "=not-a-formula"},
                                                "effectiveValue": {"stringValue": "literal"},
                                            },
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        ]
    )
    extension = GoogleSheetsFormulaExtension(
        GoogleSheetsConnector(transport=transport, access_token="token", timeout=11)
    )
    binding = extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("gsheets://book-123/Model", otf.WorksheetRef(name="Model"))
        )
    ).value
    assert binding is not None

    result = extension.read_grid(otf.GridFormulaReadRequest(binding.target, "E2:F2"))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert result.value.worksheet_id == "17"
    assert result.value.requested_range == "E2:F2"
    assert [(cell.address, cell.expression.text) for cell in result.value.formulas] == [
        ("E2", "=B2+$C$1")
    ]
    assert result.receipts[0].to_wire()["observed_count"] == 1
    assert len(transport.calls) == 2
    assert transport.calls[1]["url"] == (
        "https://sheets.googleapis.com/v4/spreadsheets/book-123?"
        "includeGridData=true&ranges=Model%21E2%3AF2&"
        "fields=sheets(properties(sheetId,title),data(startRow,startColumn,rowData(values(userEnteredValue,effectiveValue,effectiveFormat(numberFormat)))))"
    )


def test_read_grid_enforces_caller_response_limit_before_parsing() -> None:
    oversized = {
        "sheets": [{
            "properties": {"sheetId": 17, "title": "Model"},
            "padding": "x" * 200,
        }]
    }
    transport = RecordingTransport([_metadata(), oversized])
    extension = GoogleSheetsFormulaExtension(
        GoogleSheetsConnector(transport=transport, access_token="token")
    )
    binding = extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("gsheets://book-123/Model", otf.WorksheetRef(name="Model"))
        )
    ).value
    assert binding is not None

    result = extension.read_grid(
        otf.GridFormulaReadRequest(
            binding.target,
            "A1",
            limits=otf.FormulaResourceLimits(max_response_bytes=100),
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.RESOURCE_LIMIT
    assert [call["method"] for call in transport.calls] == ["GET", "GET"]


def test_bind_grid_rejects_worksheet_id_that_disagrees_with_uri_name() -> None:
    transport = RecordingTransport([_metadata()])
    extension = GoogleSheetsFormulaExtension(
        GoogleSheetsConnector(transport=transport, access_token="token")
    )

    result = extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("gsheets://book-123/Other", otf.WorksheetRef(worksheet_id="17"))
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.TARGET_NOT_FOUND


def test_read_grid_quotes_and_escapes_worksheet_title_in_a1_range() -> None:
    title = "O'Brien Sheet"
    grid = {
        "sheets": [{
            "properties": {"sheetId": 17, "title": title},
            "data": [],
        }]
    }
    transport = RecordingTransport([
        {
            "sheets": [{
                "properties": {
                    "sheetId": 17,
                    "title": title,
                    "gridProperties": {"rowCount": 100, "columnCount": 20},
                }
            }]
        },
        grid,
    ])
    extension = GoogleSheetsFormulaExtension(
        GoogleSheetsConnector(transport=transport, access_token="token")
    )
    binding = extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget(
                "gsheets://book-123/O%27Brien%20Sheet",
                otf.WorksheetRef(name=title),
            )
        )
    ).value
    assert binding is not None

    result = extension.read_grid(otf.GridFormulaReadRequest(binding.target, "A1"))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert "%27O%27%27Brien%20Sheet%27%21A1" in transport.calls[1]["url"]


def test_formula_range_limit_is_rejected_before_grid_data_io() -> None:
    transport = RecordingTransport([_metadata()])
    extension = GoogleSheetsFormulaExtension(
        GoogleSheetsConnector(transport=transport, access_token="token")
    )
    binding = extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("gsheets://book-123/Model", otf.WorksheetRef(name="Model"))
        )
    ).value
    assert binding is not None

    result = extension.read_grid(
        otf.GridFormulaReadRequest(
            binding.target,
            "A1:B1",
            limits=otf.FormulaResourceLimits(max_cells=1),
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.RESOURCE_LIMIT
    assert len(transport.calls) == 1


def test_bind_grid_rejects_ambiguous_worksheet_without_binding() -> None:
    transport = RecordingTransport(
        [
            {
                "sheets": [
                    {"properties": {"sheetId": 17, "title": "Model"}},
                    {"properties": {"sheetId": 18, "title": "Model"}},
                ]
            }
        ]
    )
    extension = GoogleSheetsFormulaExtension(
        GoogleSheetsConnector(transport=transport, access_token="token")
    )

    result = extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("gsheets://book-123/Model", otf.WorksheetRef(name="Model"))
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.TARGET_NOT_FOUND


def _grid_response(formulas: dict[str, str]) -> dict[str, Any]:
    if len(formulas) == 1:
        address, formula = next(iter(formulas.items()))
        match = __import__("re").fullmatch(r"([A-Z]+)([0-9]+)", address)
        assert match is not None
        column = 0
        for character in match.group(1):
            column = column * 26 + ord(character) - ord("A") + 1
        return {
            "sheets": [{
                "properties": {"sheetId": 17, "title": "Model"},
                "data": [{
                    "startRow": int(match.group(2)) - 1,
                    "startColumn": column - 1,
                    "rowData": [{"values": [{"userEnteredValue": {"formulaValue": formula}}]}],
                }],
            }]
        }
    cells = []
    for address in ("E2", "F2", "E3", "F3"):
        cells.append({"userEnteredValue": {"formulaValue": formulas[address]}})
    return {
        "sheets": [
            {
                "properties": {"sheetId": 17, "title": "Model"},
                "data": [{
                    "startRow": 1,
                    "startColumn": 4,
                    "rowData": [{"values": cells[:2]}, {"values": cells[2:]}],
                }],
            }
        ]
    }


def _empty_grid_response() -> dict[str, Any]:
    return {"sheets": [{"properties": {"sheetId": 17, "title": "Model"}}]}


def _extension(transport: RecordingTransport) -> GoogleSheetsFormulaExtension:
    extension = GoogleSheetsFormulaExtension(
        GoogleSheetsConnector(transport=transport, access_token="token", timeout=13)
    )
    binding = extension.bind_grid(
        otf.GridFormulaBindRequest(
            otf.GridFormulaTarget("gsheets://book-123/Model", otf.WorksheetRef(name="Model"))
        )
    )
    assert binding.value is not None
    return extension


def test_set_grid_uses_repeat_cell_and_independent_formula_text_readback() -> None:
    expected = {
        "E2": "=B2+$C$1",
        "F2": "=C2+$C$1",
        "E3": "=B3+$C$1",
        "F3": "=C3+$C$1",
    }
    transport = RecordingTransport([_metadata(), _empty_grid_response(), _grid_response(expected), _grid_response(expected)])
    extension = _extension(transport)
    target = _bound_target()

    result = extension.set_grid(
        otf.GridFormulaSetRequest(
            target,
            "E2:F3",
            otf.FormulaExpression("=B2+$C$1", otf.GOOGLE_SHEETS_A1),
            idempotency_key="set-1",
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.commit is otf.FormulaCommitState.COMMITTED
    assert result.verification is otf.FormulaVerificationState.PASSED
    assert result.value is not None
    assert result.value.affected_count == 4
    assert result.receipts[0].to_wire()["verification"] == "formula_text_readback"
    post = transport.calls[2]
    assert post["method"] == "POST"
    assert post["url"] == "https://sheets.googleapis.com/v4/spreadsheets/book-123:batchUpdate"
    assert post["body"] == {
        "requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": 17,
                    "startRowIndex": 1,
                    "endRowIndex": 3,
                    "startColumnIndex": 4,
                    "endColumnIndex": 6,
                },
                "cell": {"userEnteredValue": {"formulaValue": "=B2+$C$1"}},
                "fields": "userEnteredValue.formulaValue",
            }
        }],
        "includeSpreadsheetInResponse": True,
        "responseRanges": ["Model!E2:F3"],
        "responseIncludeGridData": True,
    }
    assert [call["method"] for call in transport.calls] == ["GET", "GET", "POST", "GET"]


def test_read_grid_values_normalizes_native_branches_and_provider_errors() -> None:
    transport = RecordingTransport([
        _metadata(),
        {
            "sheets": [{
                "properties": {"sheetId": 17, "title": "Model"},
                "data": [{
                    "startRow": 0,
                    "startColumn": 0,
                    "rowData": [{"values": [
                        {"effectiveValue": {"numberValue": 45100.5}, "effectiveFormat": {"numberFormat": {"type": "DATE_TIME", "pattern": "yyyy-mm-dd hh:mm"}}},
                        {"effectiveValue": {"stringValue": "ready"}},
                        {"effectiveValue": {"boolValue": True}},
                        {"effectiveValue": {"errorValue": {"type": "DIVIDE_BY_ZERO", "message": "do not retain"}}},
                    ]}],
                }],
            }]
        },
    ])
    extension = _extension(transport)

    result = extension.read_grid_values(otf.GridFormulaValueReadRequest(_bound_target(), "A1:D1"))

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert result.value is not None
    assert [(cell.address, cell.value.kind) for cell in result.value.values] == [
        ("A1", "logical"), ("B1", "string"), ("C1", "boolean"), ("D1", "provider_error")
    ]
    assert result.value.values[0].value.logical_type == "DATE_TIME:yyyy-mm-dd hh:mm"
    assert result.value.values[3].value.to_python() == {"provider_error": {"code": "DIVIDE_BY_ZERO"}}
    assert result.value.calculation_state is otf.CalculationState.PROVIDER_CURRENT
    assert result.value.calculation_trigger is otf.CalculationTrigger.PROVIDER_READ
    assert result.value.dependency_scope == "provider_dynamic"


def test_set_grid_reconciles_a_lost_acknowledgement_without_retrying_post() -> None:
    class LostAckTransport(RecordingTransport):
        def request(self, method, url, *, headers, body=None, timeout=None):
            if method == "POST":
                self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": deepcopy(body), "timeout": timeout})
                raise ConnectorError(ConnectorErrorCode.TIMEOUT, "request timed out", {})
            return super().request(method, url, headers=headers, body=body, timeout=timeout)

    expected = {"E2": "=B2+$C$1", "F2": "=C2+$C$1", "E3": "=B3+$C$1", "F3": "=C3+$C$1"}
    transport = LostAckTransport([_metadata(), _empty_grid_response(), _grid_response(expected)])
    extension = _extension(transport)

    result = extension.set_grid(
        otf.GridFormulaSetRequest(
            _bound_target(), "E2:F3", otf.FormulaExpression("=B2+$C$1", otf.GOOGLE_SHEETS_A1), idempotency_key="lost-1"
        )
    )

    assert result.outcome is otf.FormulaOutcome.SUCCEEDED
    assert [call["method"] for call in transport.calls] == ["GET", "GET", "POST", "GET"]


def test_set_grid_timeout_before_dispatch_is_rejected_and_does_not_reconcile() -> None:
    class BeforeDispatchTransport(RecordingTransport):
        def request(self, method, url, *, headers, body=None, timeout=None):
            if method == "POST":
                self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": deepcopy(body), "timeout": timeout})
                raise ConnectorError(ConnectorErrorCode.TIMEOUT, "request timed out", {"before_dispatch": True})
            return super().request(method, url, headers=headers, body=body, timeout=timeout)

    transport = BeforeDispatchTransport([_metadata(), _empty_grid_response()])
    extension = _extension(transport)

    result = extension.set_grid(
        otf.GridFormulaSetRequest(
            _bound_target(), "E2", otf.FormulaExpression("=1", otf.GOOGLE_SHEETS_A1), idempotency_key="timeout-1"
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.TIMEOUT
    assert [call["method"] for call in transport.calls] == ["GET", "GET", "POST"]


def test_set_grid_reuses_idempotency_key_after_timeout_before_dispatch() -> None:
    expected = {"E2": "=B2+$C$1", "F2": "=C2+$C$1", "E3": "=B3+$C$1", "F3": "=C3+$C$1"}

    class RetriableTransport(RecordingTransport):
        def __init__(self, responses):
            super().__init__(responses)
            self.post_attempts = 0

        def request(self, method, url, *, headers, body=None, timeout=None):
            if method == "POST":
                self.post_attempts += 1
                if self.post_attempts == 1:
                    self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": deepcopy(body), "timeout": timeout})
                    raise ConnectorError(ConnectorErrorCode.TIMEOUT, "request timed out", {"before_dispatch": True})
            return super().request(method, url, headers=headers, body=body, timeout=timeout)

    transport = RetriableTransport([_metadata(), _empty_grid_response(), _empty_grid_response(), _grid_response(expected), _grid_response(expected)])
    extension = _extension(transport)
    request = otf.GridFormulaSetRequest(
        _bound_target(), "E2:F3", otf.FormulaExpression("=B2+$C$1", otf.GOOGLE_SHEETS_A1), idempotency_key="retry-1"
    )

    first = extension.set_grid(request)
    second = extension.set_grid(request)

    assert first.outcome is otf.FormulaOutcome.REJECTED
    assert second.outcome is otf.FormulaOutcome.SUCCEEDED
    assert transport.post_attempts == 2


def test_set_grid_protocol_failure_after_post_protects_idempotency_key() -> None:
    transport = RecordingTransport([_metadata(), _empty_grid_response(), {"updatedSpreadsheet": []}, _empty_grid_response()])
    extension = _extension(transport)
    request = otf.GridFormulaSetRequest(
        _bound_target(), "E2", otf.FormulaExpression("=1", otf.GOOGLE_SHEETS_A1), idempotency_key="protocol-1"
    )

    first = extension.set_grid(request)
    second = extension.set_grid(request)

    assert first.outcome is otf.FormulaOutcome.FAILED
    assert first.error is not None
    assert first.error.code is otf.FormulaErrorCode.PROTOCOL_FAILURE
    assert second.outcome is otf.FormulaOutcome.UNKNOWN
    assert second.error is not None
    assert second.error.code is otf.FormulaErrorCode.UNCERTAIN_MUTATION
    assert [call["method"] for call in transport.calls].count("POST") == 1


def test_google_provider_syntax_rejection_is_sanitized() -> None:
    class RejectingTransport(RecordingTransport):
        def request(self, method, url, *, headers, body=None, timeout=None):
            if method == "POST":
                self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": deepcopy(body), "timeout": timeout})
                raise ConnectorError(
                    ConnectorErrorCode.EXECUTION_FAILED,
                    "provider diagnostic =HYPERLINK(\"https://secret.example\",\"token\")",
                    {"status": 400, "reason": "invalid formula =HYPERLINK(\"https://secret.example\",\"token\")"},
                )
            return super().request(method, url, headers=headers, body=body, timeout=timeout)

    expression = '=HYPERLINK("https://secret.example", "token")'
    transport = RejectingTransport([_metadata(), _empty_grid_response()])
    extension = _extension(transport)

    result = extension.set_grid(
        otf.GridFormulaSetRequest(
            _bound_target(), "E2", otf.FormulaExpression(expression, otf.GOOGLE_SHEETS_A1), idempotency_key="reject-1"
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.INVALID_FORMULA
    assert "HYPERLINK" not in repr(result)
    assert "secret.example" not in repr(result)
    assert [call["method"] for call in transport.calls] == ["GET", "GET", "POST"]


def test_non_formula_provider_400_is_not_classified_as_invalid_formula() -> None:
    class RejectingTransport(RecordingTransport):
        def request(self, method, url, *, headers, body=None, timeout=None):
            if method == "POST":
                self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": deepcopy(body), "timeout": timeout})
                raise ConnectorError(
                    ConnectorErrorCode.EXECUTION_FAILED,
                    "provider diagnostic contains secret formula text",
                    {"status": 400, "reason": "INVALID_ARGUMENT"},
                )
            return super().request(method, url, headers=headers, body=body, timeout=timeout)

    transport = RejectingTransport([_metadata(), _empty_grid_response()])
    extension = _extension(transport)

    result = extension.set_grid(
        otf.GridFormulaSetRequest(
            _bound_target(), "E2", otf.FormulaExpression("=1", otf.GOOGLE_SHEETS_A1), idempotency_key="bad-request-1"
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.EXECUTION_FAILED
    assert result.error.safe_details == {"provider_status_code": 400}
    assert "secret" not in repr(result)


def test_set_grid_rejects_oversized_post_response_before_parsing_or_readback() -> None:
    oversized = {"updatedSpreadsheet": {"sheets": [], "padding": "x" * (8 * 1024 * 1024)}}
    transport = RecordingTransport([_metadata(), _empty_grid_response(), oversized, _empty_grid_response()])
    extension = _extension(transport)
    request = otf.GridFormulaSetRequest(
        _bound_target(), "E2", otf.FormulaExpression("=1", otf.GOOGLE_SHEETS_A1), idempotency_key="post-limit-1"
    )

    first = extension.set_grid(request)
    second = extension.set_grid(request)

    assert first.outcome is otf.FormulaOutcome.REJECTED
    assert first.error is not None
    assert first.error.code is otf.FormulaErrorCode.RESOURCE_LIMIT
    assert second.outcome is otf.FormulaOutcome.UNKNOWN
    assert [call["method"] for call in transport.calls] == ["GET", "GET", "POST", "GET"]


def test_set_grid_enforces_caller_response_limit_on_post_response() -> None:
    oversized = {"updatedSpreadsheet": {"sheets": [], "padding": "x" * 200}}
    transport = RecordingTransport([_metadata(), _empty_grid_response(), oversized])
    extension = _extension(transport)

    result = extension.set_grid(
        otf.GridFormulaSetRequest(
            _bound_target(),
            "E2",
            otf.FormulaExpression("=1", otf.GOOGLE_SHEETS_A1),
            idempotency_key="post-caller-limit-1",
            limits=otf.FormulaResourceLimits(max_response_bytes=100),
        )
    )

    assert result.outcome is otf.FormulaOutcome.REJECTED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.RESOURCE_LIMIT
    assert [call["method"] for call in transport.calls] == ["GET", "GET", "POST"]


def test_grid_response_with_multiple_effective_branches_is_protocol_failure() -> None:
    transport = RecordingTransport([
        _metadata(),
        {
            "sheets": [{
                "properties": {"sheetId": 17, "title": "Model"},
                "data": [{
                    "rowData": [{"values": [{"effectiveValue": {"numberValue": 1, "stringValue": "bad"}}]}]
                }],
            }]
        },
    ])
    extension = _extension(transport)

    result = extension.read_grid_values(otf.GridFormulaValueReadRequest(_bound_target(), "A1"))

    assert result.outcome is otf.FormulaOutcome.FAILED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.PROTOCOL_FAILURE


def test_same_idempotency_key_replays_without_a_second_post() -> None:
    expected = {"E2": "=B2+$C$1", "F2": "=C2+$C$1", "E3": "=B3+$C$1", "F3": "=C3+$C$1"}
    transport = RecordingTransport([
        _metadata(), _empty_grid_response(), _grid_response(expected), _grid_response(expected), _empty_grid_response()
    ])
    extension = _extension(transport)
    request = otf.GridFormulaSetRequest(
        _bound_target(), "E2:F3", otf.FormulaExpression("=B2+$C$1", otf.GOOGLE_SHEETS_A1), idempotency_key="same-1"
    )

    first = extension.set_grid(request)
    second = extension.set_grid(request)

    assert first.outcome is otf.FormulaOutcome.SUCCEEDED
    assert second.outcome is otf.FormulaOutcome.SUCCEEDED
    assert second.commit is otf.FormulaCommitState.COMMITTED
    assert [call["method"] for call in transport.calls].count("POST") == 1


def test_idempotency_key_conflict_and_stale_revision_are_rejected_before_post() -> None:
    transport = RecordingTransport([
        _metadata(), _empty_grid_response(), _empty_grid_response(), _empty_grid_response(),
        _grid_response({"E2": "=1"}),
        _grid_response({"E2": "=1"}),
        _empty_grid_response(),
    ])
    extension = _extension(transport)
    target = _bound_target()
    first_read = extension.read_grid(otf.GridFormulaReadRequest(target, "E2"))
    assert first_read.value is not None

    stale = extension.set_grid(
        otf.GridFormulaSetRequest(
            target, "E2", otf.FormulaExpression("=1", otf.GOOGLE_SHEETS_A1),
            expected_revision="sha256:" + "f" * 64, idempotency_key="conflict-1",
        )
    )
    assert stale.outcome is otf.FormulaOutcome.REJECTED
    assert stale.error is not None
    assert stale.error.code is otf.FormulaErrorCode.STALE_REVISION

    accepted = extension.set_grid(
        otf.GridFormulaSetRequest(
            target, "E2", otf.FormulaExpression("=1", otf.GOOGLE_SHEETS_A1), idempotency_key="conflict-1"
        )
    )
    conflict = extension.set_grid(
        otf.GridFormulaSetRequest(
            target, "E2", otf.FormulaExpression("=2", otf.GOOGLE_SHEETS_A1), idempotency_key="conflict-1"
        )
    )

    assert accepted.outcome is otf.FormulaOutcome.SUCCEEDED
    assert conflict.outcome is otf.FormulaOutcome.REJECTED
    assert conflict.error is not None
    assert conflict.error.code is otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT
    assert [call["method"] for call in transport.calls].count("POST") == 1


def test_partial_provider_response_has_typed_partial_commit_state() -> None:
    partial = {
        "sheets": [{
            "properties": {"sheetId": 17, "title": "Model"},
            "data": [{
                "startRow": 1,
                "startColumn": 4,
                "rowData": [{"values": [{"userEnteredValue": {"formulaValue": "=B2+$C$1"}}]}],
            }],
        }]
    }
    transport = RecordingTransport([_metadata(), _empty_grid_response(), {"updatedSpreadsheet": partial}, _empty_grid_response()])
    extension = _extension(transport)
    request = otf.GridFormulaSetRequest(
        _bound_target(), "E2:F3", otf.FormulaExpression("=B2+$C$1", otf.GOOGLE_SHEETS_A1), idempotency_key="partial-1"
    )

    result = extension.set_grid(request)
    retry = extension.set_grid(request)

    assert result.outcome is otf.FormulaOutcome.PARTIAL
    assert result.commit is otf.FormulaCommitState.PARTIAL
    assert result.verification is otf.FormulaVerificationState.FAILED
    assert result.error is not None
    assert result.error.code is otf.FormulaErrorCode.PARTIAL_EFFECT
    assert retry.outcome is otf.FormulaOutcome.UNKNOWN
    assert retry.error is not None
    assert retry.error.code is otf.FormulaErrorCode.UNCERTAIN_MUTATION
    assert [call["method"] for call in transport.calls].count("POST") == 1


def test_set_grid_readback_mismatch_after_post_protects_idempotency_key() -> None:
    expected = {"E2": "=B2+$C$1", "F2": "=C2+$C$1", "E3": "=B3+$C$1", "F3": "=C3+$C$1"}
    mismatched = {"E2": "=1", "F2": "=2", "E3": "=3", "F3": "=4"}
    transport = RecordingTransport([
        _metadata(),
        _empty_grid_response(),
        _grid_response(expected),
        _grid_response(mismatched),
        _empty_grid_response(),
    ])
    extension = _extension(transport)
    request = otf.GridFormulaSetRequest(
        _bound_target(), "E2:F3", otf.FormulaExpression("=B2+$C$1", otf.GOOGLE_SHEETS_A1), idempotency_key="readback-1"
    )

    first = extension.set_grid(request)
    second = extension.set_grid(request)

    assert first.outcome is otf.FormulaOutcome.FAILED
    assert first.error is not None
    assert first.error.code is otf.FormulaErrorCode.READBACK_MISMATCH
    assert second.outcome is otf.FormulaOutcome.UNKNOWN
    assert second.error is not None
    assert second.error.code is otf.FormulaErrorCode.UNCERTAIN_MUTATION
    assert [call["method"] for call in transport.calls].count("POST") == 1
