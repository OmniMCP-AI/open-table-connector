"""Versioned operation discovery and execution request contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

_EFFECTS = frozenset({"read", "buffered_write", "publish", "session_control"})
_RESOLUTIONS = frozenset({"static", "live"})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _required(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _closed(payload: Mapping[str, Any], expected: set[str], name: str) -> None:
    if set(payload) != expected:
        raise ValueError(f"{name} wire keys mismatch")


@dataclass(frozen=True, slots=True)
class TargetSelector:
    uri: str
    sheet: str | None = None
    object_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uri", _required(self.uri, "uri"))
        for name in ("sheet", "object_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _required(value, name))

    def to_wire(self) -> dict[str, Any]:
        return {"uri": self.uri, "sheet": self.sheet, "object_id": self.object_id}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> TargetSelector:
        _closed(payload, {"uri", "sheet", "object_id"}, "TargetSelector")
        return cls(payload["uri"], payload["sheet"], payload["object_id"])


@dataclass(frozen=True, slots=True)
class ExecutionOptions:
    dry_run: bool = False
    allow_partial: bool = False
    expected_revision: str | None = None
    idempotency_key: str | None = None
    failure_directory: str | None = None

    def __post_init__(self) -> None:
        for name in ("dry_run", "allow_partial"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a bool")
        for name in ("expected_revision", "idempotency_key", "failure_directory"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or null")

    def to_wire(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "allow_partial": self.allow_partial,
            "expected_revision": self.expected_revision,
            "idempotency_key": self.idempotency_key,
            "failure_directory": self.failure_directory,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> ExecutionOptions:
        _closed(payload, {"dry_run", "allow_partial", "expected_revision", "idempotency_key", "failure_directory"}, "ExecutionOptions")
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class OperationDescriptor:
    schema: str
    operation_id: str
    version: str
    target_kind: str
    arguments_schema: Mapping[str, Any]
    capability: str
    effects: tuple[str, ...]
    limits: Mapping[str, Any] = MappingProxyType({})
    examples: tuple[Mapping[str, Any], ...] = ()
    result_schema: Mapping[str, Any] = MappingProxyType({})

    def __post_init__(self) -> None:
        for name in ("schema", "operation_id", "version", "target_kind", "capability"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        effects = tuple(self.effects)
        if not effects or any(effect not in _EFFECTS for effect in effects):
            raise ValueError("effects contains an unsupported value")
        object.__setattr__(self, "effects", effects)
        object.__setattr__(self, "arguments_schema", _freeze(self.arguments_schema))
        object.__setattr__(self, "limits", _freeze(self.limits))
        object.__setattr__(self, "result_schema", _freeze(self.result_schema))
        object.__setattr__(self, "examples", tuple(_freeze(item) for item in self.examples))

    def to_wire(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "operation_id": self.operation_id,
            "version": self.version,
            "target_kind": self.target_kind,
            "arguments_schema": _thaw(self.arguments_schema),
            "capability": self.capability,
            "effects": list(self.effects),
            "limits": _thaw(self.limits),
            "examples": [_thaw(item) for item in self.examples],
            "result_schema": _thaw(self.result_schema),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> OperationDescriptor:
        _closed(payload, {"schema", "operation_id", "version", "target_kind", "arguments_schema", "capability", "effects", "limits", "examples", "result_schema"}, "OperationDescriptor")
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class OperationRequest:
    namespace: str
    operation_id: str
    version: str
    target: TargetSelector | None
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("namespace", "operation_id", "version"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        object.__setattr__(self, "arguments", _freeze(self.arguments))

    def to_wire(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "operation_id": self.operation_id,
            "version": self.version,
            "target": self.target.to_wire() if self.target else None,
            "arguments": _thaw(self.arguments),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> OperationRequest:
        _closed(payload, {"namespace", "operation_id", "version", "target", "arguments"}, "OperationRequest")
        target = payload["target"]
        return cls(payload["namespace"], payload["operation_id"], payload["version"], TargetSelector.from_wire(target) if target is not None else None, payload["arguments"])


@dataclass(frozen=True, slots=True)
class CapabilityObservation:
    target: TargetSelector
    provider: str
    provider_version: str | None
    resolution: str
    operations: tuple[OperationDescriptor, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _required(self.provider, "provider"))
        if self.provider_version is not None:
            object.__setattr__(self, "provider_version", _required(self.provider_version, "provider_version"))
        if self.resolution not in _RESOLUTIONS:
            raise ValueError("resolution must be static or live")
        object.__setattr__(self, "operations", tuple(self.operations))

    def to_wire(self) -> dict[str, Any]:
        return {
            "target": self.target.to_wire(),
            "provider": self.provider,
            "provider_version": self.provider_version,
            "resolution": self.resolution,
            "operations": [item.to_wire() for item in self.operations],
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> CapabilityObservation:
        _closed(payload, {"target", "provider", "provider_version", "resolution", "operations"}, "CapabilityObservation")
        return cls(TargetSelector.from_wire(payload["target"]), payload["provider"], payload["provider_version"], payload["resolution"], tuple(OperationDescriptor.from_wire(item) for item in payload["operations"]))


__all__ = ["CapabilityObservation", "ExecutionOptions", "OperationDescriptor", "OperationRequest", "TargetSelector"]
