from __future__ import annotations

import open_table_connector.sdk as otc
import polars as pl
import pytest
from open_table_connector.contract import TableURI


def test_table_mode_uses_canonical_wires_and_decodes_legacy_values() -> None:
    assert otc.TableMode.BASE_MODE.to_wire() == "base-mode"
    assert otc.TableMode.SHEET_MODE.to_wire() == "sheet-mode"
    assert otc.TableMode.from_wire("base-mode") is otc.TableMode.BASE_MODE
    assert otc.TableMode.from_wire("sheet-mode") is otc.TableMode.SHEET_MODE
    assert otc.TableMode.from_wire("base") is otc.TableMode.BASE_MODE
    assert otc.TableMode.from_wire("sheet") is otc.TableMode.SHEET_MODE

    with pytest.raises(ValueError, match="table mode"):
        otc.TableMode.from_wire("worksheet")


def test_address_and_destination_values_round_trip_without_credentials() -> None:
    table = otc.DatabaseTableAddress(
        database=TableURI("postgres://warehouse"),
        name=otc.QualifiedTableName(schema="public", table="orders"),
    )
    assert table.to_wire() == {
        "kind": "database_table",
        "database": {"value": "postgres://warehouse"},
        "name": {"catalog": None, "schema": "public", "table": "orders"},
    }
    assert otc.DatabaseTableAddress.from_wire(table.to_wire()) == table

    base_destination = otc.BaseModeDestination(
        container=TableURI("gsheets://spreadsheet-id"),
        table_name="Orders",
    )
    assert base_destination.to_wire() == {
        "kind": "base-mode-destination",
        "container": {"value": "gsheets://spreadsheet-id"},
        "table_name": "Orders",
    }

    sheet_destination = otc.SheetModeDestination(
        grid=TableURI("xlsx:///tmp/orders.xlsx"),
        anchor="B3",
        header=True,
    )
    assert otc.SheetModeDestination.from_wire(sheet_destination.to_wire()) == sheet_destination


def test_sheet_range_source_requires_an_explicit_schema_policy_contract() -> None:
    source = otc.SheetRangeSource(
        grid=TableURI("xlsx:///tmp/orders.xlsx"),
        cell_range="A1:C5",
        header=True,
        schema=pl.Schema({"order_id": pl.Int64, "status": pl.String}),
        schema_policy=otc.SchemaPolicy.VALIDATE_DECLARED,
        observed_revision="rev-1",
    )

    restored = otc.SheetRangeSource.from_wire(source.to_wire())
    assert restored == source

    with pytest.raises(ValueError, match="requires schema"):
        otc.SheetRangeSource(
            grid=TableURI("xlsx:///tmp/orders.xlsx"),
            cell_range="A1:C5",
            header=True,
            schema=None,
            schema_policy=otc.SchemaPolicy.VALIDATE_DECLARED,
        )

    with pytest.raises(ValueError, match="requires schema=None"):
        otc.SheetRangeSource(
            grid=TableURI("xlsx:///tmp/orders.xlsx"),
            cell_range="A1:C5",
            header=True,
            schema=pl.Schema({"order_id": pl.Int64}),
            schema_policy=otc.SchemaPolicy.INFER_COMPLETE,
        )
