"""Connector capability manifests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from .identity import CapabilityIdentity, ConnectorIdentity


class TableMode(StrEnum):
    BASE = "base"
    SHEET = "sheet"


_MANAGED_IO_FEATURES = frozenset(
    {"projection_pushdown", "predicate_pushdown", "readback"}
)
_SECRET_KEYS = frozenset(
    {"secret", "credential", "credentials", "password", "token", "api_key", "access_token"}
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("managed_io mapping keys must be strings")
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


def _validate_schema(value: Any, *, parent_key: str | None = None) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("managed_io config_schema keys must be strings")
            lowered = key.casefold()
            if lowered in _SECRET_KEYS or lowered.endswith("_secret"):
                raise ValueError("managed_io config_schema cannot contain credential or secret fields")
            if lowered == "credential_ref" and isinstance(child, str) and not child.strip():
                raise ValueError("credential_ref must be a non-empty string")
            if lowered == "default" and parent_key is not None:
                parent_lowered = parent_key.casefold()
                if parent_lowered in _SECRET_KEYS or parent_lowered.endswith("_secret"):
                    raise ValueError("managed_io config_schema cannot contain secret defaults")
            _validate_schema(child, parent_key=key)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_schema(child, parent_key=parent_key)


def _normalize_managed_io(
    managed_io: Mapping[str, Mapping[str, Any]],
    capability_ids: set[str],
) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(managed_io, Mapping):
        raise ValueError("managed_io must be a mapping")
    normalized: dict[str, Any] = {}
    for operation, declaration in managed_io.items():
        if operation not in {"read", "write"}:
            raise ValueError("managed_io supports only read and write operations")
        if not isinstance(declaration, Mapping):
            raise ValueError(f"managed_io.{operation} must be a mapping")
        required = {"capability_id", "config_schema", "features"}
        if operation == "read":
            required.add("boundedness")
        if set(declaration) != required:
            raise ValueError(f"managed_io.{operation} has unexpected keys")
        capability_id = declaration["capability_id"]
        if not isinstance(capability_id, str) or capability_id not in capability_ids:
            raise ValueError(f"managed_io.{operation} references an unlisted capability")
        schema = declaration["config_schema"]
        if not isinstance(schema, Mapping):
            raise ValueError(f"managed_io.{operation}.config_schema must be a mapping")
        _validate_schema(schema)
        features = declaration["features"]
        if isinstance(features, (str, bytes)) or not isinstance(features, (list, tuple)):
            raise ValueError(f"managed_io.{operation}.features must be a list")
        if any(feature not in _MANAGED_IO_FEATURES for feature in features):
            raise ValueError(f"managed_io.{operation} has an unknown feature")
        if len(set(features)) != len(features):
            raise ValueError(f"managed_io.{operation}.features must be unique")
        if operation == "read" and declaration["boundedness"] not in {"bounded", "unbounded"}:
            raise ValueError("managed_io.read.boundedness must be bounded or unbounded")
        normalized[operation] = _freeze(declaration)
    return MappingProxyType(normalized)


@dataclass(frozen=True)
class CapabilityManifest:
    connector: ConnectorIdentity
    capabilities: tuple[CapabilityIdentity, ...]
    modes: tuple[TableMode, ...]
    uri_schemes: tuple[str, ...]
    managed_io: Mapping[str, Mapping[str, Any]] = MappingProxyType({})

    def __post_init__(self) -> None:
        capabilities = tuple(self.capabilities)
        ids = [item.capability_id for item in capabilities]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate capability IDs are not allowed")
        modes = tuple(self.modes)
        if not modes or any(not isinstance(mode, TableMode) for mode in modes):
            raise ValueError("capability manifest requires valid table modes")
        if len(set(modes)) != len(modes):
            raise ValueError("duplicate table modes are not allowed")
        schemes = tuple(str(item).casefold() for item in self.uri_schemes)
        if any(not item for item in schemes) or len(set(schemes)) != len(schemes):
            raise ValueError("URI schemes must be non-empty and unique")
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "modes", modes)
        object.__setattr__(self, "uri_schemes", schemes)
        object.__setattr__(
            self,
            "managed_io",
            _normalize_managed_io(self.managed_io, set(ids)),
        )

    def to_wire(self) -> dict[str, Any]:
        wire = {
            "connector": self.connector.to_wire(),
            "capabilities": [item.to_wire() for item in self.capabilities],
            "modes": [mode.value for mode in self.modes],
            "uri_schemes": list(self.uri_schemes),
        }
        if self.managed_io:
            wire["managed_io"] = _thaw(self.managed_io)
        return wire

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "CapabilityManifest":
        required = {"connector", "capabilities", "modes", "uri_schemes"}
        extra = set(payload).difference(required | {"managed_io"})
        if extra or not required.issubset(payload):
            raise ValueError("CapabilityManifest wire object has unexpected keys")
        return cls(
            connector=ConnectorIdentity.from_wire(payload["connector"]),
            capabilities=tuple(
                CapabilityIdentity.from_wire(item) for item in payload["capabilities"]
            ),
            modes=tuple(TableMode(item) for item in payload["modes"]),
            uri_schemes=tuple(payload["uri_schemes"]),
            managed_io=payload.get("managed_io", {}),
        )
