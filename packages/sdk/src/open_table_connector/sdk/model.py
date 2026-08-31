"""SDK model types."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeAlias

import polars as pl
from open_table_connector.contract import TableURI

_CELL_RANGE = re.compile(r"^[A-Z]+[1-9]\d*(?::[A-Z]+[1-9]\d*)?$")
_DECIMAL = re.compile(r"^Decimal\(precision=(\d+), scale=(\d+)\)$")
_DATETIME = re.compile(r"^Datetime\(time_unit='([^']+)', time_zone=(None|'[^']*')\)$")
_DURATION = re.compile(r"^Duration\(time_unit='([^']+)'\)$")
_ARRAY = re.compile(r"^Array\((.+), shape=(\d+)\)$")
_LIST = re.compile(r"^List\((.+)\)$")

_DTYPES_BY_NAME = {
    "Binary": pl.Binary,
    "Boolean": pl.Boolean,
    "Date": pl.Date,
    "Float32": pl.Float32,
    "Float64": pl.Float64,
    "Int8": pl.Int8,
    "Int16": pl.Int16,
    "Int32": pl.Int32,
    "Int64": pl.Int64,
    "Null": pl.Null,
    "String": pl.String,
    "Time": pl.Time,
    "UInt8": pl.UInt8,
    "UInt16": pl.UInt16,
    "UInt32": pl.UInt32,
    "UInt64": pl.UInt64,
}


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalize_uri(value: TableURI | str, field_name: str) -> TableURI:
    if isinstance(value, TableURI):
        return value
    return TableURI(_required_text(value, field_name))


def _closed_wire(payload: Mapping[str, Any], required: set[str], label: str) -> None:
    if set(payload) != required:
        missing = sorted(required.difference(payload))
        extra = sorted(set(payload).difference(required))
        raise ValueError(f"{label} wire keys mismatch; missing={missing}, extra={extra}")


def _schema_to_wire(schema: pl.Schema | None) -> list[dict[str, str]] | None:
    if schema is None:
        return None
    return [{"name": name, "dtype": str(dtype)} for name, dtype in schema.items()]


def _dtype_from_wire(value: str) -> pl.DataType:
    if value in _DTYPES_BY_NAME:
        return _DTYPES_BY_NAME[value]
    if decimal := _DECIMAL.fullmatch(value):
        precision, scale = decimal.groups()
        return pl.Decimal(int(precision), int(scale))
    if datetime := _DATETIME.fullmatch(value):
        time_unit, time_zone = datetime.groups()
        return pl.Datetime(
            time_unit=time_unit,
            time_zone=None if time_zone == "None" else time_zone[1:-1],
        )
    if duration := _DURATION.fullmatch(value):
        return pl.Duration(duration.group(1))
    if list_match := _LIST.fullmatch(value):
        return pl.List(_dtype_from_wire(list_match.group(1)))
    if array_match := _ARRAY.fullmatch(value):
        inner, shape = array_match.groups()
        return pl.Array(_dtype_from_wire(inner), int(shape))
    raise ValueError(f"unsupported schema dtype wire value: {value}")


def _schema_from_wire(payload: list[Mapping[str, Any]] | None) -> pl.Schema | None:
    if payload is None:
        return None
    items: list[tuple[str, pl.DataType]] = []
    for item in payload:
        _closed_wire(item, {"name", "dtype"}, "schema field")
        items.append(
            (
                _required_text(str(item["name"]), "name"),
                _dtype_from_wire(str(item["dtype"])),
            )
        )
    return pl.Schema(items)


class TableMode(StrEnum):
    BASE_MODE = "base-mode"
    SHEET_MODE = "sheet-mode"

    def to_wire(self) -> str:
        return self.value

    @classmethod
    def from_wire(cls, value: str) -> TableMode:
        normalized = _required_text(value, "table mode").casefold()
        if normalized in {"base-mode", "base"}:
            return cls.BASE_MODE
        if normalized in {"sheet-mode", "sheet"}:
            return cls.SHEET_MODE
        raise ValueError("table mode must be base-mode or sheet-mode")


class SchemaPolicy(StrEnum):
    VALIDATE_DECLARED = "validate_declared"
    INFER_COMPLETE = "infer_complete"

    @classmethod
    def from_wire(cls, value: str) -> SchemaPolicy:
        try:
            return cls(_required_text(value, "schema_policy"))
        except ValueError as exc:
            raise ValueError("schema_policy must be validate_declared or infer_complete") from exc


@dataclass(frozen=True, slots=True)
class QualifiedTableName:
    table: str
    schema: str | None = None
    catalog: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "table", _required_text(self.table, "table"))
        if self.schema is not None:
            object.__setattr__(self, "schema", _required_text(self.schema, "schema"))
        if self.catalog is not None:
            object.__setattr__(self, "catalog", _required_text(self.catalog, "catalog"))

    def to_wire(self) -> dict[str, str | None]:
        return {
            "catalog": self.catalog,
            "schema": self.schema,
            "table": self.table,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> QualifiedTableName:
        _closed_wire(payload, {"catalog", "schema", "table"}, "QualifiedTableName")
        return cls(
            catalog=payload["catalog"],
            schema=payload["schema"],
            table=payload["table"],
        )


@dataclass(frozen=True, slots=True)
class DirectTableAddress:
    uri: TableURI | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "uri", _normalize_uri(self.uri, "uri"))

    def to_wire(self) -> dict[str, Any]:
        return {"kind": "direct_table", "uri": self.uri.to_wire()}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> DirectTableAddress:
        _closed_wire(payload, {"kind", "uri"}, "DirectTableAddress")
        if payload["kind"] != "direct_table":
            raise ValueError("DirectTableAddress kind must be direct_table")
        return cls(uri=TableURI.from_wire(payload["uri"]))


@dataclass(frozen=True, slots=True)
class DatabaseTableAddress:
    database: TableURI | str
    name: QualifiedTableName

    def __post_init__(self) -> None:
        object.__setattr__(self, "database", _normalize_uri(self.database, "database"))
        if not isinstance(self.name, QualifiedTableName):
            raise TypeError("name must be a QualifiedTableName")

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": "database_table",
            "database": self.database.to_wire(),
            "name": self.name.to_wire(),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> DatabaseTableAddress:
        _closed_wire(payload, {"kind", "database", "name"}, "DatabaseTableAddress")
        if payload["kind"] != "database_table":
            raise ValueError("DatabaseTableAddress kind must be database_table")
        return cls(
            database=TableURI.from_wire(payload["database"]),
            name=QualifiedTableName.from_wire(payload["name"]),
        )


@dataclass(frozen=True, slots=True)
class BaseModeTableAddress:
    container: TableURI | str
    table_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "container", _normalize_uri(self.container, "container"))
        object.__setattr__(self, "table_id", _required_text(self.table_id, "table_id"))

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": "base-mode-table",
            "container": self.container.to_wire(),
            "table_id": self.table_id,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> BaseModeTableAddress:
        _closed_wire(payload, {"kind", "container", "table_id"}, "BaseModeTableAddress")
        if payload["kind"] != "base-mode-table":
            raise ValueError("BaseModeTableAddress kind must be base-mode-table")
        return cls(
            container=TableURI.from_wire(payload["container"]),
            table_id=payload["table_id"],
        )


@dataclass(frozen=True, slots=True)
class SheetModeTableAddress:
    grid: TableURI | str
    table_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "grid", _normalize_uri(self.grid, "grid"))
        object.__setattr__(self, "table_id", _required_text(self.table_id, "table_id"))

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": "sheet-mode-table",
            "grid": self.grid.to_wire(),
            "table_id": self.table_id,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> SheetModeTableAddress:
        _closed_wire(payload, {"kind", "grid", "table_id"}, "SheetModeTableAddress")
        if payload["kind"] != "sheet-mode-table":
            raise ValueError("SheetModeTableAddress kind must be sheet-mode-table")
        return cls(grid=TableURI.from_wire(payload["grid"]), table_id=payload["table_id"])


@dataclass(frozen=True, slots=True)
class DirectDestination:
    uri: TableURI | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "uri", _normalize_uri(self.uri, "uri"))

    def to_wire(self) -> dict[str, Any]:
        return {"kind": "direct-destination", "uri": self.uri.to_wire()}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> DirectDestination:
        _closed_wire(payload, {"kind", "uri"}, "DirectDestination")
        if payload["kind"] != "direct-destination":
            raise ValueError("DirectDestination kind must be direct-destination")
        return cls(uri=TableURI.from_wire(payload["uri"]))


@dataclass(frozen=True, slots=True)
class BaseModeDestination:
    container: TableURI | str
    table_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "container", _normalize_uri(self.container, "container"))
        object.__setattr__(self, "table_name", _required_text(self.table_name, "table_name"))

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": "base-mode-destination",
            "container": self.container.to_wire(),
            "table_name": self.table_name,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> BaseModeDestination:
        _closed_wire(payload, {"kind", "container", "table_name"}, "BaseModeDestination")
        if payload["kind"] != "base-mode-destination":
            raise ValueError("BaseModeDestination kind must be base-mode-destination")
        return cls(
            container=TableURI.from_wire(payload["container"]),
            table_name=payload["table_name"],
        )


@dataclass(frozen=True, slots=True)
class SheetModeDestination:
    grid: TableURI | str
    anchor: str
    header: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "grid", _normalize_uri(self.grid, "grid"))
        object.__setattr__(self, "anchor", _required_text(self.anchor, "anchor"))
        if not isinstance(self.header, bool):
            raise TypeError("header must be a bool")

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": "sheet-mode-destination",
            "grid": self.grid.to_wire(),
            "anchor": self.anchor,
            "header": self.header,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> SheetModeDestination:
        _closed_wire(payload, {"kind", "grid", "anchor", "header"}, "SheetModeDestination")
        if payload["kind"] != "sheet-mode-destination":
            raise ValueError("SheetModeDestination kind must be sheet-mode-destination")
        return cls(
            grid=TableURI.from_wire(payload["grid"]),
            anchor=payload["anchor"],
            header=payload["header"],
        )


@dataclass(frozen=True, slots=True)
class SheetRangeSource:
    grid: TableURI | str
    cell_range: str
    header: bool
    schema: pl.Schema | None
    schema_policy: SchemaPolicy
    observed_revision: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "grid", _normalize_uri(self.grid, "grid"))
        cell_range = _required_text(self.cell_range, "cell_range").upper()
        if _CELL_RANGE.fullmatch(cell_range) is None:
            raise ValueError("cell_range must be an A1-style range")
        object.__setattr__(self, "cell_range", cell_range)
        if not isinstance(self.header, bool):
            raise TypeError("header must be a bool")
        object.__setattr__(self, "schema_policy", SchemaPolicy(self.schema_policy))
        if self.schema is not None and not isinstance(self.schema, pl.Schema):
            object.__setattr__(self, "schema", pl.Schema(self.schema))
        if self.schema_policy is SchemaPolicy.VALIDATE_DECLARED and self.schema is None:
            raise ValueError("validate_declared requires schema")
        if self.schema_policy is SchemaPolicy.INFER_COMPLETE and self.schema is not None:
            raise ValueError("infer_complete requires schema=None")
        if self.observed_revision is not None:
            object.__setattr__(
                self,
                "observed_revision",
                _required_text(self.observed_revision, "observed_revision"),
            )

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": "sheet-range-source",
            "grid": self.grid.to_wire(),
            "cell_range": self.cell_range,
            "header": self.header,
            "schema": _schema_to_wire(self.schema),
            "schema_policy": self.schema_policy.value,
            "observed_revision": self.observed_revision,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> SheetRangeSource:
        _closed_wire(
            payload,
            {
                "kind",
                "grid",
                "cell_range",
                "header",
                "schema",
                "schema_policy",
                "observed_revision",
            },
            "SheetRangeSource",
        )
        if payload["kind"] != "sheet-range-source":
            raise ValueError("SheetRangeSource kind must be sheet-range-source")
        return cls(
            grid=TableURI.from_wire(payload["grid"]),
            cell_range=payload["cell_range"],
            header=payload["header"],
            schema=_schema_from_wire(payload["schema"]),
            schema_policy=SchemaPolicy.from_wire(payload["schema_policy"]),
            observed_revision=payload["observed_revision"],
        )


ExistingTableAddress: TypeAlias = (
    DirectTableAddress | DatabaseTableAddress | BaseModeTableAddress | SheetModeTableAddress
)
TableDestination: TypeAlias = DirectDestination | BaseModeDestination | SheetModeDestination


__all__ = [
    "BaseModeDestination",
    "BaseModeTableAddress",
    "DatabaseTableAddress",
    "DirectDestination",
    "DirectTableAddress",
    "ExistingTableAddress",
    "QualifiedTableName",
    "SchemaPolicy",
    "SheetModeDestination",
    "SheetModeTableAddress",
    "SheetRangeSource",
    "TableDestination",
    "TableMode",
]
