"""CLI adapters over the public connector provider interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

import polars as pl
import pyarrow as pa

from open_connectors.contract import (
    ArrowReadResult,
    BaseConvention,
    CapabilityIdentity,
    ConnectorIdentity,
    InspectRequest,
    ResourceLimits,
    TableInspection,
    TableReadRequest,
    TableURI,
    TableWriteRequest,
    TableWriteResult,
    TableMode,
)
from open_connectors.contract.fingerprints import arrow_schema_fingerprint
from open_connectors.feishu_bitable import (
    FeishuBitableConnector,
    FeishuBitableReadOptions,
    FeishuBitableTableReadRequest,
)
from open_connectors.google_sheets import (
    GoogleSheetsConnector,
    GoogleSheetsReadOptions,
    GoogleSheetsTableReadRequest,
)
from open_connectors.maybesheet import MaybeSheetConnector, MaybeSheetReadRequest, SubprocessProcessClient

from .formats import infer_format, read_local, write_local
from .model import CliOptions, Endpoint, FormatName


class ConnectorAdapter(Protocol):
    schemes: tuple[str, ...]
    identity: ConnectorIdentity
    capabilities: tuple[CapabilityIdentity, ...]

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult: ...
    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection: ...
    def write(self, endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult: ...


def _uri(endpoint: Endpoint) -> TableURI:
    if endpoint.uri is None:
        raise ValueError("provider adapters require a URI endpoint")
    return endpoint.uri


def _limits(options: CliOptions) -> ResourceLimits:
    timeout = None if options.timeout is None else int(options.timeout)
    return ResourceLimits(max_rows=options.limit, timeout_seconds=timeout)


def _frame(table: pa.Table) -> pl.DataFrame:
    return pl.from_arrow(table)


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

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult:
        request = GoogleSheetsTableReadRequest(
            _uri(endpoint),
            _limits(options),
            GoogleSheetsReadOptions(range=options.range, sheet=options.sheet),
        )
        return self._connector(options).read_arrow(request)

    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection:
        return self._connector(options).inspect(InspectRequest(_uri(endpoint)))

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

    def __post_init__(self) -> None:
        self.capabilities = tuple(self.connector.manifest.capabilities)

    def _connector(self, options: CliOptions) -> FeishuBitableConnector:
        return FeishuBitableConnector(self.transport, tenant_access_token=options.token or self.environment_token)

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult:
        request = FeishuBitableTableReadRequest(
            _uri(endpoint), _limits(options), FeishuBitableReadOptions(field_names=options.field_names)
        )
        return self._connector(options).read_arrow(request)

    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection:
        return self._connector(options).inspect(InspectRequest(_uri(endpoint)))

    def write(self, endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult:
        return self._connector(options).write(TableWriteRequest(_uri(endpoint), _frame(table), options.if_exists, options.target))


@dataclass
class MaybeSheetAdapter:
    connector: MaybeSheetConnector
    schemes: tuple[str, ...] = ("maybe", "https")
    identity: ConnectorIdentity = ConnectorIdentity("maybesheet", "0.1.0", "1.0")
    capabilities: tuple[CapabilityIdentity, ...] = (
        CapabilityIdentity("base.read", "1.0"),
        CapabilityIdentity("base.inspect", "1.0"),
        CapabilityIdentity("table.write", "1.0"),
    )

    def _target(self, endpoint: Endpoint, options: CliOptions) -> str:
        if options.target:
            return options.target
        target = urlsplit(_uri(endpoint).value).path.strip("/")
        if not target:
            raise ValueError("MaybeSheet URI requires a target")
        return target

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
        return self.connector.write(request)


@dataclass
class LocalAdapter:
    schemes: tuple[str, ...] = ("file",)
    identity: ConnectorIdentity = ConnectorIdentity("local_files", "0.1.0", "1.0")
    capabilities: tuple[CapabilityIdentity, ...] = (
        CapabilityIdentity("table.read.arrow", "1.0"),
        CapabilityIdentity("table.read.polars", "1.0"),
        CapabilityIdentity("table.inspect", "1.0"),
        CapabilityIdentity("table.write", "1.0"),
    )

    def _format(self, endpoint: Endpoint, options: CliOptions, *, output: bool = False) -> FormatName:
        return infer_format(endpoint, options.to_format if output else options.from_format)

    def read(self, endpoint: Endpoint, options: CliOptions) -> ArrowReadResult:
        table = read_local(endpoint, self._format(endpoint, options))
        return ArrowReadResult(table, _local_receipt(endpoint, table))

    def inspect(self, endpoint: Endpoint, options: CliOptions) -> TableInspection:
        result = self.read(endpoint, options)
        return TableInspection(endpoint.uri or TableURI("file:///" + str(endpoint.path)), TableMode.BASE,
                                tuple(result.table.column_names), result.receipt.schema_fingerprint,
                                result.table.num_rows, BaseConvention(ordinal_snapshot_id="local"), {"provider": "local"})

    def write(self, endpoint: Endpoint, table: pa.Table, options: CliOptions) -> TableWriteResult:
        write_local(table, endpoint, self._format(endpoint, options, output=True))
        return TableWriteResult(_local_receipt(endpoint, table), table.num_rows)


def _local_receipt(endpoint: Endpoint, table: pa.Table):
    from open_connectors.contract import NeutralReceipt
    uri = endpoint.uri or TableURI("file:///" + str(endpoint.path))
    fingerprint = arrow_schema_fingerprint(table.schema)
    return NeutralReceipt(LocalAdapter.identity, CapabilityIdentity("table.read.arrow", "1.0"),
                          "local", uri, TableMode.BASE, "local", fingerprint, fingerprint,
                          BaseConvention(ordinal_snapshot_id="local"), table.num_rows, 1)


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
