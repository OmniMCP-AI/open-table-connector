"""Explicit connector bindings; arbitrary module imports are never accepted."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol


class ProcessHandler(Protocol):
    def handle(self, context: object) -> object: ...


@dataclass(frozen=True, slots=True)
class ConnectorRegistration:
    connector_id: str
    connector_version: str
    contract_version: str
    portable_plan_version: str
    capability_versions: Mapping[str, str]
    handler: ProcessHandler

    def __post_init__(self) -> None:
        for field in (
            "connector_id",
            "connector_version",
            "contract_version",
            "portable_plan_version",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        capabilities = dict(self.capability_versions)
        if not capabilities:
            raise ValueError("capability_versions cannot be empty")
        if any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            or not value
            for key, value in capabilities.items()
        ):
            raise ValueError("capability versions must be non-empty strings")
        object.__setattr__(self, "capability_versions", MappingProxyType(capabilities))


class ConnectorProcessRegistry:
    def __init__(self, registrations: tuple[ConnectorRegistration, ...] = ()) -> None:
        self._registrations: dict[str, ConnectorRegistration] = {}
        for registration in registrations:
            self.register(registration)

    def register(self, registration: ConnectorRegistration) -> None:
        if not isinstance(registration, ConnectorRegistration):
            raise TypeError("registration must be a ConnectorRegistration")
        if registration.connector_id in self._registrations:
            raise ValueError(f"connector is already registered: {registration.connector_id}")
        self._registrations[registration.connector_id] = registration

    def resolve(self, connector_id: str) -> ConnectorRegistration:
        try:
            return self._registrations[connector_id]
        except KeyError as exc:
            raise KeyError("connector is not registered") from exc


__all__ = ["ConnectorProcessRegistry", "ConnectorRegistration", "ProcessHandler"]
