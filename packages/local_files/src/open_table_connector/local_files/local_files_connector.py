"""Compatibility facade that delegates local file reads by detected format."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias
from urllib.parse import quote

import polars as pl

from open_table_connector.contract import (
    ArrowReadResult,
    ArrowTableReader,
    InspectRequest,
    PolarsReadResult,
    PolarsTableReader,
    ResolveContext,
    ResolvedTable,
    TableInspection,
    TableInspector,
    TableMode,
    TableReadRequest,
    TableURI,
    URIResolver,
)
from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode

from .csv_connector import CsvConnector, CsvReadOptions, CsvTableReadRequest
from .excel_connector import ExcelConnector, ExcelReadOptions, ExcelTableReadRequest
from .json_reader import read_json_arrow
from .xls_reader import read_xls_arrow
from .identity import (
    CONNECTOR_IDENTITY,
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
)
from .inspection import inspection_from_read
from .manifest import CAPABILITY_MANIFEST
from .markdown_connector import MarkdownConnector, MarkdownReadOptions, MarkdownTableReadRequest
from .receipts import make_receipt, options_identity
from .resolver import LocalFormat, LocalURIResolver, ResolvedLocalTable


@dataclass(frozen=True)
class LocalReadOptions:
    separator: str = ","
    encoding: str = "utf8"
    sheet: str | None = None
    header_row: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.separator, str) or len(self.separator) != 1:
            raise ValueError("separator must be exactly one character")
        if not isinstance(self.encoding, str) or not self.encoding.strip():
            raise ValueError("encoding must be a non-empty string")
        if self.sheet is not None and (not isinstance(self.sheet, str) or not self.sheet.strip()):
            raise ValueError("sheet must be a non-empty string when supplied")
        if not isinstance(self.header_row, int) or isinstance(self.header_row, bool) or self.header_row < 1:
            raise ValueError("header_row must be positive")


@dataclass(frozen=True)
class LocalTableReadRequest(TableReadRequest):
    options: LocalReadOptions = field(default_factory=LocalReadOptions)

    @property
    def resolve_context(self) -> ResolveContext:
        return ResolveContext(resource_limits=self.resource_limits)


ConcreteConnectorRequest: TypeAlias = (
    tuple[CsvConnector, CsvTableReadRequest]
    | tuple[ExcelConnector, ExcelTableReadRequest]
    | tuple[MarkdownConnector, MarkdownTableReadRequest]
)


class LocalFilesConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader):
    identity = CONNECTOR_IDENTITY
    manifest = CAPABILITY_MANIFEST

    def __init__(self, resolver: LocalURIResolver | None = None) -> None:
        self._resolver = resolver or LocalURIResolver()
        self._csv_connector = CsvConnector()
        self._excel_connector = ExcelConnector()
        self._markdown_connector = MarkdownConnector()

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        return self._resolver.resolve(uri, context)

    def _resolve_sheet(self, request: LocalTableReadRequest, resolved: ResolvedLocalTable) -> str | None:
        if resolved.format not in {LocalFormat.EXCEL, LocalFormat.XLS}:
            if resolved.sheet or request.options.sheet:
                raise ConnectorError(
                    ConnectorErrorCode.INVALID_URI,
                    "sheet selection is supported only for Excel files",
                    {"format": resolved.format.value},
                )
            return None

        selected = resolved.sheet or request.options.sheet
        if resolved.sheet and request.options.sheet and resolved.sheet != request.options.sheet:
            raise ValueError("URI sheet and LocalReadOptions sheet disagree")
        return selected

    def _explicit_uri(self, path: Path, scheme: str, *, sheet: str | None = None) -> TableURI:
        value = path.as_uri().replace("file://", f"{scheme}://", 1)
        if sheet is not None:
            value = f"{value}#sheet={quote(sheet, safe='')}"
        return TableURI(value)

    def _build_concrete_request(
        self, request: LocalTableReadRequest, resolved: ResolvedLocalTable
    ) -> ConcreteConnectorRequest:
        if resolved.format is LocalFormat.CSV:
            return (
                self._csv_connector,
                CsvTableReadRequest(
                    self._explicit_uri(resolved.path, "csv"),
                    resource_limits=request.resource_limits,
                    options=CsvReadOptions(
                        separator=request.options.separator,
                        encoding=request.options.encoding,
                    ),
                ),
            )
        if resolved.format is LocalFormat.EXCEL:
            return (
                self._excel_connector,
                ExcelTableReadRequest(
                    self._explicit_uri(resolved.path, "excel", sheet=resolved.sheet),
                    resource_limits=request.resource_limits,
                    options=ExcelReadOptions(
                        sheet=request.options.sheet,
                        header_row=request.options.header_row,
                    ),
                ),
            )
        if resolved.format is LocalFormat.JSON:
            return (
                self._csv_connector,
                CsvTableReadRequest(
                    self._explicit_uri(resolved.path, "csv"),
                    resource_limits=request.resource_limits,
                    options=CsvReadOptions(separator=request.options.separator, encoding=request.options.encoding),
                ),
            )
        return (
            self._markdown_connector,
            MarkdownTableReadRequest(
                self._explicit_uri(resolved.path, "md"),
                resource_limits=request.resource_limits,
                options=MarkdownReadOptions(encoding=request.options.encoding),
            ),
        )

    def _read_canonical(self, request: LocalTableReadRequest):
        resolved = self.resolve(request.uri, request.resolve_context)
        resource = resolved.resource
        sheet = self._resolve_sheet(request, resource)
        if resource.format is LocalFormat.JSON:
            table = read_json_arrow(resource.path, limits=request.resource_limits)
            return table, resource.path, "data", ("data",)
        if resource.format is LocalFormat.XLS:
            table, selected_sheet, worksheets = read_xls_arrow(
                resource.path,
                sheet=sheet,
                header_row=request.options.header_row,
                limits=request.resource_limits,
            )
            return table, resource.path, selected_sheet, worksheets

        connector, concrete_request = self._build_concrete_request(
            request,
            ResolvedLocalTable(path=resource.path, format=resource.format, sheet=sheet),
        )

        if resource.format is LocalFormat.CSV:
            table, path = connector._read_canonical(concrete_request)
            return table, path, "data", ("data",)
        if resource.format is LocalFormat.EXCEL:
            table, path, selected_sheet, worksheets = connector._read_canonical(concrete_request)
            return table, path, selected_sheet, worksheets

        table, path = connector._read_canonical(concrete_request)
        return table, path, "data", ("data",)

    def _result(self, request: LocalTableReadRequest, capability):
        table, path, sheet, _ = self._read_canonical(request)
        receipt = make_receipt(
            table,
            path=path,
            uri=request.uri,
            sheet=sheet,
            header_row=request.options.header_row,
            parameters=options_identity(request.options, sheet=sheet),
            capability=capability,
        )
        return table, receipt

    def read_arrow(self, request: LocalTableReadRequest) -> ArrowReadResult:
        table, receipt = self._result(request, TABLE_READ_ARROW_CAPABILITY)
        return ArrowReadResult(table=table, receipt=receipt)

    def read_polars(self, request: LocalTableReadRequest) -> PolarsReadResult:
        table, receipt = self._result(request, TABLE_READ_POLARS_CAPABILITY)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=receipt)

    def inspect(self, request: InspectRequest | LocalTableReadRequest) -> TableInspection:
        if isinstance(request, LocalTableReadRequest):
            local_request = request
        else:
            local_request = LocalTableReadRequest(request.uri, resource_limits=request.resource_limits)
        table, _, sheet, worksheets = self._read_canonical(local_request)
        return inspection_from_read(
            InspectRequest(local_request.uri, resource_limits=local_request.resource_limits),
            table=table,
            sheet=sheet,
            worksheets=worksheets,
            mode=TableMode.SHEET,
            header_row=local_request.options.header_row,
        )


__all__ = ["LocalFilesConnector", "LocalReadOptions", "LocalTableReadRequest"]
