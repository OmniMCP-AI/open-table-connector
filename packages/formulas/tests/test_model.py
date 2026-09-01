from __future__ import annotations

import pytest
from open_table_connector.formulas import (
    BoundFieldFormulaTarget,
    BoundGridFormulaTarget,
    FieldFormulaTarget,
    FieldRecalculationScope,
    FieldRef,
    FormulaExpression,
    FormulaResourceLimits,
    GridFormulaTarget,
    GridRecalculationScope,
    WorksheetRef,
)


def test_targets_are_kind_safe_and_closed() -> None:
    grid = GridFormulaTarget(
        grid="gsheets://book-1",
        worksheet=WorksheetRef(name="Model"),
    )
    field = FieldFormulaTarget(
        table=object(),
        field=FieldRef(field_id="fld-margin"),
    )

    assert grid.grid.value == "gsheets://book-1"
    assert field.field.field_id == "fld-margin"

    with pytest.raises(ValueError, match="exactly one"):
        WorksheetRef(name="Model", worksheet_id="17")


def test_formula_expression_preserves_native_text_exactly() -> None:
    expression = FormulaExpression(
        "='Base Data'!$A2+EXT.FETCH(\"https://x.test\")",
        "maybe-sheet-a1",
    )

    assert expression.text == "='Base Data'!$A2+EXT.FETCH(\"https://x.test\")"
    assert expression.sha256.startswith("sha256:")


def test_bound_targets_require_stable_provider_ids() -> None:
    bound_grid = BoundGridFormulaTarget(
        grid="gsheets://book-1",
        worksheet=WorksheetRef(worksheet_id="17"),
    )
    bound_field = BoundFieldFormulaTarget(
        table=object(),
        field=FieldRef(field_id="fld-margin"),
    )

    assert bound_grid.worksheet.worksheet_id == "17"
    assert bound_field.field.field_id == "fld-margin"

    with pytest.raises(ValueError, match="stable"):
        BoundGridFormulaTarget(
            grid="gsheets://book-1",
            worksheet=WorksheetRef(name="Model"),
        )


def test_resource_limits_and_recalculation_scopes_are_closed() -> None:
    limits = FormulaResourceLimits(
        max_cells=10,
        max_records=20,
        max_response_bytes=30,
        timeout_seconds=4.5,
    )

    assert limits.max_cells == 10
    assert tuple(scope.value for scope in GridRecalculationScope) == (
        "range",
        "worksheet",
        "workbook",
    )
    assert tuple(scope.value for scope in FieldRecalculationScope) == ("field", "table")

