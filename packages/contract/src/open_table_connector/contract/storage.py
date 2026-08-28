"""Separate neutral physical storage capability; not a Dataset Store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import polars as pl

from .receipts import NeutralReceipt
from .uri import TableURI


@dataclass(frozen=True)
class TableWriteRequest:
    uri: TableURI
    frame: pl.DataFrame
    if_exists: str = "error"
    table: str | None = None


@dataclass(frozen=True)
class TableWriteResult:
    receipt: NeutralReceipt
    affected_rows: int


@runtime_checkable
class TableWriter(Protocol):
    def write(self, request: TableWriteRequest) -> TableWriteResult: ...


@runtime_checkable
class TransactionalStore(Protocol):
    def begin(self, uri: TableURI) -> None: ...

    def commit(self) -> None: ...

    def abort(self) -> None: ...
