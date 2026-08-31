from __future__ import annotations

from pathlib import Path

import pytest
from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    HOST_GOOGLE_DOCS,
    OPTION_TIMEOUT_SECONDS,
    PROVIDER_GOOGLE_SHEETS,
    SETTING_ENDPOINT,
    AdapterEndpoint,
    AdapterFormat,
    AdapterOptions,
    ConnectorError,
    ConnectorErrorCode,
    ProviderConfig,
    ProviderFactoryContext,
    TableURI,
    parse_adapter_endpoint,
)


def test_provider_factory_context_hides_credentials_and_transports() -> None:
    config = ProviderConfig(
        provider_id=PROVIDER_GOOGLE_SHEETS,
        credential_reference="work-google",
        environment={SETTING_ENDPOINT: "OTC_GOOGLE_ENDPOINT"},
        options={OPTION_TIMEOUT_SECONDS: 30},
    )
    context = ProviderFactoryContext(
        config=config,
        environment={SETTING_ENDPOINT: "https://example.test"},
        credentials={CREDENTIAL_ACCESS_TOKEN: "provider-secret"},
        transports={PROVIDER_GOOGLE_SHEETS: object()},
    )

    assert "provider-secret" not in repr(context)
    assert "https://example.test" not in repr(context)
    assert "transports" not in repr(context)
    assert context.environment[SETTING_ENDPOINT] == "https://example.test"
    assert context.credentials[CREDENTIAL_ACCESS_TOKEN] == "provider-secret"


def test_adapter_endpoint_rejects_mixed_uri_and_path() -> None:
    with pytest.raises(ValueError, match="cannot have both"):
        AdapterEndpoint(
            raw="orders.csv",
            uri=TableURI("csv:///tmp/orders.csv"),
            path=Path("orders.csv"),
        )


def test_adapter_options_normalize_formats_and_validate_limits() -> None:
    options = AdapterOptions(from_format="json", output_format="jsonl")
    assert options.from_format is AdapterFormat.JSON
    assert options.output_format is AdapterFormat.JSONL
    with pytest.raises(ValueError, match="positive"):
        AdapterOptions(limit=0)


def test_parse_adapter_endpoint_keeps_file_scheme_knowledge_in_contract(tmp_path) -> None:
    endpoint = parse_adapter_endpoint((tmp_path / "orders.csv").as_uri())
    assert endpoint.uri is None
    assert endpoint.path == tmp_path / "orders.csv"
    assert endpoint.is_stdio is False


def test_configuration_error_exposes_only_explicit_safe_details() -> None:
    error = ConnectorError.configuration(
        "provider configuration is invalid",
        safe_details={"provider_id": PROVIDER_GOOGLE_SHEETS},
    )
    assert error.code is ConnectorErrorCode.CONFIGURATION
    assert error.to_wire()["safe_details"] == {
        "provider_id": PROVIDER_GOOGLE_SHEETS
    }


def test_host_constant_remains_a_single_canonical_route_value() -> None:
    assert HOST_GOOGLE_DOCS == "docs.google.com"
