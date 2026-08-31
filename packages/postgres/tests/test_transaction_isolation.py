from __future__ import annotations

import pytest
from open_table_connector.contract import ConnectorError, ExecutionRequest, ResourceLimits, TableURI
from open_table_connector.postgres import (
    PostgresConnector,
    PostgresReadOptions,
    PostgresTableReadRequest,
)

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


def test_query_reads_reject_an_active_writable_transaction() -> None:
    factory = RecordingFactory([[], []])
    connector = PostgresConnector(factory)
    uri = TableURI("postgres://localhost/analytics")
    transaction = connector.begin(uri)
    request = PostgresTableReadRequest(
        uri,
        options=PostgresReadOptions(query="SELECT 1"),
        resource_limits=ResourceLimits(max_rows=1),
    )
    with pytest.raises(ConnectorError, match="writable PostgreSQL transaction"):
        connector.read_arrow(request)
    transaction.abort()
