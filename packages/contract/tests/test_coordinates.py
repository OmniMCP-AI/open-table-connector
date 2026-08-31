from __future__ import annotations

import pytest

from open_table_connector.contract import BaseCoordinate, SheetCoordinate


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


def test_base_coordinate_rejects_conflicting_identities_and_round_trips_wire() -> None:
    with pytest.raises(ValueError, match="exactly one identity"):
        BaseCoordinate(record_id="row-1", key={"id": "row-1"})

    coordinate = BaseCoordinate(key={"id": "row-1"})
    assert BaseCoordinate.from_wire(coordinate.to_wire()) == coordinate


def test_base_coordinate_rejects_nonportable_key_scalars() -> None:
    with pytest.raises(ValueError, match="string, integer"):
        BaseCoordinate(key={"when": object()})
    with pytest.raises(ValueError, match="finite"):
        BaseCoordinate(key={"value": float("nan")})


def test_sheet_coordinate_requires_positive_row_and_preserves_column() -> None:
    coordinate = SheetCoordinate(sheet="Orders", row=3, column="B")

    assert coordinate.to_wire() == {"sheet": "Orders", "row": 3, "column": "B"}

    with pytest.raises(ValueError, match="positive"):
        SheetCoordinate(sheet="Orders", row=0)
