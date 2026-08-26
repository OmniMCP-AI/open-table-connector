from __future__ import annotations

import sqlite3

from open_connectors.contract import TableURI
from open_connectors.sqlite.reader import SQLiteConnector, SQLiteReadOptions, SQLiteTableReadRequest


def test_sqlite_reads_real_db_and_preserves_base_coordinates(tmp_path) -> None:
    path = tmp_path / "orders.db"
    connection = sqlite3.connect(path)
    connection.execute("create table orders (id text, amount text)")
    connection.executemany("insert into orders values (?, ?)", [("a", "1.00"), ("b", None)])
    connection.commit()
    connection.close()

    result = SQLiteConnector().read_polars(
        SQLiteTableReadRequest(TableURI(f"sqlite://{path.as_posix()}"), options=SQLiteReadOptions(table="orders", record_id_field="id"))
    )

    assert result.frame.to_dicts() == [{"id": "a", "amount": "1.00"}, {"id": "b", "amount": None}]
    assert result.receipt.coordinate_convention.record_id_field == "id"
