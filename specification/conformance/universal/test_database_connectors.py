from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import polars as pl
import pytest

from open_table_connector.contract import (
    BaseConvention,
    ConnectorError,
    ConnectorErrorCode,
    ExecutionRequest,
    ResolveContext,
    ResourceLimits,
    TableMode,
    TableURI,
)
from open_table_connector.postgres import (
    PostgresConnector,
    PostgresReadOptions,
    PostgresTableReadRequest,
)
from open_table_connector.sqlite import (
    SQLiteConnector,
    SQLiteReadOptions,
    SQLiteTableReadRequest,
)

from specification.conformance.universal.assertions import (
    assert_error_is_safe,
    assert_receipt_matches_table,
)
from specification.conformance.universal.cases import (
    ConnectorCase,
    case,
    cases_with,
)
from specification.conformance.universal.fixtures import (
    RecordedSqlCall,
    RecordingPostgresFactory,
    UniversalFixtureBundle,
)


_DATABASE_CASE_NAMES = ("sqlite", "postgres")
_POSTGRES_CREDENTIALS = {
    "user": "fixture-user",
    "password": "fixture-password",
    "sslmode": "require",
}


def _database_case_with(capability: str, case_name: str) -> ConnectorCase:
    matching = {
        item.name: item
        for item in cases_with(capability)
        if item.name in _DATABASE_CASE_NAMES
    }
    assert set(matching) == set(_DATABASE_CASE_NAMES), (
        f"database capability filter for {capability!r} returned {tuple(matching)!r}"
    )
    return matching[case_name]


def _postgres_fixture(connector_case: ConnectorCase):
    fixture = connector_case.database_fixture
    assert fixture is not None
    return fixture


def _recorded_calls(connection):
    return [call for cursor in connection.cursors for call in cursor.calls]


class _RecordingSQLiteConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self.close_calls = 0

    def __getattr__(self, name: str):
        return getattr(self._connection, name)

    def close(self) -> None:
        self.close_calls += 1
        self._connection.close()


class _RecordingSQLiteFactory:
    def __init__(self) -> None:
        self.connections: list[_RecordingSQLiteConnection] = []

    def __call__(self, path: str) -> _RecordingSQLiteConnection:
        connection = _RecordingSQLiteConnection(sqlite3.connect(path))
        self.connections.append(connection)
        return connection


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_uri_resolution_is_base_mode_and_connection_free(
    case_name: str,
    tmp_path: Path,
    isolated_universal_fixture_bundle: UniversalFixtureBundle,
) -> None:
    connector_case = case(case_name)
    context = ResolveContext(
        credentials=_POSTGRES_CREDENTIALS if case_name == "postgres" else None
    )

    resolved = connector_case.connector.resolve(connector_case.table_uri, context)

    assert resolved.uri == connector_case.table_uri
    assert resolved.mode is TableMode.BASE
    if case_name == "sqlite":
        assert resolved.resource.path == str(
            isolated_universal_fixture_bundle.sqlite_path
        )
        assert isolated_universal_fixture_bundle.sqlite_path.parent == tmp_path
    else:
        assert resolved.resource.connect_kwargs == {
            "host": "fixture.local",
            "dbname": "analytics",
            **_POSTGRES_CREDENTIALS,
        }
        assert _postgres_fixture(connector_case).connection_factory.calls == []


@pytest.mark.parametrize(
    "scheme",
    ("postgres", "postgresql"),
    ids=("postgres", "postgresql-alias"),
)
def test_postgres_uri_aliases_resolve_with_the_same_connection_details(
    scheme: str,
) -> None:
    connector_case = case("postgres")
    context = ResolveContext(credentials=_POSTGRES_CREDENTIALS)

    resolved = connector_case.connector.resolve(
        TableURI(f"{scheme}://fixture.local/analytics"),
        context,
    )

    assert resolved.mode is TableMode.BASE
    assert resolved.resource.connect_kwargs == {
        "host": "fixture.local",
        "dbname": "analytics",
        **_POSTGRES_CREDENTIALS,
    }
    assert _postgres_fixture(connector_case).connection_factory.calls == []


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_reads_honor_max_rows(case_name: str) -> None:
    connector_case = _database_case_with("table.read.arrow", case_name)
    binding = connector_case.capability_binding("table.read.arrow")
    assert binding.read_arrow is not None

    result = binding.read_arrow(ResourceLimits(max_rows=1, timeout_seconds=3))

    assert result.table.to_pylist() == [{"id": "a", "amount": "1.00"}]
    assert result.receipt.row_count == 1
    assert result.receipt.batch_count == 1
    if case_name == "postgres":
        fixture = _postgres_fixture(connector_case)
        assert fixture.connection_factory.calls == [
            {
                "host": "fixture.local",
                "dbname": "analytics",
                **_POSTGRES_CREDENTIALS,
            }
        ]
        connection = fixture.connection_factory.connections[-1]
        assert connection.cursors[0].fetchmany_sizes == [1]
        assert connection.cursors[0].description_reads == 1
        assert connection.closed
        assert connection.close_calls == 1
        assert all(cursor.closed for cursor in connection.cursors)
        assert all(cursor.close_calls == 1 for cursor in connection.cursors)


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_arrow_and_polars_reads_have_value_and_receipt_parity(
    case_name: str,
) -> None:
    connector_case = _database_case_with("table.read.arrow", case_name)
    arrow_binding = connector_case.capability_binding("table.read.arrow")
    polars_binding = connector_case.capability_binding("table.read.polars")
    assert arrow_binding.read_arrow is not None
    assert polars_binding.read_polars is not None
    limits = ResourceLimits(max_rows=2)

    arrow_result = arrow_binding.read_arrow(limits)
    polars_result = polars_binding.read_polars(limits)

    assert polars_result.frame.to_dicts() == arrow_result.table.to_pylist()
    assert polars_result.receipt.schema_fingerprint == (
        arrow_result.receipt.schema_fingerprint
    )
    assert polars_result.receipt.content_fingerprint == (
        arrow_result.receipt.content_fingerprint
    )
    assert polars_result.receipt.operation_id == arrow_result.receipt.operation_id


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_inspection_agrees_with_reads(case_name: str) -> None:
    connector_case = _database_case_with("table.inspect", case_name)
    inspect_binding = connector_case.capability_binding("table.inspect")
    assert inspect_binding.inspect is not None
    limits = ResourceLimits()

    inspection = inspect_binding.inspect(limits)
    if case_name == "sqlite":
        result = connector_case.connector.read_arrow(
            SQLiteTableReadRequest(connector_case.table_uri, limits)
        )
    else:
        result = connector_case.connector.read_arrow(
            PostgresTableReadRequest(
                connector_case.table_uri,
                resource_limits=limits,
                credentials=_POSTGRES_CREDENTIALS,
            )
        )

    assert inspection.safe_uri == connector_case.table_uri
    assert inspection.mode is TableMode.BASE
    assert inspection.columns == tuple(result.table.column_names)
    assert inspection.schema_fingerprint == result.receipt.schema_fingerprint
    assert result.table.to_pylist() == [
        {"default_id": "default-a", "label": "default resource"}
    ]
    assert inspection.row_count == result.table.num_rows == 1
    if case_name == "postgres":
        fixture = _postgres_fixture(connector_case)
        inspect_call = fixture.connection_factory.connections[0].cursors[0].calls[0]
        assert inspect_call.statement == "SELECT * FROM public.table"
        assert inspect_call.parameters == ()


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_table_options_select_the_declared_table(case_name: str) -> None:
    connector_case = _database_case_with("table.read.arrow", case_name)
    options = (
        SQLiteReadOptions(table="orders", record_id_field="id")
        if case_name == "sqlite"
        else PostgresReadOptions(table="public.orders", record_id_field="id")
    )
    request = (
        SQLiteTableReadRequest(connector_case.table_uri, options=options)
        if case_name == "sqlite"
        else PostgresTableReadRequest(
            connector_case.table_uri,
            options=options,
            credentials=_POSTGRES_CREDENTIALS,
        )
    )

    result = connector_case.connector.read_arrow(request)

    assert result.table.to_pylist() == [
        {"id": "a", "amount": "1.00"},
        {"id": "b", "amount": None},
    ]
    assert result.receipt.coordinate_convention.record_id_field == "id"
    if case_name == "postgres":
        fixture = _postgres_fixture(connector_case)
        call = fixture.connection_factory.connections[-1].cursors[0].calls[0]
        assert call.statement == "SELECT * FROM public.orders"
        assert call.parameters == ()


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_sql_options_execute_exact_statement_and_parameters(
    case_name: str,
) -> None:
    connector_case = _database_case_with("table.read.arrow", case_name)
    if case_name == "sqlite":
        options = SQLiteReadOptions(
            query="SELECT id, amount FROM orders WHERE id = ?",
            parameters=("b",),
            key_fields=("id",),
        )
        request = SQLiteTableReadRequest(connector_case.table_uri, options=options)
    else:
        options = PostgresReadOptions(
            query="SELECT id, amount FROM orders WHERE id = %s",
            parameters=("b",),
            key_fields=("id",),
        )
        request = PostgresTableReadRequest(
            connector_case.table_uri,
            options=options,
            credentials=_POSTGRES_CREDENTIALS,
        )

    result = connector_case.connector.read_arrow(request)

    assert result.table.to_pylist() == [{"id": "b", "amount": None}]
    assert result.receipt.coordinate_convention.key_fields == ("id",)
    if case_name == "postgres":
        fixture = _postgres_fixture(connector_case)
        call = fixture.connection_factory.connections[-1].cursors[0].calls[0]
        assert call.statement == "SELECT id, amount FROM orders WHERE id = %s"
        assert call.parameters == ("b",)


@pytest.mark.parametrize(
    ("case_name", "policy"),
    tuple(
        pytest.param(case_name, policy, id=f"{case_name}:{policy}")
        for case_name in _DATABASE_CASE_NAMES
        for policy in ("append", "replace")
    ),
)
def test_database_writes_accept_append_and_replace_with_exact_sql(
    case_name: str,
    policy: str,
    write_frame: pl.DataFrame,
    isolated_universal_fixture_bundle: UniversalFixtureBundle,
) -> None:
    connector_case = _database_case_with("table.write", case_name)
    binding = connector_case.capability_binding("table.write")
    assert binding.write is not None

    result = binding.write(write_frame, policy)

    assert result.affected_rows == 2
    assert result.receipt.row_count == 2
    if case_name == "sqlite":
        connection = sqlite3.connect(isolated_universal_fixture_bundle.sqlite_path)
        try:
            rows = connection.execute(
                "SELECT id, amount FROM orders ORDER BY rowid"
            ).fetchall()
        finally:
            connection.close()
        expected_prefix = [] if policy == "replace" else [("a", "1.00"), ("b", None)]
        assert rows == expected_prefix + [("write-1", "3.50"), ("write-2", "4.00")]
    else:
        fixture = _postgres_fixture(connector_case)
        connection = fixture.connection_factory.connections[-1]
        expected_statements = []
        if policy == "replace":
            expected_statements.append('DROP TABLE IF EXISTS "public"."orders"')
        expected_statements.extend(
            [
                'CREATE TABLE IF NOT EXISTS "public"."orders" '
                '("id" TEXT, "amount" TEXT)',
                'INSERT INTO "public"."orders" ("id", "amount") '
                "VALUES (%s, %s)",
            ]
        )
        calls = _recorded_calls(connection)
        assert [call.statement for call in calls] == expected_statements
        assert calls[-1].kind == "executemany"
        assert calls[-1].parameters == (
            ("write-1", "3.50"),
            ("write-2", "4.00"),
        )
        assert len(connection.cursors) == len(expected_statements)
        assert len({id(cursor) for cursor in connection.cursors}) == len(
            connection.cursors
        )
        assert all(cursor.closed for cursor in connection.cursors)
        assert all(cursor.close_calls == 1 for cursor in connection.cursors)
        assert connection.commits == 1
        assert connection.closed


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_error_policy_fails_on_existing_table_without_commit(
    case_name: str,
    write_frame: pl.DataFrame,
    isolated_universal_fixture_bundle: UniversalFixtureBundle,
) -> None:
    connector_case = _database_case_with("table.write", case_name)
    binding = connector_case.capability_binding("table.write")
    assert binding.write is not None

    with pytest.raises(ConnectorError) as raised:
        binding.write(write_frame, "error")

    assert raised.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert_error_is_safe(raised.value, forbidden_values=("fixture-password",))
    if case_name == "sqlite":
        connection = sqlite3.connect(isolated_universal_fixture_bundle.sqlite_path)
        try:
            count = connection.execute("SELECT count(*) FROM orders").fetchone()[0]
        finally:
            connection.close()
        assert count == 2
    else:
        fixture = _postgres_fixture(connector_case)
        connection = fixture.connection_factory.connections[-1]
        assert connection.commits == 0
        assert connection.closed
        assert [call.statement for call in _recorded_calls(connection)] == [
            'CREATE TABLE "public"."orders" ("id" TEXT, "amount" TEXT)'
        ]
        assert all(cursor.closed for cursor in connection.cursors)
        assert all(cursor.close_calls == 1 for cursor in connection.cursors)


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_invalid_write_policy_is_rejected_before_connection(
    case_name: str,
    write_frame: pl.DataFrame,
) -> None:
    connector_case = _database_case_with("table.write", case_name)
    binding = connector_case.capability_binding("table.write")
    assert binding.write is not None

    with pytest.raises(ConnectorError) as raised:
        binding.write(write_frame, "merge")

    assert raised.value.code is ConnectorErrorCode.INVALID_URI
    if case_name == "postgres":
        assert _postgres_fixture(connector_case).connection_factory.calls == []


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_execute_commits_and_closes_outside_transactions(
    case_name: str,
) -> None:
    connector_case = _database_case_with("table.execute", case_name)
    binding = connector_case.capability_binding("table.execute")
    assert binding.invoke is not None

    result = binding.invoke()

    assert result.status == "completed"
    assert result.affected_rows == 1
    if case_name == "sqlite":
        read = connector_case.capability_binding("table.read.arrow").read_arrow
        assert read is not None
        rows = read(ResourceLimits()).table.to_pylist()
        assert rows[0] == {"id": "a", "amount": "2.00"}
    else:
        fixture = _postgres_fixture(connector_case)
        connection = fixture.connection_factory.connections[-1]
        assert _recorded_calls(connection) == [
            RecordedSqlCall(
                "UPDATE public.orders SET amount = %s WHERE id = %s",
                ("2.00", "a"),
                "execute",
            )
        ]
        assert connection.cursors[0].rowcount_reads == 2
        assert all(cursor.closed for cursor in connection.cursors)
        assert all(cursor.close_calls == 1 for cursor in connection.cursors)
        assert connection.commits == 1
        assert connection.rollbacks == 0
        assert connection.closed


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_transactions_defer_close_until_commit(case_name: str) -> None:
    connector_case = _database_case_with("table.execute", case_name)
    connector = connector_case.connector
    statement = (
        "UPDATE orders SET amount = ? WHERE id = ?"
        if case_name == "sqlite"
        else "UPDATE public.orders SET amount = %s WHERE id = %s"
    )

    connector.begin(connector_case.table_uri)
    result = connector.execute(
        ExecutionRequest(connector_case.table_uri, statement, ("5.00", "a"))
    )

    assert result.affected_rows == 1
    if case_name == "postgres":
        fixture = _postgres_fixture(connector_case)
        connection = fixture.connection_factory.connections[-1]
        assert connection.commits == 0
        assert not connection.closed
        assert all(cursor.closed for cursor in connection.cursors)
        assert all(cursor.close_calls == 1 for cursor in connection.cursors)

    connector.commit()

    if case_name == "sqlite":
        read = connector_case.capability_binding("table.read.arrow").read_arrow
        assert read is not None
        assert read(ResourceLimits()).table.to_pylist()[0]["amount"] == "5.00"
    else:
        assert connection.commits == 1
        assert connection.rollbacks == 0
        assert connection.closed
        assert connection.close_calls == 1
        assert all(cursor.closed for cursor in connection.cursors)
        assert all(cursor.close_calls == 1 for cursor in connection.cursors)


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_transactions_rollback_and_close_on_abort(case_name: str) -> None:
    connector_case = _database_case_with("table.execute", case_name)
    connector = connector_case.connector
    statement = (
        "UPDATE orders SET amount = ? WHERE id = ?"
        if case_name == "sqlite"
        else "UPDATE public.orders SET amount = %s WHERE id = %s"
    )

    connector.begin(connector_case.table_uri)
    connector.execute(
        ExecutionRequest(connector_case.table_uri, statement, ("9.00", "a"))
    )
    connector.abort()

    if case_name == "sqlite":
        read = connector_case.capability_binding("table.read.arrow").read_arrow
        assert read is not None
        assert read(ResourceLimits()).table.to_pylist()[0]["amount"] == "1.00"
    else:
        fixture = _postgres_fixture(connector_case)
        connection = fixture.connection_factory.connections[-1]
        assert connection.commits == 0
        assert connection.rollbacks == 1
        assert connection.closed
        assert connection.close_calls == 1
        assert all(cursor.closed for cursor in connection.cursors)
        assert all(cursor.close_calls == 1 for cursor in connection.cursors)


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_transaction_state_errors_are_stable_and_connection_free(
    case_name: str,
) -> None:
    connector_case = _database_case_with("table.execute", case_name)

    with pytest.raises(ConnectorError) as raised:
        connector_case.connector.commit()

    assert raised.value.code is ConnectorErrorCode.CONFLICT
    assert raised.value.safe_details == {}
    if case_name == "postgres":
        assert _postgres_fixture(connector_case).connection_factory.calls == []


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_read_receipts_are_safe_and_match_bounded_tables(
    case_name: str,
) -> None:
    connector_case = _database_case_with("table.read.arrow", case_name)
    binding = connector_case.capability_binding("table.read.arrow")
    assert binding.read_arrow is not None

    result = binding.read_arrow(ResourceLimits(max_rows=1))

    assert_receipt_matches_table(
        result.receipt,
        result.table,
        expected_connector=connector_case.identity,
        expected_capability="table.read.arrow",
        expected_mode=TableMode.BASE,
        expected_safe_uri=connector_case.table_uri,
        forbidden_values=("fixture-password",),
    )
    convention = result.receipt.coordinate_convention
    assert isinstance(convention, BaseConvention)
    assert convention.record_id_field == ("id" if case_name == "sqlite" else None)
    assert convention.key_fields == (() if case_name == "sqlite" else ("id",))
    assert "fixture-password" not in json.dumps(result.receipt.to_wire())


@pytest.mark.parametrize("case_name", _DATABASE_CASE_NAMES, ids=str)
def test_database_write_receipts_are_safe_and_match_input_tables(
    case_name: str,
    write_frame: pl.DataFrame,
) -> None:
    connector_case = _database_case_with("table.write", case_name)
    binding = connector_case.capability_binding("table.write")
    assert binding.write is not None

    result = binding.write(write_frame, "replace")

    assert_receipt_matches_table(
        result.receipt,
        write_frame.to_arrow(),
        expected_connector=connector_case.identity,
        expected_capability="table.write",
        expected_mode=TableMode.BASE,
        expected_safe_uri=connector_case.table_uri,
        forbidden_values=("fixture-password",),
    )
    assert result.affected_rows == write_frame.height


def test_postgres_fixture_never_opens_an_external_connection() -> None:
    connector_case = _database_case_with("table.read.arrow", "postgres")
    binding = connector_case.capability_binding("table.read.arrow")
    assert binding.read_arrow is not None

    result = binding.read_arrow(ResourceLimits(max_rows=2))

    fixture = _postgres_fixture(connector_case)
    assert result.table.to_pylist()
    assert fixture.connection_factory.calls == [
        {
            "host": "fixture.local",
            "dbname": "analytics",
            **_POSTGRES_CREDENTIALS,
        }
    ]
    assert len(fixture.connection_factory.connections) == 1


def test_postgres_authentication_failures_are_stable_and_safe() -> None:
    raw_failure = RuntimeError(
        "recorded authentication rejection for fixture-password"
    )
    factory = RecordingPostgresFactory(connection_failure=raw_failure)
    connector = PostgresConnector(connection_factory=factory)
    uri = TableURI("postgres://fixture.local/analytics")
    request = PostgresTableReadRequest(
        uri,
        options=PostgresReadOptions(table="public.orders"),
        credentials=_POSTGRES_CREDENTIALS,
    )

    with pytest.raises(ConnectorError) as raised:
        connector.read_arrow(request)

    assert raised.value.code is ConnectorErrorCode.AUTHENTICATION
    assert raised.value.message == "PostgreSQL connection failed"
    assert "authentication rejection" in raised.value.safe_details["reason"]
    assert_error_is_safe(raised.value, forbidden_values=("fixture-password",))
    assert factory.calls == [
        {
            "host": "fixture.local",
            "dbname": "analytics",
            **_POSTGRES_CREDENTIALS,
        }
    ]
    assert factory.connections == []


def test_postgres_execution_failures_are_stable_and_close_connections() -> None:
    raw_failure = RuntimeError("recorded cursor rejection for fixture-password")
    factory = RecordingPostgresFactory(execution_failure=raw_failure)
    connector = PostgresConnector(connection_factory=factory)
    request = PostgresTableReadRequest(
        TableURI("postgres://fixture.local/analytics"),
        options=PostgresReadOptions(query="SELECT id, amount FROM orders"),
        credentials=_POSTGRES_CREDENTIALS,
    )

    with pytest.raises(ConnectorError) as raised:
        connector.read_arrow(request)

    assert raised.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert raised.value.message == "PostgreSQL read failed"
    assert "cursor rejection" in raised.value.safe_details["reason"]
    assert_error_is_safe(raised.value, forbidden_values=("fixture-password",))
    connection = factory.connections[-1]
    assert connection.cursors[0].calls[0].statement == (
        "SELECT id, amount FROM orders"
    )
    assert connection.closed
    assert all(cursor.closed for cursor in connection.cursors)
    assert all(cursor.close_calls == 1 for cursor in connection.cursors)


def test_sqlite_execution_failures_are_stable_and_close_the_database(
    isolated_universal_fixture_bundle: UniversalFixtureBundle,
) -> None:
    connector_case = _database_case_with("table.read.arrow", "sqlite")
    factory = _RecordingSQLiteFactory()
    connector = SQLiteConnector(connection_factory=factory)
    request = SQLiteTableReadRequest(
        connector_case.table_uri,
        options=SQLiteReadOptions(table="missing_orders"),
    )

    with pytest.raises(ConnectorError) as raised:
        connector.read_arrow(request)

    assert raised.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert raised.value.message == "SQLite read failed"
    assert "no such table" in raised.value.safe_details["reason"]
    assert_error_is_safe(raised.value)
    assert len(factory.connections) == 1
    assert factory.connections[0].close_calls == 1


def test_postgres_recording_dbapi_returns_distinct_cursors_and_fails_closed() -> None:
    factory = RecordingPostgresFactory()
    connection = factory(host="fixture.local", dbname="analytics")
    cursor = connection.cursor()
    second_cursor = connection.cursor()

    assert second_cursor is not cursor

    with pytest.raises(AssertionError, match="unexpected recorded SQL"):
        cursor.execute("DELETE FROM public.orders", ())

    cursor.close()
    assert cursor.closed
    assert cursor.close_calls == 1
    with pytest.raises(AssertionError, match="closed cursor"):
        cursor.fetchmany(1)

    second_cursor.close()
    connection.close()
    with pytest.raises(AssertionError, match="closed connection"):
        connection.commit()
    with pytest.raises(AssertionError, match="refuses external host"):
        factory(host="database.example", dbname="analytics")
