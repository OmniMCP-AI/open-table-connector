from __future__ import annotations

import open_table_connector.sdk as otc
import polars as pl
import pytest


def test_sql_preparation_is_pure_and_collect_executes_relational_queries() -> None:
    query = otc.sql(
        """
        SELECT order_id, amount
        FROM orders
        WHERE amount >= :minimum
        ORDER BY order_id
        LIMIT 2
        """,
        sources={
            "orders": pl.DataFrame(
                {
                    "order_id": [3, 1, 2],
                    "amount": [30, 10, 20],
                }
            )
        },
        parameters={"minimum": 15},
    )

    client = otc.Client(registry=otc.ConnectorRegistry())
    result = client.collect(query)

    assert result.require_value().to_dict(as_series=False) == {
        "order_id": [2, 3],
        "amount": [20, 30],
    }
    assert result.receipts[-1].details["execution_location"] == "sdk-local"


def test_client_sql_convenience_matches_prepare_plus_collect(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    orders = client.open("fake://warehouse/orders").require_value()

    query = otc.sql(
        """
        SELECT order_id, status
        FROM orders
        ORDER BY order_id
        """,
        sources={"orders": orders},
    )

    prepared = client.collect(query).require_value()
    direct = client.sql(
        """
        SELECT order_id, status
        FROM orders
        ORDER BY order_id
        """,
        sources={"orders": orders},
    ).require_value()

    assert direct.to_dict(as_series=False) == prepared.to_dict(as_series=False)


def test_sql_rejects_unbound_sources_and_offset() -> None:
    with pytest.raises(otc.OTCError) as unbound:
        otc.sql("SELECT * FROM missing ORDER BY id", sources={})

    assert unbound.value.result.error is not None
    assert unbound.value.result.error.code is otc.ErrorCode.INVALID_SQL

    with pytest.raises(otc.OTCError) as offset:
        otc.sql(
            "SELECT order_id FROM orders ORDER BY order_id OFFSET 1",
            sources={"orders": pl.DataFrame({"order_id": [1, 2]})},
        )

    assert offset.value.result.error is not None
    assert offset.value.result.error.code is otc.ErrorCode.INVALID_SQL


def test_query_bindings_are_immutable_and_plan_hash_is_canonical() -> None:
    frame = pl.DataFrame({"order_id": [1], "amount": [10]})
    sources = {"orders": frame}
    tags = ["open"]
    parameters = {"minimum": 5, "tags": tags}
    first = otc.sql(
        "SELECT order_id FROM orders WHERE amount >= :minimum ORDER BY order_id",
        sources=sources,
        parameters=parameters,
    )
    second = otc.sql(
        "  select order_id\nfrom orders where amount >= :minimum order by order_id  ",
        sources={"orders": frame},
        parameters={"minimum": 99, "tags": ["done"]},
    )

    sources["other"] = frame
    parameters["minimum"] = 999
    tags.append("done")

    assert tuple(first.sources) == ("orders",)
    assert dict(first.parameters) == {"minimum": 5, "tags": ("open",)}
    assert first.plan_hash == second.plan_hash
    assert first.definition_hash == second.definition_hash
    assert first.plan_hash.startswith("sha256:")
    assert first.definition_hash.startswith("sha256:")
    with pytest.raises(TypeError):
        first.sources["other"] = frame  # type: ignore[index]


def test_query_affinity_is_preflighted_across_nested_sources_before_reads(fake_connector) -> None:
    left_client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    right_client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    left = left_client.open("fake://warehouse/orders").require_value()
    right = right_client.open("fake://warehouse/orders").require_value()
    query = otc.sql(
        """
        SELECT left_orders.order_id
        FROM left_orders
        INNER JOIN right_orders
          ON left_orders.order_id = right_orders.order_id
        ORDER BY left_orders.order_id
        """,
        sources={"left_orders": left, "right_orders": right},
    )
    fake_connector.calls.clear()

    with pytest.raises(otc.OTCError) as raised:
        left_client.collect(query)

    assert raised.value.result.error is not None
    assert raised.value.result.error.code is otc.ErrorCode.CLIENT_AFFINITY_MISMATCH
    assert all(call[0] != "read_table" for call in fake_connector.calls)


def test_sql_resource_admission_covers_sources_output_bytes_and_receipt_evidence() -> None:
    client = otc.Client(registry=otc.ConnectorRegistry())
    frame = pl.DataFrame({"order_id": [1, 2], "payload": ["a", "b"]})

    with pytest.raises(otc.OTCError) as source_limit:
        client.sql(
            "SELECT order_id FROM orders ORDER BY order_id",
            sources={"orders": frame},
            limits=otc.SqlResourceLimits(max_source_rows=1),
        )
    assert source_limit.value.result.error is not None
    assert source_limit.value.result.error.code is otc.ErrorCode.RESOURCE_LIMIT

    result = client.sql(
        "SELECT order_id FROM orders ORDER BY order_id",
        sources={"orders": frame},
        limits=otc.SqlResourceLimits(max_output_bytes=1024),
    )
    evidence = result.receipts[-1].details
    assert evidence["observed"]["source_rows"] == 2
    assert evidence["observed"]["output_rows"] == 2
    assert evidence["observed"]["output_bytes"] > 0
    assert evidence["effective_limits"]["max_duration_ms"] == 30_000
