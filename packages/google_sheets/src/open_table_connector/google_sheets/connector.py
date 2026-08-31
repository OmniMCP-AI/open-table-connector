from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping, Protocol
from urllib.parse import quote, unquote, urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import polars as pl
import pyarrow as pa

from open_table_connector.contract import (
    ArrowReadResult, ArrowTableReader, CapabilityIdentity, CapabilityManifest, ConnectorError,
    ConnectorErrorCode, ConnectorIdentity, InspectRequest, PolarsReadResult, PolarsTableReader,
    ResolveContext, ResolvedTable, SheetConvention, TableInspection, TableInspector, TableMode,
    TableReadRequest, TableURI, TableWriteRequest, TableWriteResult, TableWriter, URIResolver,
)
from open_table_connector.contract.fingerprints import arrow_content_fingerprint, arrow_schema_fingerprint, operation_identity

CONNECTOR_IDENTITY = ConnectorIdentity("google_sheets", "0.1.0", "1.0")
URI_RESOLVER_CAPABILITY = CapabilityIdentity("uri.resolve", "1.0")
TABLE_INSPECT_CAPABILITY = CapabilityIdentity("table.inspect", "1.0")
TABLE_READ_ARROW_CAPABILITY = CapabilityIdentity("table.read.arrow", "1.0")
TABLE_READ_POLARS_CAPABILITY = CapabilityIdentity("table.read.polars", "1.0")
TABLE_WRITE_CAPABILITY = CapabilityIdentity("table.write", "1.0")
GOOGLE_SHEETS_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
CAPABILITY_MANIFEST = CapabilityManifest(CONNECTOR_IDENTITY, (URI_RESOLVER_CAPABILITY, TABLE_INSPECT_CAPABILITY, TABLE_READ_ARROW_CAPABILITY, TABLE_READ_POLARS_CAPABILITY, TABLE_WRITE_CAPABILITY), (TableMode.SHEET,), ("gsheets", "https"))


class SheetsTransport(Protocol):
    def request(self, method: str, url: str, *, headers: Mapping[str, str], body: Mapping[str, Any] | None = None, timeout: int | None = None) -> Mapping[str, Any]: ...


class UrllibSheetsTransport:
    def request(self, method, url, *, headers, body=None, timeout=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read(GOOGLE_SHEETS_MAX_RESPONSE_BYTES + 1)
                if len(payload) > GOOGLE_SHEETS_MAX_RESPONSE_BYTES:
                    raise ConnectorError(
                        ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED,
                        "Google Sheets response exceeded the configured byte limit",
                        {"max_bytes": GOOGLE_SHEETS_MAX_RESPONSE_BYTES},
                    )
                return json.loads(payload)
        except HTTPError as exc:
            code = (
                ConnectorErrorCode.AUTHENTICATION
                if exc.code in {401, 403}
                else ConnectorErrorCode.EXECUTION_FAILED
            )
            raise ConnectorError(code, "Google Sheets request failed", {"status": exc.code}) from None
        except TimeoutError:
            raise ConnectorError(ConnectorErrorCode.TIMEOUT, "Google Sheets request timed out", {}) from None
        except ConnectorError:
            raise
        except Exception:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "Google Sheets request failed", {"reason": "unexpected transport exception"}) from None


@dataclass(frozen=True)
class GoogleSheetsReadOptions:
    range: str | None = None
    sheet: str | None = None
    header_row: int = 1

    def __post_init__(self):
        if self.range is not None and not self.range.strip():
            raise ValueError("range must be non-empty when supplied")
        if self.sheet is not None and not self.sheet.strip():
            raise ValueError("sheet must be non-empty when supplied")
        if not isinstance(self.header_row, int) or isinstance(self.header_row, bool) or self.header_row < 1:
            raise ValueError("header_row must be positive")


@dataclass(frozen=True)
class GoogleSheetsTableReadRequest(TableReadRequest):
    options: GoogleSheetsReadOptions = field(default_factory=GoogleSheetsReadOptions)


@dataclass(frozen=True)
class ResolvedGoogleSheet:
    spreadsheet_id: str
    sheet: str


def _arrow_from_values(values: list[list[Any]], header_row: int) -> pa.Table:
    if len(values) < header_row:
        return pa.table({})
    names: list[str] = []
    for index, value in enumerate(values[header_row - 1]):
        name = str(value).strip() or f"column_{index + 1}"
        if name in names:
            name = f"{name}_{index + 1}"
        names.append(name)
    rows = values[header_row:]
    columns = {}
    for index, name in enumerate(names):
        column = [row[index] if index < len(row) else None for row in rows]
        try:
            columns[name] = pa.array(column)
        except (pa.ArrowInvalid, pa.ArrowTypeError):
            columns[name] = pa.array([None if item is None else str(item) for item in column], type=pa.string())
    return pa.table(columns)


class GoogleSheetsConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader, TableWriter):
    identity = CONNECTOR_IDENTITY
    manifest = CAPABILITY_MANIFEST

    def __init__(self, transport: SheetsTransport | None = None, *, access_token: str | None = None, timeout: int = 30):
        self._transport = transport or UrllibSheetsTransport()
        self._access_token = access_token
        self._timeout = timeout

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        parsed = urlsplit(uri.value)
        if uri.scheme == "gsheets":
            spreadsheet_id = parsed.netloc
            sheet = unquote(parsed.path.lstrip("/"))
        elif uri.scheme == "https" and parsed.hostname == "docs.google.com":
            parts = parsed.path.split("/")
            try:
                spreadsheet_id = parts[parts.index("d") + 1]
            except (ValueError, IndexError):
                raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Google Sheets URI requires a spreadsheet ID", {}) from None
            if parsed.fragment.startswith("gid="):
                raw_gid = unquote(parsed.fragment.removeprefix("gid="))
                if not raw_gid.isdigit():
                    raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Google Sheets gid must be a non-negative integer", {})
                sheet = self._sheet_title(spreadsheet_id, int(raw_gid))
            else:
                sheet = "Sheet1"
        else:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Google Sheets Connector requires a gsheets URI or Google Sheets URL", {"scheme": uri.scheme})
        if not spreadsheet_id or not sheet:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Google Sheets URI requires a spreadsheet and sheet", {})
        return ResolvedTable(uri, TableMode.SHEET, ResolvedGoogleSheet(spreadsheet_id, sheet))

    def _sheet_title(self, spreadsheet_id: str, gid: int) -> str:
        if isinstance(gid, bool) or not isinstance(gid, int) or gid < 0:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Google Sheets gid must be a non-negative integer", {})
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}"
            "?fields=sheets(properties(sheetId,title))"
        )
        payload = self._transport.request("GET", url, headers=self._headers(), timeout=self._timeout)
        matches = [
            item.get("properties", {})
            for item in payload.get("sheets", [])
            if item.get("properties", {}).get("sheetId") == gid
        ]
        if len(matches) != 1 or not matches[0].get("title"):
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "Google Sheets gid does not identify exactly one sheet", {})
        return str(matches[0]["title"])

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            raise ConnectorError.authentication("Google Sheets access token is not configured")
        return {"Authorization": f"Bearer {self._access_token}"}

    def _read(self, request: GoogleSheetsTableReadRequest):
        resource = self.resolve(request.uri, ResolveContext(resource_limits=request.resource_limits)).resource
        options = request.options
        selected_sheet = options.sheet or resource.sheet
        value_range = options.range or selected_sheet
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(resource.spreadsheet_id, safe='')}/values/{quote(value_range, safe='')}?majorDimension=ROWS"
        payload = self._transport.request("GET", url, headers=self._headers(), timeout=request.resource_limits.timeout_seconds or self._timeout)
        table = _arrow_from_values(list(payload.get("values", [])), options.header_row)
        if request.resource_limits.max_rows is not None:
            table = table.slice(0, request.resource_limits.max_rows)
        revision = "sha256:" + sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        return table, revision, selected_sheet

    def _receipt(self, request, table, revision, sheet, capability):
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=TABLE_READ_ARROW_CAPABILITY, uri=request.uri, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, parameters={"sheet": sheet, "range": request.options.range, "header_row": request.options.header_row})
        from open_table_connector.contract import NeutralReceipt
        return NeutralReceipt(CONNECTOR_IDENTITY, capability, operation, request.uri, TableMode.SHEET, revision, schema, content, SheetConvention(sheet, request.options.header_row, request.options.header_row + 1), table.num_rows, 1)

    def read_arrow(self, request):
        request = request if isinstance(request, GoogleSheetsTableReadRequest) else GoogleSheetsTableReadRequest(request.uri, request.resource_limits)
        table, revision, sheet = self._read(request)
        return ArrowReadResult(table, self._receipt(request, table, revision, sheet, TABLE_READ_ARROW_CAPABILITY))

    def read_polars(self, request):
        result = self.read_arrow(request)
        return PolarsReadResult(pl.from_arrow(result.table), result.receipt)

    def inspect(self, request: InspectRequest):
        result = self.read_arrow(request)
        return TableInspection(request.uri, TableMode.SHEET, tuple(result.table.column_names), result.receipt.schema_fingerprint, result.table.num_rows, result.receipt.coordinate_convention, {"provider": "google_sheets"})

    def write(self, request: TableWriteRequest) -> TableWriteResult:
        if request.if_exists == "error":
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "Google Sheets cannot enforce create-if-empty atomically",
                {"if_exists": request.if_exists},
            )
        if request.if_exists not in {"error", "append", "replace"}:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "if_exists must be error, append, or replace", {})
        resource = self.resolve(request.uri, ResolveContext()).resource
        value_range = request.table or resource.sheet
        values = [list(request.frame.columns), *[list(row) for row in request.frame.rows()]]
        body = {"range": value_range, "majorDimension": "ROWS", "values": values}
        method = "POST" if request.if_exists == "append" else "PUT"
        suffix = ":append" if method == "POST" else ""
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{quote(resource.spreadsheet_id, safe='')}/values/{quote(value_range, safe='')}{suffix}?valueInputOption=RAW&includeValuesInResponse=true"
        payload = self._transport.request(method, url, headers=self._headers(), body=body, timeout=self._timeout)
        revision = "sha256:" + sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        table = pa.Table.from_pydict({name: request.frame.get_column(name).to_list() for name in request.frame.columns})
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=TABLE_WRITE_CAPABILITY, uri=request.uri, source_revision=revision, schema_fingerprint=schema, content_fingerprint=content, parameters={"range": value_range, "if_exists": request.if_exists})
        from open_table_connector.contract import NeutralReceipt
        receipt = NeutralReceipt(CONNECTOR_IDENTITY, TABLE_WRITE_CAPABILITY, operation, request.uri, TableMode.SHEET, revision, schema, content, SheetConvention(resource.sheet), table.num_rows, 1)
        return TableWriteResult(receipt, request.frame.height)
