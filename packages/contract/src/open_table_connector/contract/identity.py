"""Immutable identities shared by neutral Connector implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _closed_wire(payload: Mapping[str, Any], required: set[str], label: str) -> None:
    if set(payload) != required:
        missing = sorted(required.difference(payload))
        extra = sorted(set(payload).difference(required))
        raise ValueError(f"{label} wire keys mismatch; missing={missing}, extra={extra}")


@dataclass(frozen=True)
class ConnectorIdentity:
    connector_id: str
    connector_version: str
    contract_version: str

    def __post_init__(self) -> None:
        for field_name in ("connector_id", "connector_version", "contract_version"):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )

    def to_wire(self) -> dict[str, str]:
        return {
            "connector_id": self.connector_id,
            "connector_version": self.connector_version,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "ConnectorIdentity":
        _closed_wire(
            payload,
            {"connector_id", "connector_version", "contract_version"},
            "ConnectorIdentity",
        )
        return cls(**payload)


@dataclass(frozen=True)
class CapabilityIdentity:
    capability_id: str
    capability_version: str

    def __post_init__(self) -> None:
        for field_name in ("capability_id", "capability_version"):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )

    def to_wire(self) -> dict[str, str]:
        return {
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "CapabilityIdentity":
        _closed_wire(
            payload,
            {"capability_id", "capability_version"},
            "CapabilityIdentity",
        )
        return cls(**payload)
