import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pyarrow as pa
import pytest

from open_table_connector.contract import ConnectorError, ConnectorErrorCode
from open_table_connector.cli.formats import infer_format, read_local, write_local
from open_table_connector.cli.model import Endpoint, FormatName, parse_endpoint
from open_table_connector.cli.output import emit_error


def _strict_json_loads(text: str):
    def reject_constant(value: str):
        raise ValueError(f"non-standard JSON constant: {value}")

    return json.loads(text, parse_constant=reject_constant)


def test_csv_reader_preserves_empty_cells(tmp_path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id,amount,name\n1,,Bee\n", encoding="utf-8")
    table = read_local(parse_endpoint(str(source)), FormatName.CSV)
    assert table.to_pylist() == [{"id": "1", "amount": None, "name": "Bee"}]


def test_json_array_reader_unions_object_keys(tmp_path) -> None:
    source = tmp_path / "rows.json"
    source.write_text('[{"id":"a","amount":1},{"id":"b","name":"Bee"}]', encoding="utf-8")
    table = read_local(parse_endpoint(str(source)), FormatName.JSON)
    assert table.column_names == ["id", "amount", "name"]
    assert table.to_pylist() == [
        {"id": "a", "amount": 1, "name": None},
        {"id": "b", "amount": None, "name": "Bee"},
    ]


def test_jsonl_reader_ignores_blank_lines(tmp_path) -> None:
    source = tmp_path / "rows.jsonl"
    source.write_text('{"id":"a"}\n\n{"id":"b"}\n', encoding="utf-8")
    assert read_local(parse_endpoint(str(source)), FormatName.JSONL).num_rows == 2


def test_markdown_table_reader_accepts_separator_row(tmp_path) -> None:
    source = tmp_path / "rows.table"
    source.write_text("| id | amount |\n| --- | ---: |\n| a | 1 |\n", encoding="utf-8")
    assert read_local(parse_endpoint(str(source)), FormatName.TABLE).to_pylist() == [{"id": "a", "amount": "1"}]


def test_markdown_table_reader_rejects_separator_row_with_wrong_width(tmp_path) -> None:
    source = tmp_path / "rows.table"
    source.write_text("| a | b |\n| --- |\n| 1 | 2 |\n", encoding="utf-8")
    with pytest.raises(ConnectorError, match="inconsistent column count") as excinfo:
        read_local(parse_endpoint(str(source)), FormatName.TABLE)
    assert excinfo.value.safe_details["line"] == 2


def test_markdown_table_reader_treats_invalid_separator_grammar_as_data(tmp_path) -> None:
    source = tmp_path / "rows.table"
    source.write_text("| a | b |\n| ::- | --- |\n| 1 | 2 |\n", encoding="utf-8")
    assert read_local(parse_endpoint(str(source)), FormatName.TABLE).to_pylist() == [
        {"a": "::-", "b": "---"},
        {"a": "1", "b": "2"},
    ]


def test_jsonl_writer_emits_one_object_per_line() -> None:
    stream = io.StringIO()
    write_local(pa.table({"id": ["a"], "amount": [1]}), parse_endpoint("-"), FormatName.JSONL, stream)
    assert stream.getvalue() == '{"id":"a","amount":1}\n'


def test_table_writer_escapes_special_characters_and_keeps_rows_aligned() -> None:
    stream = io.StringIO()
    table = pa.table({"value": ["left|right", r"C:\temp", "line1\nline2"]})

    write_local(table, parse_endpoint("-"), FormatName.TABLE, stream)

    lines = stream.getvalue().splitlines()
    assert lines == [
        "| value        |",
        "| ------------ |",
        r"| left\|right  |",
        r"| C:\\temp     |",
        r"| line1\nline2 |",
    ]
    assert len({len(line) for line in lines}) == 1


@pytest.mark.parametrize("value", ["left|right", r"C:\temp", "line1\nline2"])
def test_markdown_table_writer_output_round_trips_escaped_cells(value: str) -> None:
    stream = io.StringIO()
    write_local(pa.table({"value": [value]}), parse_endpoint("-"), FormatName.TABLE, stream)

    table = read_local(
        parse_endpoint("-"),
        FormatName.TABLE,
        io.StringIO(stream.getvalue()),
    )

    assert table.to_pylist() == [{"value": value}]


def test_markdown_table_writer_preserves_separator_looking_data_rows() -> None:
    stream = io.StringIO()
    write_local(
        pa.table({"a": ["---"], "b": ["---"]}),
        parse_endpoint("-"),
        FormatName.TABLE,
        stream,
    )

    table = read_local(
        parse_endpoint("-"),
        FormatName.TABLE,
        io.StringIO(stream.getvalue()),
    )

    assert table.to_pylist() == [{"a": "---", "b": "---"}]


@pytest.mark.parametrize("format_name", (FormatName.JSON, FormatName.JSONL))
def test_json_writers_preserve_nested_arrow_values(format_name) -> None:
    table = pa.table(
        {
            "date": [date(2026, 8, 28)],
            "timestamp": [datetime(2026, 8, 28, 1, 2, 3, tzinfo=timezone.utc)],
            "decimal": pa.array([Decimal("12.30")], type=pa.decimal128(4, 2)),
            "nested": pa.array([[1.0, 2.0]]),
        }
    )
    stream = io.StringIO()

    write_local(table, parse_endpoint("-"), format_name, stream)

    payload = _strict_json_loads(stream.getvalue())
    row = payload[0] if format_name is FormatName.JSON else payload
    assert row == {
        "date": "2026-08-28",
        "timestamp": "2026-08-28T01:02:03.000000000Z",
        "decimal": "12.30",
        "nested": [1.0, 2.0],
    }


@pytest.mark.parametrize("format_name", (FormatName.JSON, FormatName.JSONL))
def test_json_writers_reject_non_finite_values(format_name) -> None:
    with pytest.raises(ConnectorError, match="non-finite"):
        write_local(
            pa.table({"value": [float("nan")]}),
            parse_endpoint("-"),
            format_name,
            io.StringIO(),
        )


def test_infer_format_uses_explicit_format() -> None:
    endpoint = parse_endpoint("rows.csv")
    assert infer_format(endpoint, FormatName.JSONL) is FormatName.JSONL


def test_infer_format_uses_file_suffix_for_auto() -> None:
    endpoint = parse_endpoint("rows.table")
    assert infer_format(endpoint, FormatName.AUTO) is FormatName.TABLE


@pytest.mark.parametrize(
    ("component", "expected_details", "secret"),
    (
        ("?view=query-secret&mode=compact", {"query_keys": ["mode", "view"]}, "query-secret"),
        ("#token=fragment-secret&sheet=Orders", {"fragment_keys": ["sheet", "token"]}, "fragment-secret"),
    ),
)
def test_local_destination_rejects_uri_components_without_leaking_values(
    tmp_path,
    component: str,
    expected_details: dict[str, list[str]],
    secret: str,
) -> None:
    destination = tmp_path / "orders.csv"
    endpoint = parse_endpoint(f"csv://{destination}{component}")

    with pytest.raises(ConnectorError) as raised:
        write_local(pa.table({"id": ["1"]}), endpoint, FormatName.CSV)

    output = io.StringIO()
    assert emit_error(raised.value, output) == 2
    payload = json.loads(output.getvalue())
    assert raised.value.code is ConnectorErrorCode.INVALID_URI
    assert payload["safe_details"] == expected_details
    assert secret not in output.getvalue()
    assert endpoint.raw not in output.getvalue()


@pytest.mark.parametrize(
    ("component", "expected_details", "secret"),
    (
        ("?opaque-query-secret", {"query_keys": []}, "opaque-query-secret"),
        ("#opaque-fragment-secret", {"fragment_keys": []}, "opaque-fragment-secret"),
    ),
)
def test_local_destination_rejects_opaque_uri_components_without_leaking_tokens(
    tmp_path,
    component: str,
    expected_details: dict[str, list[str]],
    secret: str,
) -> None:
    destination = tmp_path / "orders.csv"
    endpoint = parse_endpoint(f"csv://{destination}{component}")

    with pytest.raises(ConnectorError) as raised:
        write_local(pa.table({"id": ["1"]}), endpoint, FormatName.CSV)

    output = io.StringIO()
    assert emit_error(raised.value, output) == 2
    payload = json.loads(output.getvalue())
    assert raised.value.code is ConnectorErrorCode.INVALID_URI
    assert payload["safe_details"] == expected_details
    assert secret not in str(raised.value.safe_details)
    assert secret not in output.getvalue()
    assert endpoint.raw not in output.getvalue()


def test_local_destination_accepts_localhost_absolute_uri(tmp_path) -> None:
    destination = tmp_path / "orders.csv"
    endpoint = parse_endpoint(f"csv://localhost{destination}")

    write_local(pa.table({"id": ["1"]}), endpoint, FormatName.CSV)

    assert destination.read_text(encoding="utf8") == "id\n1\n"


def test_local_destination_rejects_relative_explicit_uri() -> None:
    endpoint = parse_endpoint("csv:orders.csv")

    with pytest.raises(ConnectorError) as raised:
        write_local(pa.table({"id": ["1"]}), endpoint, FormatName.CSV)

    assert raised.value.code is ConnectorErrorCode.INVALID_URI
