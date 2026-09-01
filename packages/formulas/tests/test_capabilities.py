from __future__ import annotations

from open_table_connector.contract import CapabilityIdentity
from open_table_connector.formulas import (
    ALL_CAPABILITIES,
    EXCEL_A1,
    FEISHU_BITABLE,
    FIELD_READ,
    FIELD_RECALCULATE,
    FIELD_SET,
    FIELD_VALUES_READ,
    FORMULA_DIALECTS,
    GOOGLE_SHEETS_A1,
    GRID_READ,
    GRID_RECALCULATE,
    GRID_SET,
    GRID_VALUES_READ,
    MAYBE_BASE,
    MAYBE_SHEET_A1,
)


def test_formula_capabilities_are_closed_and_ordered() -> None:
    assert ALL_CAPABILITIES == (
        GRID_READ,
        GRID_SET,
        GRID_VALUES_READ,
        GRID_RECALCULATE,
        FIELD_READ,
        FIELD_SET,
        FIELD_VALUES_READ,
        FIELD_RECALCULATE,
    )
    assert all(isinstance(capability, CapabilityIdentity) for capability in ALL_CAPABILITIES)
    assert [capability.to_reference() for capability in ALL_CAPABILITIES] == [
        "formula.grid.read/1.0",
        "formula.grid.set/1.0",
        "formula.grid.values.read/1.0",
        "formula.grid.recalculate/1.0",
        "formula.field.read/1.0",
        "formula.field.set/1.0",
        "formula.field.values.read/1.0",
        "formula.field.recalculate/1.0",
    ]


def test_formula_dialects_are_closed_and_stable() -> None:
    assert FORMULA_DIALECTS == (
        GOOGLE_SHEETS_A1,
        MAYBE_SHEET_A1,
        EXCEL_A1,
        MAYBE_BASE,
        FEISHU_BITABLE,
    )

