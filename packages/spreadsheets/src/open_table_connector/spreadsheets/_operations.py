"""Internal normalized change records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from open_table_connector.contract import CapabilityIdentity


@dataclass(frozen=True, slots=True)
class Change:
    operation_id: str
    capability: CapabilityIdentity
    target_key: str
    arguments: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id.strip():
            raise ValueError("operation_id must be a non-empty string")
        if not isinstance(self.capability, CapabilityIdentity):
            raise TypeError("capability must be a CapabilityIdentity")
        if not isinstance(self.target_key, str) or not self.target_key.strip():
            raise ValueError("target_key must be a non-empty string")
        if not isinstance(self.arguments, dict):
            raise TypeError("arguments must be a dictionary")
        object.__setattr__(self, "arguments", dict(self.arguments))


__all__ = ["Change"]
