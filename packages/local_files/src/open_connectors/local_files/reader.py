"""Framework-neutral CSV and Excel Connector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import polars as pl

from open_connectors.contract import (
    ArrowReadResult,
    ArrowTableReader,
    InspectRequest,
    PolarsReadResult,
    PolarsTableReader,
    ResourceLimits,
    ResolveContext,
    ResolvedTable,
    TableInspector,
    TableMode,
    TableReadRequest,
    TableURI,
    URIResolver,
)

from .csv_reader import read_csv_arrow
from .excel_reader import read_excel_arrow
from .json_reader import read_json_arrow
from .xls_reader import read_xls_arrow
from .identity import CONNECTOR_IDENTITY, TABLE_READ_ARROW_CAPABILITY, TABLE_READ_POLARS_CAPABILITY
from .inspection import inspection_from_read
from .manifest import CAPABILITY_MANIFEST
from .receipts import make_receipt, options_identity
from .resolver import LocalURIResolver, ResolvedLocalTable


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


class LocalFilesConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader):
    identity = CONNECTOR_IDENTITY
    manifest = CAPABILITY_MANIFEST

    def __init__(self, resolver: LocalURIResolver | None = None) -> None:
        self._resolver = resolver or LocalURIResolver()

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        return self._resolver.resolve(uri, context)

    def _resolve_sheet(self, request: LocalTableReadRequest, resolved: ResolvedLocalTable) -> str | None:
        selected = resolved.sheet or request.options.sheet
        if resolved.sheet and request.options.sheet and resolved.sheet != request.options.sheet:
            raise ValueError("URI sheet and LocalReadOptions sheet disagree")
        return selected

    def _read_canonical(self, request: LocalTableReadRequest):
        resolved = self.resolve(request.uri, request.resolve_context)
        resource = resolved.resource
        sheet = self._resolve_sheet(request, resource)
        if resource.format.value == "csv":
            separator = request.options.separator
            if resource.path.suffix.casefold() == ".tsv" and separator == ",":
                separator = "\t"
            table = read_csv_arrow(
                resource.path,
                separator=separator,
                encoding=request.options.encoding,
                limits=request.resource_limits,
            )
            selected_sheet = sheet or "data"
            worksheets = (selected_sheet,)
        elif resource.format.value == "json":
            table = read_json_arrow(resource.path, limits=request.resource_limits)
            selected_sheet = sheet or "data"
            worksheets = (selected_sheet,)
        elif resource.format.value == "xls":
            table, selected_sheet, worksheets = read_xls_arrow(
                resource.path,
                sheet=sheet,
                header_row=request.options.header_row,
                limits=request.resource_limits,
            )
        else:
            table, selected_sheet, worksheets = read_excel_arrow(
                resource.path,
                sheet=sheet,
                header_row=request.options.header_row,
                limits=request.resource_limits,
            )
        return table, resource.path, selected_sheet, worksheets

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

    def inspect(self, request: InspectRequest):
        local_request = LocalTableReadRequest(request.uri, resource_limits=request.resource_limits)
        table, _, sheet, worksheets = self._read_canonical(local_request)
        return inspection_from_read(
            request,
            table=table,
            sheet=sheet,
            worksheets=worksheets,
            mode=TableMode.SHEET,
        )


__all__ = ["LocalFilesConnector", "LocalReadOptions", "LocalTableReadRequest"]
