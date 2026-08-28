"""Connector capability manifests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .identity import CapabilityIdentity, ConnectorIdentity


class TableMode(StrEnum):
    BASE = "base"
    SHEET = "sheet"


@dataclass(frozen=True)
class CapabilityManifest:
    connector: ConnectorIdentity
    capabilities: tuple[CapabilityIdentity, ...]
    modes: tuple[TableMode, ...]
    uri_schemes: tuple[str, ...]

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

    def to_wire(self) -> dict[str, Any]:
        return {
            "connector": self.connector.to_wire(),
            "capabilities": [item.to_wire() for item in self.capabilities],
            "modes": [mode.value for mode in self.modes],
            "uri_schemes": list(self.uri_schemes),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "CapabilityManifest":
        required = {"connector", "capabilities", "modes", "uri_schemes"}
        if set(payload) != required:
            raise ValueError("CapabilityManifest wire object has unexpected keys")
        return cls(
            connector=ConnectorIdentity.from_wire(payload["connector"]),
            capabilities=tuple(
                CapabilityIdentity.from_wire(item) for item in payload["capabilities"]
            ),
            modes=tuple(TableMode(item) for item in payload["modes"]),
            uri_schemes=tuple(payload["uri_schemes"]),
        )
