"""CLI adapter owned by the Feishu Bitable provider package."""

from __future__ import annotations

import math
from dataclasses import dataclass

import polars as pl
import pyarrow as pa
from open_table_connector.contract import (
    CREDENTIAL_TENANT_ACCESS_TOKEN,
    IF_EXISTS_APPEND,
    IF_EXISTS_ERROR,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_FEISHU_BITABLE,
    SCHEME_FEISHU,
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

from .connector import (
    CAPABILITY_MANIFEST,
    CONNECTOR_IDENTITY,
    FEISHU_API_ENDPOINT,
    FeishuBitableConnector,
    FeishuBitableReadOptions,
    FeishuBitableTableReadRequest,
)
from .identity import FEISHU_RECORD_ID_FIELD


@dataclass
class FeishuBitableCliAdapter(ConnectorAdapter, WritePreflightAdapter):
    connector: FeishuBitableConnector

    identity = CONNECTOR_IDENTITY
    schemes = (SCHEME_FEISHU, PROVIDER_FEISHU_BITABLE)
    hosts: tuple[str, ...] = ()
    capabilities = tuple(CAPABILITY_MANIFEST.capabilities)
    modes = tuple(CAPABILITY_MANIFEST.modes)
    provider_owned_fields = (FEISHU_RECORD_ID_FIELD,)

    def _connector_for_options(self, options: AdapterOptions) -> FeishuBitableConnector:
        token = getattr(options, "token", None)
        if not token:
            return self.connector
        return FeishuBitableConnector(
            self.connector._transport,
            tenant_access_token=token,
            timeout=self.connector._timeout,
            api_endpoint=self.connector._api_endpoint,
        )

    @classmethod
    def from_context(cls, context: ProviderFactoryContext) -> FeishuBitableCliAdapter:
        return _factory(context)

    def read(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> ArrowReadResult:
        uri = _uri(endpoint)
        request = FeishuBitableTableReadRequest(
            uri,
            _limits(options),
            FeishuBitableReadOptions(field_names=options.field_names),
        )
        return self._connector_for_options(options).read_arrow(request)

    def inspect(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> TableInspection:
        return self._connector_for_options(options).inspect(
            InspectRequest(_uri(endpoint), _limits(options))
        )

    def preflight_write(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> None:
        del endpoint
        if options.if_exists == IF_EXISTS_ERROR:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "Feishu Bitable cannot enforce create-if-empty atomically",
                {"if_exists": options.if_exists},
            )
        if options.if_exists != IF_EXISTS_APPEND:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "Feishu Bitable only supports append writes",
                {"if_exists": options.if_exists},
            )

    def write(
        self, endpoint: AdapterEndpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult:
        return self._connector_for_options(options).write(
            TableWriteRequest(
                _uri(endpoint), pl.from_arrow(table), options.if_exists, options.target
            )
        )


def _uri(endpoint: AdapterEndpoint):
    if endpoint.uri is None:
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "Feishu Bitable requires a URI endpoint",
            {"endpoint": endpoint.raw},
        )
    return endpoint.uri


def _limits(options: AdapterOptions):
    from open_table_connector.contract import ResourceLimits

    timeout = None if options.timeout is None else math.ceil(options.timeout)
    return ResourceLimits(max_rows=options.limit, timeout_seconds=timeout)


def _factory(context: ProviderFactoryContext) -> FeishuBitableCliAdapter:
    if set(context.config.environment) - {SETTING_ENDPOINT}:
        raise ValueError("Feishu Bitable environment contains an unknown setting")
    if set(context.config.options) - {OPTION_TIMEOUT_SECONDS}:
        raise ValueError("Feishu Bitable options contain an unknown setting")
    if set(context.credentials) - {CREDENTIAL_TENANT_ACCESS_TOKEN}:
        raise ValueError("Feishu Bitable credentials contain an unknown field")
    timeout = context.config.options.get(OPTION_TIMEOUT_SECONDS, 30)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("Feishu Bitable timeout must be positive")
    endpoint = context.environment.get(SETTING_ENDPOINT, FEISHU_API_ENDPOINT)
    return FeishuBitableCliAdapter(
        FeishuBitableConnector(
            context.transports.get(PROVIDER_FEISHU_BITABLE),
            tenant_access_token=context.credentials.get(CREDENTIAL_TENANT_ACCESS_TOKEN),
            timeout=int(timeout),
            api_endpoint=endpoint,
        )
    )


def feishu_bitable_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        PROVIDER_FEISHU_BITABLE,
        CONNECTOR_IDENTITY,
        (SCHEME_FEISHU, PROVIDER_FEISHU_BITABLE),
        _factory,
        capabilities=tuple(CAPABILITY_MANIFEST.capabilities),
        modes=tuple(CAPABILITY_MANIFEST.modes),
    )


__all__ = ["FeishuBitableCliAdapter", "feishu_bitable_cli_plugin"]
