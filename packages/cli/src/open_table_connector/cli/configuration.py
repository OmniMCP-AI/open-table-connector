"""Strict, reference-only CLI configuration loading."""

from __future__ import annotations

import errno
import os
import stat
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from open_table_connector.contract import (
    CLI_CONFIG_DIRECTORY,
    CLI_CONFIG_ENV,
    CLI_CONFIG_FILENAME,
    CLI_CONFIG_SCHEMA_VERSION,
    XDG_CONFIG_HOME_ENV,
    ConnectorError,
    ProviderConfig,
)

CLI_CONFIG_MAX_BYTES = 1_048_576
_PROVIDER_FIELDS = frozenset({"id", "enabled", "key", "env", "options"})
_SECRET_LIKE_PARTS = frozenset({"token", "password", "secret", "credential", "api_key", "apikey"})


def _error(
    message: str, *, path: Path | None = None, field_name: str | None = None
) -> ConnectorError:
    details: dict[str, str] = {}
    if path is not None:
        details["path"] = str(path)
    if field_name is not None:
        details["field"] = field_name
    return ConnectorError.configuration(message, safe_details=details)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


@dataclass(frozen=True)
class CredentialBinding:
    env: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "env", _text(self.env, "environment variable"))


@dataclass(frozen=True)
class CliConfig:
    providers: Mapping[str, ProviderConfig] = field(default_factory=dict)
    credentials: Mapping[str, Mapping[str, CredentialBinding]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.providers, Mapping) or not isinstance(self.credentials, Mapping):
            raise TypeError("providers and credentials must be mappings")
        providers: dict[str, ProviderConfig] = {}
        for raw_id, provider in self.providers.items():
            provider_id = _text(raw_id, "provider ID")
            if not isinstance(provider, ProviderConfig):
                raise TypeError("providers must contain ProviderConfig values")
            if provider.provider_id != provider_id:
                raise ValueError("provider mapping key must match provider_id")
            providers[provider_id] = provider
        credentials: dict[str, Mapping[str, CredentialBinding]] = {}
        for raw_reference, bindings in self.credentials.items():
            reference = _text(raw_reference, "credential reference")
            if not isinstance(bindings, Mapping):
                raise TypeError("credential entries must be mappings")
            normalized: dict[str, CredentialBinding] = {}
            for raw_field, binding in bindings.items():
                logical_field = _text(raw_field, "credential field")
                if not isinstance(binding, CredentialBinding):
                    raise TypeError("credential fields must contain CredentialBinding values")
                normalized[logical_field] = binding
            credentials[reference] = MappingProxyType(normalized)
        object.__setattr__(self, "providers", MappingProxyType(providers))
        object.__setattr__(self, "credentials", MappingProxyType(credentials))

    @classmethod
    def empty(cls) -> CliConfig:
        return cls()


def resolve_config_path(
    explicit: str | Path | None,
    environ: Mapping[str, str],
    *,
    home: Path | None = None,
) -> Path | None:
    if explicit is not None:
        return Path(explicit).expanduser()
    configured = environ.get(CLI_CONFIG_ENV)
    if configured:
        return Path(configured).expanduser()
    if home is None:
        home = Path.home()
    xdg_home = environ.get(XDG_CONFIG_HOME_ENV)
    if xdg_home:
        xdg_path = Path(xdg_home).expanduser() / CLI_CONFIG_DIRECTORY / CLI_CONFIG_FILENAME
        if xdg_path.exists():
            return xdg_path
    default_path = home / ".config" / CLI_CONFIG_DIRECTORY / CLI_CONFIG_FILENAME
    if default_path.exists():
        return default_path
    return None


def _read_config_bytes(path: Path, *, explicit: bool) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    before = None
    if not nofollow:
        try:
            before = path.lstat()
        except FileNotFoundError:
            if explicit:
                raise _error("configuration path does not exist", path=path) from None
            return b""
        except OSError as exc:
            raise _error("configuration path cannot be inspected", path=path) from exc
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise _error("configuration path does not exist", path=path) from exc
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise _error("configuration file must be a regular file", path=path) from exc
        raise _error("configuration file cannot be opened", path=path) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise _error("configuration file must be a regular file", path=path)
        if before is not None and (
            not stat.S_ISREG(before.st_mode)
            or metadata.st_dev != before.st_dev
            or metadata.st_ino != before.st_ino
        ):
            raise _error("configuration file changed during open", path=path)
        chunks: list[bytes] = []
        total = 0
        while total <= CLI_CONFIG_MAX_BYTES:
            chunk = os.read(descriptor, min(65_536, CLI_CONFIG_MAX_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > CLI_CONFIG_MAX_BYTES:
            raise _error("configuration file exceeds maximum size", path=path)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a table")
    return value


def _parse_config(document: Mapping[str, Any], path: Path) -> CliConfig:
    if set(document) - {"schema_version", "providers", "credentials"}:
        raise _error("configuration contains an unknown field", path=path)
    if document.get("schema_version") != CLI_CONFIG_SCHEMA_VERSION:
        raise _error(
            "unsupported configuration schema version",
            path=path,
            field_name="schema_version",
        )

    providers: dict[str, ProviderConfig] = {}
    raw_providers = document.get("providers", [])
    if not isinstance(raw_providers, list):
        raise _error("providers must be an array", path=path, field_name="providers")
    try:
        for index, raw_provider in enumerate(raw_providers):
            provider = _mapping(raw_provider, f"providers[{index}]")
            if set(provider) - _PROVIDER_FIELDS:
                raise _error(
                    "provider contains an unknown field",
                    path=path,
                    field_name=f"providers[{index}]",
                )
            provider_id = _text(provider.get("id"), "provider id")
            if provider_id in providers:
                raise _error("duplicate provider ID", path=path, field_name="providers.id")
            enabled = provider.get("enabled", True)
            if not isinstance(enabled, bool):
                raise _error(
                    "provider enabled must be a boolean",
                    path=path,
                    field_name="providers.enabled",
                )
            key = provider.get("key")
            if key is not None:
                key = _text(key, "credential reference")
            environment = _mapping(provider.get("env", {}), "provider env")
            normalized_environment = {
                _text(raw_key, "environment field"): _text(raw_value, "environment variable")
                for raw_key, raw_value in environment.items()
            }
            options = _mapping(provider.get("options", {}), "provider options")
            for raw_key in options:
                key_name = _text(raw_key, "option name")
                normalized_name = key_name.casefold().replace("-", "_")
                if any(part in normalized_name for part in _SECRET_LIKE_PARTS):
                    raise _error(
                        "secret-like option names are not allowed",
                        path=path,
                        field_name=key_name,
                    )
            providers[provider_id] = ProviderConfig(
                provider_id,
                enabled=enabled,
                credential_reference=key,
                environment=normalized_environment,
                options=options,
            )
    except ConnectorError:
        raise
    except (TypeError, ValueError) as exc:
        raise _error("invalid provider configuration", path=path, field_name="providers") from exc

    credentials: dict[str, dict[str, CredentialBinding]] = {}
    raw_credentials = document.get("credentials", {})
    try:
        credential_tables = _mapping(raw_credentials, "credentials")
        for raw_reference, raw_fields in credential_tables.items():
            reference = _text(raw_reference, "credential reference")
            fields = _mapping(raw_fields, "credential fields")
            normalized_fields: dict[str, CredentialBinding] = {}
            for raw_field, raw_source in fields.items():
                logical_field = _text(raw_field, "credential field")
                if not isinstance(raw_source, Mapping):
                    raise _error(
                        "credential source must contain only an environment reference",
                        path=path,
                        field_name=logical_field,
                    )
                source = _mapping(raw_source, f"credentials.{reference}.{logical_field}")
                if set(source) != {"env"}:
                    raise _error(
                        "credential source must contain only an environment reference",
                        path=path,
                        field_name=logical_field,
                    )
                normalized_fields[logical_field] = CredentialBinding(
                    _text(source["env"], "environment variable")
                )
            credentials[reference] = normalized_fields
    except ConnectorError:
        raise
    except (TypeError, ValueError) as exc:
        raise _error(
            "invalid credential configuration", path=path, field_name="credentials"
        ) from exc
    return CliConfig(providers=providers, credentials=credentials)


def load_cli_config(
    path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> CliConfig:
    environment = {} if environ is None else environ
    selected = resolve_config_path(path, environment, home=home)
    if selected is None:
        return CliConfig.empty()
    explicit = path is not None or bool(environment.get(CLI_CONFIG_ENV))
    raw = _read_config_bytes(selected, explicit=explicit)
    if not raw:
        if explicit:
            raise _error("configuration file is empty", path=selected)
        return CliConfig.empty()
    try:
        text = raw.decode("utf-8")
        document = tomllib.loads(text)
        if not isinstance(document, Mapping):
            raise ValueError("configuration document must be a table")
    except ConnectorError:
        raise
    except (UnicodeDecodeError, tomllib.TOMLDecodeError, ValueError) as exc:
        raise _error("configuration document is invalid", path=selected) from exc
    return _parse_config(document, selected)


__all__ = [
    "CLI_CONFIG_MAX_BYTES",
    "CliConfig",
    "CredentialBinding",
    "load_cli_config",
    "resolve_config_path",
]
