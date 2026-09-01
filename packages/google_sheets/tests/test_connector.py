from __future__ import annotations

from urllib.error import URLError

import polars as pl
import pytest
from open_table_connector.contract import (
    ConnectorError,
    ConnectorErrorCode,
    InspectRequest,
    ResolveContext,
    ResourceLimits,
    TableReadRequest,
    TableURI,
    TableWriteRequest,
)
from open_table_connector.google_sheets import GoogleSheetsConnector
from open_table_connector.google_sheets.connector import (
    GOOGLE_SHEETS_MAX_RESPONSE_BYTES,
    UrllibSheetsTransport,
)


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, dict | None]] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append((method, url, headers, body))
        if method == "GET":
            if "fields=sheets" in url:
                return {"sheets": [{"properties": {"sheetId": 0, "title": "Orders"}}]}
            return {"range": "Orders!A1:B3", "values": [["id", "amount"], ["a", 1], ["b", 2]]}
        return {"updatedRange": "Orders!A1:B2", "updatedRows": 2, "updatedColumns": 2}


def test_google_sheets_transport_redacts_credentials_from_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = "provider-credential-secret"

    def fail_request(*_args, **_kwargs):
        raise RuntimeError(f"provider rejected credential {credential}")

    monkeypatch.setattr(
        "open_table_connector.google_sheets.connector.urlopen",
        fail_request,
    )

    with pytest.raises(ConnectorError) as raised:
        UrllibSheetsTransport().request(
            "GET",
            "https://sheets.googleapis.com/v4/spreadsheets/fixture/values/Orders",
            headers={"Authorization": f"Bearer {credential}"},
        )

    assert raised.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert raised.value.message == "Google Sheets request failed"
    assert raised.value.safe_details == {
        "reason": "unexpected transport exception"
    }
    assert credential not in repr(raised.value.to_wire())


def test_google_sheets_transport_bounds_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size):
            assert size == GOOGLE_SHEETS_MAX_RESPONSE_BYTES + 1
            return b"x" * size

    monkeypatch.setattr("open_table_connector.google_sheets.connector.urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(ConnectorError) as raised:
        UrllibSheetsTransport().request("GET", "https://example.test", headers={})
    assert raised.value.code is ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED


def test_google_sheets_transport_classifies_url_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "open_table_connector.google_sheets.connector.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError(TimeoutError("read timed out"))),
    )

    with pytest.raises(ConnectorError) as raised:
        UrllibSheetsTransport().request("GET", "https://example.test", headers={})

    assert raised.value.code is ConnectorErrorCode.TIMEOUT


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


def test_google_gid_resolves_to_sheet_title() -> None:
    transport = FakeTransport()
    connector = GoogleSheetsConnector(transport=transport, access_token="token")
    connector.read_arrow(TableReadRequest(TableURI("https://docs.google.com/spreadsheets/d/sheet-123/edit#gid=0")))
    assert "Orders" in transport.calls[1][1]
    assert "gid=0" not in transport.calls[1][1]


def test_google_error_policy_rejected_before_provider_io() -> None:
    transport = FakeTransport()
    connector = GoogleSheetsConnector(transport=transport, access_token="token")
    with pytest.raises(ConnectorError) as raised:
        connector.write(TableWriteRequest(TableURI("gsheets://sheet-123/Orders"), pl.DataFrame({"id": [1]}), if_exists="error"))
    assert raised.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert transport.calls == []


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
    assert "valueInputOption=RAW" in url
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
    with pytest.raises(ConnectorError):
        connector.resolve(TableURI("https://example.com/not-sheets"), ResolveContext())
