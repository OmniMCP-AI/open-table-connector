"""Concrete Excel connector and request seam."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from open_table_connector.contract import (
    ArrowReadResult,
    ArrowTableReader,
    InspectRequest,
    PolarsReadResult,
    PolarsTableReader,
    ResolveContext,
    ResolvedTable,
    SheetConvention,
    TableInspector,
    TableMode,
    TableReadRequest,
    TableURI,
    URIResolver,
)

from .excel_reader import read_excel_arrow
from .identity import (
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    connector_identity,
)
from .inspection import inspection_from_read
from .manifest import capability_manifest
from .receipts import make_receipt, normalize_parameters
from .resolver import LocalFormat, ResolvedLocalTable, _resolve_explicit_local_path


EXCEL_CONNECTOR_IDENTITY = connector_identity("excel")
EXCEL_CAPABILITY_MANIFEST = capability_manifest(
    connector=EXCEL_CONNECTOR_IDENTITY,
    uri_schemes=("excel",),
)


@dataclass(frozen=True)
class ExcelReadOptions:
    sheet: str | None = None
    header_row: int = 1

    def __post_init__(self) -> None:
        if self.sheet is not None and (not isinstance(self.sheet, str) or not self.sheet.strip()):
            raise ValueError("sheet must be a non-empty string when supplied")
        if not isinstance(self.header_row, int) or isinstance(self.header_row, bool) or self.header_row < 1:
            raise ValueError("header_row must be positive")


@dataclass(frozen=True)
class ExcelTableReadRequest(TableReadRequest):
    options: ExcelReadOptions = field(default_factory=ExcelReadOptions)

    @property
    def resolve_context(self) -> ResolveContext:
        return ResolveContext(resource_limits=self.resource_limits)


class ExcelConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader):
    identity = EXCEL_CONNECTOR_IDENTITY
    manifest = EXCEL_CAPABILITY_MANIFEST

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        path, sheet = _resolve_explicit_local_path(
            uri,
            context,
            scheme="excel",
            expected_format=LocalFormat.EXCEL,
            allow_sheet_fragment=True,
        )
        return ResolvedTable(
            uri=uri,
            mode=TableMode.SHEET,
            resource=ResolvedLocalTable(path=path, format=LocalFormat.EXCEL, sheet=sheet),
        )

    def _resolve_sheet(self, request: ExcelTableReadRequest, resolved: ResolvedLocalTable) -> str | None:
        selected = resolved.sheet or request.options.sheet
        if resolved.sheet and request.options.sheet and resolved.sheet != request.options.sheet:
            raise ValueError("URI sheet and ExcelReadOptions sheet disagree")
        return selected

    def _read_canonical(self, request: ExcelTableReadRequest):
        resolved = self.resolve(request.uri, request.resolve_context)
        sheet = self._resolve_sheet(request, resolved.resource)
        table, selected_sheet, worksheets = read_excel_arrow(
            resolved.resource.path,
            sheet=sheet,
            header_row=request.options.header_row,
            limits=request.resource_limits,
        )
        return table, resolved.resource.path, selected_sheet, worksheets

    def _result(self, request: ExcelTableReadRequest, capability):
        table, path, sheet, _ = self._read_canonical(request)
        receipt = make_receipt(
            table,
            path=path,
            uri=request.uri,
            parameters=normalize_parameters(
                {
                    "sheet": sheet,
                    "header_row": request.options.header_row,
                }
            ),
            capability=capability,
            connector=self.identity,
            coordinate_convention=SheetConvention(
                sheet=sheet,
                header_rows=request.options.header_row,
                first_data_row=request.options.header_row + 1,
            ),
        )
        return table, receipt

    def read_arrow(self, request: ExcelTableReadRequest) -> ArrowReadResult:
        table, receipt = self._result(request, TABLE_READ_ARROW_CAPABILITY)
        return ArrowReadResult(table=table, receipt=receipt)

    def read_polars(self, request: ExcelTableReadRequest) -> PolarsReadResult:
        table, receipt = self._result(request, TABLE_READ_POLARS_CAPABILITY)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=receipt)

    def inspect(self, request: InspectRequest):
        table, _, sheet, worksheets = self._read_canonical(
            ExcelTableReadRequest(request.uri, resource_limits=request.resource_limits)
        )
        return inspection_from_read(
            request,
            table=table,
            sheet=sheet,
            header_row=1,
            worksheets=worksheets,
            mode=TableMode.SHEET,
            formula_text_captured=False,
            formula_calculated=False,
        )


__all__ = ["ExcelConnector", "ExcelReadOptions", "ExcelTableReadRequest"]
