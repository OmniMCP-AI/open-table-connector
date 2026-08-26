from __future__ import annotations

import pytest

from open_connectors.contract import BaseCoordinate, SheetCoordinate


def test_base_coordinate_accepts_stable_record_id() -> None:
    coordinate = BaseCoordinate(record_id="row-1")

    assert coordinate.identity_kind == "record_id"
    assert coordinate.to_wire() == {"record_id": "row-1"}


def test_base_coordinate_accepts_declared_key_before_snapshot_ordinal() -> None:
    coordinate = BaseCoordinate(
        key={"account_id": "a-1", "period": "2026-08"},
    )

    assert coordinate.identity_kind == "key"
    assert coordinate.to_wire() == {
        "key": {"account_id": "a-1", "period": "2026-08"},
    }


def test_base_coordinate_requires_snapshot_for_ordinal() -> None:
    with pytest.raises(ValueError, match="snapshot"):
        BaseCoordinate(ordinal=4)


def test_base_coordinate_requires_record_id_key_or_ordinal() -> None:
    with pytest.raises(ValueError, match="record_id, key, or ordinal"):
        BaseCoordinate()


def test_sheet_coordinate_requires_positive_row_and_preserves_column() -> None:
    coordinate = SheetCoordinate(sheet="Orders", row=3, column="B")

    assert coordinate.to_wire() == {"sheet": "Orders", "row": 3, "column": "B"}

    with pytest.raises(ValueError, match="positive"):
        SheetCoordinate(sheet="Orders", row=0)
