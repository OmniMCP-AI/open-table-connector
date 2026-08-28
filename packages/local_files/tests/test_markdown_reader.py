from __future__ import annotations

from open_table_connector.local_files.markdown_reader import (
    is_markdown_payload,
    read_markdown_arrow,
)


def test_markdown_reader_round_trips_escaped_cells_and_hyphen_rows() -> None:
    table = read_markdown_arrow(
        "| id | note |\n| --- | --- |\n| 1 | a \\| b |\n| - | - |\n",
        source="orders.md",
    )

    assert table.to_pylist() == [
        {"id": "1", "note": "a | b"},
        {"id": "-", "note": "-"},
    ]


def test_markdown_payload_requires_a_pipe_table_separator() -> None:
    assert is_markdown_payload("# title\nplain prose\n") is False
    assert is_markdown_payload("| id |\n| --- |\n| 1 |\n") is True
