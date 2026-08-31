"""Configured, lazy scheme and capability dispatch for the OTC CLI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from open_table_connector.contract import (
    CREDENTIAL_ACCESS_TOKEN,
    CREDENTIAL_TENANT_ACCESS_TOKEN,
    PROVIDER_FEISHU_BITABLE,
    PROVIDER_GOOGLE_SHEETS,
    PROVIDER_MAYBE_SHEET,
    ProviderConfig,
)

from .configuration import CliConfig, CredentialBinding, load_cli_config
from .configured_registry import ConfiguredConnectorRegistry, discover_configured_plugins
from .credentials import EnvironmentCredentialResolver, apply_credential_overrides
from .plugins import _descriptor_entries

ConnectorRegistry = ConfiguredConnectorRegistry

_DEFAULT_CREDENTIAL_BINDINGS = {
    PROVIDER_GOOGLE_SHEETS: {
        "reference": "default-google-sheets",
        "field": CREDENTIAL_ACCESS_TOKEN,
        "env": "GOOGLE_SHEETS_ACCESS_TOKEN",
    },
    PROVIDER_FEISHU_BITABLE: {
        "reference": "default-feishu-bitable",
        "field": CREDENTIAL_TENANT_ACCESS_TOKEN,
        "env": "FEISHU_TENANT_ACCESS_TOKEN",
    },
    PROVIDER_MAYBE_SHEET: {
        "reference": "default-maybe-sheet",
        "field": CREDENTIAL_ACCESS_TOKEN,
        "env": "MAYBE_SHEET_ACCESS_TOKEN",
    },
}


def build_default_registry(
    env: Mapping[str, str] | None = None,
    transports: Mapping[str, Any] | None = None,
    *,
    config_path: str | None = None,
    credential_overrides: Mapping[str, str] | None = None,
) -> ConfiguredConnectorRegistry:
    environ = {} if env is None else dict(env)
    config = load_cli_config(config_path, environ=environ)
    config = _with_default_credential_bindings(config, environ)
    if credential_overrides:
        config = apply_credential_overrides(config, credential_overrides)
    discovered = discover_configured_plugins(config, entries=_descriptor_entries())
    return ConfiguredConnectorRegistry.from_descriptors(
        (item.descriptor for item in discovered),
        config,
        resolver=EnvironmentCredentialResolver(config, environ),
        environ=environ,
        transports=transports,
    )


def _with_default_credential_bindings(config: CliConfig, environ: Mapping[str, str]) -> CliConfig:
    providers = dict(config.providers)
    credentials = {reference: dict(bindings) for reference, bindings in config.credentials.items()}
    changed = False

    for provider_id, binding in _DEFAULT_CREDENTIAL_BINDINGS.items():
        env_name = binding["env"]
        if env_name not in environ:
            continue
        provider = providers.get(provider_id, ProviderConfig(provider_id))
        if provider.credential_reference is not None:
            continue
        reference = binding["reference"]
        field_name = binding["field"]
        credentials.setdefault(reference, {})[field_name] = CredentialBinding(env_name)
        providers[provider_id] = ProviderConfig(
            provider.provider_id,
            enabled=provider.enabled,
            credential_reference=reference,
            environment=provider.environment,
            options=provider.options,
        )
        changed = True

    if not changed:
        return config
    return CliConfig(providers=providers, credentials=credentials)


__all__ = ["ConnectorRegistry", "ConfiguredConnectorRegistry", "build_default_registry"]
