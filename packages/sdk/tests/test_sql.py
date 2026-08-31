from __future__ import annotations

import sqlite3

import open_table_connector.sdk as otc
import polars as pl
import pytest


def test_sql_supports_join_and_grouped_aggregate() -> None:
    query = otc.sql(
        """
        SELECT orders.region, SUM(orders.amount) AS total_amount, MAX(rates.fx) AS max_fx
        FROM orders
        INNER JOIN rates ON orders.region = rates.region
        GROUP BY orders.region
        ORDER BY orders.region
        """,
        sources={
            "orders": pl.DataFrame(
                {
                    "region": ["apac", "emea", "apac"],
                    "amount": [10, 15, 20],
                }
            ),
            "rates": pl.DataFrame(
                {
                    "region": ["apac", "emea"],
                    "fx": [7.1, 0.92],
                }
            ),
        },
    )

    result = otc.Client(registry=otc.ConnectorRegistry()).collect(query).require_value()

    assert result.to_dict(as_series=False) == {
        "region": ["apac", "emea"],
        "total_amount": [30, 15],
        "max_fx": [7.1, 0.92],
    }


def test_sql_local_execution_does_not_depend_on_polars_sql_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_sql_context(*args, **kwargs):  # pragma: no cover - this must stay unused.
        raise AssertionError("Polars SQLContext must not be used by the SDK SQL mapper")

    monkeypatch.setattr(pl, "SQLContext", fail_sql_context)

    query = otc.sql(
        """
        SELECT orders.region, SUM(orders.amount) AS total_amount
        FROM orders
        GROUP BY orders.region
        ORDER BY orders.region
        """,
        sources={
            "orders": pl.DataFrame(
                {
                    "region": ["apac", "emea", "apac"],
                    "amount": [10, 15, 20],
                }
            ),
        },
    )

    result = otc.Client(registry=otc.ConnectorRegistry()).collect(query).require_value()

    assert result.to_dict(as_series=False) == {
        "region": ["apac", "emea"],
        "total_amount": [30, 15],
    }


def test_sql_left_join_preserves_unmatched_left_rows() -> None:
    query = otc.sql(
        """
        SELECT orders.order_id, rates.fx
        FROM orders
        LEFT JOIN rates ON orders.region = rates.region
        ORDER BY orders.order_id
        """,
        sources={
            "orders": pl.DataFrame({"order_id": [1, 2], "region": ["apac", "unknown"]}),
            "rates": pl.DataFrame({"region": ["apac"], "fx": [7.1]}),
        },
    )

    result = otc.Client(registry=otc.ConnectorRegistry()).collect(query).require_value()

    assert result.to_dict(as_series=False) == {
        "order_id": [1, 2],
        "fx": [7.1, None],
    }


def test_provider_native_sql_is_explicit_read_only_for_queries_and_tracks_mutation_lifecycle(
    fake_connector,
) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    native = client.native_sql("fake://warehouse")

    rows = native.query(
        "SELECT order_id, status FROM orders ORDER BY order_id",
        limits=otc.NativeSqlResourceLimits(max_rows=10, max_bytes=1024),
    )
    assert rows.require_value().to_dict(as_series=False)["order_id"] == [1, 2]
    assert rows.commit is otc.CommitState.NOT_APPLICABLE
    assert rows.receipts[-1].details["statement_hash"].startswith("sha256:")

    with pytest.raises(otc.OTCError) as unsafe:
        native.query("DELETE FROM orders")
    assert unsafe.value.result.error is not None
    assert unsafe.value.result.error.code is otc.ErrorCode.INVALID_SQL
    assert all(call != ("read_native_sql", "DELETE FROM orders") for call in fake_connector.calls)

    with pytest.raises(otc.OTCError) as external_function:
        native.query("SELECT load_extension('unsafe')")
    assert external_function.value.result.error is not None
    assert external_function.value.result.error.code is otc.ErrorCode.INVALID_SQL
    assert all(
        call != ("read_native_sql", "SELECT load_extension('unsafe')")
        for call in fake_connector.calls
    )

    mutating_cte = "WITH removed AS (DELETE FROM orders RETURNING *) SELECT * FROM removed"
    with pytest.raises(otc.OTCError) as nested_mutation:
        native.query(mutating_cte)
    assert nested_mutation.value.result.error is not None
    assert nested_mutation.value.result.error.code is otc.ErrorCode.INVALID_SQL
    assert all(call != ("read_native_sql", mutating_cte) for call in fake_connector.calls)

    changed = native.execute(
        "UPDATE orders SET status = ? WHERE order_id = ?",
        parameters=("done", 1),
        idempotency_key="native-update-1",
    )
    assert changed.require_value() == 2
    assert changed.commit is otc.CommitState.COMMITTED
    assert changed.receipts[-1].details["idempotency_key"] == "native-update-1"


def test_provider_native_sql_rejects_connectors_without_native_capabilities() -> None:
    from .conftest import legacy_descriptor

    client = otc.Client.from_config(
        otc.ClientConfig.empty(),
        descriptors=(legacy_descriptor(),),
        resolver=otc.EnvironmentCredentialResolver(otc.ClientConfig.empty(), {}),
    )

    with pytest.raises(otc.OTCError) as raised:
        client.native_sql("legacy://warehouse").query("SELECT 1")

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.UNSUPPORTED_CAPABILITY


def test_provider_native_sql_adapts_the_existing_sqlite_executor(tmp_path) -> None:
    from open_table_connector.contract import PluginDescriptor
    from open_table_connector.sqlite import SQLiteConnector

    path = tmp_path / "native.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE orders (order_id INTEGER, status TEXT)")
    connection.execute("INSERT INTO orders VALUES (1, 'open')")
    connection.commit()
    connection.close()
    connector = SQLiteConnector()
    descriptor = PluginDescriptor(
        "sqlite",
        connector.identity,
        ("sqlite",),
        lambda _context: connector,
    )
    client = otc.Client.from_config(
        otc.ClientConfig.empty(),
        descriptors=(descriptor,),
        resolver=otc.EnvironmentCredentialResolver(otc.ClientConfig.empty(), {}),
    )
    native = client.native_sql(f"sqlite://{path.as_posix()}")

    rows = native.query("SELECT order_id, status FROM orders ORDER BY order_id")
    changed = native.execute(
        "UPDATE orders SET status = ? WHERE order_id = ?",
        parameters=("done", 1),
        idempotency_key="sqlite-native-update",
    )

    assert rows.require_value().to_dict(as_series=False) == {
        "order_id": [1],
        "status": ["open"],
    }
    assert changed.require_value() == 1
