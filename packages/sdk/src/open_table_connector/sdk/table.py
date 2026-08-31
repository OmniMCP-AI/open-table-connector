"""Public physical Table types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

import polars as pl
from open_table_connector.contract import TableURI

from .model import TableMode
from .result import CommitState, OperationResult, OTCError, Outcome, VerificationState

if TYPE_CHECKING:
    from open_table_connector.timeseries import TemporalTableDescriptor

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
    def __init__(self, table: Table, *, idempotency_key: str | None = None) -> None:
        self._table = table
        self._idempotency_key = idempotency_key
        self._commands: list[tuple[str, object, object]] = []
        self._state = "open"

    def _ensure_open(self) -> None:
        if self._state != "open":
            raise RuntimeError(f"transaction is already {self._state}")

    def insert(self, frame: pl.DataFrame):
        self._ensure_open()
        self._table._client._assert_open()
        if not isinstance(frame, pl.DataFrame):
            raise TypeError("frame must be a polars DataFrame")
        self._commands.append(("insert", frame.clone(), None))
        return self

    def update(self, frame: pl.DataFrame, *, keys: tuple[str, ...]):
        self._ensure_open()
        self._table._client._assert_open()
        if not isinstance(frame, pl.DataFrame):
            raise TypeError("frame must be a polars DataFrame")
        normalized_keys = tuple(str(key).strip() for key in keys)
        if not normalized_keys or any(not key for key in normalized_keys):
            raise ValueError("keys must contain at least one non-empty column name")
        self._commands.append(("update", frame.clone(), normalized_keys))
        return self

    def delete(self, *, where, parameters: Mapping[str, Any] | None = None):
        self._ensure_open()
        self._table._client._assert_open()
        if where is None:
            raise ValueError("where is required")
        self._commands.append(
            ("delete", where, None if parameters is None else dict(parameters))
        )
        return self

    def commit(self):
        self._ensure_open()
        self._table._client._assert_open()
        self._state = "committing"
        connector = self._table._client._connector_for_binding(self._table._binding)
        transaction = None
        receipts = []
        try:
            transaction = connector.begin_transaction(self._table._binding)
            for operation, payload, options in self._commands:
                if operation == "insert":
                    result = transaction.insert(payload)
                elif operation == "update":
                    result = transaction.update(payload, keys=options)
                else:
                    result = transaction.delete(where=payload, parameters=options)
                delivered = self._table._client._deliver(result)
                receipts.extend(delivered.receipts)
            committed = self._table._client._deliver(transaction.commit())
            receipts.extend(committed.receipts)
        except OTCError as error:
            receipts.extend(error.result.receipts)
            if transaction is not None:
                try:
                    aborted = self._table._client._deliver(transaction.abort())
                except OTCError as abort_error:
                    receipts.extend(abort_error.result.receipts)
                else:
                    receipts.extend(aborted.receipts)
            self._state = "aborted"
            failed = replace(error.result, receipts=tuple(receipts))
            message = failed.error.message if failed.error is not None else str(error)
            raise OTCError(message, failed) from error
        except BaseException:
            if transaction is not None:
                try:
                    transaction.abort()
                finally:
                    self._state = "aborted"
            else:
                self._state = "aborted"
            raise
        self._state = "committed"
        return OperationResult(
            value=None,
            outcome=committed.outcome,
            commit=committed.commit,
            verification=committed.verification,
            receipts=tuple(receipts),
            warnings=committed.warnings,
        )

    def abort(self):
        self._ensure_open()
        self._table._client._assert_open()
        self._commands.clear()
        self._state = "aborted"
        return OperationResult(
            value=None,
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.SKIPPED,
            receipts=(),
        )


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
        return self._client._normalize_frame_result(
            self._client._connector_for_binding(self._binding).read_table(self._binding)
        )

    def read_page(self, *, limit: int, continuation: str | None = None):
        self._client._assert_open()
        return self._client._normalize_frame_result(
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

    def transaction(self, *, idempotency_key: str | None = None) -> TableTransaction:
        self._client._assert_open()
        return TableTransaction(self, idempotency_key=idempotency_key)

    def time_series(self, descriptor: TemporalTableDescriptor):
        self._client._assert_open()
        from .temporal import TimeSeriesView

        return TimeSeriesView(self, descriptor)


__all__ = [
    "CapabilitySet",
    "Table",
    "TableBinding",
    "TableInspection",
    "TableTransaction",
]
