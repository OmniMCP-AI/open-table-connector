"""Capability-specific Arrow and Polars table readers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import polars as pl
import pyarrow as pa

from .receipts import NeutralReceipt
from .resolve import ResourceLimits
from .uri import TableURI


@dataclass(frozen=True)
class TableReadRequest:
    uri: TableURI
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)


@dataclass(frozen=True)
class ArrowReadResult:
    table: pa.Table
    receipt: NeutralReceipt


@dataclass(frozen=True)
class PolarsReadResult:
    frame: pl.DataFrame
    receipt: NeutralReceipt


@runtime_checkable
class ArrowTableReader(Protocol):
    def read_arrow(self, request: TableReadRequest) -> ArrowReadResult: ...


@runtime_checkable
class PolarsTableReader(Protocol):
    def read_polars(self, request: TableReadRequest) -> PolarsReadResult: ...

