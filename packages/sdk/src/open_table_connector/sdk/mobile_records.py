"""Optional record-level update protocol for mobile table clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .result import OperationResult
from .table import TableBinding


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class RecordUpdateRequest:
    record_id: str
    patch: Mapping[str, object]
    expected_table_revision: str
    expected_record_revision: str
    idempotency_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _required_text(self.record_id, "record_id"))
        object.__setattr__(self, "patch", dict(self.patch))
        for name in ("expected_table_revision", "expected_record_revision", "idempotency_key"):
            object.__setattr__(self, name, _required_text(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class RecordUpdateValue:
    record_id: str
    record_revision: str
    table_revision: str
    values: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _required_text(self.record_id, "record_id"))
        object.__setattr__(self, "record_revision", _required_text(self.record_revision, "record_revision"))
        object.__setattr__(self, "table_revision", _required_text(self.table_revision, "table_revision"))
        object.__setattr__(self, "values", dict(self.values))


@runtime_checkable
class RecordUpdater(Protocol):
    def update_record(
        self, binding: TableBinding, request: RecordUpdateRequest
    ) -> OperationResult[RecordUpdateValue]: ...


__all__ = ["RecordUpdateRequest", "RecordUpdateValue", "RecordUpdater"]
