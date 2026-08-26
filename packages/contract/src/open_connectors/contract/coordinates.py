"""The closed Base/Sheet coordinate union."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, TypeAlias

from .scalars import Scalar, scalar_to_wire


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class BaseCoordinate:
    record_id: str | None = None
    key: Mapping[str, Scalar] = field(default_factory=dict)
    ordinal: int | None = None
    snapshot_id: str | None = None

    def __post_init__(self) -> None:
        if self.record_id is not None:
            object.__setattr__(self, "record_id", _text(self.record_id, "record_id"))
        key = dict(self.key)
        if any(not isinstance(name, str) or not name.strip() for name in key):
            raise ValueError("BaseCoordinate key names must be non-empty strings")
        if any(value is None for value in key.values()):
            raise ValueError("BaseCoordinate key values cannot be null")
        object.__setattr__(self, "key", key)
        if self.ordinal is not None:
            if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool) or self.ordinal < 1:
                raise ValueError("BaseCoordinate ordinal must be positive")
            if self.snapshot_id is None:
                raise ValueError("BaseCoordinate ordinal requires a snapshot")
        elif self.snapshot_id is not None:
            raise ValueError("BaseCoordinate snapshot requires an ordinal")
        if self.record_id is None and not key and self.ordinal is None:
            raise ValueError("BaseCoordinate requires record_id, key, or ordinal")
        if self.snapshot_id is not None:
            object.__setattr__(self, "snapshot_id", _text(self.snapshot_id, "snapshot_id"))

    @property
    def identity_kind(self) -> str:
        if self.record_id is not None:
            return "record_id"
        if self.key:
            return "key"
        return "ordinal"

    def to_wire(self) -> dict[str, Any]:
        if self.identity_kind == "record_id":
            return {"record_id": self.record_id}
        if self.identity_kind == "key":
            return {
                "key": {
                    name: scalar_to_wire(value)
                    for name, value in sorted(self.key.items())
                }
            }
        return {"ordinal": self.ordinal, "snapshot_id": self.snapshot_id}


@dataclass(frozen=True)
class SheetCoordinate:
    sheet: str | int
    row: int
    column: str | int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.sheet, str):
            object.__setattr__(self, "sheet", _text(self.sheet, "sheet"))
        elif not isinstance(self.sheet, int) or isinstance(self.sheet, bool):
            raise ValueError("SheetCoordinate sheet must be a non-empty string or integer")
        if not isinstance(self.row, int) or isinstance(self.row, bool) or self.row < 1:
            raise ValueError("SheetCoordinate row must be positive")
        if self.column is not None and isinstance(self.column, str):
            object.__setattr__(self, "column", _text(self.column, "column"))
        elif self.column is not None and (
            not isinstance(self.column, int) or isinstance(self.column, bool)
        ):
            raise ValueError("SheetCoordinate column must be a string or integer")

    def to_wire(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"sheet": self.sheet, "row": self.row}
        if self.column is not None:
            payload["column"] = self.column
        return payload


TableCoordinate: TypeAlias = BaseCoordinate | SheetCoordinate


@dataclass(frozen=True)
class BaseConvention:
    record_id_field: str | None = None
    key_fields: tuple[str, ...] = ()
    ordinal_snapshot_id: str | None = None

    @property
    def mode(self) -> str:
        return "base"

    def __post_init__(self) -> None:
        if self.record_id_field is not None:
            object.__setattr__(self, "record_id_field", _text(self.record_id_field, "record_id_field"))
        fields = tuple(_text(field, "key field") for field in self.key_fields)
        if len(set(fields)) != len(fields):
            raise ValueError("BaseConvention key fields must be unique")
        object.__setattr__(self, "key_fields", fields)
        if self.ordinal_snapshot_id is not None:
            object.__setattr__(
                self,
                "ordinal_snapshot_id",
                _text(self.ordinal_snapshot_id, "ordinal_snapshot_id"),
            )
        if not self.record_id_field and not fields and not self.ordinal_snapshot_id:
            raise ValueError("BaseConvention requires record ID, key, or ordinal identity")


@dataclass(frozen=True)
class SheetConvention:
    sheet: str | int
    header_rows: int = 1
    first_data_row: int = 2

    @property
    def mode(self) -> str:
        return "sheet"

    def __post_init__(self) -> None:
        if isinstance(self.sheet, str):
            object.__setattr__(self, "sheet", _text(self.sheet, "sheet"))
        elif not isinstance(self.sheet, int) or isinstance(self.sheet, bool):
            raise ValueError("SheetConvention sheet must be a string or integer")
        if self.header_rows < 1:
            raise ValueError("SheetConvention header_rows must be positive")
        if self.first_data_row < 1:
            raise ValueError("SheetConvention first_data_row must be positive")
