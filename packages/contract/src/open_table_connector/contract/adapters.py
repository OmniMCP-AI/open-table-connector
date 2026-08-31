"""Neutral adapter values shared by the CLI host and provider packages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, TypeAlias, runtime_checkable
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pyarrow as pa

from .capabilities import TableMode
from .identity import CapabilityIdentity, ConnectorIdentity
from .inspect import TableInspection
from .names import (
    FORMAT_AUTO,
    FORMAT_TABLE,
    IF_EXISTS_APPEND,
    IF_EXISTS_ERROR,
    IF_EXISTS_REPLACE,
    PROVIDER_CSV,
    PROVIDER_EXCEL,
    PROVIDER_JSON,
    PROVIDER_JSONL,
    SCHEME_FILE,
)
from .read import ArrowReadResult
from .storage import TableWriteResult
from .uri import TableURI


class AdapterFormat(StrEnum):
    AUTO = FORMAT_AUTO
    CSV = PROVIDER_CSV
    EXCEL = PROVIDER_EXCEL
    JSON = PROVIDER_JSON
    JSONL = PROVIDER_JSONL
    TABLE = FORMAT_TABLE


ConfigScalar: TypeAlias = str | int | float | bool
ConfigValue: TypeAlias = ConfigScalar | tuple[ConfigScalar, ...]


def _required_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _immutable_text_mapping(values: Mapping[str, str], label: str) -> Mapping[str, str]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{label} must be a mapping")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = _required_text(raw_key, f"{label} key")
        normalized[key] = _required_text(raw_value, f"{label}[{key!r}]")
    return MappingProxyType(normalized)


def _config_value(value: object, label: str) -> ConfigValue:
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        result: list[ConfigScalar] = []
        for item in value:
            if not isinstance(item, (str, int, float, bool)):
                raise TypeError(f"{label} must contain only scalar values")
            result.append(item)
        return tuple(result)
    raise TypeError(f"{label} must be a scalar or sequence of scalars")


@dataclass(frozen=True)
class AdapterEndpoint:
    raw: str
    uri: TableURI | None = None
    path: Path | None = None
    is_stdio: bool = False

    def __post_init__(self) -> None:
        raw = _required_text(self.raw, "raw")
        object.__setattr__(self, "raw", raw)
        if not isinstance(self.is_stdio, bool):
            raise TypeError("is_stdio must be a bool")
        if self.is_stdio:
            if self.uri is not None or self.path is not None:
                raise ValueError("stdio endpoints cannot carry a uri or path")
            return
        if self.uri is None and self.path is None:
            raise ValueError("endpoint must have either a uri or a path")
        if self.uri is not None and not isinstance(self.uri, TableURI):
            raise TypeError("uri must be a TableURI")
        if self.path is not None and not isinstance(self.path, Path):
            raise TypeError("path must be a Path")
        if self.uri is not None and self.path is not None:
            raise ValueError("endpoint cannot have both a uri and a path")


@dataclass(frozen=True)
class AdapterOptions:
    from_format: AdapterFormat = AdapterFormat.AUTO
    output_format: AdapterFormat = AdapterFormat.AUTO
    to_format: AdapterFormat = AdapterFormat.AUTO
    limit: int | None = None
    timeout: float | int | None = None
    sheet: str | None = None
    range: str | None = None
    field_names: tuple[str, ...] = ()
    if_exists: str = IF_EXISTS_ERROR
    target: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("from_format", "output_format", "to_format"):
            object.__setattr__(self, field_name, parse_adapter_format(getattr(self, field_name)))
        if self.limit is not None and (
            not isinstance(self.limit, int) or isinstance(self.limit, bool) or self.limit <= 0
        ):
            raise ValueError("limit must be a positive integer when supplied")
        if self.timeout is not None and (
            not isinstance(self.timeout, (int, float))
            or isinstance(self.timeout, bool)
            or self.timeout <= 0
        ):
            raise ValueError("timeout must be a positive number when supplied")
        fields = tuple(_required_text(item, "field name") for item in self.field_names)
        object.__setattr__(self, "field_names", fields)
        if self.if_exists not in {IF_EXISTS_APPEND, IF_EXISTS_ERROR, IF_EXISTS_REPLACE}:
            raise ValueError("if_exists must be append, error, or replace")
        for field_name in ("sheet", "range", "target"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _required_text(value, field_name))


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    enabled: bool = True
    credential_reference: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    options: Mapping[str, ConfigValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _required_text(self.provider_id, "provider_id"))
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a bool")
        if self.credential_reference is not None:
            object.__setattr__(
                self,
                "credential_reference",
                _required_text(self.credential_reference, "credential_reference"),
            )
        object.__setattr__(
            self, "environment", _immutable_text_mapping(self.environment, "environment")
        )
        normalized_options: dict[str, ConfigValue] = {}
        if not isinstance(self.options, Mapping):
            raise TypeError("options must be a mapping")
        for raw_key, raw_value in self.options.items():
            key = _required_text(raw_key, "options key")
            normalized_options[key] = _config_value(raw_value, f"options[{key!r}]")
        object.__setattr__(self, "options", MappingProxyType(normalized_options))


@dataclass(frozen=True)
class ProviderFactoryContext:
    config: ProviderConfig
    environment: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    credentials: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    transports: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.config, ProviderConfig):
            raise TypeError("config must be a ProviderConfig")
        object.__setattr__(
            self, "environment", _immutable_text_mapping(self.environment, "environment")
        )
        object.__setattr__(
            self, "credentials", _immutable_text_mapping(self.credentials, "credentials")
        )
        if not isinstance(self.transports, Mapping):
            raise TypeError("transports must be a mapping")
        object.__setattr__(self, "transports", MappingProxyType(dict(self.transports)))


@runtime_checkable
class ConnectorAdapter(Protocol):
    identity: ConnectorIdentity
    schemes: tuple[str, ...]
    hosts: tuple[str, ...]
    capabilities: tuple[CapabilityIdentity, ...]
    modes: tuple[TableMode, ...]

    def read(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> ArrowReadResult: ...

    def inspect(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> TableInspection: ...

    def write(
        self, endpoint: AdapterEndpoint, table: pa.Table, options: AdapterOptions
    ) -> TableWriteResult: ...


@runtime_checkable
class WritePreflightAdapter(Protocol):
    def preflight_write(self, endpoint: AdapterEndpoint, options: AdapterOptions) -> None: ...


def parse_adapter_endpoint(value: str) -> AdapterEndpoint:
    value = _required_text(value, "endpoint")
    if value == "-":
        return AdapterEndpoint(raw=value, is_stdio=True)
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return AdapterEndpoint(raw=value, path=Path(value))
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme.casefold() == SCHEME_FILE:
        validated = TableURI(value)
        file_uri = urlsplit(validated.value)
        if file_uri.netloc.casefold() not in ("", "localhost"):
            raise ValueError("file endpoint authority must be empty or localhost")
        if file_uri.query or file_uri.fragment:
            raise ValueError("file endpoint cannot contain a query or fragment")
        return AdapterEndpoint(raw=value, path=Path(url2pathname(file_uri.path)))
    if parsed.scheme:
        return AdapterEndpoint(raw=value, uri=TableURI(value))
    return AdapterEndpoint(raw=value, path=Path(value))


def parse_adapter_format(value: str | None) -> AdapterFormat:
    if value is None:
        return AdapterFormat.AUTO
    if isinstance(value, AdapterFormat):
        return value
    if not isinstance(value, str):
        raise ValueError("format must be a string when supplied")
    try:
        return AdapterFormat(value.casefold())
    except ValueError as exc:
        raise ValueError(f"unsupported format: {value}") from exc


__all__ = [
    "AdapterEndpoint",
    "AdapterFormat",
    "AdapterOptions",
    "ConfigScalar",
    "ConfigValue",
    "ConnectorAdapter",
    "ProviderConfig",
    "ProviderFactoryContext",
    "WritePreflightAdapter",
    "parse_adapter_endpoint",
    "parse_adapter_format",
]
