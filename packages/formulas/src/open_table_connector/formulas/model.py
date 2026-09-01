"""Immutable formula targets and expressions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from open_table_connector.contract import TableURI

from .capabilities import FORMULA_DIALECTS

_MAX_FORMULA_BYTES = 1024 * 1024
_TTable = TypeVar("_TTable")


def _normalize_optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string when provided")
    return value.strip()


def _require_exactly_one(name: str | None, stable_id: str | None, *, label: str) -> None:
    if (name is None) == (stable_id is None):
        raise ValueError(f"{label} requires exactly one of name or stable ID")


@dataclass(frozen=True, slots=True)
class FormulaResourceLimits:
    max_cells: int | None = None
    max_records: int | None = None
    max_response_bytes: int | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class WorksheetRef:
    name: str | None = None
    worksheet_id: str | None = None

    def __post_init__(self) -> None:
        normalized_name = _normalize_optional_text(self.name, "name")
        normalized_id = _normalize_optional_text(self.worksheet_id, "worksheet_id")
        _require_exactly_one(normalized_name, normalized_id, label="WorksheetRef")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "worksheet_id", normalized_id)


@dataclass(frozen=True, slots=True)
class FieldRef:
    name: str | None = None
    field_id: str | None = None

    def __post_init__(self) -> None:
        normalized_name = _normalize_optional_text(self.name, "name")
        normalized_id = _normalize_optional_text(self.field_id, "field_id")
        _require_exactly_one(normalized_name, normalized_id, label="FieldRef")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "field_id", normalized_id)


@dataclass(frozen=True, slots=True)
class FormulaExpression:
    text: str
    dialect: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if not self.text.strip():
            raise ValueError("text must not be blank")
        if self.dialect not in FORMULA_DIALECTS:
            raise ValueError("dialect must be one of FORMULA_DIALECTS")
        payload = self.text.encode("utf-8")
        if len(payload) > _MAX_FORMULA_BYTES:
            raise ValueError("text must be at most 1 MiB encoded as UTF-8")

    @property
    def sha256(self) -> str:
        return f"sha256:{hashlib.sha256(self.text.encode('utf-8')).hexdigest()}"

    @property
    def byte_count(self) -> int:
        return len(self.text.encode("utf-8"))

    def __repr__(self) -> str:
        return (
            "FormulaExpression("
            f"dialect={self.dialect!r}, "
            f"byte_count={self.byte_count}, "
            f"sha256={self.sha256!r})"
        )


@dataclass(frozen=True, slots=True)
class GridFormulaTarget:
    grid: TableURI | str
    worksheet: WorksheetRef

    def __post_init__(self) -> None:
        object.__setattr__(self, "grid", TableURI(self.grid))


@dataclass(frozen=True, slots=True)
class BoundGridFormulaTarget:
    grid: TableURI | str
    worksheet: WorksheetRef

    def __post_init__(self) -> None:
        object.__setattr__(self, "grid", TableURI(self.grid))
        if self.worksheet.worksheet_id is None:
            raise ValueError("BoundGridFormulaTarget requires a stable worksheet ID")


@dataclass(frozen=True, slots=True)
class FieldFormulaTarget(Generic[_TTable]):
    table: _TTable
    field: FieldRef


@dataclass(frozen=True, slots=True)
class BoundFieldFormulaTarget(Generic[_TTable]):
    table: _TTable
    field: FieldRef

    def __post_init__(self) -> None:
        if self.field.field_id is None:
            raise ValueError("BoundFieldFormulaTarget requires a stable field ID")


class GridRecalculationScope(StrEnum):
    RANGE = "range"
    WORKSHEET = "worksheet"
    WORKBOOK = "workbook"


class FieldRecalculationScope(StrEnum):
    FIELD = "field"
    TABLE = "table"


__all__ = [
    "BoundFieldFormulaTarget",
    "BoundGridFormulaTarget",
    "FieldFormulaTarget",
    "FieldRecalculationScope",
    "FieldRef",
    "FormulaExpression",
    "FormulaResourceLimits",
    "GridFormulaTarget",
    "GridRecalculationScope",
    "WorksheetRef",
]
