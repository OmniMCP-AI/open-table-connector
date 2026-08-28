"""Concrete Markdown connector and request seam."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl
from open_table_connector.contract import (
    ArrowReadResult,
    ArrowTableReader,
    ConnectorError,
    ConnectorErrorCode,
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

from .identity import (
    TABLE_READ_ARROW_CAPABILITY,
    TABLE_READ_POLARS_CAPABILITY,
    connector_identity,
)
from .inspection import inspection_from_read
from .manifest import capability_manifest
from .markdown_reader import read_markdown_arrow
from .receipts import make_receipt, normalize_parameters
from .resolver import LocalFormat, ResolvedLocalTable, _resolve_explicit_local_path


MARKDOWN_CONNECTOR_IDENTITY = connector_identity("md")
MARKDOWN_CAPABILITY_MANIFEST = capability_manifest(
    connector=MARKDOWN_CONNECTOR_IDENTITY,
    uri_schemes=("md",),
)
MARKDOWN_COORDINATE_CONVENTION = SheetConvention(sheet="data", header_rows=1, first_data_row=2)


@dataclass(frozen=True)
class MarkdownReadOptions:
    encoding: str = "utf8"

    def __post_init__(self) -> None:
        if not isinstance(self.encoding, str) or not self.encoding.strip():
            raise ValueError("encoding must be a non-empty string")


@dataclass(frozen=True)
class MarkdownTableReadRequest(TableReadRequest):
    options: MarkdownReadOptions = field(default_factory=MarkdownReadOptions)

    @property
    def resolve_context(self) -> ResolveContext:
        return ResolveContext(resource_limits=self.resource_limits)


class MarkdownConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader):
    identity = MARKDOWN_CONNECTOR_IDENTITY
    manifest = MARKDOWN_CAPABILITY_MANIFEST

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        path, _ = _resolve_explicit_local_path(
            uri,
            context,
            scheme="md",
            expected_format=LocalFormat.MARKDOWN,
        )
        return ResolvedTable(
            uri=uri,
            mode=TableMode.SHEET,
            resource=ResolvedLocalTable(path=path, format=LocalFormat.MARKDOWN),
        )

    def _read_canonical(self, request: MarkdownTableReadRequest):
        resolved = self.resolve(request.uri, request.resolve_context)
        path = resolved.resource.path
        try:
            text = path.read_bytes().decode(request.options.encoding)
        except (OSError, UnicodeError, LookupError) as exc:
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "Markdown file could not be decoded",
                {"path": str(path), "encoding": request.options.encoding, "reason": str(exc)},
            ) from None
        table = read_markdown_arrow(text, source=str(path))
        if request.resource_limits.max_rows is not None:
            table = table.slice(0, request.resource_limits.max_rows)
        return table, path

    def _result(self, request: MarkdownTableReadRequest, capability):
        table, path = self._read_canonical(request)
        receipt = make_receipt(
            table,
            path=path,
            uri=request.uri,
            parameters=normalize_parameters({"encoding": request.options.encoding}),
            capability=capability,
            connector=self.identity,
            coordinate_convention=MARKDOWN_COORDINATE_CONVENTION,
        )
        return table, receipt

    def read_arrow(self, request: MarkdownTableReadRequest) -> ArrowReadResult:
        table, receipt = self._result(request, TABLE_READ_ARROW_CAPABILITY)
        return ArrowReadResult(table=table, receipt=receipt)

    def read_polars(self, request: MarkdownTableReadRequest) -> PolarsReadResult:
        table, receipt = self._result(request, TABLE_READ_POLARS_CAPABILITY)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=receipt)

    def inspect(self, request: InspectRequest):
        table, _ = self._read_canonical(
            MarkdownTableReadRequest(request.uri, resource_limits=request.resource_limits)
        )
        return inspection_from_read(
            request,
            table=table,
            sheet="data",
            header_row=1,
            worksheets=("data",),
            mode=TableMode.SHEET,
        )


__all__ = ["MarkdownConnector", "MarkdownReadOptions", "MarkdownTableReadRequest"]
