from __future__ import annotations

import open_table_connector.sdk as otc
import polars as pl


def test_table_operations_delegate_through_the_bound_client(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()

    inspection = table.inspect().require_value()
    capabilities = table.capabilities().require_value()
    full = table.read().require_value()
    page = table.read_page(limit=1)
    inserted = table.insert(pl.DataFrame({"order_id": [3], "status": ["queued"]})).require_value()
    updated = table.update(
        pl.DataFrame({"order_id": [3], "status": ["done"]}),
        keys=("order_id",),
    ).require_value()
    deleted = table.delete(where=otc.all_rows()).require_value()
    dropped = table.drop()

    assert inspection.schema == fake_connector.frame.schema
    assert capabilities.supports("table.transaction")
    assert full.height == 2
    assert page.require_value().height == 1
    assert page.continuation == "page-2"
    assert inserted == 1
    assert updated == 1
    assert deleted == 1
    assert dropped.value is None


def test_table_transaction_exposes_insert_update_delete_commit(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()

    transaction = table.transaction()
    transaction.insert(pl.DataFrame({"order_id": [3], "status": ["queued"]}))
    transaction.update(
        pl.DataFrame({"order_id": [3], "status": ["done"]}),
        keys=("order_id",),
    )
    transaction.delete(where=otc.all_rows())
    committed = transaction.commit()

    assert committed.outcome is otc.Outcome.SUCCEEDED
    assert ("begin_transaction", "fake://warehouse/orders") in fake_connector.calls


def test_table_transaction_is_local_until_commit(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    table = client.open("fake://warehouse/orders").require_value()

    transaction = table.transaction()
    transaction.insert(pl.DataFrame({"order_id": [3], "status": ["queued"]}))
    transaction.delete(where=otc.all_rows())

    assert not any(
        call[0] in {"begin_transaction", "insert", "delete"}
        for call in fake_connector.calls
    )

    transaction.abort()
    assert not any(call[0] == "abort" for call in fake_connector.calls)
