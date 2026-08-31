"""SDK predicate types."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    raise ValueError("predicate parameters must be JSON-compatible values")


class PredicateKind(StrEnum):
    SQL = "sql"
    ALL_ROWS = "all_rows"


@dataclass(frozen=True, slots=True)
class PortablePredicate:
    expression: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    kind: PredicateKind = PredicateKind.SQL

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", PredicateKind(self.kind))
        if self.kind is PredicateKind.ALL_ROWS:
            if self.expression is not None or self.parameters:
                raise ValueError("all_rows predicate cannot carry expression or parameters")
            return
        if not isinstance(self.expression, str) or not self.expression.strip():
            raise ValueError("sql predicate expression must be a non-empty string")
        object.__setattr__(self, "expression", self.expression.strip())
        object.__setattr__(self, "parameters", _json_value(dict(self.parameters or {})))

    def to_wire(self) -> dict[str, Any]:
        if self.kind is PredicateKind.ALL_ROWS:
            return {"kind": "all_rows"}
        return {
            "kind": "sql",
            "expression": self.expression,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> PortablePredicate:
        kind = payload.get("kind")
        if kind == PredicateKind.ALL_ROWS.value:
            if set(payload) != {"kind"}:
                raise ValueError("all_rows predicate wire keys mismatch")
            return cls(kind=PredicateKind.ALL_ROWS)
        if kind == PredicateKind.SQL.value:
            if set(payload) != {"kind", "expression", "parameters"}:
                raise ValueError("sql predicate wire keys mismatch")
            return cls(expression=payload["expression"], parameters=payload["parameters"])
        raise ValueError("predicate kind must be sql or all_rows")


def all_rows() -> PortablePredicate:
    return PortablePredicate(kind=PredicateKind.ALL_ROWS)


__all__ = ["PortablePredicate", "PredicateKind", "all_rows"]
