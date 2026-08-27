import io

import pyarrow as pa
import pytest

from open_connectors.contract import ConnectorError
from open_connectors.cli.formats import infer_format, read_local, write_local
from open_connectors.cli.model import Endpoint, FormatName, parse_endpoint


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


def test_infer_format_uses_explicit_format() -> None:
    endpoint = parse_endpoint("rows.csv")
    assert infer_format(endpoint, FormatName.JSONL) is FormatName.JSONL


def test_infer_format_uses_file_suffix_for_auto() -> None:
    endpoint = parse_endpoint("rows.table")
    assert infer_format(endpoint, FormatName.AUTO) is FormatName.TABLE
