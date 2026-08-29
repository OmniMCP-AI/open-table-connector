from __future__ import annotations

from open_table_connector.contract import ExecutionRequest, TableURI
from open_table_connector.postgres import PostgresConnector

from .test_temporal_storage_recording import RecordingFactory


def test_postgres_explicit_transaction_is_context_local_and_operations_close_connections() -> None:
    factory = RecordingFactory([[], [], []])
    connector = PostgresConnector(factory)
    uri = TableURI("postgres://localhost/analytics")

    connector.execute(ExecutionRequest(uri, "SELECT 1", ()))
    transaction = connector.begin(uri)
    transaction.execute(ExecutionRequest(uri, "UPDATE t SET x = %s", (1,)))
    transaction.abort()
    connector.execute(ExecutionRequest(uri, "SELECT 2", ()))

    assert not hasattr(connector, "_transaction_connection")
    assert len(factory.connections) == 3
    assert factory.connections[0].closed is True
    assert factory.connections[1].rollbacks == 1
    assert factory.connections[2].closed is True
