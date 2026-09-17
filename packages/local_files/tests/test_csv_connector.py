from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest
from open_table_connector.conformance import run_read_suite
from open_table_connector.contract import (
    SCHEME_FILE,
    InspectRequest,
    ResolveContext,
    ResourceLimits,
    TableMode,
    TableURI,
)
from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode
from open_table_connector.local_files.csv_connector import (
    CsvConnector,
    CsvReadOptions,
    CsvTableReadRequest,
)
from open_table_connector.local_files.resolver import LocalFormat


def test_csv_connector_identity_and_manifest_pin_the_public_scheme() -> None:
    connector = CsvConnector()

    assert connector.identity.connector_id == "csv"
    assert connector.manifest.connector == connector.identity
    assert connector.manifest.uri_schemes == (SCHEME_FILE,)
    assert connector.manifest.modes == (TableMode.SHEET,)
    assert [capability.capability_id for capability in connector.manifest.capabilities] == [
        "uri.resolve",
        "table.inspect",
        "table.read.arrow",
        "table.read.polars",
    ]


def test_csv_connector_reads_arrow_and_polars_with_matching_receipts(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount,label\n1,2.50,中文\n2,,last\n", encoding="utf-8")
    request = CsvTableReadRequest(TableURI(source.as_uri()))

    connector = CsvConnector()
    arrow_result = connector.read_arrow(request)
    polars_result = connector.read_polars(request)

    assert isinstance(arrow_result.table, pa.Table)
    assert arrow_result.table.to_pylist() == [
        {"id": "1", "amount": "2.50", "label": "中文"},
        {"id": "2", "amount": None, "label": "last"},
    ]
    assert polars_result.frame.to_dicts() == [
        {"id": "1", "amount": "2.50", "label": "中文"},
        {"id": "2", "amount": None, "label": "last"},
    ]
    assert arrow_result.receipt.connector.connector_id == "csv"
    assert polars_result.receipt.connector.connector_id == "csv"
    assert arrow_result.receipt.safe_uri == TableURI(source.as_uri())
    assert polars_result.receipt.safe_uri == TableURI(source.as_uri())
    assert arrow_result.receipt.coordinate_convention.sheet == "data"
    assert arrow_result.receipt.coordinate_convention.header_rows == 1
    assert arrow_result.receipt.coordinate_convention.first_data_row == 2


def test_csv_connector_resolves_canonical_file_uri(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\n1,2.50\n", encoding="utf-8")
    uri = TableURI(source.as_uri())

    resolved = CsvConnector().resolve(uri, ResolveContext())

    assert resolved.uri == uri
    assert resolved.resource.path == source
    assert resolved.resource.format is LocalFormat.CSV


def test_csv_connector_rejects_csv_scheme_as_public_route() -> None:
    retired_route = "csv" + ":///tmp/orders.csv"

    with pytest.raises(ConnectorError, match="file Connector accepts only file URIs") as raised:
        CsvConnector().resolve(TableURI(retired_route), ResolveContext())

    assert raised.value.code is ConnectorErrorCode.INVALID_URI
    assert raised.value.safe_details == {"scheme": "csv"}


def test_csv_connector_honors_delimiter_and_row_limit(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id;amount\n1;2.50\n2;3.25\n", encoding="utf-8")
    request = CsvTableReadRequest(
        TableURI(source.as_uri()),
        resource_limits=ResourceLimits(max_rows=1),
        options=CsvReadOptions(separator=";"),
    )

    result = CsvConnector().read_arrow(request)

    assert result.table.to_pylist() == [{"id": "1", "amount": "2.50"}]


def test_csv_connector_inspection_reports_schema_and_sheet_facts(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\n1,2.50\n", encoding="utf-8")

    inspection = CsvConnector().inspect(InspectRequest(TableURI(source.as_uri())))

    assert inspection.safe_uri == TableURI(source.as_uri())
    assert inspection.mode is TableMode.SHEET
    assert inspection.columns == ("id", "amount")
    assert inspection.row_count == 1
    assert inspection.coordinate_convention.sheet == "data"
    assert inspection.facts["worksheets"] == ["data"]
    assert inspection.schema_fingerprint


def test_csv_connector_rejects_query_parameters_before_reading(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\n1,2.50\n", encoding="utf-8")

    with pytest.raises(ConnectorError) as raised:
        CsvConnector().resolve(
            TableURI(f"{source.as_uri()}?dialect=excel"),
            CsvTableReadRequest(TableURI(source.as_uri())).resolve_context,
        )

    assert raised.value.code is ConnectorErrorCode.INVALID_URI


def test_csv_connector_rejects_mismatched_excel_payload(tmp_path: Path) -> None:
    from openpyxl import Workbook

    source = tmp_path / "orders.xlsx"
    workbook = Workbook()
    workbook.active.append(["id"])
    workbook.active.append(["1"])
    workbook.save(source)

    with pytest.raises(ConnectorError) as raised:
        CsvConnector().read_arrow(CsvTableReadRequest(TableURI(source.as_uri())))

    assert raised.value.code is ConnectorErrorCode.INVALID_URI


def test_csv_connector_maps_unknown_encoding_to_connector_error(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    request = CsvTableReadRequest(
        TableURI(source.as_uri()),
        options=CsvReadOptions(encoding="x-open-table-connector-unknown"),
    )

    with pytest.raises(ConnectorError) as raised:
        CsvConnector().read_arrow(request)

    assert raised.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert raised.value.safe_details["encoding"] == "x-open-table-connector-unknown"


def test_csv_connector_passes_shared_read_conformance(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\n1,2.50\n2,\n", encoding="utf-8")

    run_read_suite(CsvConnector(), [CsvTableReadRequest(TableURI(source.as_uri()))])
