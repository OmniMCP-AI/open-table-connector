import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pyarrow as pa
import pytest

from open_connectors.contract import ConnectorError
from open_connectors.cli.formats import infer_format, read_local, write_local
from open_connectors.cli.model import Endpoint, FormatName, parse_endpoint


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
    assert stream.getvalue() == '{"amount":1,"id":"a"}\n'


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
def test_json_writers_normalize_arrow_scalars_to_strict_json(format_name) -> None:
    table = pa.table(
        {
            "nan": [float("nan")],
            "positive_infinity": [float("inf")],
            "negative_infinity": [float("-inf")],
            "date": [date(2026, 8, 28)],
            "timestamp": [datetime(2026, 8, 28, 1, 2, 3, tzinfo=timezone.utc)],
            "decimal": pa.array([Decimal("12.30")], type=pa.decimal128(4, 2)),
            "nested": pa.array([[float("nan"), float("inf"), float("-inf")]]),
        }
    )
    stream = io.StringIO()

    write_local(table, parse_endpoint("-"), format_name, stream)

    payload = _strict_json_loads(stream.getvalue())
    row = payload[0] if format_name is FormatName.JSON else payload
    assert row == {
        "nan": None,
        "positive_infinity": None,
        "negative_infinity": None,
        "date": "2026-08-28",
        "timestamp": "2026-08-28T01:02:03+00:00",
        "decimal": "12.30",
        "nested": "[null,null,null]",
    }


def test_infer_format_uses_explicit_format() -> None:
    endpoint = parse_endpoint("rows.csv")
    assert infer_format(endpoint, FormatName.JSONL) is FormatName.JSONL


def test_infer_format_uses_file_suffix_for_auto() -> None:
    endpoint = parse_endpoint("rows.table")
    assert infer_format(endpoint, FormatName.AUTO) is FormatName.TABLE
