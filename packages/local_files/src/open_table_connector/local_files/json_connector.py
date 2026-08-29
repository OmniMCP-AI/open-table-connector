"""Concrete strict JSON and JSONL BASE-table connector."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable
from urllib.parse import parse_qsl, unquote, urlsplit

import polars as pl

from open_table_connector.contract import (
    ArrowReadResult,
    ArrowTableReader,
    BaseConvention,
    ConnectorError,
    ConnectorErrorCode,
    InspectRequest,
    PolarsReadResult,
    PolarsTableReader,
    ResolveContext,
    ResolvedTable,
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
from .json_codec import parse_json_table, parse_jsonl_table
from .manifest import capability_manifest
from .probe import LocalFormat
from .receipts import make_receipt, normalize_parameters, source_revision
from .resolver import ResolvedLocalTable


JSON_CONNECTOR_IDENTITY = connector_identity("json")
JSON_CAPABILITY_MANIFEST = capability_manifest(
    connector=JSON_CONNECTOR_IDENTITY,
    uri_schemes=("json", "jsonl"),
)


@dataclass(frozen=True)
class JsonTableReadRequest(TableReadRequest):
    @property
    def resolve_context(self) -> ResolveContext:
        return ResolveContext(resource_limits=self.resource_limits)


class JsonConnector(URIResolver, TableInspector, ArrowTableReader, PolarsTableReader):
    identity = JSON_CONNECTOR_IDENTITY
    manifest = JSON_CAPABILITY_MANIFEST

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock

    def resolve(self, uri: TableURI, context: ResolveContext) -> ResolvedTable:
        started = self._clock()
        path, format_name = _json_path(uri)
        table = _read_json_path(path, format_name, context.resource_limits.max_bytes)
        _check_limits(table.num_rows, context.resource_limits, started, self._clock)
        return ResolvedTable(
            uri=uri,
            mode=TableMode.BASE,
            resource=ResolvedLocalTable(path=path, format=format_name),
        )

    def _read_canonical(self, request: JsonTableReadRequest):
        started = self._clock()
        path, format_name = _json_path(request.uri)
        table = _read_json_path(path, format_name, request.resource_limits.max_bytes)
        _check_limits(table.num_rows, request.resource_limits, started, self._clock)
        return table, path

    def _result(self, request: JsonTableReadRequest, capability):
        table, path = self._read_canonical(request)
        receipt = make_receipt(
            table,
            path=path,
            uri=request.uri,
            parameters=normalize_parameters({"format": request.uri.scheme, "encoding": "utf-8"}),
            capability=capability,
            connector=self.identity,
            mode=TableMode.BASE,
        )
        return table, receipt

    def read_arrow(self, request: JsonTableReadRequest) -> ArrowReadResult:
        table, receipt = self._result(request, TABLE_READ_ARROW_CAPABILITY)
        return ArrowReadResult(table=table, receipt=receipt)

    def read_polars(self, request: JsonTableReadRequest) -> PolarsReadResult:
        table, receipt = self._result(request, TABLE_READ_POLARS_CAPABILITY)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=receipt)

    def inspect(self, request: InspectRequest):
        table, path = self._read_canonical(
            JsonTableReadRequest(request.uri, resource_limits=request.resource_limits)
        )
        return inspection_from_read(
            request,
            table=table,
            sheet="data",
            worksheets=("data",),
            mode=TableMode.BASE,
            coordinate_convention=BaseConvention(
                ordinal_snapshot_id=source_revision(path)
            ),
        )


def _json_path(uri: TableURI) -> tuple[Path, LocalFormat]:
    if uri.scheme not in {"json", "jsonl"}:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "JSON Connector accepts only json and jsonl URIs",
            {"scheme": uri.scheme},
        )
    parsed = urlsplit(uri.value)
    if parsed.query or parsed.fragment or parsed.netloc not in {"", "localhost"}:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "JSON URI cannot contain a host, query, or fragment",
            {
                "query_keys": sorted(key for key, _ in parse_qsl(parsed.query)),
                "has_fragment": bool(parsed.fragment),
            },
        )
    path = Path(unquote(parsed.path))
    if not path.is_absolute() or ".." in path.parts or not path.is_file():
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "JSON URI must address one regular absolute file",
            {"path": str(path)},
        )
    if path.is_symlink():
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "JSON URI cannot address a symlink",
            {"path": str(path)},
        )
    format_name = LocalFormat.JSON if uri.scheme == "json" else LocalFormat.JSONL
    return path, format_name


def _read_json_path(path: Path, format_name: LocalFormat, max_bytes: int | None):
    try:
        size = path.stat().st_size
        if max_bytes is not None and size > max_bytes:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "JSON input exceeds the configured byte limit",
                {"size": size, "max_bytes": max_bytes},
            )
        with path.open("rb") as stream:
            data = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
    except OSError as exc:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON input could not be read",
            {"path": str(path), "reason": exc.strerror or type(exc).__name__},
        ) from None
    if max_bytes is not None and len(data) > max_bytes:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "JSON input exceeds the configured byte limit",
            {"size": len(data), "max_bytes": max_bytes},
        )
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON input is not strict UTF-8",
            {"path": str(path)},
        ) from None
    parser = parse_json_table if format_name is LocalFormat.JSON else parse_jsonl_table
    return parser(text, source=str(path))


def _check_limits(rows: int, limits, started: float, clock: Callable[[], float]) -> None:
    if limits.max_rows is not None and rows > limits.max_rows:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "JSON input exceeds the configured row limit",
            {"rows": rows, "max_rows": limits.max_rows},
        )
    if limits.timeout_seconds is not None and clock() - started > limits.timeout_seconds:
        raise ConnectorError(
            ConnectorErrorCode.TIMEOUT,
            "JSON input exceeded the configured timeout",
            {"timeout_seconds": limits.timeout_seconds},
        )


__all__ = ["JsonConnector", "JsonTableReadRequest"]
