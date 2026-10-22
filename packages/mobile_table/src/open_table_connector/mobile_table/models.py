from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

FieldType = Literal["string", "integer", "number", "boolean", "date", "datetime", "unknown"]
Support = Literal["supported", "unsupported", "unknown"]
Outcome = Literal["succeeded", "rejected", "failed", "partial", "unknown", "planned"]
Commit = Literal["not_applicable", "not_started", "not_committed", "committed", "partial", "unknown"]
Verification = Literal["passed", "failed", "skipped", "unavailable", "not_applicable"]


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return {str(key): item for key, item in value.items()}


_SECRET_KEY = re.compile(r"(?:token|secret|password|passwd|authorization|cookie|api[_-]?key|credential)", re.IGNORECASE)


def _safe_details(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("error details must be an object")

    def clean(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {str(key): clean(child) for key, child in item.items() if not _SECRET_KEY.search(str(key))}
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            return [clean(child) for child in item]
        if item is None or isinstance(item, (str, bool, int)):
            return item
        if isinstance(item, float) and math.isfinite(item):
            return item
        raise TypeError("error details must contain only JSON values")

    return clean(value)


def _tuple_strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be an array")
    return tuple(_text(item, name) for item in value)


@dataclass(frozen=True, slots=True)
class MobileField:
    id: str
    label: str
    type: FieldType
    nullable: bool
    editable: bool
    read_only_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "field id"))
        object.__setattr__(self, "label", _text(self.label, "field label"))
        if self.type not in {"string", "integer", "number", "boolean", "date", "datetime", "unknown"}:
            raise ValueError("field type is unsupported")
        if not isinstance(self.nullable, bool) or not isinstance(self.editable, bool):
            raise TypeError("field nullable and editable must be boolean")
        if self.read_only_reason is not None:
            object.__setattr__(self, "read_only_reason", _text(self.read_only_reason, "read_only_reason"))

    def to_wire(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "nullable": self.nullable,
            "editable": self.editable,
            "read_only_reason": self.read_only_reason,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> MobileField:
        item = _mapping(payload, "field")
        return cls(
            id=item["id"],
            label=item["label"],
            type=item["type"],
            nullable=item["nullable"],
            editable=item["editable"],
            read_only_reason=item.get("read_only_reason"),
        )


@dataclass(frozen=True, slots=True)
class MobileRecord:
    record_id: str
    record_revision: str
    values: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _text(self.record_id, "record_id"))
        object.__setattr__(self, "record_revision", _text(self.record_revision, "record_revision"))
        object.__setattr__(self, "values", _safe_details(self.values))

    def to_wire(self) -> dict[str, Any]:
        return {"record_id": self.record_id, "record_revision": self.record_revision, "values": dict(self.values)}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> MobileRecord:
        item = _mapping(payload, "record")
        return cls(item["record_id"], item["record_revision"], item["values"])


@dataclass(frozen=True, slots=True)
class MobileError:
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _text(self.code, "error code"))
        object.__setattr__(self, "message", _text(self.message, "error message"))
        object.__setattr__(self, "details", _safe_details(self.details))

    def to_wire(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": dict(self.details)}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> MobileError:
        item = _mapping(payload, "error")
        return cls(item["code"], item["message"], item.get("details", {}))


@dataclass(frozen=True, slots=True)
class MobileCapabilities:
    contract: str
    request_id: str
    table_uri: str
    capability: str
    read: Mapping[str, Any]
    record_update: Mapping[str, Any]
    limits: Mapping[str, Any]
    source: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("read", "record_update", "limits", "source"):
            object.__setattr__(self, name, _safe_details(getattr(self, name)))

    def to_wire(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "request_id": self.request_id,
            "table_uri": self.table_uri,
            "capability": self.capability,
            "read": dict(self.read),
            "record_update": dict(self.record_update),
            "limits": dict(self.limits),
            "source": dict(self.source),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> MobileCapabilities:
        item = _mapping(payload, "capabilities")
        return cls(
            contract=_text(item["contract"], "contract"),
            request_id=_text(item["request_id"], "request_id"),
            table_uri=_text(item["table_uri"], "table_uri"),
            capability=_text(item["capability"], "capability"),
            read=_mapping(item["read"], "read"),
            record_update=_mapping(item["record_update"], "record_update"),
            limits=_mapping(item["limits"], "limits"),
            source=_mapping(item["source"], "source"),
        )


@dataclass(frozen=True, slots=True)
class MobileInspection:
    table_uri: str
    mode: str
    schema_fingerprint: str
    row_count: int
    source_revision: str
    coordinate_convention: Mapping[str, Any]
    fields: tuple[MobileField, ...]
    contract: str = "otc.mobile.table/1.0"
    request_id: str = "inspection"

    def __post_init__(self) -> None:
        for name in ("table_uri", "mode", "schema_fingerprint", "source_revision", "contract", "request_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if isinstance(self.row_count, bool) or not isinstance(self.row_count, int) or self.row_count < 0:
            raise ValueError("row_count must be a non-negative integer")
        object.__setattr__(self, "coordinate_convention", _safe_details(self.coordinate_convention))
        object.__setattr__(self, "fields", tuple(self.fields))

    def to_wire(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "request_id": self.request_id,
            "table_uri": self.table_uri,
            "mode": self.mode,
            "schema_fingerprint": self.schema_fingerprint,
            "row_count": self.row_count,
            "source_revision": self.source_revision,
            "coordinate_convention": dict(self.coordinate_convention),
            "fields": [field.to_wire() for field in self.fields],
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> MobileInspection:
        item = _mapping(payload, "inspection")
        return cls(
            table_uri=item["table_uri"],
            mode=item["mode"],
            schema_fingerprint=item["schema_fingerprint"],
            row_count=item["row_count"],
            source_revision=item["source_revision"],
            coordinate_convention=item["coordinate_convention"],
            fields=tuple(MobileField.from_wire(field) for field in item["fields"]),
            contract=item.get("contract", "otc.mobile.table/1.0"),
            request_id=item.get("request_id", "inspection"),
        )


@dataclass(frozen=True, slots=True)
class MobileReadPage:
    table_uri: str
    mode: str
    source_revision: str
    fields: tuple[MobileField, ...]
    rows: tuple[MobileRecord, ...]
    next_page_token: str | None
    contract: str = "otc.mobile.table/1.0"
    request_id: str = "read"

    def __post_init__(self) -> None:
        for name in ("table_uri", "mode", "source_revision", "contract", "request_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.next_page_token is not None:
            object.__setattr__(self, "next_page_token", _text(self.next_page_token, "next_page_token"))
        object.__setattr__(self, "fields", tuple(self.fields))
        object.__setattr__(self, "rows", tuple(self.rows))

    def to_wire(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "request_id": self.request_id,
            "table_uri": self.table_uri,
            "mode": self.mode,
            "source_revision": self.source_revision,
            "fields": [field.to_wire() for field in self.fields],
            "rows": [row.to_wire() for row in self.rows],
            "next_page_token": self.next_page_token,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> MobileReadPage:
        item = _mapping(payload, "read page")
        return cls(
            table_uri=item["table_uri"],
            mode=item["mode"],
            source_revision=item["source_revision"],
            fields=tuple(MobileField.from_wire(field) for field in item["fields"]),
            rows=tuple(MobileRecord.from_wire(row) for row in item["rows"]),
            next_page_token=item.get("next_page_token"),
            contract=item.get("contract", "otc.mobile.table/1.0"),
            request_id=item.get("request_id", "read"),
        )


@dataclass(frozen=True, slots=True)
class MobileUpdateResult:
    contract: str
    request_id: str
    operation_id: str | None
    outcome: Outcome
    commit: Commit
    verification: Verification
    table_revision: str | None
    record: MobileRecord | None
    receipts: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract", _text(self.contract, "contract"))
        object.__setattr__(self, "request_id", _text(self.request_id, "request_id"))
        if self.operation_id is not None:
            object.__setattr__(self, "operation_id", _text(self.operation_id, "operation_id"))
        for name, values in {
            "outcome": {"succeeded", "rejected", "failed", "partial", "unknown", "planned"},
            "commit": {"not_applicable", "not_started", "not_committed", "committed", "partial", "unknown"},
            "verification": {"passed", "failed", "skipped", "unavailable", "not_applicable"},
        }.items():
            if getattr(self, name) not in values:
                raise ValueError(f"invalid {name} state")
        if self.table_revision is not None:
            object.__setattr__(self, "table_revision", _text(self.table_revision, "table_revision"))
        object.__setattr__(self, "receipts", tuple(_safe_details(receipt) for receipt in self.receipts))

    def to_wire(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "outcome": self.outcome,
            "commit": self.commit,
            "verification": self.verification,
            "table_revision": self.table_revision,
            "record": None if self.record is None else self.record.to_wire(),
            "receipts": [dict(receipt) for receipt in self.receipts],
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> MobileUpdateResult:
        item = _mapping(payload, "update result")
        if "error" in item:
            raise ValueError("update error envelope is not an update result")
        record = item.get("record")
        return cls(
            contract=item["contract"],
            request_id=item["request_id"],
            operation_id=item.get("operation_id"),
            outcome=item["outcome"],
            commit=item["commit"],
            verification=item["verification"],
            table_revision=item.get("table_revision"),
            record=None if record is None else MobileRecord.from_wire(record),
            receipts=tuple(item.get("receipts", ())),
        )
