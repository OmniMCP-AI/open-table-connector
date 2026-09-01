"""Provider-facing formula extension protocols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .errors import FormulaExtensionResult
from .observations import (
    FieldFormulaObservation,
    FieldFormulaValueObservation,
    FormulaMutation,
    GridFormulaObservation,
    GridFormulaValueObservation,
    RecalculationObservation,
)
from .operations import (
    FieldFormulaBinding,
    FieldFormulaBindRequest,
    FieldFormulaReadRequest,
    FieldFormulaRecalculateRequest,
    FieldFormulaSetRequest,
    FieldFormulaValueReadRequest,
    GridFormulaBinding,
    GridFormulaBindRequest,
    GridFormulaReadRequest,
    GridFormulaRecalculateRequest,
    GridFormulaSetRequest,
    GridFormulaValueReadRequest,
    unsupported_result,
)


@runtime_checkable
class GridFormulaConnectorExtension(Protocol):
    def bind_grid(self, request: GridFormulaBindRequest) -> FormulaExtensionResult[GridFormulaBinding]: ...
    def read_grid(self, request: GridFormulaReadRequest) -> FormulaExtensionResult[GridFormulaObservation]: ...
    def set_grid(self, request: GridFormulaSetRequest) -> FormulaExtensionResult[FormulaMutation]: ...
    def read_grid_values(
        self, request: GridFormulaValueReadRequest
    ) -> FormulaExtensionResult[GridFormulaValueObservation]: ...
    def recalculate_grid(
        self, request: GridFormulaRecalculateRequest
    ) -> FormulaExtensionResult[RecalculationObservation]: ...


@runtime_checkable
class FieldFormulaConnectorExtension(Protocol):
    def bind_field(self, request: FieldFormulaBindRequest) -> FormulaExtensionResult[FieldFormulaBinding]: ...
    def read_field(self, request: FieldFormulaReadRequest) -> FormulaExtensionResult[FieldFormulaObservation]: ...
    def set_field(self, request: FieldFormulaSetRequest) -> FormulaExtensionResult[FormulaMutation]: ...
    def read_field_values(
        self, request: FieldFormulaValueReadRequest
    ) -> FormulaExtensionResult[FieldFormulaValueObservation]: ...
    def recalculate_field(
        self, request: FieldFormulaRecalculateRequest
    ) -> FormulaExtensionResult[RecalculationObservation]: ...


@runtime_checkable
class FormulaConnectorExtension(
    GridFormulaConnectorExtension,
    FieldFormulaConnectorExtension,
    Protocol,
):
    pass


@dataclass(frozen=True, slots=True)
class CompositeFormulaConnectorExtension:
    grid: GridFormulaConnectorExtension | None = None
    field: FieldFormulaConnectorExtension | None = None

    def bind_grid(self, request: GridFormulaBindRequest) -> FormulaExtensionResult[GridFormulaBinding]:
        if self.grid is None:
            return unsupported_result(target_kind="grid", capability="formula.grid.read/1.0")
        return self.grid.bind_grid(request)

    def read_grid(self, request: GridFormulaReadRequest) -> FormulaExtensionResult[GridFormulaObservation]:
        if self.grid is None:
            return unsupported_result(target_kind="grid", capability="formula.grid.read/1.0")
        return self.grid.read_grid(request)

    def set_grid(self, request: GridFormulaSetRequest) -> FormulaExtensionResult[FormulaMutation]:
        if self.grid is None:
            return unsupported_result(target_kind="grid", capability="formula.grid.set/1.0")
        return self.grid.set_grid(request)

    def read_grid_values(
        self, request: GridFormulaValueReadRequest
    ) -> FormulaExtensionResult[GridFormulaValueObservation]:
        if self.grid is None:
            return unsupported_result(target_kind="grid", capability="formula.grid.values.read/1.0")
        return self.grid.read_grid_values(request)

    def recalculate_grid(
        self, request: GridFormulaRecalculateRequest
    ) -> FormulaExtensionResult[RecalculationObservation]:
        if self.grid is None:
            return unsupported_result(target_kind="grid", capability="formula.grid.recalculate/1.0")
        return self.grid.recalculate_grid(request)

    def bind_field(self, request: FieldFormulaBindRequest) -> FormulaExtensionResult[FieldFormulaBinding]:
        if self.field is None:
            return unsupported_result(target_kind="field", capability="formula.field.read/1.0")
        return self.field.bind_field(request)

    def read_field(self, request: FieldFormulaReadRequest) -> FormulaExtensionResult[FieldFormulaObservation]:
        if self.field is None:
            return unsupported_result(target_kind="field", capability="formula.field.read/1.0")
        return self.field.read_field(request)

    def set_field(self, request: FieldFormulaSetRequest) -> FormulaExtensionResult[FormulaMutation]:
        if self.field is None:
            return unsupported_result(target_kind="field", capability="formula.field.set/1.0")
        return self.field.set_field(request)

    def read_field_values(
        self, request: FieldFormulaValueReadRequest
    ) -> FormulaExtensionResult[FieldFormulaValueObservation]:
        if self.field is None:
            return unsupported_result(target_kind="field", capability="formula.field.values.read/1.0")
        return self.field.read_field_values(request)

    def recalculate_field(
        self, request: FieldFormulaRecalculateRequest
    ) -> FormulaExtensionResult[RecalculationObservation]:
        if self.field is None:
            return unsupported_result(target_kind="field", capability="formula.field.recalculate/1.0")
        return self.field.recalculate_field(request)


__all__ = [
    "CompositeFormulaConnectorExtension",
    "FieldFormulaConnectorExtension",
    "FormulaConnectorExtension",
    "GridFormulaConnectorExtension",
]
