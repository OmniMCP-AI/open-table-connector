"""Scoped credential resolution for configured provider adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Protocol

from open_table_connector.contract import ConnectorError, ProviderConfig

from .configuration import CliConfig


class CredentialLease:
    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = {str(key): str(value) for key, value in values.items()}
        self._disposed = False

    @property
    def values(self) -> Mapping[str, str]:
        if self._disposed:
            raise RuntimeError("credential lease is disposed")
        return MappingProxyType(self._values)

    def dispose(self) -> None:
        self._values.clear()
        self._disposed = True

    def __enter__(self) -> CredentialLease:
        if self._disposed:
            raise RuntimeError("credential lease is disposed")
        return self

    def __exit__(self, *_: object) -> None:
        self.dispose()

    def __repr__(self) -> str:
        return "CredentialLease(<redacted>)"


class CredentialResolver(Protocol):
    def resolve(self, provider: ProviderConfig) -> CredentialLease: ...


class EnvironmentCredentialResolver:
    def __init__(self, config: CliConfig, environ: Mapping[str, str]) -> None:
        self._config = config
        self._environ = dict(environ)

    def resolve(self, provider: ProviderConfig) -> CredentialLease:
        reference = provider.credential_reference
        if reference is None:
            return CredentialLease({})
        bindings = self._config.credentials.get(reference)
        if bindings is None:
            raise ConnectorError.authentication(
                "credential reference is not configured",
                safe_details={"provider_id": provider.provider_id, "reference": reference},
            )
        values: dict[str, str] = {}
        for logical_field, binding in bindings.items():
            value = self._environ.get(binding.env)
            if value is None:
                raise ConnectorError.configuration(
                    "credential environment binding is missing",
                    safe_details={
                        "provider_id": provider.provider_id,
                        "field": logical_field,
                        "environment": binding.env,
                    },
                )
            values[logical_field] = value
        return CredentialLease(values)


def parse_credential_overrides(values: Sequence[str]) -> Mapping[str, str]:
    overrides: dict[str, str] = {}
    for raw_value in values:
        if not isinstance(raw_value, str) or "=" not in raw_value:
            raise ValueError("credential overrides must use PROVIDER=REFERENCE")
        provider_id, reference = raw_value.split("=", 1)
        provider_id = provider_id.strip()
        reference = reference.strip()
        if not provider_id or not reference:
            raise ValueError("credential overrides must use non-empty PROVIDER=REFERENCE")
        if provider_id in overrides:
            raise ValueError("duplicate credential override provider")
        overrides[provider_id] = reference
    return MappingProxyType(overrides)


def apply_credential_overrides(
    config: CliConfig, overrides: Mapping[str, str]
) -> CliConfig:
    providers = dict(config.providers)
    for raw_provider_id, raw_reference in overrides.items():
        provider_id = str(raw_provider_id).strip()
        reference = str(raw_reference).strip()
        if not provider_id or not reference:
            raise ValueError("credential overrides must use non-empty PROVIDER=REFERENCE")
        if reference not in config.credentials:
            raise ValueError("credential override references an unknown credential key")
        provider = providers.get(provider_id)
        providers[provider_id] = (
            ProviderConfig(
                provider_id,
                enabled=True,
                credential_reference=reference,
            )
            if provider is None
            else ProviderConfig(
                provider.provider_id,
                enabled=provider.enabled,
                credential_reference=reference,
                environment=provider.environment,
                options=provider.options,
            )
        )
    return CliConfig(providers=providers, credentials=config.credentials)


__all__ = [
    "CredentialLease",
    "CredentialResolver",
    "EnvironmentCredentialResolver",
    "apply_credential_overrides",
    "parse_credential_overrides",
]
