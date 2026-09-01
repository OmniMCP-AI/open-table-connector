from __future__ import annotations

import sqlite3

import polars as pl
from open_table_connector.contract import ExecutionRequest, TableURI, TableWriteRequest
from open_table_connector.sqlite.reader import (
    SQLiteConnector,
    SQLiteReadOptions,
    SQLiteTableReadRequest,
)


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


def test_sqlite_reads_qualified_main_table(tmp_path) -> None:
    path = tmp_path / "qualified.db"
    connection = sqlite3.connect(path)
    connection.execute("create table orders (id integer)")
    connection.execute("insert into orders values (1)")
    connection.commit()
    connection.close()
    result = SQLiteConnector().read_polars(
        SQLiteTableReadRequest(
            TableURI(f"sqlite://{path.as_posix()}"),
            options=SQLiteReadOptions(table="main.orders"),
        )
    )
    assert result.frame.to_dicts() == [{"id": 1}]


def test_sqlite_write_execute_and_transaction_are_physical_roles(tmp_path) -> None:
    path = tmp_path / "materialized.db"
    uri = TableURI(f"sqlite://{path.as_posix()}")
    connector = SQLiteConnector()
    frame = pl.DataFrame({"id": ["a", "b"], "amount": ["1.00", None]})

    written = connector.write(TableWriteRequest(uri, frame, table="orders"))
    assert written.affected_rows == 2
    executed = connector.execute(ExecutionRequest(uri, "UPDATE orders SET amount = ? WHERE id = ?", ("2.00", "a")))
    assert executed.status == "completed"
    assert executed.affected_rows == 1

    connector.begin(uri)
    connector.execute(ExecutionRequest(uri, "INSERT INTO orders (id, amount) VALUES (?, ?)", ("c", "3.00")))
    connector.abort()
    assert connector.read_polars(SQLiteTableReadRequest(uri, options=SQLiteReadOptions(table="orders"))).frame.height == 2
