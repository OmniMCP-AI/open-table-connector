from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    HOST_GOOGLE_DOCS,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_GOOGLE_SHEETS,
    SCHEME_GSHEETS,
    SCHEME_HTTPS,
    SETTING_ENDPOINT,
    AdapterOptions,
    ProviderConfig,
    ProviderFactoryContext,
    parse_adapter_endpoint,
)
from open_table_connector.formulas import CompositeFormulaConnectorExtension
from open_table_connector.google_sheets.cli_adapter import google_sheets_cli_plugin
from open_table_connector.google_sheets.formula import GoogleSheetsFormulaExtension


@dataclass(frozen=True)
class RecordedCall:
    method: str
    url: str
    headers: dict[str, str]
    body: dict | None
    timeout: int | None


class RecordingTransport:
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self._responses = responses
        self.calls: list[RecordedCall] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append(RecordedCall(method, url, dict(headers), body, timeout))
        return self._responses[method]


def test_google_cli_factory_uses_logical_credentials_not_global_environment() -> None:
    transport = RecordingTransport({"GET": {"values": [["id"], ["1"]]}})
    context = ProviderFactoryContext(
        ProviderConfig(
            PROVIDER_GOOGLE_SHEETS,
            credential_reference="work-google",
            environment={SETTING_ENDPOINT: "GOOGLE_TEST_ENDPOINT"},
            options={OPTION_TIMEOUT_SECONDS: 7},
        ),
        environment={SETTING_ENDPOINT: "https://sheets.example.test"},
        credentials={CREDENTIAL_ACCESS_TOKEN: "configured-secret"},
        transports={PROVIDER_GOOGLE_SHEETS: transport},
    )
    adapter = google_sheets_cli_plugin().factory(context)

    result = adapter.read(
        parse_adapter_endpoint("gsheets://book/Orders"),
        AdapterOptions(range="A1:B2"),
    )

    assert result.table.to_pylist() == [{"id": "1"}]
    assert transport.calls[0].headers == {"Authorization": "Bearer configured-secret"}
    assert transport.calls[0].url.startswith("https://sheets.example.test/")
    assert transport.calls[0].timeout == 7


def test_google_cli_descriptor_owns_https_host_route() -> None:
    descriptor = google_sheets_cli_plugin()
    assert descriptor.identity.connector_id == PROVIDER_GOOGLE_SHEETS
    assert descriptor.route_keys() == (
        (SCHEME_GSHEETS, None),
        (SCHEME_HTTPS, HOST_GOOGLE_DOCS),
    )


def test_google_cli_formula_extension_reuses_configured_connector() -> None:
    transport = RecordingTransport({"GET": {"values": [["id"], ["1"]]}})
    context = ProviderFactoryContext(
        ProviderConfig(PROVIDER_GOOGLE_SHEETS, credential_reference="work-google"),
        environment={},
        credentials={CREDENTIAL_ACCESS_TOKEN: "configured-secret"},
        transports={PROVIDER_GOOGLE_SHEETS: transport},
    )
    adapter = google_sheets_cli_plugin().factory(context)

    extension = adapter.formula_extension_for()

    assert isinstance(extension, CompositeFormulaConnectorExtension)
    assert isinstance(extension.grid, GoogleSheetsFormulaExtension)
    assert extension.field is None
    assert extension.grid._connector is adapter.connector
