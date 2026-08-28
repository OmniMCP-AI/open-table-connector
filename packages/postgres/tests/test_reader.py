from __future__ import annotations

import polars as pl
import pyarrow as pa

from open_table_connector.contract import ExecutionRequest, ResourceLimits, TableURI, TableWriteRequest
from open_table_connector.postgres.reader import PostgresConnector, PostgresReadOptions, PostgresTableReadRequest


class Cursor:
    description = [("id",), ("amount",)]

    def execute(self, statement, parameters):
        self.statement = statement

    def fetchmany(self, size):
        rows, self.rows = getattr(self, "rows", [("a", "1.00"), ("b", None)]), []
        return rows[:size]

    @property
    def rowcount(self):
        return 1

    def executemany(self, statement, rows):
        self.statement = statement


class Connection:
    def __init__(self): self.cursor_value = Cursor()
    def cursor(self): return self.cursor_value
    def close(self): pass
    def commit(self): pass
    def rollback(self): pass


def test_postgres_arrow_polars_parity_and_base_receipt() -> None:
    connector = PostgresConnector(lambda **kwargs: Connection())
    request = PostgresTableReadRequest(
        TableURI("postgres://localhost/analytics"),
        options=PostgresReadOptions(query="SELECT id, amount FROM orders", key_fields=("id",)),
        resource_limits=ResourceLimits(max_rows=10),
    )

    arrow = connector.read_arrow(request)
    polars = connector.read_polars(request)

    assert isinstance(arrow.table, pa.Table)
    assert isinstance(polars.frame, pl.DataFrame)
    assert arrow.table.to_pylist() == polars.frame.to_arrow().to_pylist()
    assert arrow.receipt.operation_id == polars.receipt.operation_id
    assert arrow.receipt.mode.value == "base"
    assert arrow.receipt.coordinate_convention.key_fields == ("id",)


def test_postgres_write_and_execute_use_separate_neutral_roles() -> None:
    connector = PostgresConnector(lambda **kwargs: Connection())
    uri = TableURI("postgres://localhost/analytics")
    frame = pl.DataFrame({"id": ["a"], "amount": ["1.00"]})

    written = connector.write(TableWriteRequest(uri, frame, table="public.orders"))
    assert written.receipt.capability.capability_id == "table.write"
    result = connector.execute(ExecutionRequest(uri, "UPDATE public.orders SET amount = %s", ("2.00",)))
    assert result.status == "completed"
