from __future__ import annotations

import pytest
from open_table_connector.cli.configuration import CliConfig, CredentialBinding
from open_table_connector.cli.credentials import (
    EnvironmentCredentialResolver,
    apply_credential_overrides,
    parse_credential_overrides,
)
from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    PROVIDER_GOOGLE_SHEETS,
    ConnectorError,
    ProviderConfig,
)


def cli_config_with_credential(
    reference: str, logical_field: str, environment_name: str
) -> CliConfig:
    return CliConfig(
        providers={},
        credentials={
            reference: {logical_field: CredentialBinding(env=environment_name)}
        },
    )


def test_environment_resolver_returns_scoped_logical_credentials() -> None:
    config = cli_config_with_credential(
        "work-google", CREDENTIAL_ACCESS_TOKEN, "GOOGLE_TOKEN"
    )
    resolver = EnvironmentCredentialResolver(config, {"GOOGLE_TOKEN": "secret-value"})
    provider = ProviderConfig(
        PROVIDER_GOOGLE_SHEETS, credential_reference="work-google"
    )

    with resolver.resolve(provider) as lease:
        assert lease.values == {CREDENTIAL_ACCESS_TOKEN: "secret-value"}
        assert "secret-value" not in repr(lease)
    with pytest.raises(RuntimeError, match="disposed"):
        _ = lease.values


def test_credential_override_requires_provider_equals_reference() -> None:
    overrides = parse_credential_overrides(
        [f"{PROVIDER_GOOGLE_SHEETS}=work-google"]
    )
    assert overrides == {PROVIDER_GOOGLE_SHEETS: "work-google"}
    with pytest.raises(ValueError, match="PROVIDER=REFERENCE"):
        parse_credential_overrides(["work-google"])


def test_credential_override_updates_provider_reference_only() -> None:
    config = CliConfig(
        providers={
            PROVIDER_GOOGLE_SHEETS: ProviderConfig(
                PROVIDER_GOOGLE_SHEETS, credential_reference="old"
            )
        },
        credentials={"old": {}, "new": {}},
    )

    updated = apply_credential_overrides(
        config, {PROVIDER_GOOGLE_SHEETS: "new"}
    )

    assert updated.providers[PROVIDER_GOOGLE_SHEETS].credential_reference == "new"


def test_missing_environment_binding_does_not_leak_value_or_name() -> None:
    config = cli_config_with_credential(
        "work-google", CREDENTIAL_ACCESS_TOKEN, "GOOGLE_TOKEN"
    )
    resolver = EnvironmentCredentialResolver(config, {})

    with pytest.raises(ConnectorError) as raised:
        resolver.resolve(
            ProviderConfig(PROVIDER_GOOGLE_SHEETS, credential_reference="work-google")
        )

    assert raised.value.safe_details["environment"] == "GOOGLE_TOKEN"
    assert "secret" not in repr(raised.value).casefold()
