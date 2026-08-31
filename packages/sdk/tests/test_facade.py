from __future__ import annotations

import open_table_connector.sdk as sdk
import polars as pl
from open_table_connector import otc


def test_public_otc_facade_exposes_pure_sql_factory() -> None:
    query = otc.sql(
        "SELECT id FROM orders",
        sources={"orders": pl.DataFrame({"id": [1]})},
    )

    assert isinstance(query, sdk.Query)
    assert query.statement == "SELECT id FROM orders"


def test_public_otc_facade_delegates_read_to_configured_client(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    otc.configure(client)
    try:
        result = otc.read("fake://warehouse/orders")
        assert result.require_value().height == 2
    finally:
        otc.close_default_client()
