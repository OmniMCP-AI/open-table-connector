"""Immutable formula observations, values, and capability details."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from open_table_connector.contract import CapabilityIdentity, TableURI

from .capabilities import (
    FIELD_RECALCULATE,
    FORMULA_DIALECTS,
    GRID_RECALCULATE,
)
from .model import (
    FieldRecalculationScope,
    FormulaExpression,
    GridRecalculationScope,
)
from .ranges import A1Rectangle

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TARGET_KINDS = {"grid", "field"}
_DEPENDENCY_SCOPE = "provider_dynamic"
_FORMULA_VALUE_KINDS = {
    "null",
    "boolean",
    "integer",
    "number",
    "string",
    "sequence",
    "mapping",
    "logical",
    "provider_error",
}
_GRID_SCOPES = {scope.value for scope in GridRecalculationScope}
_FIELD_SCOPES = {scope.value for scope in FieldRecalculationScope}
_VERIFICATIONS = {"passed", "unavailable"}


def _closed_wire(payload: Mapping[str, Any], required: set[str], label: str) -> None:
    if set(payload) != required:
        missing = sorted(required.difference(payload))
        extra = sorted(set(payload).difference(required))
        raise ValueError(f"{label} wire keys mismatch; missing={missing}, extra={extra}")


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _hash(value: object, field: str) -> str:
    text = _required_text(value, field)
    if _HASH_RE.fullmatch(text) is None:
        raise ValueError(f"{field} must be a lowercase sha256 identity")
    return text


def _positive_int_or_none(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer when provided")
    return value


def _target_kind(value: object) -> str:
    kind = _required_text(value, "target_kind")
    if kind not in _TARGET_KINDS:
        raise ValueError("target_kind must be 'grid' or 'field'")
    return kind


def _table_uri(value: TableURI | str) -> TableURI:
    return value if isinstance(value, TableURI) else TableURI(value)


def _scope_family(target_kind: str) -> set[str]:
    return _GRID_SCOPES if target_kind == "grid" else _FIELD_SCOPES


def _normalize_unique_texts(values: Sequence[object], field: str) -> tuple[str, ...]:
    normalized = tuple(_required_text(value, field) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class FormulaErrorValue:
    code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))

    def to_wire(self) -> dict[str, str]:
        return {"code": self.code}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaErrorValue:
        _closed_wire(payload, {"code"}, "FormulaErrorValue")
        return cls(code=payload["code"])


@dataclass(frozen=True, slots=True)
class FormulaValue:
    kind: str
    value: object = None
    logical_type: str | None = None

    def __post_init__(self) -> None:
        kind = _required_text(self.kind, "kind")
        if kind not in _FORMULA_VALUE_KINDS:
            raise ValueError("kind must be a closed FormulaValue tag")
        object.__setattr__(self, "kind", kind)
        if kind == "null":
            if self.value is not None or self.logical_type is not None:
                raise ValueError("null FormulaValue cannot carry payload")
            return
        if kind == "boolean":
            if not isinstance(self.value, bool) or self.logical_type is not None:
                raise ValueError("boolean FormulaValue requires a bool value")
            return
        if kind == "integer":
            if isinstance(self.value, bool) or not isinstance(self.value, int) or self.logical_type is not None:
                raise ValueError("integer FormulaValue requires an int value")
            return
        if kind == "number":
            if (
                isinstance(self.value, bool)
                or not isinstance(self.value, (int, float))
                or not math.isfinite(float(self.value))
                or self.logical_type is not None
            ):
                raise ValueError("number FormulaValue requires a finite numeric value")
            object.__setattr__(self, "value", float(self.value))
            return
        if kind == "string":
            if not isinstance(self.value, str) or self.logical_type is not None:
                raise ValueError("string FormulaValue requires a string value")
            return
        if kind == "sequence":
            if self.logical_type is not None or not isinstance(self.value, tuple):
                raise ValueError("sequence FormulaValue requires an immutable value tuple")
            if not all(isinstance(item, FormulaValue) for item in self.value):
                raise TypeError("sequence FormulaValue items must be FormulaValue")
            return
        if kind == "mapping":
            if self.logical_type is not None or not isinstance(self.value, tuple):
                raise ValueError("mapping FormulaValue requires immutable entries")
            keys: list[str] = []
            for item in self.value:
                if not isinstance(item, tuple) or len(item) != 2:
                    raise TypeError("mapping FormulaValue entries must be key/value pairs")
                key, nested = item
                keys.append(_required_text(key, "mapping key"))
                if not isinstance(nested, FormulaValue):
                    raise TypeError("mapping FormulaValue values must be FormulaValue")
            if len(set(keys)) != len(keys):
                raise ValueError("mapping FormulaValue keys must be unique")
            return
        if kind == "logical":
            logical_type = _required_text(self.logical_type, "logical_type")
            if not isinstance(self.value, (str, int, float)) or isinstance(self.value, bool):
                raise ValueError("logical FormulaValue requires string or finite numeric representation")
            if isinstance(self.value, float) and not math.isfinite(self.value):
                raise ValueError("logical FormulaValue numeric representation must be finite")
            object.__setattr__(self, "logical_type", logical_type)
            return
        if not isinstance(self.value, FormulaErrorValue) or self.logical_type is not None:
            raise ValueError("provider_error FormulaValue requires FormulaErrorValue payload")

    @classmethod
    def from_python(cls, value: object) -> FormulaValue:
        if value is None:
            return cls("null")
        if isinstance(value, bool):
            return cls("boolean", value)
        if isinstance(value, int):
            return cls("integer", value)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("FormulaValue numbers must be finite")
            return cls("number", value)
        if isinstance(value, str):
            return cls("string", value)
        if isinstance(value, Mapping):
            entries = tuple((str(key), cls.from_python(nested)) for key, nested in value.items())
            if any(not isinstance(key, str) for key in value):
                raise TypeError("FormulaValue mappings require string keys")
            return cls("mapping", entries)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return cls("sequence", tuple(cls.from_python(item) for item in value))
        raise TypeError("FormulaValue must be JSON-compatible")

    @classmethod
    def logical(cls, logical_type: str, value: str | int | float) -> FormulaValue:
        return cls("logical", value=value, logical_type=logical_type)

    @classmethod
    def provider_error(cls, value: FormulaErrorValue) -> FormulaValue:
        return cls("provider_error", value=value)

    def to_python(self) -> object:
        if self.kind == "null":
            return None
        if self.kind in {"boolean", "integer", "number", "string"}:
            return self.value
        if self.kind == "sequence":
            return [item.to_python() for item in self.value]
        if self.kind == "mapping":
            return {key: nested.to_python() for key, nested in self.value}
        if self.kind == "logical":
            return {"logical_type": self.logical_type, "value": self.value}
        return {"provider_error": self.value.to_wire()}

    def to_wire(self) -> dict[str, object]:
        if self.kind == "null":
            return {"kind": "null"}
        if self.kind in {"boolean", "integer", "number", "string"}:
            return {"kind": self.kind, "value": self.value}
        if self.kind == "sequence":
            return {"kind": "sequence", "items": [item.to_wire() for item in self.value]}
        if self.kind == "mapping":
            return {
                "kind": "mapping",
                "entries": {key: nested.to_wire() for key, nested in self.value},
            }
        if self.kind == "logical":
            return {"kind": "logical", "logical_type": self.logical_type, "value": self.value}
        return {"kind": "provider_error", "error": self.value.to_wire()}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaValue:
        if "kind" not in payload:
            _closed_wire(payload, {"kind"}, "FormulaValue")
        kind = payload.get("kind")
        if kind == "null":
            _closed_wire(payload, {"kind"}, "FormulaValue")
            return cls("null")
        if kind in {"boolean", "integer", "number", "string"}:
            _closed_wire(payload, {"kind", "value"}, "FormulaValue")
            return cls(kind, payload["value"])
        if kind == "sequence":
            _closed_wire(payload, {"kind", "items"}, "FormulaValue")
            items = payload["items"]
            if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
                raise TypeError("FormulaValue sequence items must be a list")
            return cls("sequence", tuple(cls.from_wire(item) for item in items))
        if kind == "mapping":
            _closed_wire(payload, {"kind", "entries"}, "FormulaValue")
            entries = payload["entries"]
            if not isinstance(entries, Mapping):
                raise TypeError("FormulaValue mapping entries must be an object")
            return cls("mapping", tuple((key, cls.from_wire(value)) for key, value in entries.items()))
        if kind == "logical":
            _closed_wire(payload, {"kind", "logical_type", "value"}, "FormulaValue")
            return cls("logical", value=payload["value"], logical_type=payload["logical_type"])
        if kind == "provider_error":
            _closed_wire(payload, {"kind", "error"}, "FormulaValue")
            return cls.provider_error(FormulaErrorValue.from_wire(payload["error"]))
        raise ValueError("unsupported FormulaValue kind")


@dataclass(frozen=True, slots=True)
class FormulaCapabilityDetails:
    target_kind: str
    dialects: tuple[str, ...]
    max_cells_per_operation: int | None
    max_expression_bytes: int
    recalculation_scopes: tuple[str, ...]
    calculation_states: tuple[CalculationState, ...]
    mutation_atomicity: MutationAtomicity
    revision_enforcement: RevisionEnforcement
    idempotency_strength: IdempotencyStrength

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_kind", _target_kind(self.target_kind))
        object.__setattr__(self, "dialects", _normalize_unique_texts(self.dialects, "dialects"))
        if any(dialect not in FORMULA_DIALECTS for dialect in self.dialects):
            raise ValueError("dialects must be drawn from FORMULA_DIALECTS")
        object.__setattr__(
            self,
            "max_cells_per_operation",
            _positive_int_or_none(self.max_cells_per_operation, "max_cells_per_operation"),
        )
        if (
            isinstance(self.max_expression_bytes, bool)
            or not isinstance(self.max_expression_bytes, int)
            or self.max_expression_bytes <= 0
        ):
            raise ValueError("max_expression_bytes must be a positive integer")
        allowed_scopes = _scope_family(self.target_kind)
        scopes = _normalize_unique_texts(self.recalculation_scopes, "recalculation_scopes")
        if any(scope not in allowed_scopes for scope in scopes):
            raise ValueError("recalculation scopes must match the target kind")
        object.__setattr__(self, "recalculation_scopes", scopes)
        states = tuple(
            state if isinstance(state, CalculationState) else CalculationState(state)
            for state in self.calculation_states
        )
        if len(set(states)) != len(states):
            raise ValueError("calculation_states must not contain duplicates")
        object.__setattr__(self, "calculation_states", states)
        object.__setattr__(
            self,
            "mutation_atomicity",
            self.mutation_atomicity
            if isinstance(self.mutation_atomicity, MutationAtomicity)
            else MutationAtomicity(self.mutation_atomicity),
        )
        object.__setattr__(
            self,
            "revision_enforcement",
            self.revision_enforcement
            if isinstance(self.revision_enforcement, RevisionEnforcement)
            else RevisionEnforcement(self.revision_enforcement),
        )
        object.__setattr__(
            self,
            "idempotency_strength",
            self.idempotency_strength
            if isinstance(self.idempotency_strength, IdempotencyStrength)
            else IdempotencyStrength(self.idempotency_strength),
        )

    def to_wire(self) -> dict[str, object]:
        return {
            "target_kind": self.target_kind,
            "dialects": list(self.dialects),
            "max_cells_per_operation": self.max_cells_per_operation,
            "max_expression_bytes": self.max_expression_bytes,
            "recalculation_scopes": list(self.recalculation_scopes),
            "calculation_states": [state.value for state in self.calculation_states],
            "mutation_atomicity": self.mutation_atomicity.value,
            "revision_enforcement": self.revision_enforcement.value,
            "idempotency_strength": self.idempotency_strength.value,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaCapabilityDetails:
        _closed_wire(
            payload,
            {
                "target_kind",
                "dialects",
                "max_cells_per_operation",
                "max_expression_bytes",
                "recalculation_scopes",
                "calculation_states",
                "mutation_atomicity",
                "revision_enforcement",
                "idempotency_strength",
            },
            "FormulaCapabilityDetails",
        )
        return cls(
            target_kind=payload["target_kind"],
            dialects=tuple(payload["dialects"]),
            max_cells_per_operation=payload["max_cells_per_operation"],
            max_expression_bytes=payload["max_expression_bytes"],
            recalculation_scopes=tuple(payload["recalculation_scopes"]),
            calculation_states=tuple(CalculationState(value) for value in payload["calculation_states"]),
            mutation_atomicity=MutationAtomicity(payload["mutation_atomicity"]),
            revision_enforcement=RevisionEnforcement(payload["revision_enforcement"]),
            idempotency_strength=IdempotencyStrength(payload["idempotency_strength"]),
        )


@dataclass(frozen=True, slots=True)
class FormulaCapabilitySet:
    capabilities: tuple[CapabilityIdentity, ...]
    details: FormulaCapabilityDetails

    def __post_init__(self) -> None:
        if not isinstance(self.details, FormulaCapabilityDetails):
            raise TypeError("details must be a FormulaCapabilityDetails")
        capabilities = tuple(
            capability if isinstance(capability, CapabilityIdentity) else CapabilityIdentity.from_wire(capability)
            for capability in self.capabilities
        )
        references = [capability.to_reference() for capability in capabilities]
        if len(set(references)) != len(references):
            raise ValueError("duplicate capability identities are not allowed")
        target_prefix = f"formula.{self.details.target_kind}."
        if any(not capability.capability_id.startswith(target_prefix) for capability in capabilities):
            raise ValueError("capability target kind must match capability details")
        if GRID_RECALCULATE in capabilities and not self.details.recalculation_scopes:
            raise ValueError("grid recalculation capability requires supported recalculation scopes")
        if FIELD_RECALCULATE in capabilities and not self.details.recalculation_scopes:
            raise ValueError("field recalculation capability requires supported recalculation scopes")
        object.__setattr__(self, "capabilities", capabilities)

    def to_wire(self) -> dict[str, object]:
        return {
            "capabilities": [capability.to_wire() for capability in self.capabilities],
            "details": self.details.to_wire(),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaCapabilitySet:
        _closed_wire(payload, {"capabilities", "details"}, "FormulaCapabilitySet")
        capabilities = payload["capabilities"]
        if not isinstance(capabilities, Sequence) or isinstance(capabilities, (str, bytes, bytearray)):
            raise TypeError("capabilities must be a list")
        return cls(
            capabilities=tuple(CapabilityIdentity.from_wire(item) for item in capabilities),
            details=FormulaCapabilityDetails.from_wire(payload["details"]),
        )


class CalculationState(StrEnum):
    PROVIDER_CURRENT = "provider_current"
    CACHED = "cached"
    UNKNOWN = "unknown"


class CalculationTrigger(StrEnum):
    EXPLICIT_RECALCULATION = "explicit_recalculation"
    MUTATION = "mutation"
    PROVIDER_READ = "provider_read"
    STORED_CACHE = "stored_cache"


class MutationAtomicity(StrEnum):
    ATOMIC = "atomic"
    PARTIAL_REPORTED = "partial_reported"
    UNKNOWN = "unknown"


class RevisionEnforcement(StrEnum):
    ATOMIC = "atomic"
    CHECKED = "checked"
    UNAVAILABLE = "unavailable"


class IdempotencyStrength(StrEnum):
    PROVIDER = "provider"
    HOST_LEDGER = "host_ledger"
    RECONCILED = "reconciled"


@dataclass(frozen=True, slots=True)
class FormulaCell:
    address: str
    expression: FormulaExpression

    def __post_init__(self) -> None:
        cell = A1Rectangle.parse(_required_text(self.address, "address"))
        if cell.cell_count != 1 or cell.worksheet_name is not None:
            raise ValueError("address must be a single unbound A1 cell")
        object.__setattr__(self, "address", cell.start_address)
        if not isinstance(self.expression, FormulaExpression):
            raise TypeError("expression must be a FormulaExpression")

    def to_wire(self) -> dict[str, object]:
        return {"address": self.address, "expression": self.expression.to_wire()}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaCell:
        _closed_wire(payload, {"address", "expression"}, "FormulaCell")
        return cls(address=payload["address"], expression=FormulaExpression.from_wire(payload["expression"]))


@dataclass(frozen=True, slots=True)
class GridFormulaObservation:
    worksheet_id: str
    requested_range: str
    formulas: tuple[FormulaCell, ...]
    observed_revision: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheet_id", _required_text(self.worksheet_id, "worksheet_id"))
        selector = A1Rectangle.parse(_required_text(self.requested_range, "requested_range"))
        if selector.worksheet_name is not None:
            raise ValueError("requested_range must be unbound after target binding")
        object.__setattr__(self, "requested_range", self.requested_range.strip())
        object.__setattr__(self, "observed_revision", _hash(self.observed_revision, "observed_revision"))
        formulas = tuple(self.formulas)
        addresses = [cell.address for cell in formulas]
        if len(set(addresses)) != len(addresses):
            raise ValueError("duplicate cell formulas are not allowed")
        if any(not isinstance(cell, FormulaCell) for cell in formulas):
            raise TypeError("formulas must contain FormulaCell values")
        object.__setattr__(self, "formulas", formulas)

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "formula.grid.observation",
            "worksheet_id": self.worksheet_id,
            "requested_range": self.requested_range,
            "formulas": [cell.to_wire() for cell in self.formulas],
            "observed_revision": self.observed_revision,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> GridFormulaObservation:
        _closed_wire(
            payload,
            {"kind", "worksheet_id", "requested_range", "formulas", "observed_revision"},
            "GridFormulaObservation",
        )
        if payload["kind"] != "formula.grid.observation":
            raise ValueError("unsupported grid observation kind")
        return cls(
            worksheet_id=payload["worksheet_id"],
            requested_range=payload["requested_range"],
            formulas=tuple(FormulaCell.from_wire(item) for item in payload["formulas"]),
            observed_revision=payload["observed_revision"],
        )


@dataclass(frozen=True, slots=True)
class FieldFormulaObservation:
    table_uri: TableURI | str
    field_id: str
    field_name: str
    expression: FormulaExpression
    result_type: str | None
    observed_revision: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "table_uri", _table_uri(self.table_uri))
        object.__setattr__(self, "field_id", _required_text(self.field_id, "field_id"))
        object.__setattr__(self, "field_name", _required_text(self.field_name, "field_name"))
        if not isinstance(self.expression, FormulaExpression):
            raise TypeError("expression must be a FormulaExpression")
        if self.result_type is not None:
            object.__setattr__(self, "result_type", _required_text(self.result_type, "result_type"))
        object.__setattr__(self, "observed_revision", _hash(self.observed_revision, "observed_revision"))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "formula.field.observation",
            "table_uri": self.table_uri.to_wire(),
            "field_id": self.field_id,
            "field_name": self.field_name,
            "expression": self.expression.to_wire(),
            "result_type": self.result_type,
            "observed_revision": self.observed_revision,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FieldFormulaObservation:
        _closed_wire(
            payload,
            {"kind", "table_uri", "field_id", "field_name", "expression", "result_type", "observed_revision"},
            "FieldFormulaObservation",
        )
        if payload["kind"] != "formula.field.observation":
            raise ValueError("unsupported field observation kind")
        return cls(
            table_uri=TableURI.from_wire(payload["table_uri"]),
            field_id=payload["field_id"],
            field_name=payload["field_name"],
            expression=FormulaExpression.from_wire(payload["expression"]),
            result_type=payload["result_type"],
            observed_revision=payload["observed_revision"],
        )


@dataclass(frozen=True, slots=True)
class FormulaValueCell:
    address: str
    value: FormulaValue

    def __post_init__(self) -> None:
        cell = A1Rectangle.parse(_required_text(self.address, "address"))
        if cell.cell_count != 1 or cell.worksheet_name is not None:
            raise ValueError("address must be a single unbound A1 cell")
        object.__setattr__(self, "address", cell.start_address)
        if not isinstance(self.value, FormulaValue):
            raise TypeError("value must be a FormulaValue")

    def to_wire(self) -> dict[str, object]:
        return {"address": self.address, "value": self.value.to_wire()}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaValueCell:
        _closed_wire(payload, {"address", "value"}, "FormulaValueCell")
        return cls(address=payload["address"], value=FormulaValue.from_wire(payload["value"]))


@dataclass(frozen=True, slots=True)
class FormulaRecordValue:
    record_id: str
    value: FormulaValue

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _required_text(self.record_id, "record_id"))
        if not isinstance(self.value, FormulaValue):
            raise TypeError("value must be a FormulaValue")

    def to_wire(self) -> dict[str, object]:
        return {"record_id": self.record_id, "value": self.value.to_wire()}

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaRecordValue:
        _closed_wire(payload, {"record_id", "value"}, "FormulaRecordValue")
        return cls(record_id=payload["record_id"], value=FormulaValue.from_wire(payload["value"]))


@dataclass(frozen=True, slots=True)
class GridFormulaValueObservation:
    worksheet_id: str
    requested_range: str
    values: tuple[FormulaValueCell, ...]
    calculation_state: CalculationState
    calculation_trigger: CalculationTrigger
    dependency_scope: str
    observed_revision: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "worksheet_id", _required_text(self.worksheet_id, "worksheet_id"))
        selector = A1Rectangle.parse(_required_text(self.requested_range, "requested_range"))
        if selector.worksheet_name is not None:
            raise ValueError("requested_range must be unbound after target binding")
        object.__setattr__(self, "requested_range", self.requested_range.strip())
        values = tuple(self.values)
        addresses = [cell.address for cell in values]
        if len(set(addresses)) != len(addresses):
            raise ValueError("duplicate cell values are not allowed")
        if any(not isinstance(cell, FormulaValueCell) for cell in values):
            raise TypeError("values must contain FormulaValueCell values")
        object.__setattr__(self, "values", values)
        object.__setattr__(
            self,
            "calculation_state",
            self.calculation_state
            if isinstance(self.calculation_state, CalculationState)
            else CalculationState(self.calculation_state),
        )
        object.__setattr__(
            self,
            "calculation_trigger",
            self.calculation_trigger
            if isinstance(self.calculation_trigger, CalculationTrigger)
            else CalculationTrigger(self.calculation_trigger),
        )
        if self.dependency_scope != _DEPENDENCY_SCOPE:
            raise ValueError("dependency_scope must be provider_dynamic")
        object.__setattr__(self, "observed_revision", _hash(self.observed_revision, "observed_revision"))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "formula.grid.values.observation",
            "worksheet_id": self.worksheet_id,
            "requested_range": self.requested_range,
            "values": [value.to_wire() for value in self.values],
            "calculation_state": self.calculation_state.value,
            "calculation_trigger": self.calculation_trigger.value,
            "dependency_scope": self.dependency_scope,
            "observed_revision": self.observed_revision,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> GridFormulaValueObservation:
        _closed_wire(
            payload,
            {
                "kind",
                "worksheet_id",
                "requested_range",
                "values",
                "calculation_state",
                "calculation_trigger",
                "dependency_scope",
                "observed_revision",
            },
            "GridFormulaValueObservation",
        )
        if payload["kind"] != "formula.grid.values.observation":
            raise ValueError("unsupported grid value observation kind")
        return cls(
            worksheet_id=payload["worksheet_id"],
            requested_range=payload["requested_range"],
            values=tuple(FormulaValueCell.from_wire(item) for item in payload["values"]),
            calculation_state=CalculationState(payload["calculation_state"]),
            calculation_trigger=CalculationTrigger(payload["calculation_trigger"]),
            dependency_scope=payload["dependency_scope"],
            observed_revision=payload["observed_revision"],
        )


@dataclass(frozen=True, slots=True)
class FieldFormulaValueObservation:
    table_uri: TableURI | str
    field_id: str
    field_name: str
    values: tuple[FormulaRecordValue, ...]
    calculation_state: CalculationState
    calculation_trigger: CalculationTrigger
    dependency_scope: str
    observed_revision: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "table_uri", _table_uri(self.table_uri))
        object.__setattr__(self, "field_id", _required_text(self.field_id, "field_id"))
        object.__setattr__(self, "field_name", _required_text(self.field_name, "field_name"))
        values = tuple(self.values)
        record_ids = [record.record_id for record in values]
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("duplicate record values are not allowed")
        if any(not isinstance(record, FormulaRecordValue) for record in values):
            raise TypeError("values must contain FormulaRecordValue values")
        object.__setattr__(self, "values", values)
        object.__setattr__(
            self,
            "calculation_state",
            self.calculation_state
            if isinstance(self.calculation_state, CalculationState)
            else CalculationState(self.calculation_state),
        )
        object.__setattr__(
            self,
            "calculation_trigger",
            self.calculation_trigger
            if isinstance(self.calculation_trigger, CalculationTrigger)
            else CalculationTrigger(self.calculation_trigger),
        )
        if self.dependency_scope != _DEPENDENCY_SCOPE:
            raise ValueError("dependency_scope must be provider_dynamic")
        object.__setattr__(self, "observed_revision", _hash(self.observed_revision, "observed_revision"))

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "formula.field.values.observation",
            "table_uri": self.table_uri.to_wire(),
            "field_id": self.field_id,
            "field_name": self.field_name,
            "values": [value.to_wire() for value in self.values],
            "calculation_state": self.calculation_state.value,
            "calculation_trigger": self.calculation_trigger.value,
            "dependency_scope": self.dependency_scope,
            "observed_revision": self.observed_revision,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FieldFormulaValueObservation:
        _closed_wire(
            payload,
            {
                "kind",
                "table_uri",
                "field_id",
                "field_name",
                "values",
                "calculation_state",
                "calculation_trigger",
                "dependency_scope",
                "observed_revision",
            },
            "FieldFormulaValueObservation",
        )
        if payload["kind"] != "formula.field.values.observation":
            raise ValueError("unsupported field value observation kind")
        return cls(
            table_uri=TableURI.from_wire(payload["table_uri"]),
            field_id=payload["field_id"],
            field_name=payload["field_name"],
            values=tuple(FormulaRecordValue.from_wire(item) for item in payload["values"]),
            calculation_state=CalculationState(payload["calculation_state"]),
            calculation_trigger=CalculationTrigger(payload["calculation_trigger"]),
            dependency_scope=payload["dependency_scope"],
            observed_revision=payload["observed_revision"],
        )


@dataclass(frozen=True, slots=True)
class FormulaMutation:
    target_kind: str
    affected_count: int
    formula_observation: GridFormulaObservation | FieldFormulaObservation
    revision_before: str | None
    revision_after: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_kind", _target_kind(self.target_kind))
        if isinstance(self.affected_count, bool) or not isinstance(self.affected_count, int) or self.affected_count <= 0:
            raise ValueError("affected_count must be a positive integer")
        if self.revision_before is not None:
            object.__setattr__(self, "revision_before", _hash(self.revision_before, "revision_before"))
        object.__setattr__(self, "revision_after", _hash(self.revision_after, "revision_after"))
        expected_type = GridFormulaObservation if self.target_kind == "grid" else FieldFormulaObservation
        if not isinstance(self.formula_observation, expected_type):
            raise ValueError("formula_observation target kind must match target_kind")
        expected_count = len(self.formula_observation.formulas) if self.target_kind == "grid" else 1
        if self.affected_count != expected_count:
            raise ValueError("affected_count must match the observed mutation scope")

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "formula.mutation",
            "target_kind": self.target_kind,
            "affected_count": self.affected_count,
            "formula_observation": self.formula_observation.to_wire(),
            "revision_before": self.revision_before,
            "revision_after": self.revision_after,
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> FormulaMutation:
        _closed_wire(
            payload,
            {
                "kind",
                "target_kind",
                "affected_count",
                "formula_observation",
                "revision_before",
                "revision_after",
            },
            "FormulaMutation",
        )
        if payload["kind"] != "formula.mutation":
            raise ValueError("unsupported formula operation kind")
        target_kind = _target_kind(payload["target_kind"])
        observation = (
            GridFormulaObservation.from_wire(payload["formula_observation"])
            if target_kind == "grid"
            else FieldFormulaObservation.from_wire(payload["formula_observation"])
        )
        return cls(
            target_kind=target_kind,
            affected_count=payload["affected_count"],
            formula_observation=observation,
            revision_before=payload["revision_before"],
            revision_after=payload["revision_after"],
        )


@dataclass(frozen=True, slots=True)
class RecalculationObservation:
    target_kind: str
    requested_scope: str
    effective_scope: str
    revision_before: str | None
    revision_after: str | None
    provider_status: str
    calculation_state: CalculationState
    verification: str
    value_observation: GridFormulaValueObservation | FieldFormulaValueObservation | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_kind", _target_kind(self.target_kind))
        allowed_scopes = _scope_family(self.target_kind)
        requested_scope = _required_text(self.requested_scope, "requested_scope")
        effective_scope = _required_text(self.effective_scope, "effective_scope")
        if requested_scope not in allowed_scopes or effective_scope not in allowed_scopes:
            raise ValueError("scope must be supported for the target kind")
        object.__setattr__(self, "requested_scope", requested_scope)
        object.__setattr__(self, "effective_scope", effective_scope)
        if self.revision_before is not None:
            object.__setattr__(self, "revision_before", _hash(self.revision_before, "revision_before"))
        if self.revision_after is not None:
            object.__setattr__(self, "revision_after", _hash(self.revision_after, "revision_after"))
        object.__setattr__(self, "provider_status", _required_text(self.provider_status, "provider_status"))
        object.__setattr__(
            self,
            "calculation_state",
            self.calculation_state
            if isinstance(self.calculation_state, CalculationState)
            else CalculationState(self.calculation_state),
        )
        verification = _required_text(self.verification, "verification")
        if verification not in _VERIFICATIONS:
            raise ValueError("verification must be passed or unavailable")
        object.__setattr__(self, "verification", verification)
        expected_value_type = GridFormulaValueObservation if self.target_kind == "grid" else FieldFormulaValueObservation
        if self.value_observation is not None and not isinstance(self.value_observation, expected_value_type):
            raise ValueError("value_observation target kind must match target_kind")
        if self.verification == "passed" and self.value_observation is None:
            raise ValueError("verification passed requires a value observation")
        if self.verification == "unavailable" and self.value_observation is not None:
            raise ValueError("verification unavailable cannot carry a value observation")

    def to_wire(self) -> dict[str, object]:
        return {
            "kind": "formula.recalculation",
            "target_kind": self.target_kind,
            "requested_scope": self.requested_scope,
            "effective_scope": self.effective_scope,
            "revision_before": self.revision_before,
            "revision_after": self.revision_after,
            "provider_status": self.provider_status,
            "calculation_state": self.calculation_state.value,
            "verification": self.verification,
            "value_observation": None if self.value_observation is None else self.value_observation.to_wire(),
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> RecalculationObservation:
        _closed_wire(
            payload,
            {
                "kind",
                "target_kind",
                "requested_scope",
                "effective_scope",
                "revision_before",
                "revision_after",
                "provider_status",
                "calculation_state",
                "verification",
                "value_observation",
            },
            "RecalculationObservation",
        )
        if payload["kind"] != "formula.recalculation":
            raise ValueError("unsupported formula operation kind")
        target_kind = _target_kind(payload["target_kind"])
        value_observation = payload["value_observation"]
        if value_observation is not None:
            value_observation = (
                GridFormulaValueObservation.from_wire(value_observation)
                if target_kind == "grid"
                else FieldFormulaValueObservation.from_wire(value_observation)
            )
        return cls(
            target_kind=target_kind,
            requested_scope=payload["requested_scope"],
            effective_scope=payload["effective_scope"],
            revision_before=payload["revision_before"],
            revision_after=payload["revision_after"],
            provider_status=payload["provider_status"],
            calculation_state=CalculationState(payload["calculation_state"]),
            verification=payload["verification"],
            value_observation=value_observation,
        )


__all__ = [
    "CalculationState",
    "CalculationTrigger",
    "FieldFormulaObservation",
    "FieldFormulaValueObservation",
    "FormulaCapabilityDetails",
    "FormulaCapabilitySet",
    "FormulaCell",
    "FormulaErrorValue",
    "FormulaMutation",
    "FormulaRecordValue",
    "FormulaValue",
    "FormulaValueCell",
    "GridFormulaObservation",
    "GridFormulaValueObservation",
    "IdempotencyStrength",
    "MutationAtomicity",
    "RecalculationObservation",
    "RevisionEnforcement",
]
