from pathlib import Path

import pytest
from openpyxl import load_workbook

from open_table_connector.cli.model import CliOptions, FormatName, parse_endpoint
from open_table_connector.cli.pipeline import convert_endpoint, import_endpoint
from open_table_connector.cli.registry import build_default_registry
from open_table_connector.contract import ConnectorError, ConnectorErrorCode


def test_cli_lists_concrete_local_connector_types() -> None:
    registry = build_default_registry()

    identities = {adapter.identity.connector_id for adapter in registry.list()}

    assert {"local_files", "csv", "excel", "md"} <= identities


@pytest.mark.parametrize(
    ("raw", "connector_id"),
    (
        ("csv:///tmp/orders.csv", "csv"),
        ("excel:///tmp/orders.xlsx", "excel"),
        ("md:///tmp/orders.md", "md"),
    ),
)
def test_registry_routes_explicit_local_scheme(raw: str, connector_id: str) -> None:
    adapter = build_default_registry().connector_for(parse_endpoint(raw))

    assert adapter.identity.connector_id == connector_id


def test_registry_routes_bare_path_to_local_files_facade(tmp_path: Path) -> None:
    endpoint = parse_endpoint(str(tmp_path / "orders.csv"))

    adapter = build_default_registry().connector_for(endpoint)

    assert adapter.identity.connector_id == "local_files"


def test_cli_converts_csv_to_explicit_markdown_destination(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    destination = tmp_path / "orders.md"
    source.write_text("id\n1\n", encoding="utf8")

    summary = convert_endpoint(
        parse_endpoint(str(source)),
        parse_endpoint(f"md://{destination}"),
        build_default_registry(),
        CliOptions(),
    )

    assert summary.rows_written == 1
    assert destination.read_text(encoding="utf8").splitlines()[0].startswith("| id")


def test_cli_converts_csv_to_explicit_excel_destination(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    destination = tmp_path / "orders.xlsx"
    source.write_text("id\n1\n", encoding="utf8")

    summary = convert_endpoint(
        parse_endpoint(str(source)),
        parse_endpoint(f"excel://{destination}"),
        build_default_registry(),
        CliOptions(),
    )

    assert summary.rows_written == 1
    workbook = load_workbook(destination, read_only=True, data_only=True)
    try:
        assert list(workbook.active.values) == [("id",), ("1",)]
    finally:
        workbook.close()


def test_explicit_local_destination_scheme_takes_precedence_over_to_format(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    destination = tmp_path / "orders.md"
    source.write_text("id\n1\n", encoding="utf8")

    convert_endpoint(
        parse_endpoint(str(source)),
        parse_endpoint(f"md://{destination}"),
        build_default_registry(),
        CliOptions(to_format=FormatName.JSON),
    )

    assert destination.read_text(encoding="utf8").splitlines()[0].startswith("| id")


def test_import_rejects_explicit_local_destination_before_read(tmp_path: Path) -> None:
    source = tmp_path / "orders.csv"
    source.write_text("id\n1\n", encoding="utf8")

    with pytest.raises(ConnectorError) as error:
        import_endpoint(
            parse_endpoint(str(source)),
            parse_endpoint(f"csv://{tmp_path / 'copy.csv'}"),
            build_default_registry(),
            CliOptions(),
        )

    assert error.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert error.value.safe_details["scheme"] == "csv"
