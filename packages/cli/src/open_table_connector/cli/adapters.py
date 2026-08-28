"""CLI adapters over the public connector provider interfaces."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

import polars as pl
import pyarrow as pa

from open_table_connector.contract import (
    ArrowReadResult,
    BaseConvention,
    CapabilityIdentity,
    ConnectorError,
    ConnectorErrorCode,
    ConnectorIdentity,
    InspectRequest,
    NeutralReceipt,
    ResourceLimits,
    TableInspection,
    TableReadRequest,
    TableURI,
    TableWriteRequest,
    TableWriteResult,
    TableMode,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
    operation_identity,
)
from open_table_connector.feishu_bitable import (
    FeishuBitableConnector,
    FeishuBitableReadOptions,
    FeishuBitableTableReadRequest,
)
from open_table_connector.google_sheets import (
    GoogleSheetsConnector,
    GoogleSheetsReadOptions,
    GoogleSheetsTableReadRequest,
)
from open_table_connector.maybesheet import MaybeSheetConnector, MaybeSheetReadRequest, SubprocessProcessClient

from .formats import infer_format, read_local, write_local
from .model import CliOptions, Endpoint, FormatName


class ConnectorAdapter(Protocol):
    schemes: tuple[str, ...]
    identity: ConnectorIdentity
    capabilities: tuple[CapabilityIdentity, ...]
    modes: tuple[TableMode, ...]

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult: ...
    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection: ...
    def write(self, endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult: ...


def _uri(endpoint: Endpoint) -> TableURI:
    if endpoint.uri is None:
        raise ValueError("provider adapters require a URI endpoint")
    return endpoint.uri


def _limits(options: CliOptions) -> ResourceLimits:
    timeout = None if options.timeout is None else math.ceil(options.timeout)
    return ResourceLimits(max_rows=options.limit, timeout_seconds=timeout)


def _frame(table: pa.Table) -> pl.DataFrame:
    return pl.from_arrow(table)


def _limited_table(table: pa.Table, options: CliOptions) -> pa.Table:
    if options.limit is None:
        return table
    return table.slice(0, options.limit)


def _conflict(endpoint: Endpoint) -> ConnectorError:
    return ConnectorError(
        ConnectorErrorCode.CONFLICT,
        "destination already contains rows",
        {"scheme": endpoint.uri.scheme if endpoint.uri else "file"},
    )


def _local_uri(endpoint: Endpoint) -> TableURI:
    if endpoint.path is not None:
        return TableURI(endpoint.path.resolve().as_uri())
    return TableURI("stdio://stdin")


@dataclass
class GoogleSheetsAdapter:
    connector: GoogleSheetsConnector
    transport: Any = None
    environment_token: str | None = None
    schemes: tuple[str, ...] = ("gsheets", "https")
    identity: ConnectorIdentity = ConnectorIdentity("google_sheets", "0.1.0", "1.0")
    capabilities: tuple[CapabilityIdentity, ...] = ()

    def __post_init__(self) -> None:
        self.capabilities = tuple(self.connector.manifest.capabilities)

    def _connector(self, options: CliOptions) -> GoogleSheetsConnector:
        return GoogleSheetsConnector(self.transport, access_token=options.token or self.environment_token)

    def preflight_write(self, endpoint: Endpoint, options: CliOptions) -> None:
        if options.if_exists not in {"error", "append", "replace"}:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "if_exists must be error, append, or replace",
                {},
            )
        if options.if_exists != "error":
            return
        result = self._connector(options).read_arrow(
            GoogleSheetsTableReadRequest(
                _uri(endpoint),
                _limits(options),
                GoogleSheetsReadOptions(range=options.target),
            )
        )
        if result.table.num_rows:
            raise _conflict(endpoint)

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult:
        request = GoogleSheetsTableReadRequest(
            _uri(endpoint),
            _limits(options),
            GoogleSheetsReadOptions(range=options.range, sheet=options.sheet),
        )
        return self._connector(options).read_arrow(request)

    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection:
        return self._connector(options).inspect(InspectRequest(_uri(endpoint), _limits(options)))

    def write(self, endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult:
        return self._connector(options).write(TableWriteRequest(_uri(endpoint), _frame(table), options.if_exists, options.target))


@dataclass
class FeishuBitableAdapter:
    connector: FeishuBitableConnector
    transport: Any = None
    environment_token: str | None = None
    schemes: tuple[str, ...] = ("feishu", "feishu_bitable")
    identity: ConnectorIdentity = ConnectorIdentity("feishu_bitable", "0.1.0", "1.0")
    capabilities: tuple[CapabilityIdentity, ...] = ()
    provider_owned_fields: tuple[str, ...] = ("_record_id",)

    def __post_init__(self) -> None:
        self.capabilities = tuple(self.connector.manifest.capabilities)

    def _connector(self, options: CliOptions) -> FeishuBitableConnector:
        return FeishuBitableConnector(self.transport, tenant_access_token=options.token or self.environment_token)

    def preflight_write(self, endpoint: Endpoint, options: CliOptions) -> None:
        if options.if_exists not in {"append", "error"}:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "Feishu Bitable only supports append writes",
                {"if_exists": options.if_exists},
            )
        if options.if_exists != "error":
            return
        result = self._connector(options).read_arrow(
            FeishuBitableTableReadRequest(
                _uri(endpoint), _limits(options), FeishuBitableReadOptions()
            )
        )
        if result.table.num_rows:
            raise _conflict(endpoint)

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult:
        request = FeishuBitableTableReadRequest(
            _uri(endpoint), _limits(options), FeishuBitableReadOptions(field_names=options.field_names)
        )
        return self._connector(options).read_arrow(request)

    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection:
        return self._connector(options).inspect(InspectRequest(_uri(endpoint), _limits(options)))

    def write(self, endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult:
        return self._connector(options).write(TableWriteRequest(_uri(endpoint), _frame(table), options.if_exists, options.target))


@dataclass
class MaybeSheetAdapter:
    connector: MaybeSheetConnector
    schemes: tuple[str, ...] = ("maybe", "https")
    identity: ConnectorIdentity = ConnectorIdentity("maybesheet", "0.1.0", "1.0")
    modes: tuple[TableMode, ...] = (TableMode.BASE,)
    capabilities: tuple[CapabilityIdentity, ...] = (
        CapabilityIdentity("base.read", "1.0"),
        CapabilityIdentity("base.inspect", "1.0"),
        CapabilityIdentity("table.write", "1.0"),
    )

    def _target(self, endpoint: Endpoint, options: CliOptions) -> str:
        uri = _uri(endpoint)
        if uri.scheme == "https":
            if options.target:
                return options.target
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet HTTPS document URLs require an explicit target",
                {"option": "target"},
            )

        if uri.scheme == "maybe":
            parsed = urlsplit(uri.value)
            target = parsed.path[1:] if parsed.path.startswith("/") else ""
            if (
                not parsed.netloc.strip()
                or not target
                or "/" in target
                or parsed.query
                or parsed.fragment
            ):
                raise ConnectorError(
                    ConnectorErrorCode.INVALID_URI,
                    "MaybeSheet URI must use maybe://DOCUMENT/TARGET",
                    {"scheme": "maybe"},
                )
            return options.target or target

        if options.target:
            return options.target
        target = urlsplit(uri.value).path.strip("/")
        if not target:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet URI requires an explicit target",
                {"option": "target"},
            )
        return target

    def preflight_write(self, endpoint: Endpoint, options: CliOptions) -> None:
        if options.if_exists in {"replace", "error"}:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "MaybeSheet table writes support append only",
                {"if_exists": options.if_exists},
            )
        if options.if_exists != "append":
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "if_exists must be append for MaybeSheet table writes",
                {"if_exists": options.if_exists},
            )
        self._target(endpoint, options)

    def _request(self, endpoint: Endpoint, options: CliOptions) -> MaybeSheetReadRequest:
        token = options.token
        credentials = {} if token is None else {"access_token": token}
        return MaybeSheetReadRequest(
            _uri(endpoint), TableMode.BASE, self._target(endpoint, options), _limits(options), credentials
        )

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult:
        return self.connector.read_arrow(self._request(endpoint, options))

    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection:
        return self.connector.inspect(self._request(endpoint, options))

    def write(self, endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult:
        request = TableWriteRequest(_uri(endpoint), _frame(table), options.if_exists, self._target(endpoint, options))
        credentials = None if options.token is None else {"access_token": options.token}
        return self.connector.write(request, credentials=credentials)


@dataclass
class LocalAdapter:
    schemes: tuple[str, ...] = ("file",)
    identity: ConnectorIdentity = ConnectorIdentity("local_files", "0.1.0", "1.0")
    modes: tuple[TableMode, ...] = (TableMode.BASE,)
    capabilities: tuple[CapabilityIdentity, ...] = (
        CapabilityIdentity("table.read.arrow", "1.0"),
        CapabilityIdentity("table.read.polars", "1.0"),
        CapabilityIdentity("table.inspect", "1.0"),
        CapabilityIdentity("table.write", "1.0"),
    )

    def _format(self, endpoint: Endpoint, options: CliOptions, *, output: bool = False) -> FormatName:
        return infer_format(endpoint, options.to_format if output else options.from_format)

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult:
        table = _limited_table(read_local(endpoint, self._format(endpoint, options)), options)
        return ArrowReadResult(table, _local_receipt(endpoint, table, _LOCAL_READ_CAPABILITY))

    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection:
        result = self.read(endpoint, options)
        return TableInspection(_local_uri(endpoint), TableMode.BASE,
                                tuple(result.table.column_names), result.receipt.schema_fingerprint,
                                result.table.num_rows,
                                BaseConvention(ordinal_snapshot_id=result.receipt.source_revision),
                                {"provider": "local"})

    def write(self, endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult:
        write_local(table, endpoint, self._format(endpoint, options, output=True))
        return TableWriteResult(_local_receipt(endpoint, table, _LOCAL_WRITE_CAPABILITY), table.num_rows)


_LOCAL_READ_CAPABILITY = CapabilityIdentity("table.read.arrow", "1.0")
_LOCAL_WRITE_CAPABILITY = CapabilityIdentity("table.write", "1.0")


def _local_receipt(
    endpoint: Endpoint, table: pa.Table, capability: CapabilityIdentity
) -> NeutralReceipt:
    uri = _local_uri(endpoint)
    schema = arrow_schema_fingerprint(table.schema)
    content = arrow_content_fingerprint(table)
    source_revision = "sha256:" + content
    operation = operation_identity(
        connector=LocalAdapter.identity,
        capability=capability,
        uri=uri,
        source_revision=source_revision,
        schema_fingerprint=schema,
        content_fingerprint=content,
    )
    return NeutralReceipt(
        LocalAdapter.identity,
        capability,
        operation,
        uri,
        TableMode.BASE,
        source_revision,
        schema,
        content,
        BaseConvention(ordinal_snapshot_id=source_revision),
        table.num_rows,
        1,
    )


def build_adapters(env: Mapping[str, str], transports: Mapping[str, Any] | None = None) -> tuple[ConnectorAdapter, ...]:
    transports = transports or {}
    google = GoogleSheetsConnector(transports.get("google_sheets"), access_token=env.get("GOOGLE_SHEETS_ACCESS_TOKEN"))
    feishu = FeishuBitableConnector(transports.get("feishu_bitable"), tenant_access_token=env.get("FEISHU_TENANT_ACCESS_TOKEN"))
    maybe = MaybeSheetConnector(transports.get("maybesheet") or SubprocessProcessClient(environment=env))
    return (
        GoogleSheetsAdapter(google, transports.get("google_sheets"), env.get("GOOGLE_SHEETS_ACCESS_TOKEN")),
        FeishuBitableAdapter(feishu, transports.get("feishu_bitable"), env.get("FEISHU_TENANT_ACCESS_TOKEN")),
        MaybeSheetAdapter(maybe),
        LocalAdapter(),
    )


__all__ = ["ConnectorAdapter", "build_adapters"]
