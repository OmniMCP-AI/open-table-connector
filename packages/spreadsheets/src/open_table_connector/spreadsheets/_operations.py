"""Internal normalized change records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from open_table_connector.contract import CapabilityIdentity


def freeze(value: Any) -> Any:
    """Detach and recursively freeze caller-owned containers."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    return value



@dataclass(frozen=True, slots=True)
class Change:
    operation_id: str
    capability: CapabilityIdentity
    target_key: str
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id.strip():
            raise ValueError("operation_id must be a non-empty string")
        if not isinstance(self.capability, CapabilityIdentity):
            raise TypeError("capability must be a CapabilityIdentity")
        if not isinstance(self.target_key, str) or not self.target_key.strip():
            raise ValueError("target_key must be a non-empty string")
        if not isinstance(self.arguments, Mapping):
            raise TypeError("arguments must be a dictionary")
        object.__setattr__(self, "arguments", freeze(self.arguments))


__all__ = ["Change"]
