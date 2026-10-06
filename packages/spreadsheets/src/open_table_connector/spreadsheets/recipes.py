"""Closed, observed layout recipe contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .rich import RichObjectRequest

SCHEMA = "otc.spreadsheet-recipe/1.0"
_DISALLOWED = {"values", "expression", "formula", "content", "asset", "assets"}


@dataclass(frozen=True, slots=True)
class LayoutRecipe:
    schema: str
    version: str
    requirements: tuple[str, ...]
    operations: tuple[RichObjectRequest, ...]

    def __post_init__(self) -> None:
        if self.schema != SCHEMA or self.version != "1.0":
            raise ValueError("unsupported recipe schema or version")
        if len(self.operations) > 10_000:
            raise ValueError("recipe contains more than 10000 operations")
        expected = tuple(sorted({f"spreadsheet.{item.operation_id}/1.0" for item in self.operations}))
        if tuple(sorted(self.requirements)) != expected:
            raise ValueError("recipe requirements do not match operations")
        object.__setattr__(self, "requirements", tuple(self.requirements))
        object.__setattr__(self, "operations", tuple(self.operations))

    def to_wire(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "requirements": list(self.requirements),
            "operations": [
                {"operation_id": item.operation_id, "target_key": item.target_key, "arguments": dict(item.arguments)}
                for item in self.operations
            ],
        }


def parse_recipe(payload: object) -> LayoutRecipe:
    if not isinstance(payload, Mapping) or set(payload) != {"schema", "version", "requirements", "operations"}:
        raise ValueError("recipe envelope keys mismatch")
    raw_operations = payload["operations"]
    if not isinstance(raw_operations, list):
        raise ValueError("recipe operations must be a list")
    operations = []
    for raw in raw_operations:
        if not isinstance(raw, Mapping) or set(raw) != {"operation_id", "target_key", "arguments"}:
            raise ValueError("recipe operation keys mismatch")
        arguments = raw["arguments"]
        if not isinstance(arguments, Mapping):
            raise ValueError("recipe arguments must be an object")
        forbidden = sorted(_DISALLOWED.intersection(arguments))
        if forbidden:
            raise ValueError(f"recipe cannot contain {forbidden[0]}")
        operations.append(RichObjectRequest(str(raw["operation_id"]), str(raw["target_key"]), arguments))
    requirements = payload["requirements"]
    if not isinstance(requirements, list) or any(not isinstance(item, str) for item in requirements):
        raise ValueError("recipe requirements must be a string list")
    return LayoutRecipe(str(payload["schema"]), str(payload["version"]), tuple(requirements), tuple(operations))


__all__ = ["LayoutRecipe", "SCHEMA", "parse_recipe"]
