"""CLI adapter owned by the Maybe Sheet provider package."""

from __future__ import annotations

import math
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import polars as pl
import pyarrow as pa
from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    HOST_MAYBE,
    IF_EXISTS_APPEND,
    OPTION_LIVE_MATERIALIZATION_EVIDENCE,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_MAYBE_SHEET,
    SCHEME_HTTPS,
    SETTING_BINARY,
    AdapterEndpoint,
    AdapterOptions,
    ArrowReadResult,
    BaseTableBindingAdapter,
    ConnectorAdapter,
    ConnectorError,
    ConnectorErrorCode,
    PluginDescriptor,
    ProviderFactoryContext,
    ResourceLimits,
    TableInspection,
    TableMode,
    TableURI,
    TableWriteRequest,
    TableWriteResult,
    WritePreflightAdapter,
)
from open_table_connector.formulas import CompositeFormulaConnectorExtension

from .connector import MaybeSheetConnector, MaybeSheetReadRequest
from .field_formula import MaybeSheetFieldFormulaExtension
from .grid_formula import MaybeSheetGridFormulaExtension
from .identity import (
    BASE_INSPECT_CAPABILITY,
    BASE_READ_CAPABILITY,
    CONNECTOR_IDENTITY,
    FORMULA_FIELD_READ_CAPABILITY,
    FORMULA_FIELD_RECALCULATE_CAPABILITY,
    FORMULA_FIELD_SET_CAPABILITY,
    FORMULA_FIELD_VALUES_READ_CAPABILITY,
    FORMULA_GRID_READ_CAPABILITY,
    FORMULA_GRID_RECALCULATE_CAPABILITY,
    FORMULA_GRID_SET_CAPABILITY,
    FORMULA_GRID_VALUES_READ_CAPABILITY,
    TABLE_WRITE_CAPABILITY,
)
from .process import SubprocessProcessClient, _absolute_executable


@dataclass
class MaybeSheetCliAdapter(
    ConnectorAdapter, WritePreflightAdapter, BaseTableBindingAdapter
):
    connector: MaybeSheetConnector
    credentials: dict[str, str]
    timeout_seconds: float = 120.0
    live_materialization_evidence: bool = False

    identity = CONNECTOR_IDENTITY
    schemes = (SCHEME_HTTPS,)
    hosts = (HOST_MAYBE,)
    capabilities = (
        BASE_READ_CAPABILITY,
        BASE_INSPECT_CAPABILITY,
        TABLE_WRITE_CAPABILITY,
        FORMULA_GRID_READ_CAPABILITY,
        FORMULA_GRID_SET_CAPABILITY,
        FORMULA_GRID_VALUES_READ_CAPABILITY,
        FORMULA_GRID_RECALCULATE_CAPABILITY,
        FORMULA_FIELD_READ_CAPABILITY,
        FORMULA_FIELD_SET_CAPABILITY,
        FORMULA_FIELD_VALUES_READ_CAPABILITY,
        FORMULA_FIELD_RECALCULATE_CAPABILITY,
    )
    modes = (TableMode.BASE, TableMode.SHEET)

    @classmethod
    def from_context(cls, context: ProviderFactoryContext) -> MaybeSheetCliAdapter:
        return _factory(context)

    @staticmethod
    def _maybe_table_id_from_query(query: str) -> str | None:
        parts = parse_qsl(query, keep_blank_values=True)
        if len(parts) != 1:
            return None
        name, value = parts[0]
        if name != "table_id":
            return None
        value = value.strip()
        if not value:
            return None
        return value

    def _target_selector(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> tuple[str, bool]:
        if endpoint.uri is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet requires a URI endpoint",
                {"endpoint": endpoint.raw},
            )
        uri = endpoint.uri
        parsed = urlsplit(uri.value)
        if uri.scheme != SCHEME_HTTPS:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "MaybeSheet requires an HTTPS URL",
                {"scheme": uri.scheme},
            )
        if parsed.fragment:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet URLs cannot contain a fragment",
                {"scheme": SCHEME_HTTPS},
            )
        if parsed.query:
            table_id = self._maybe_table_id_from_query(parsed.query)
            if table_id is None:
                raise ConnectorError(
                    ConnectorErrorCode.INVALID_URI,
                    "MaybeSheet URL query must contain only table_id",
                    {"scheme": SCHEME_HTTPS},
                )
            if options.target:
                raise ConnectorError(
                    ConnectorErrorCode.INVALID_URI,
                    "MaybeSheet URL table_id cannot be combined with an explicit target",
                    {"scheme": SCHEME_HTTPS},
                )
            return table_id, True
        if options.target:
            return options.target, False
        raise ConnectorError(
            ConnectorErrorCode.INVALID_URI,
            "MaybeSheet HTTPS document URLs require an explicit target",
            {"option": "target"},
        )

    def bind_base_table(self, endpoint: AdapterEndpoint, table_id: str) -> AdapterEndpoint:
        if endpoint.uri is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet requires a URI endpoint",
                {"endpoint": endpoint.raw},
            )
        uri = endpoint.uri
        if uri.scheme != SCHEME_HTTPS:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "MaybeSheet base table binding requires an HTTPS URL",
                {"scheme": uri.scheme},
            )
        parsed = urlsplit(uri.value)
        if (
            parsed.path.strip("/") or parsed.query or parsed.fragment
        ):
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet base table URL cannot contain a query or fragment",
                {"endpoint": endpoint.raw},
            )
        bound_uri = TableURI(
            urlunsplit(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    urlencode({"table_id": table_id}),
                    "",
                )
            )
        )
        return AdapterEndpoint(raw=bound_uri.value, uri=bound_uri)

    def _request(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> MaybeSheetReadRequest:
        target, target_is_id = self._target_selector(endpoint, options)
        return MaybeSheetReadRequest(
            uri=endpoint.uri,
            mode=TableMode.BASE,
            target=target,
            resource_limits=ResourceLimits(
                max_rows=options.limit,
                timeout_seconds=(
                    int(self.timeout_seconds)
                    if options.timeout is None
                    else math.ceil(options.timeout)
                ),
            ),
            credentials=self._credentials_for_options(options),
            target_is_id=target_is_id,
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
        _ = self._target_selector(endpoint, options)

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
            self._target_selector(endpoint, options)[0],
        )
        return self.connector.write(request, credentials=self._credentials_for_options(options))

    def spreadsheet_provider(self):
        from .spreadsheet import MaybeSpreadsheetProvider

        return MaybeSpreadsheetProvider(self.connector, self.credentials, self.timeout_seconds)

    def formula_extension_for(self) -> CompositeFormulaConnectorExtension:
        return CompositeFormulaConnectorExtension(
            grid=MaybeSheetGridFormulaExtension(
                self.connector,
                self.credentials,
                self.timeout_seconds,
            ),
            field=MaybeSheetFieldFormulaExtension(
                self.connector,
                self.credentials,
                self.timeout_seconds,
            ),
        )

    def sdk_connector(self):
        """Expose native Base creation only when the process proves its contract."""
        from .materialization import MaybeSheetSdkConnector

        return MaybeSheetSdkConnector(self, live_evidence=self.live_materialization_evidence)


def _factory(context: ProviderFactoryContext) -> MaybeSheetCliAdapter:
    allowed = {SETTING_BINARY}
    if set(context.config.environment) - allowed:
        raise ValueError("MaybeSheet environment contains an unknown setting")
    if set(context.config.options) - {
        OPTION_TIMEOUT_SECONDS,
        OPTION_LIVE_MATERIALIZATION_EVIDENCE,
    }:
        raise ValueError("MaybeSheet options contain an unknown setting")
    if set(context.credentials) - {CREDENTIAL_ACCESS_TOKEN}:
        raise ValueError("MaybeSheet credentials contain an unknown field")
    timeout = context.config.options.get(OPTION_TIMEOUT_SECONDS, 120)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("MaybeSheet timeout must be positive")
    live_evidence = context.config.options.get(OPTION_LIVE_MATERIALIZATION_EVIDENCE, False)
    if not isinstance(live_evidence, bool):
        raise ValueError("MaybeSheet live materialization evidence must be a bool")
    process = context.transports.get(PROVIDER_MAYBE_SHEET)
    if process is None:
        binary = context.environment.get(SETTING_BINARY, "mbs")
        process = SubprocessProcessClient(
            binary=(_absolute_executable(binary) if binary != "mbs" else binary),
            timeout_seconds=float(timeout),
        )
    return MaybeSheetCliAdapter(
        MaybeSheetConnector(process), dict(context.credentials), float(timeout), live_evidence
    )


def maybe_sheet_cli_plugin() -> PluginDescriptor:
    return PluginDescriptor(
        PROVIDER_MAYBE_SHEET,
        CONNECTOR_IDENTITY,
        (SCHEME_HTTPS,),
        _factory,
        (HOST_MAYBE,),
        capabilities=MaybeSheetCliAdapter.capabilities,
        modes=MaybeSheetCliAdapter.modes,
        runtime_metadata=True,
    )


__all__ = ["MaybeSheetCliAdapter", "maybe_sheet_cli_plugin"]
