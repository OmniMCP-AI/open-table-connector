"""Closed capability identities and formula dialects."""

from __future__ import annotations

from open_table_connector.contract import CapabilityIdentity

GRID_READ = CapabilityIdentity("formula.grid.read", "1.0")
GRID_SET = CapabilityIdentity("formula.grid.set", "1.0")
GRID_VALUES_READ = CapabilityIdentity("formula.grid.values.read", "1.0")
GRID_RECALCULATE = CapabilityIdentity("formula.grid.recalculate", "1.0")
FIELD_READ = CapabilityIdentity("formula.field.read", "1.0")
FIELD_SET = CapabilityIdentity("formula.field.set", "1.0")
FIELD_VALUES_READ = CapabilityIdentity("formula.field.values.read", "1.0")
FIELD_RECALCULATE = CapabilityIdentity("formula.field.recalculate", "1.0")

ALL_CAPABILITIES = (
    GRID_READ,
    GRID_SET,
    GRID_VALUES_READ,
    GRID_RECALCULATE,
    FIELD_READ,
    FIELD_SET,
    FIELD_VALUES_READ,
    FIELD_RECALCULATE,
)

GOOGLE_SHEETS_A1 = "google-sheets-a1"
MAYBE_SHEET_A1 = "maybe-sheet-a1"
EXCEL_A1 = "excel-a1"
MAYBE_BASE = "maybe-base"
FEISHU_BITABLE = "feishu-bitable"

FORMULA_DIALECTS = (
    GOOGLE_SHEETS_A1,
    MAYBE_SHEET_A1,
    EXCEL_A1,
    MAYBE_BASE,
    FEISHU_BITABLE,
)

__all__ = [
    "ALL_CAPABILITIES",
    "EXCEL_A1",
    "FEISHU_BITABLE",
    "FIELD_READ",
    "FIELD_RECALCULATE",
    "FIELD_SET",
    "FIELD_VALUES_READ",
    "FORMULA_DIALECTS",
    "GOOGLE_SHEETS_A1",
    "GRID_READ",
    "GRID_RECALCULATE",
    "GRID_SET",
    "GRID_VALUES_READ",
    "MAYBE_BASE",
    "MAYBE_SHEET_A1",
]
