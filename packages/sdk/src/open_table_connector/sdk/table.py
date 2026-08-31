"""Public physical Table types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import polars as pl
from open_table_connector.contract import TableURI

from .model import TableMode

if TYPE_CHECKING:
    from .client import Client


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    capability_ids: tuple[str, ...]
    modes: tuple[TableMode, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(_required_text(item, "capability_id") for item in self.capability_ids)
        if len(set(normalized)) != len(normalized):
            raise ValueError("capability_ids must be unique")
        object.__setattr__(self, "capability_ids", normalized)
        object.__setattr__(
            self, "modes", tuple(TableMode.from_wire(str(mode)) for mode in self.modes)
        )

    def supports(self, capability_id: str) -> bool:
        return _required_text(capability_id, "capability_id") in self.capability_ids


@dataclass(frozen=True, slots=True)
class TableBinding:
    uri: TableURI
    mode: TableMode
    schema: pl.Schema
    observed_revision: str | None
    connector_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", TableMode.from_wire(str(self.mode)))
        if not isinstance(self.schema, pl.Schema):
            object.__setattr__(self, "schema", pl.Schema(self.schema))
        if self.observed_revision is not None:
            object.__setattr__(
                self,
                "observed_revision",
                _required_text(self.observed_revision, "observed_revision"),
            )
        object.__setattr__(self, "connector_id", _required_text(self.connector_id, "connector_id"))


@dataclass(frozen=True, slots=True)
class TableInspection:
    uri: TableURI
    mode: TableMode
    schema: pl.Schema
    row_count: int | None = None
    observed_revision: str | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", TableMode.from_wire(str(self.mode)))
        if not isinstance(self.schema, pl.Schema):
            object.__setattr__(self, "schema", pl.Schema(self.schema))
        if self.row_count is not None and self.row_count < 0:
            raise ValueError("row_count must be non-negative")
        if self.observed_revision is not None:
            object.__setattr__(
                self,
                "observed_revision",
                _required_text(self.observed_revision, "observed_revision"),
            )
        object.__setattr__(self, "facts", dict(self.facts))


class TableTransaction:
    def __init__(self, table: Table, transaction: object) -> None:
        self._table = table
        self._transaction = transaction

    def insert(self, frame: pl.DataFrame):
        self._table._client._assert_open()
        return self._table._client._deliver(self._transaction.insert(frame))

    def update(self, frame: pl.DataFrame, *, keys: tuple[str, ...]):
        self._table._client._assert_open()
        return self._table._client._deliver(self._transaction.update(frame, keys=keys))

    def delete(self, *, where, parameters: Mapping[str, Any] | None = None):
        self._table._client._assert_open()
        return self._table._client._deliver(
            self._transaction.delete(
                where=where, parameters=None if parameters is None else dict(parameters)
            )
        )

    def commit(self):
        self._table._client._assert_open()
        return self._table._client._deliver(self._transaction.commit())

    def abort(self):
        self._table._client._assert_open()
        return self._table._client._deliver(self._transaction.abort())


class Table:
    def __init__(self, client: Client, binding: TableBinding) -> None:
        self._client = client
        self._binding = binding

    @property
    def uri(self) -> TableURI:
        return self._binding.uri

    @property
    def mode(self) -> TableMode:
        return self._binding.mode

    @property
    def schema(self) -> pl.Schema:
        return self._binding.schema

    @property
    def observed_revision(self) -> str | None:
        return self._binding.observed_revision

    @property
    def connector_id(self) -> str:
        return self._binding.connector_id

    def inspect(self):
        self._client._assert_open()
        return self._client._deliver(
            self._client._connector_for_binding(self._binding).inspect_table(self._binding)
        )

    def capabilities(self):
        self._client._assert_open()
        return self._client._deliver(
            self._client._connector_for_binding(self._binding).capabilities_for(self._binding)
        )

    def read(self):
        self._client._assert_open()
        return self._client._deliver(
            self._client._connector_for_binding(self._binding).read_table(self._binding)
        )

    def read_page(self, *, limit: int, continuation: str | None = None):
        self._client._assert_open()
        return self._client._deliver(
            self._client._connector_for_binding(self._binding).read_table(
                self._binding,
                limit=limit,
                continuation=continuation,
            )
        )

    def insert(self, frame: pl.DataFrame):
        self._client._assert_open()
        return self._client._deliver(
            self._client._connector_for_binding(self._binding).insert_rows(self._binding, frame)
        )

    def update(self, frame: pl.DataFrame, *, keys: tuple[str, ...]):
        self._client._assert_open()
        return self._client._deliver(
            self._client._connector_for_binding(self._binding).update_rows(
                self._binding,
                frame,
                keys=keys,
            )
        )

    def delete(self, *, where, parameters: Mapping[str, Any] | None = None):
        self._client._assert_open()
        return self._client._deliver(
            self._client._connector_for_binding(self._binding).delete_rows(
                self._binding,
                where=where,
                parameters=None if parameters is None else dict(parameters),
            )
        )

    def drop(self):
        self._client._assert_open()
        return self._client._deliver(
            self._client._connector_for_binding(self._binding).drop_table(self._binding)
        )

    def transaction(self) -> TableTransaction:
        self._client._assert_open()
        transaction = self._client._connector_for_binding(self._binding).begin_transaction(
            self._binding
        )
        return TableTransaction(self, transaction)


__all__ = [
    "CapabilitySet",
    "Table",
    "TableBinding",
    "TableInspection",
    "TableTransaction",
]
