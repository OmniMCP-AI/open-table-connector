from __future__ import annotations

from pathlib import Path

import pytest

from open_table_connector.contract import InspectRequest, ResourceLimits, TableMode, TableURI
from open_table_connector.contract.errors import ConnectorError, ConnectorErrorCode
from open_table_connector.conformance import run_read_suite
from open_table_connector.local_files.markdown_connector import (
    MarkdownConnector,
    MarkdownReadOptions,
    MarkdownTableReadRequest,
)


def test_markdown_connector_identity_and_manifest_pin_the_public_scheme() -> None:
    connector = MarkdownConnector()

    assert connector.identity.connector_id == "md"
    assert connector.manifest.connector == connector.identity
    assert connector.manifest.uri_schemes == ("md",)
    assert connector.manifest.modes == (TableMode.SHEET,)
    assert [capability.capability_id for capability in connector.manifest.capabilities] == [
        "uri.resolve",
        "table.inspect",
        "table.read.arrow",
        "table.read.polars",
    ]


def test_markdown_connector_reads_pipe_tables_with_matching_receipts(tmp_path: Path) -> None:
    source = tmp_path / "orders.md"
    source.write_text("| id | note |\n| --- | --- |\n| 1 | a \\| b |\n| - | - |\n", encoding="utf-8")
    request = MarkdownTableReadRequest(TableURI(f"md://{source}"))

    connector = MarkdownConnector()
    arrow_result = connector.read_arrow(request)
    polars_result = connector.read_polars(request)

    assert arrow_result.table.to_pylist() == [
        {"id": "1", "note": "a | b"},
        {"id": "-", "note": "-"},
    ]
    assert polars_result.frame.to_dicts() == [
        {"id": "1", "note": "a | b"},
        {"id": "-", "note": "-"},
    ]
    assert arrow_result.receipt.connector.connector_id == "md"
    assert polars_result.receipt.connector.connector_id == "md"
    assert arrow_result.receipt.coordinate_convention.sheet == "data"


def test_markdown_connector_honors_row_limit(tmp_path: Path) -> None:
    source = tmp_path / "orders.md"
    source.write_text("| id |\n| --- |\n| 1 |\n| 2 |\n", encoding="utf-8")
    request = MarkdownTableReadRequest(
        TableURI(f"md://{source}"),
        resource_limits=ResourceLimits(max_rows=1),
        options=MarkdownReadOptions(),
    )

    result = MarkdownConnector().read_arrow(request)

    assert result.table.to_pylist() == [{"id": "1"}]


def test_markdown_connector_inspection_reports_data_sheet_facts(tmp_path: Path) -> None:
    source = tmp_path / "orders.md"
    source.write_text("| id |\n| --- |\n| 1 |\n", encoding="utf-8")

    inspection = MarkdownConnector().inspect(InspectRequest(TableURI(f"md://{source}")))

    assert inspection.mode is TableMode.SHEET
    assert inspection.columns == ("id",)
    assert inspection.row_count == 1
    assert inspection.coordinate_convention.sheet == "data"
    assert inspection.facts["worksheets"] == ["data"]


def test_markdown_connector_rejects_relative_paths() -> None:
    with pytest.raises(ConnectorError) as raised:
        MarkdownConnector().read_arrow(MarkdownTableReadRequest(TableURI("md://orders.md")))

    assert raised.value.code is ConnectorErrorCode.INVALID_URI


def test_markdown_connector_rejects_mismatched_csv_payload(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id,amount\n1,2.50\n", encoding="utf-8")

    with pytest.raises(ConnectorError) as raised:
        MarkdownConnector().read_arrow(MarkdownTableReadRequest(TableURI(f"md://{source}")))

    assert raised.value.code is ConnectorErrorCode.INVALID_URI


def test_markdown_connector_passes_shared_read_conformance(tmp_path: Path) -> None:
    source = tmp_path / "orders.md"
    source.write_text("| id | amount |\n| --- | --- |\n| 1 | 2.50 |\n| 2 | |\n", encoding="utf-8")

    run_read_suite(
        MarkdownConnector(),
        [MarkdownTableReadRequest(TableURI(f"md://{source}"))],
    )
