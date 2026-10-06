"""Provider-neutral rich object requests and qualification evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, bytearray):
        return bytes(value)
    return value


_OPTION_KEYS = {
    "image.insert": frozenset({"content", "mime_type", "anchor", "sha256"}),
    "image.read": frozenset({"picture_id"}),
    "image.delete": frozenset({"picture_id", "index"}),
    "image.list": frozenset(),
}


@dataclass(frozen=True, slots=True)
class RichObjectRequest:
    operation_id: str
    target_key: str
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id.strip():
            raise ValueError("operation_id must be a non-empty string")
        if not isinstance(self.target_key, str) or not self.target_key.strip():
            raise ValueError("target_key must be a non-empty string")
        if not isinstance(self.arguments, Mapping):
            raise TypeError("arguments must be a mapping")
        allowed = _OPTION_KEYS.get(self.operation_id)
        if allowed is not None and any(key not in allowed for key in self.arguments):
            raise ValueError("unknown rich object option")
        object.__setattr__(self, "arguments", _freeze(self.arguments))

    def to_change(self):
        from ._operations import Change
        from .capabilities import ALL_CAPABILITIES

        capability_id = "spreadsheet." + self.operation_id
        capability = next((item for item in ALL_CAPABILITIES if item.capability_id == capability_id), None)
        if capability is None:
            from open_table_connector.contract import CapabilityIdentity

            capability = CapabilityIdentity(capability_id, "1.0")
        return Change(self.operation_id, capability, self.target_key, dict(self.arguments))


@dataclass(frozen=True, slots=True)
class ObjectObservation:
    object_id: str
    kind: str
    fields: Mapping[str, object]
    coverage: tuple[str, ...]
    content_hash: str | None = None

    def __post_init__(self) -> None:
        for name in ("object_id", "kind"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be a non-empty string")
        object.__setattr__(self, "fields", _freeze(self.fields))
        object.__setattr__(self, "coverage", tuple(str(item) for item in self.coverage))


@dataclass(frozen=True, slots=True)
class RichQualification:
    provider_id: str
    operation_id: str
    options_schema: Mapping[str, object]
    status: str
    evidence: tuple[str, ...]
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"qualified", "blocked"}:
            raise ValueError("status must be qualified or blocked")
        object.__setattr__(self, "options_schema", _freeze(self.options_schema))
        object.__setattr__(self, "evidence", tuple(str(item) for item in self.evidence))


_QUALIFICATIONS = {
    ("local_files", "image.insert"): RichQualification("local_files", "image.insert", {"type": "object"}, "qualified", ("local image roundtrip",)),
    ("maybe_sheet", "image.insert"): RichQualification("maybe_sheet", "image.insert", {"type": "object"}, "blocked", (), "live disposable evidence required"),
    ("maybe_sheet", "chart.create"): RichQualification("maybe_sheet", "chart.create", {"type": "object"}, "blocked", (), "no admitted protocol operation"),
}


def qualification(provider_id: str, operation_id: str) -> RichQualification:
    return _QUALIFICATIONS.get(
        (provider_id, operation_id),
        RichQualification(provider_id, operation_id, {"type": "object"}, "blocked", (), "operation is not qualified"),
    )


__all__ = ["ObjectObservation", "RichObjectRequest", "RichQualification", "qualification"]
