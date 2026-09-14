"""Connector capability manifests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .identity import CapabilityIdentity, ConnectorIdentity


class TableMode(StrEnum):
    BASE = "base"
    SHEET = "sheet"


@dataclass(frozen=True)
class MaterializationCapability:
    """One create-only materialization capability and its exact surface."""

    capability: CapabilityIdentity
    profiles: tuple[str, ...]
    modes: tuple[TableMode, ...]

    def __post_init__(self) -> None:
        if self.capability != CapabilityIdentity("table.materialize.create", "1.0"):
            raise ValueError("materialization capability must be table.materialize.create/1.0")
        profiles = tuple(str(profile).strip() for profile in self.profiles)
        if not profiles or any(not profile for profile in profiles) or len(set(profiles)) != len(profiles):
            raise ValueError("materialization profiles must be non-empty and unique")
        modes = tuple(self.modes)
        if not modes or any(not isinstance(mode, TableMode) for mode in modes):
            raise ValueError("materialization capability requires valid table modes")
        if len(set(modes)) != len(modes):
            raise ValueError("duplicate materialization modes are not allowed")
        object.__setattr__(self, "profiles", profiles)
        object.__setattr__(self, "modes", modes)

    def to_wire(self) -> dict[str, Any]:
        return {
            "capability": self.capability.to_wire(),
            "profiles": list(self.profiles),
            "modes": [mode.value for mode in self.modes],
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> MaterializationCapability:
        if set(payload) != {"capability", "profiles", "modes"}:
            raise ValueError("MaterializationCapability wire object has unexpected keys")
        return cls(
            capability=CapabilityIdentity.from_wire(payload["capability"]),
            profiles=tuple(payload["profiles"]),
            modes=tuple(TableMode(mode) for mode in payload["modes"]),
        )


@dataclass(frozen=True)
class CapabilityManifest:
    connector: ConnectorIdentity
    capabilities: tuple[CapabilityIdentity, ...]
    modes: tuple[TableMode, ...]
    uri_schemes: tuple[str, ...]
    materialization: tuple[MaterializationCapability, ...] = ()

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
        materialization = tuple(self.materialization)
        if any(not isinstance(item, MaterializationCapability) for item in materialization):
            raise ValueError("materialization entries must be MaterializationCapability values")
        if any(item.capability not in capabilities for item in materialization):
            raise ValueError("materialization capability must also be advertised in capabilities")
        object.__setattr__(self, "materialization", materialization)

    def to_wire(self) -> dict[str, Any]:
        return {
            "connector": self.connector.to_wire(),
            "capabilities": [item.to_wire() for item in self.capabilities],
            "modes": [mode.value for mode in self.modes],
            "uri_schemes": list(self.uri_schemes),
            "materialization": [item.to_wire() for item in self.materialization],
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> CapabilityManifest:
        required = {"connector", "capabilities", "modes", "uri_schemes"}
        if set(payload) not in (required, required | {"materialization"}):
            raise ValueError("CapabilityManifest wire object has unexpected keys")
        return cls(
            connector=ConnectorIdentity.from_wire(payload["connector"]),
            capabilities=tuple(
                CapabilityIdentity.from_wire(item) for item in payload["capabilities"]
            ),
            modes=tuple(TableMode(item) for item in payload["modes"]),
            uri_schemes=tuple(payload["uri_schemes"]),
            materialization=tuple(
                MaterializationCapability.from_wire(item) for item in payload["materialization"]
            ) if "materialization" in payload else (),
        )
