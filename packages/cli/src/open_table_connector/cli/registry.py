"""Configured, lazy scheme and capability dispatch for the OTC CLI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .configuration import load_cli_config
from .configured_registry import ConfiguredConnectorRegistry, discover_configured_plugins
from .credentials import EnvironmentCredentialResolver, apply_credential_overrides
from .plugins import _descriptor_entries

ConnectorRegistry = ConfiguredConnectorRegistry


def build_default_registry(
    env: Mapping[str, str] | None = None,
    transports: Mapping[str, Any] | None = None,
    *,
    config_path: str | None = None,
    credential_overrides: Mapping[str, str] | None = None,
) -> ConfiguredConnectorRegistry:
    environ = {} if env is None else dict(env)
    config = load_cli_config(config_path, environ=environ)
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


__all__ = ["ConnectorRegistry", "ConfiguredConnectorRegistry", "build_default_registry"]
