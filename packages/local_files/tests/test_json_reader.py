from __future__ import annotations

from pathlib import Path

from open_connectors.contract import TableURI
from open_connectors.local_files.reader import LocalFilesConnector, LocalTableReadRequest


def test_json_records_keep_first_seen_column_order_and_types(tmp_path: Path) -> None:
    source = tmp_path / "orders.json"
    source.write_text('[{"id": 1, "label": "first"}, {"id": 2, "amount": 3.5}]', encoding="utf-8")

    result = LocalFilesConnector().read_polars(LocalTableReadRequest(TableURI(source.as_uri())))

    assert result.frame.columns == ["id", "label", "amount"]
    assert result.frame.to_dicts() == [
        {"id": 1, "label": "first", "amount": None},
        {"id": 2, "label": None, "amount": 3.5},
    ]


def test_json_array_uses_first_row_as_deterministic_header(tmp_path: Path) -> None:
    source = tmp_path / "orders.json"
    source.write_text('[["id", "amount"], ["1", 2.5]]', encoding="utf-8")

    result = LocalFilesConnector().read_polars(LocalTableReadRequest(TableURI(source.as_uri())))

    assert result.frame.to_dicts() == [{"id": "1", "amount": 2.5}]
