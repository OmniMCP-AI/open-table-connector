"""Shared portable create-only materialization contract."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import polars as pl
from open_table_connector.contract import (
    CAPABILITY_TABLE_MATERIALIZE_CREATE,
    CapabilityIdentity,
)

from .model import TableDestination

PORTABLE_TABLE_PROFILE_V1 = "otc.portable-table/v1"
MATERIALIZE_CREATE_CAPABILITY = CapabilityIdentity(CAPABILITY_TABLE_MATERIALIZE_CREATE, "1.0")
_DECIMAL = re.compile(r"^Decimal\(precision=(\d+), scale=(\d+)\)$")


def _canonical(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("portable profile rejects non-finite Float64 values")
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise ValueError(f"portable profile cannot fingerprint {type(value).__name__} values")


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _validate_schema(frame: pl.DataFrame) -> None:
    if not frame.columns or any(not isinstance(name, str) or not name.strip() for name in frame.columns):
        raise ValueError("portable profile requires non-empty field names")
    if len(set(frame.columns)) != len(frame.columns):
        raise ValueError("portable profile requires unique field names")
    for name, dtype in frame.schema.items():
        rendered = str(dtype)
        allowed = rendered in {"String", "Boolean", "Int64", "Float64", "Date"}
        allowed = allowed or _DECIMAL.fullmatch(rendered) is not None
        allowed = allowed or (rendered.startswith("Datetime(") and "time_zone='UTC'" in rendered and "time_unit='us'" in rendered)
        if not allowed:
            raise ValueError(f"portable profile does not support dtype {rendered} for field {name}")
        if rendered == "Float64" and not frame.get_column(name).is_finite().fill_null(True).all():
            raise ValueError(f"portable profile rejects non-finite Float64 values for field {name}")


def validate_portable_frame(frame: pl.DataFrame) -> None:
    if not isinstance(frame, pl.DataFrame):
        raise TypeError("portable materialization source must be a polars DataFrame")
    _validate_schema(frame)


@dataclass(frozen=True, slots=True)
class MaterializationRequest:
    source: pl.DataFrame
    destination: TableDestination
    profile: str
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.profile != PORTABLE_TABLE_PROFILE_V1:
            raise ValueError(f"unsupported materialization profile: {self.profile!r}")
        if not isinstance(self.idempotency_key, str) or not self.idempotency_key.strip():
            raise ValueError("idempotency_key must be a non-empty string")
        key = self.idempotency_key.strip()
        if len(key) > 256 or re.search(r"(?i)(bearer|token|secret|password|api[_-]?key)", key):
            raise ValueError("idempotency_key must be non-secret")
        if not isinstance(self.destination, tuple(TableDestination.__args__)):
            raise TypeError("destination must be a TableDestination")
        validate_portable_frame(self.source)
        object.__setattr__(self, "source", self.source.clone())
        object.__setattr__(self, "idempotency_key", key)

    @property
    def row_count(self) -> int:
        return self.source.height

    @property
    def schema_fingerprint(self) -> str:
        return _digest({"profile": self.profile, "fields": [{"name": name, "dtype": str(dtype)} for name, dtype in self.source.schema.items()]})

    @property
    def content_fingerprint(self) -> str:
        return _digest({"schema_fingerprint": self.schema_fingerprint, "rows": [[_canonical(value) for value in row] for row in self.source.iter_rows()]})


__all__ = [
    "MATERIALIZE_CREATE_CAPABILITY",
    "PORTABLE_TABLE_PROFILE_V1",
    "MaterializationRequest",
    "validate_portable_frame",
]
