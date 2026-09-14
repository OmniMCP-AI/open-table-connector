from datetime import UTC, date, datetime
from decimal import Decimal

import polars as pl
import pytest
from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import (
    PORTABLE_TABLE_PROFILE_V1,
    Client,
    ConnectorRegistry,
    ErrorCode,
    OTCError,
    SheetModeDestination,
)
from open_table_connector.sdk.model import SheetModeTableAddress
from openpyxl import Workbook, load_workbook


def _client():
    return Client(registry=ConnectorRegistry([LocalFilesConnector()]))


def _portable(client, frame, destination):
    return client.materialize(
        frame,
        to=destination,
        profile=PORTABLE_TABLE_PROFILE_V1,
        idempotency_key="excel-portable-test",
    )


def test_portable_excel_uses_structured_destination_and_recovers_exact_types(tmp_path):
    path = tmp_path / "typed.xlsx"
    source = pl.DataFrame(
        {
            "text": ["東京", "", None],
            "flag": [True, False, None],
            "integer": [9223372036854775807, -9223372036854775808, None],
            "float": [1.5, None, -0.0],
            "decimal": [Decimal("123.40"), None, Decimal("-0.01")],
            "day": [date(2024, 1, 2), None, date(1999, 12, 31)],
            "stamp": [
                datetime(2024, 1, 2, 3, 4, 5, 678901, tzinfo=UTC),
                None,
                datetime(1999, 12, 31, 23, 59, 59, tzinfo=UTC),
            ],
        },
        schema={
            "text": pl.String,
            "flag": pl.Boolean,
            "integer": pl.Int64,
            "float": pl.Float64,
            "decimal": pl.Decimal(precision=10, scale=2),
            "day": pl.Date,
            "stamp": pl.Datetime("us", "UTC"),
        },
    )
    destination = SheetModeDestination(path.as_uri(), "A1", True, "Base")

    result = _portable(_client(), source, destination)

    address = result.require_value()._binding.address
    assert isinstance(address, SheetModeTableAddress)
    assert address.grid.value == path.as_uri()
    assert address.table_id
    assert SheetModeTableAddress.from_wire(address.to_wire()) == address
    assert _client().open(address).require_value().read().require_value().equals(source)


def test_portable_excel_all_null_and_zero_rows_require_durable_metadata(tmp_path):
    path = tmp_path / "empty.xlsx"
    source = pl.DataFrame(
        {"empty": [None, None]}, schema={"empty": pl.Decimal(precision=8, scale=3)}
    )
    result = _portable(_client(), source, f"file://{path}#sheet=Base")
    assert _client().open(result.require_value()._binding.address).require_value().read().require_value().equals(source)

    zero = pl.DataFrame(schema={"id": pl.Int64, "when": pl.Datetime("us", "UTC")})
    _portable(_client(), zero, f"file://{path}#sheet=Zero")
    assert _client().open(f"file://{path}#sheet=Zero").require_value().read().require_value().equals(zero)


def test_portable_excel_rejects_casefold_conflict_and_preserves_unrelated_sheet(tmp_path):
    path = tmp_path / "existing.xlsx"
    book = Workbook()
    report = book.active
    report.title = "Report"
    report["A1"] = "Title"
    report["A1"].font = report["A1"].font.copy(bold=True)
    report["B1"] = "=1+2"
    book.save(path)
    book.close()

    result = _portable(_client(), pl.DataFrame({"id": [1]}), f"file://{path}#sheet=Base")
    assert result.commit.value == "committed"
    before = path.read_bytes()
    with pytest.raises(OTCError) as caught:
        _portable(_client(), pl.DataFrame({"id": [2]}), f"file://{path}#sheet=base")
    assert caught.value.result.error.code is ErrorCode.DESTINATION_EXISTS
    assert path.read_bytes() == before
    observed = load_workbook(path, data_only=False)
    try:
        assert observed["Report"]["A1"].value == "Title"
        assert observed["Report"]["A1"].font.bold is True
        assert observed["Report"]["B1"].value == "=1+2"
    finally:
        observed.close()


def test_portable_excel_missing_or_tampered_metadata_never_infers_schema(tmp_path):
    path = tmp_path / "tampered.xlsx"
    result = _portable(_client(), pl.DataFrame({"id": [1]}), f"file://{path}#sheet=Base")
    address = result.require_value()._binding.address
    book = load_workbook(path)
    try:
        metadata = next(sheet for sheet in book.worksheets if sheet.title.startswith("_otc_materialization_"))
        metadata["A1"] = "tampered"
        book.save(path)
    finally:
        book.close()
    with pytest.raises(OTCError) as caught:
        _client().open(address)
    assert caught.value.result.error.code is ErrorCode.INVALID_SCHEMA
