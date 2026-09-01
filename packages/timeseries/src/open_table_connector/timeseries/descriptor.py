"""Temporal table descriptors and deterministic descriptor identity."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pyarrow as pa


class TimestampPrecision(StrEnum):
    SECOND = "second"
    MILLISECOND = "millisecond"
    MICROSECOND = "microsecond"
    NANOSECOND = "nanosecond"


class DuplicatePolicy(StrEnum):
    PRESERVE = "preserve"
    REJECT = "reject"
    REPLACE_LATEST = "replace-latest"


class TemporalOrdering(StrEnum):
    UNSPECIFIED = "unspecified"
    NONDECREASING = "nondecreasing"
    STRICT = "strict"


_DESCRIPTOR_FIELDS = (
    "time_field",
    "timezone",
    "precision",
    "series_key_fields",
    "tag_fields",
    "value_fields",
    "ingestion_time_field",
    "duplicate_policy",
    "ordering",
)


def _name(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _names(values: object, field: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field} must be an array of strings")
    result = tuple(_name(value, field) for value in values)
    if len(result) != len(set(result)):
        raise ValueError(f"{field} contains duplicate fields")
    return result


@dataclass(frozen=True, slots=True)
class TemporalTableDescriptor:
    time_field: str
    timezone: str
    precision: TimestampPrecision
    series_key_fields: tuple[str, ...]
    tag_fields: tuple[str, ...]
    value_fields: tuple[str, ...]
    ingestion_time_field: str | None
    duplicate_policy: DuplicatePolicy
    ordering: TemporalOrdering

    def __post_init__(self) -> None:
        object.__setattr__(self, "time_field", _name(self.time_field, "time_field"))
        object.__setattr__(self, "timezone", _name(self.timezone, "timezone"))
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be an IANA timezone name") from exc
        try:
            object.__setattr__(self, "precision", TimestampPrecision(self.precision))
            object.__setattr__(self, "duplicate_policy", DuplicatePolicy(self.duplicate_policy))
            object.__setattr__(self, "ordering", TemporalOrdering(self.ordering))
        except ValueError as exc:
            raise ValueError("descriptor contains an unsupported enum value") from exc
        object.__setattr__(
            self,
            "series_key_fields",
            _names(self.series_key_fields, "series_key_fields"),
        )
        object.__setattr__(self, "tag_fields", _names(self.tag_fields, "tag_fields"))
        object.__setattr__(self, "value_fields", _names(self.value_fields, "value_fields"))
        if not self.value_fields:
            raise ValueError("value_fields must contain at least one field")
        if self.ingestion_time_field is not None:
            object.__setattr__(
                self,
                "ingestion_time_field",
                _name(self.ingestion_time_field, "ingestion_time_field"),
            )

        roles = (
            (self.time_field,),
            self.series_key_fields,
            self.tag_fields,
            self.value_fields,
            () if self.ingestion_time_field is None else (self.ingestion_time_field,),
        )
        flattened = tuple(field for role in roles for field in role)
        if len(flattened) != len(set(flattened)):
            raise ValueError("a field cannot be declared in more than one role")
        if self.duplicate_policy is DuplicatePolicy.REPLACE_LATEST and self.ingestion_time_field is None:
            raise ValueError("replace-latest requires ingestion_time_field")

    @property
    def declared_fields(self) -> tuple[str, ...]:
        return (
            self.time_field,
            *self.series_key_fields,
            *self.tag_fields,
            *self.value_fields,
            *(() if self.ingestion_time_field is None else (self.ingestion_time_field,)),
        )

    def to_wire(self) -> dict[str, object]:
        return {
            "time_field": self.time_field,
            "timezone": self.timezone,
            "precision": self.precision.value,
            "series_key_fields": list(self.series_key_fields),
            "tag_fields": list(self.tag_fields),
            "value_fields": list(self.value_fields),
            "ingestion_time_field": self.ingestion_time_field,
            "duplicate_policy": self.duplicate_policy.value,
            "ordering": self.ordering.value,
        }


def descriptor_from_wire(document: Mapping[str, object]) -> TemporalTableDescriptor:
    if not isinstance(document, Mapping):
        raise ValueError("descriptor must be an object")
    keys = set(document)
    expected = set(_DESCRIPTOR_FIELDS)
    unknown = sorted(keys - expected)
    missing = sorted(expected - keys)
    if unknown:
        raise ValueError(f"unknown descriptor fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing descriptor fields: {', '.join(missing)}")
    return TemporalTableDescriptor(**{field: document[field] for field in _DESCRIPTOR_FIELDS})


def temporal_descriptor_hash(descriptor: TemporalTableDescriptor, arrow_schema: pa.Schema) -> str:
    if not isinstance(descriptor, TemporalTableDescriptor):
        raise TypeError("descriptor must be a TemporalTableDescriptor")
    if not isinstance(arrow_schema, pa.Schema):
        raise TypeError("arrow_schema must be a pyarrow.Schema")
    schema_fields = set(arrow_schema.names)
    missing = sorted(set(descriptor.declared_fields) - schema_fields)
    if missing:
        raise ValueError(f"Arrow schema is missing declared fields: {', '.join(missing)}")
    payload = {
        "descriptor": descriptor.to_wire(),
        "arrow_schema": arrow_schema.serialize().to_pybytes().hex(),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "DuplicatePolicy",
    "TemporalOrdering",
    "TemporalTableDescriptor",
    "TimestampPrecision",
    "descriptor_from_wire",
    "temporal_descriptor_hash",
]
