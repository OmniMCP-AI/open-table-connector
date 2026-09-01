"""CLI adapter owned by the Maybe Sheet provider package."""

from __future__ import annotations

import math
from dataclasses import dataclass
from urllib.parse import urlsplit

import polars as pl
import pyarrow as pa
from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    HOST_MAYBE,
    IF_EXISTS_APPEND,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_MAYBE_SHEET,
    SCHEME_HTTPS,
    SCHEME_MAYBE,
    SETTING_BINARY,
    AdapterEndpoint,
    AdapterOptions,
    ArrowReadResult,
    ConnectorAdapter,
    ConnectorError,
    ConnectorErrorCode,
    PluginDescriptor,
    ProviderFactoryContext,
    ResourceLimits,
    TableInspection,
    TableMode,
    TableWriteRequest,
    TableWriteResult,
    WritePreflightAdapter,
)
from open_table_connector.formulas import CompositeFormulaConnectorExtension

from .connector import MaybeSheetConnector, MaybeSheetReadRequest
from .grid_formula import MaybeSheetGridFormulaExtension
from .identity import (
    BASE_INSPECT_CAPABILITY,
    BASE_READ_CAPABILITY,
    CONNECTOR_IDENTITY,
    TABLE_WRITE_CAPABILITY,
)
from .process import SubprocessProcessClient, _absolute_executable


@dataclass
class MaybeSheetCliAdapter(ConnectorAdapter, WritePreflightAdapter):
    connector: MaybeSheetConnector
    credentials: dict[str, str]
    timeout_seconds: float = 120.0

    identity = CONNECTOR_IDENTITY
    schemes = (SCHEME_MAYBE, SCHEME_HTTPS)
    hosts = (HOST_MAYBE,)
    capabilities = (BASE_READ_CAPABILITY, BASE_INSPECT_CAPABILITY, TABLE_WRITE_CAPABILITY)
    modes = (TableMode.BASE,)

    @classmethod
    def from_context(cls, context: ProviderFactoryContext) -> MaybeSheetCliAdapter:
        return _factory(context)

    def _target(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> str:
        if endpoint.uri is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet requires a URI endpoint",
                {"endpoint": endpoint.raw},
            )
        uri = endpoint.uri
        if uri.scheme == SCHEME_HTTPS:
            if options.target:
                return options.target
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet HTTPS document URLs require an explicit target",
                {"option": "target"},
            )
        parsed = urlsplit(uri.value)
        target = parsed.path.strip("/")
        if uri.scheme == SCHEME_MAYBE and (
            not parsed.netloc or not target or "/" in target or parsed.query or parsed.fragment
        ):
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet URI must use maybe://DOCUMENT/TARGET",
                {"scheme": SCHEME_MAYBE},
            )
        if options.target:
            return options.target
        if not target:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet URI requires an explicit target",
                {"option": "target"},
            )
        return target

    def _request(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> MaybeSheetReadRequest:
        if endpoint.uri is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet requires a URI endpoint",
                {"endpoint": endpoint.raw},
            )
        return MaybeSheetReadRequest(
            endpoint.uri,
            TableMode.BASE,
            self._target(endpoint, options),
            ResourceLimits(
                max_rows=options.limit,
                timeout_seconds=(
                    int(self.timeout_seconds)
                    if options.timeout is None
                    else math.ceil(options.timeout)
                ),
            ),
            self._credentials_for_options(options),
        )

    def _credentials_for_options(self, options: AdapterOptions) -> dict[str, str]:
        token = getattr(options, "token", None)
        if not token:
            return dict(self.credentials)
        return {CREDENTIAL_ACCESS_TOKEN: token}

    def read(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> ArrowReadResult:
        return self.connector.read_arrow(self._request(endpoint, options))

    def inspect(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> TableInspection:
        return self.connector.inspect(self._request(endpoint, options))

    def preflight_write(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> None:
        if options.if_exists != IF_EXISTS_APPEND:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "MaybeSheet table writes support append only",
                {"if_exists": options.if_exists},
            )
        self._target(endpoint, options)

    def write(
        self, endpoint: AdapterEndpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult:
        if endpoint.uri is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet requires a URI endpoint",
                {"endpoint": endpoint.raw},
            )
        request = TableWriteRequest(
            endpoint.uri,
            pl.from_arrow(table),
            options.if_exists,
            self._target(endpoint, options),
        )
        return self.connector.write(request, credentials=self._credentials_for_options(options))

    def formula_extension_for(self) -> CompositeFormulaConnectorExtension:
        field_extension = getattr(self, "field_formula_extension", None)
        return CompositeFormulaConnectorExtension(
            grid=MaybeSheetGridFormulaExtension(
                self.connector,
                self.credentials,
                self.timeout_seconds,
            ),
            field=field_extension,
        )


def _factory(context: ProviderFactoryContext) -> MaybeSheetCliAdapter:
    allowed = {SETTING_BINARY}
    if set(context.config.environment) - allowed:
        raise ValueError("MaybeSheet environment contains an unknown setting")
    if set(context.config.options) - {OPTION_TIMEOUT_SECONDS}:
        raise ValueError("MaybeSheet options contain an unknown setting")
    if set(context.credentials) - {CREDENTIAL_ACCESS_TOKEN}:
        raise ValueError("MaybeSheet credentials contain an unknown field")
    timeout = context.config.options.get(OPTION_TIMEOUT_SECONDS, 120)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("MaybeSheet timeout must be positive")
    process = context.transports.get(PROVIDER_MAYBE_SHEET)
    if process is None:
        binary = context.environment.get(SETTING_BINARY, "mbs")
        process = SubprocessProcessClient(
            binary=(_absolute_executable(binary) if binary != "mbs" else binary),
            timeout_seconds=float(timeout),
        )
    return MaybeSheetCliAdapter(
        MaybeSheetConnector(process), dict(context.credentials), float(timeout)
    )


def maybe_sheet_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        PROVIDER_MAYBE_SHEET,
        CONNECTOR_IDENTITY,
        (SCHEME_MAYBE, SCHEME_HTTPS),
        _factory,
        (HOST_MAYBE,),
        capabilities=(BASE_READ_CAPABILITY, BASE_INSPECT_CAPABILITY, TABLE_WRITE_CAPABILITY),
        modes=(TableMode.BASE,),
    )


__all__ = ["MaybeSheetCliAdapter", "maybe_sheet_cli_plugin"]
