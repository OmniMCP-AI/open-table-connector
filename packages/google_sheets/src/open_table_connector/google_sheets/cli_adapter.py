"""CLI adapter owned by the Google Sheets provider package."""

from __future__ import annotations

import math
from dataclasses import dataclass

import polars as pl
import pyarrow as pa
from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    HOST_GOOGLE_DOCS,
    IF_EXISTS_APPEND,
    IF_EXISTS_ERROR,
    IF_EXISTS_REPLACE,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_GOOGLE_SHEETS,
    SCHEME_GSHEETS,
    SCHEME_HTTPS,
    SETTING_ENDPOINT,
    AdapterEndpoint,
    AdapterOptions,
    ArrowReadResult,
    ConnectorAdapter,
    ConnectorError,
    ConnectorErrorCode,
    InspectRequest,
    PluginDescriptor,
    ProviderFactoryContext,
    TableInspection,
    TableWriteRequest,
    TableWriteResult,
    WritePreflightAdapter,
)
from open_table_connector.formulas import (
    GRID_READ,
    GRID_SET,
    GRID_VALUES_READ,
    CompositeFormulaConnectorExtension,
)

from .connector import (
    CAPABILITY_MANIFEST,
    CONNECTOR_IDENTITY,
    GOOGLE_SHEETS_API_ENDPOINT,
    GoogleSheetsConnector,
    GoogleSheetsReadOptions,
    GoogleSheetsTableReadRequest,
)


@dataclass
class GoogleSheetsCliAdapter(ConnectorAdapter, WritePreflightAdapter):
    connector: GoogleSheetsConnector

    identity = CONNECTOR_IDENTITY
    schemes = (SCHEME_GSHEETS, SCHEME_HTTPS)
    hosts = (HOST_GOOGLE_DOCS,)
    capabilities = (
        *CAPABILITY_MANIFEST.capabilities,
        GRID_READ,
        GRID_SET,
        GRID_VALUES_READ,
    )
    modes = tuple(CAPABILITY_MANIFEST.modes)

    def _connector_for_options(self, options: AdapterOptions) -> GoogleSheetsConnector:
        token = getattr(options, "token", None)
        if not token:
            return self.connector
        return GoogleSheetsConnector(
            self.connector._transport,
            access_token=token,
            timeout=self.connector._timeout,
            api_endpoint=self.connector._api_endpoint,
        )

    def read(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> ArrowReadResult:
        if endpoint.uri is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "Google Sheets requires a URI endpoint",
                {},
            )
        request = GoogleSheetsTableReadRequest(
            endpoint.uri,
            resource_limits=_limits(options),
            options=GoogleSheetsReadOptions(range=options.range, sheet=options.sheet),
        )
        return self._connector_for_options(options).read_arrow(request)

    def inspect(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> TableInspection:
        if endpoint.uri is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "Google Sheets requires a URI endpoint",
                {},
            )
        return self._connector_for_options(options).inspect(
            InspectRequest(endpoint.uri, _limits(options))
        )

    def preflight_write(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> None:
        del endpoint
        if options.if_exists not in {IF_EXISTS_ERROR, IF_EXISTS_APPEND, IF_EXISTS_REPLACE}:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "Google Sheets if_exists value is invalid",
                {},
            )
        if options.if_exists == IF_EXISTS_ERROR:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "Google Sheets cannot enforce create-if-empty atomically",
                {"if_exists": options.if_exists},
            )

    def write(
        self, endpoint: AdapterEndpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult:
        if endpoint.uri is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "Google Sheets requires a URI endpoint",
                {},
            )
        return self._connector_for_options(options).write(
            TableWriteRequest(
                endpoint.uri,
                pl.from_arrow(table),
                options.if_exists,
                options.target,
            )
        )

    def formula_extension_for(self) -> CompositeFormulaConnectorExtension:
        from .formula import GoogleSheetsFormulaExtension

        return CompositeFormulaConnectorExtension(
            grid=GoogleSheetsFormulaExtension(self.connector),
            field=None,
        )


def _limits(options: AdapterOptions):
    from open_table_connector.contract import ResourceLimits

    timeout = None if options.timeout is None else math.ceil(options.timeout)
    return ResourceLimits(max_rows=options.limit, timeout_seconds=timeout)


def _factory(context: ProviderFactoryContext) -> ConnectorAdapter:
    allowed_environment = {SETTING_ENDPOINT}
    if set(context.config.environment) - allowed_environment:
        raise ValueError("Google Sheets environment contains an unknown setting")
    allowed_options = {OPTION_TIMEOUT_SECONDS}
    if set(context.config.options) - allowed_options:
        raise ValueError("Google Sheets options contain an unknown setting")
    if set(context.credentials) - {CREDENTIAL_ACCESS_TOKEN}:
        raise ValueError("Google Sheets credentials contain an unknown field")
    timeout = context.config.options.get(OPTION_TIMEOUT_SECONDS, 30)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("Google Sheets timeout must be positive")
    endpoint = context.environment.get(SETTING_ENDPOINT, GOOGLE_SHEETS_API_ENDPOINT)
    return GoogleSheetsCliAdapter(
        GoogleSheetsConnector(
            context.transports.get(PROVIDER_GOOGLE_SHEETS),
            access_token=context.credentials.get(CREDENTIAL_ACCESS_TOKEN),
            timeout=int(timeout),
            api_endpoint=endpoint,
        )
    )


def google_sheets_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        PROVIDER_GOOGLE_SHEETS,
        CONNECTOR_IDENTITY,
        (SCHEME_GSHEETS, SCHEME_HTTPS),
        _factory,
        (HOST_GOOGLE_DOCS,),
        capabilities=GoogleSheetsCliAdapter.capabilities,
        modes=tuple(CAPABILITY_MANIFEST.modes),
    )


__all__ = ["GoogleSheetsCliAdapter", "google_sheets_cli_plugin"]
