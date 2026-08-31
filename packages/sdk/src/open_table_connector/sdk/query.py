"""Deferred query values."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Any

import polars as pl


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


class QueryLane(StrEnum):
    RELATIONAL = "relational"
    TEMPORAL = "temporal"


@dataclass(frozen=True, slots=True)
class SqlResourceLimits:
    max_source_rows: int = 1_000_000
    max_source_bytes: int = 256 * 1024 * 1024
    max_total_input_rows: int = 2_000_000
    max_total_input_bytes: int = 512 * 1024 * 1024
    max_intermediate_rows: int = 2_000_000
    max_intermediate_bytes: int = 512 * 1024 * 1024
    max_output_rows: int = 100_000
    max_output_bytes: int = 128 * 1024 * 1024
    max_duration_ms: int = 30_000

    def __post_init__(self) -> None:
        for field_name in (
            "max_source_rows",
            "max_source_bytes",
            "max_total_input_rows",
            "max_total_input_bytes",
            "max_intermediate_rows",
            "max_intermediate_bytes",
            "max_output_rows",
            "max_output_bytes",
            "max_duration_ms",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")

    def to_wire(self) -> dict[str, int]:
        return asdict(self)


def _canonical_value(value: object) -> object:
    canonical_plan = getattr(value, "canonical_plan", None)
    if callable(canonical_plan):
        return _canonical_value(canonical_plan())
    to_wire = getattr(value, "to_wire", None)
    if callable(to_wire):
        return _canonical_value(to_wire())
    if isinstance(value, pl.Schema):
        return [{"name": name, "dtype": str(dtype)} for name, dtype in value.items()]
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _canonical_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return {"type": f"{type(value).__module__}.{type(value).__qualname__}"}


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze_value(item) for item in value), key=repr))
    return value


def _source_definition(source: object) -> object:
    if isinstance(source, pl.DataFrame):
        return {"kind": "dataframe", "schema": _canonical_value(source.schema)}
    if isinstance(source, Query):
        return {"kind": "query", "definition_hash": source.definition_hash}
    uri = getattr(source, "uri", None)
    schema = getattr(source, "schema", None)
    if uri is not None and schema is not None:
        return {
            "kind": "physical",
            "uri": getattr(uri, "value", str(uri)),
            "schema": _canonical_value(schema),
            "observed_revision": getattr(source, "observed_revision", None),
        }
    return _canonical_value(source)


def _digest(payload: object) -> str:
    encoded = json.dumps(
        _canonical_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class Query:
    lane: QueryLane
    statement: str
    sources: Mapping[str, object]
    parameters: Mapping[str, Any] = field(default_factory=dict)
    limits: object = field(default_factory=SqlResourceLimits)
    _definition: object | None = field(default=None, repr=False, compare=False)
    _plan_hash: str = field(init=False, repr=False, compare=False)
    _definition_hash: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lane", QueryLane(self.lane))
        object.__setattr__(self, "statement", _required_text(self.statement, "statement"))
        normalized_sources = {
            _required_text(name, "source name"): source for name, source in self.sources.items()
        }
        object.__setattr__(self, "sources", MappingProxyType(normalized_sources))
        normalized_parameters = {
            _required_text(name, "parameter name"): _freeze_value(value)
            for name, value in self.parameters.items()
        }
        object.__setattr__(self, "parameters", MappingProxyType(normalized_parameters))
        if self.lane is QueryLane.RELATIONAL and not isinstance(self.limits, SqlResourceLimits):
            raise TypeError("limits must be a SqlResourceLimits")
        canonical_plan_hash = getattr(self._definition, "canonical_plan_hash", None)
        if callable(canonical_plan_hash):
            plan_hash = str(canonical_plan_hash())
        else:
            plan_payload = (
                {"lane": self.lane.value, "statement": " ".join(self.statement.split())}
                if self._definition is None
                else {"lane": self.lane.value, "plan": _canonical_value(self._definition)}
            )
            plan_hash = _digest(plan_payload)
        definition_payload = {
            "plan_hash": plan_hash,
            "sources": [
                {"alias": name, "definition": _source_definition(source)}
                for name, source in normalized_sources.items()
            ],
            "parameters": [
                {"name": name, "type": f"{type(value).__module__}.{type(value).__qualname__}"}
                for name, value in normalized_parameters.items()
            ],
            "limits": _canonical_value(self.limits),
        }
        object.__setattr__(self, "_plan_hash", plan_hash)
        object.__setattr__(self, "_definition_hash", _digest(definition_payload))

    @property
    def plan_hash(self) -> str:
        return self._plan_hash

    @property
    def definition_hash(self) -> str:
        return self._definition_hash


__all__ = ["Query", "QueryLane", "SqlResourceLimits"]
