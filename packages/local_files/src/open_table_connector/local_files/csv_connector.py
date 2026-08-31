"""Concrete CSV connector and request seam."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from open_table_connector.contract import (
    ArrowReadResult,
    ArrowTableReader,
    PROVIDER_CSV,
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

from .csv_reader import read_csv_arrow
from .identity import (
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    connector_identity,
)
from .inspection import inspection_from_read
from .manifest import capability_manifest
from .receipts import make_receipt, normalize_parameters
from .resolver import LocalFormat, ResolvedLocalTable, _resolve_explicit_local_path


CSV_CONNECTOR_IDENTITY = connector_identity(PROVIDER_CSV)
CSV_CAPABILITY_MANIFEST = capability_manifest(
    connector=CSV_CONNECTOR_IDENTITY, uri_schemes=(PROVIDER_CSV,)
)
CSV_COORDINATE_CONVENTION = SheetConvention(sheet="data", header_rows=1, first_data_row=2)


@dataclass(frozen=True)
class CsvReadOptions:
    separator: str = ","
    encoding: str = "utf8"

    def __post_init__(self) -> None:
        if not isinstance(self.separator, str) or len(self.separator) != 1:
            raise ValueError("separator must be exactly one character")
        if not isinstance(self.encoding, str) or not self.encoding.strip():
            raise ValueError("encoding must be a non-empty string")


@dataclass(frozen=True)
class CsvTableReadRequest(TableReadRequest):
    options: CsvReadOptions = field(default_factory=CsvReadOptions)

    @property
    def resolve_context(self) -> ResolveContext:
        return ResolveContext(resource_limits=self.resource_limits)


class CsvConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader):
    identity = CSV_CONNECTOR_IDENTITY
    manifest = CSV_CAPABILITY_MANIFEST

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        path, _ = _resolve_explicit_local_path(
            uri,
            context,
            scheme=PROVIDER_CSV,
            expected_format=LocalFormat.CSV,
        )
        return ResolvedTable(
            uri=uri,
            mode=TableMode.SHEET,
            resource=ResolvedLocalTable(path=path, format=LocalFormat.CSV),
        )

    def _read_canonical(self, request: CsvTableReadRequest):
        resolved = self.resolve(request.uri, request.resolve_context)
        table = read_csv_arrow(
            resolved.resource.path,
            separator=request.options.separator,
            encoding=request.options.encoding,
            limits=request.resource_limits,
        )
        return table, resolved.resource.path

    def _result(self, request: CsvTableReadRequest, capability):
        table, path = self._read_canonical(request)
        receipt = make_receipt(
            table,
            path=path,
            uri=request.uri,
            parameters=normalize_parameters(
                {
                    "separator": request.options.separator,
                    "encoding": request.options.encoding,
                }
            ),
            capability=capability,
            connector=self.identity,
            coordinate_convention=CSV_COORDINATE_CONVENTION,
        )
        return table, receipt

    def read_arrow(self, request: CsvTableReadRequest) -> ArrowReadResult:
        table, receipt = self._result(request, TABLE_READ_ARROW_CAPABILITY)
        return ArrowReadResult(table=table, receipt=receipt)

    def read_polars(self, request: CsvTableReadRequest) -> PolarsReadResult:
        table, receipt = self._result(request, TABLE_READ_POLARS_CAPABILITY)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=receipt)

    def inspect(self, request: InspectRequest):
        table, _ = self._read_canonical(
            CsvTableReadRequest(request.uri, resource_limits=request.resource_limits)
        )
        return inspection_from_read(
            request,
            table=table,
            sheet="data",
            header_row=1,
            worksheets=("data",),
            mode=TableMode.SHEET,
        )


__all__ = ["CsvConnector", "CsvReadOptions", "CsvTableReadRequest"]
