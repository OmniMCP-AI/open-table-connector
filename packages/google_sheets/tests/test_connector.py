from __future__ import annotations

import polars as pl
import pytest

from open_connectors.contract import InspectRequest, ResourceLimits, ResolveContext, TableReadRequest, TableURI, TableWriteRequest
from open_connectors.google_sheets import GoogleSheetsConnector, GoogleSheetsReadOptions


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, dict | None]] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append((method, url, headers, body))
        if method == "GET":
            return {"range": "Orders!A1:B3", "values": [["id", "amount"], ["a", 1], ["b", 2]]}
        return {"updatedRange": "Orders!A1:B2", "updatedRows": 2, "updatedColumns": 2}


def test_google_sheets_reads_values_and_builds_receipt() -> None:
    transport = FakeTransport()
    connector = GoogleSheetsConnector(transport=transport, access_token="token")
    request = TableReadRequest(
        TableURI("https://docs.google.com/spreadsheets/d/sheet-123/edit#gid=0"),
    )

    result = connector.read_polars(request)

    assert result.frame.to_dicts() == [{"id": "a", "amount": 1}, {"id": "b", "amount": 2}]
    assert result.receipt.safe_uri == request.uri
    assert result.receipt.mode.value == "sheet"
    assert transport.calls[0][0] == "GET"
    assert "sheet-123" in transport.calls[0][1]
    assert transport.calls[0][2]["Authorization"] == "Bearer token"
    assert transport.calls[0][3] is None
    assert result.receipt.vendor_receipt_ref is None


def test_google_sheets_read_applies_max_rows_to_table_and_receipt() -> None:
    transport = FakeTransport()
    connector = GoogleSheetsConnector(transport=transport, access_token="token")
    request = TableReadRequest(
        TableURI("https://docs.google.com/spreadsheets/d/sheet-123/edit#gid=0"),
        ResourceLimits(max_rows=1),
    )

    result = connector.read_polars(request)

    assert result.frame.to_dicts() == [{"id": "a", "amount": 1}]
    assert result.receipt.row_count == 1


def test_google_sheets_uses_credentials_and_writes_values() -> None:
    transport = FakeTransport()
    connector = GoogleSheetsConnector(transport=transport, access_token="token")
    uri = TableURI("gsheets://sheet-123/Orders")

    result = connector.write(
        TableWriteRequest(uri, pl.DataFrame({"id": ["a"], "amount": [3]}), if_exists="replace", table="Orders!A1")
    )

    assert result.affected_rows == 1
    method, url, headers, body = transport.calls[0]
    assert method == "PUT"
    assert "Orders%21A1" in url
    assert headers["Authorization"] == "Bearer token"
    assert body == {"range": "Orders!A1", "majorDimension": "ROWS", "values": [["id", "amount"], ["a", 3]]}
    assert result.receipt.vendor_receipt_ref is None


def test_google_sheets_inspection_reports_sheet_convention() -> None:
    connector = GoogleSheetsConnector(transport=FakeTransport(), access_token="token")
    inspection = connector.inspect(InspectRequest(TableURI("gsheets://sheet-123/Orders")))

    assert inspection.columns == ("id", "amount")
    assert inspection.row_count == 2
    assert inspection.coordinate_convention.sheet == "Orders"


def test_google_sheets_rejects_invalid_uri() -> None:
    connector = GoogleSheetsConnector(transport=FakeTransport(), access_token="token")
    with pytest.raises(Exception):
        connector.resolve(TableURI("https://example.com/not-sheets"), ResolveContext())
