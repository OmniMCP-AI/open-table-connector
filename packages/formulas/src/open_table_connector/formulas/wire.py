"""Closed wire dispatch helpers for formula observations and operations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from .observations import (
    FieldFormulaObservation,
    FieldFormulaValueObservation,
    FormulaMutation,
    GridFormulaObservation,
    GridFormulaValueObservation,
    RecalculationObservation,
)


def formula_observation_from_wire(
    payload: Mapping[str, object],
) -> (
    GridFormulaObservation
    | FieldFormulaObservation
    | GridFormulaValueObservation
    | FieldFormulaValueObservation
):
    kind = payload.get("kind")
    if kind == "formula.grid.observation":
        return GridFormulaObservation.from_wire(payload)
    if kind == "formula.field.observation":
        return FieldFormulaObservation.from_wire(payload)
    if kind == "formula.grid.values.observation":
        return GridFormulaValueObservation.from_wire(payload)
    if kind == "formula.field.values.observation":
        return FieldFormulaValueObservation.from_wire(payload)
    raise ValueError("unsupported formula observation kind")


def formula_operation_from_wire(
    payload: Mapping[str, object],
) -> FormulaMutation | RecalculationObservation:
    kind = payload.get("kind")
    if kind == "formula.mutation":
        return FormulaMutation.from_wire(payload)
    if kind == "formula.recalculation":
        return RecalculationObservation.from_wire(payload)
    raise ValueError("unsupported formula operation kind")


def formula_observation_hash(
    observation: GridFormulaObservation
    | FieldFormulaObservation
    | GridFormulaValueObservation
    | FieldFormulaValueObservation,
) -> str:
    encoded = json.dumps(
        observation.to_wire(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "formula_observation_from_wire",
    "formula_observation_hash",
    "formula_operation_from_wire",
]
