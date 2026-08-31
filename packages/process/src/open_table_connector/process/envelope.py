"""Closed control envelopes for ``otc.connector-process/v1``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from open_table_connector.timeseries import ArrowArtifactReference, ResourceBounds

PROCESS_PROTOCOL = "otc.connector-process/v1"
PORTABLE_PLAN_VERSION = "otc.portable-temporal-plan/v1"
_FIELDS = (
    "protocol",
    "message_id",
    "session_id",
    "operation",
    "connector",
    "capability_version",
    "resource_limits",
    "credential_reference",
    "payload",
    "artifact_references",
)
_CONNECTOR_FIELDS = ("id", "version", "contract_version")


class ProcessOperation(StrEnum):
    HELLO = "hello"
    DESCRIBE = "describe"
    EXECUTE = "execute"
    STAGE = "stage"
    COMMIT = "commit"
    READBACK = "readback"
    ABORT = "abort"
    CANCEL = "cancel"


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _closed_mapping(value: object, fields: tuple[str, ...], name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    unknown = sorted(set(value).difference(fields))
    missing = sorted(set(fields).difference(value))
    if unknown:
        raise ValueError(f"unknown {name} fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing {name} fields: {', '.join(missing)}")
    return dict(value)


def _artifact_from_wire(value: object) -> ArrowArtifactReference:
    item = _closed_mapping(
        value,
        ("relative_path", "sha256", "size_bytes", "media_type"),
        "artifact reference",
    )
    return ArrowArtifactReference(**item)


@dataclass(frozen=True, slots=True)
class ConnectorProcessEnvelope:
    protocol: str
    message_id: str
    session_id: str
    operation: ProcessOperation
    connector: Mapping[str, str]
    capability_version: str
    resource_limits: ResourceBounds
    credential_reference: str | None
    payload: Mapping[str, object]
    artifact_references: tuple[ArrowArtifactReference, ...]

    def __post_init__(self) -> None:
        if self.protocol != PROCESS_PROTOCOL:
            raise ValueError("unsupported connector process protocol")
        object.__setattr__(self, "message_id", _text(self.message_id, "message_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        object.__setattr__(self, "operation", ProcessOperation(self.operation))
        connector = _closed_mapping(self.connector, _CONNECTOR_FIELDS, "connector")
        connector = {
            key: _text(connector[key], f"connector.{key}") for key in _CONNECTOR_FIELDS
        }
        object.__setattr__(self, "connector", MappingProxyType(connector))
        object.__setattr__(
            self,
            "capability_version",
            _text(self.capability_version, "capability_version"),
        )
        if not isinstance(self.resource_limits, ResourceBounds):
            if not isinstance(self.resource_limits, Mapping):
                raise TypeError("resource_limits must be an object")
            object.__setattr__(
                self,
                "resource_limits",
                ResourceBounds(**dict(self.resource_limits)),
            )
        if self.credential_reference is not None:
            object.__setattr__(
                self,
                "credential_reference",
                _text(self.credential_reference, "credential_reference"),
            )
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be an object")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        if not isinstance(self.artifact_references, (tuple, list)):
            raise TypeError("artifact_references must be an array")
        object.__setattr__(
            self,
            "artifact_references",
            tuple(
                item
                if isinstance(item, ArrowArtifactReference)
                else _artifact_from_wire(item)
                for item in self.artifact_references
            ),
        )
        is_response = "ok" in self.payload
        if is_response:
            allowed = {"ok", "result", "error"}
            unknown = set(self.payload).difference(allowed)
            if unknown:
                raise ValueError(f"unknown response payload fields: {', '.join(sorted(unknown))}")
            if not isinstance(self.payload["ok"], bool):
                raise TypeError("response ok must be a boolean")
            if self.payload["ok"] and "result" not in self.payload:
                raise ValueError("successful response requires result")
            if not self.payload["ok"] and "error" not in self.payload:
                raise ValueError("failed response requires error")
        elif self.operation is ProcessOperation.EXECUTE:
            required = {"target", "portable_plan"}
            missing = required.difference(self.payload)
            unknown = set(self.payload).difference(required | {"snapshot_reference", "capability"})
            if missing:
                raise ValueError(f"execute payload is missing: {', '.join(sorted(missing))}")
            if unknown:
                raise ValueError(
                    f"unknown execute payload fields: {', '.join(sorted(unknown))}"
                )
            if not isinstance(self.payload["portable_plan"], Mapping):
                raise TypeError("portable_plan must be an object")

    def to_wire(self) -> dict[str, object]:
        return {
            "protocol": self.protocol,
            "message_id": self.message_id,
            "session_id": self.session_id,
            "operation": self.operation.value,
            "connector": dict(self.connector),
            "capability_version": self.capability_version,
            "resource_limits": self.resource_limits.to_wire(),
            "credential_reference": self.credential_reference,
            "payload": dict(self.payload),
            "artifact_references": [item.to_wire() for item in self.artifact_references],
        }

    @classmethod
    def from_wire(cls, value: object) -> ConnectorProcessEnvelope:
        """Deprecated alias for request decoding."""
        return cls.from_request_wire(value)

    @classmethod
    def from_request_wire(cls, value: object) -> ConnectorProcessEnvelope:
        return cls._from_wire(value, response=False)

    @classmethod
    def from_response_wire(cls, value: object) -> ConnectorProcessEnvelope:
        return cls._from_wire(value, response=True)

    @classmethod
    def _from_wire(cls, value: object, *, response: bool) -> ConnectorProcessEnvelope:
        item = _closed_mapping(value, _FIELDS, "envelope")
        payload = item.get("payload")
        if not isinstance(payload, Mapping):
            raise TypeError("envelope payload must be an object")
        if response and "ok" not in payload:
            raise ValueError("response payload requires ok")
        if not response and "ok" in payload:
            raise ValueError("request payload cannot contain ok")
        return cls(**item)


__all__ = [
    "ConnectorProcessEnvelope",
    "PORTABLE_PLAN_VERSION",
    "PROCESS_PROTOCOL",
    "ProcessOperation",
]
