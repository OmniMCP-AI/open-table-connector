from __future__ import annotations

import pytest
from open_table_connector.formulas import A1Rectangle


def test_a1_range_parses_cells_and_preserves_absolute_markers() -> None:
    rectangle = A1Rectangle.parse("'Base Data'!$a2:B$4")

    assert rectangle.worksheet_name == "Base Data"
    assert rectangle.start_address == "$A2"
    assert rectangle.end_address == "B$4"
    assert rectangle.height == 3
    assert rectangle.width == 2
    assert rectangle.cell_count == 6


@pytest.mark.parametrize(
    "selector",
    ["A:A", "2:2", "A2:A", "B4:A1", "A1,B2", "A0", "A00", "$B0:C2"],
)
def test_a1_range_rejects_unbounded_reversed_or_disjoint_selectors(selector: str) -> None:
    with pytest.raises(ValueError):
        A1Rectangle.parse(selector)


def test_a1_range_rejects_prefix_after_binding() -> None:
    rectangle = A1Rectangle.parse("A1:B2")

    with pytest.raises(ValueError, match="worksheet prefix"):
        rectangle.require_unbound_selector("'Model'!A1:B2")
