from __future__ import annotations

import polars as pl

from open_connectors.contract import InspectRequest, TableReadRequest, TableURI, TableWriteRequest
from open_connectors.feishu_bitable import FeishuBitableConnector, FeishuBitableReadOptions, FeishuBitableTableReadRequest


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, dict | None]] = []

    def request(self, method, url, *, headers, body=None, timeout=None):
        self.calls.append((method, url, headers, body))
        if method == "GET" and "/records" in url:
            return {
                "code": 0,
                "data": {
                    "items": [
                        {"record_id": "rec_1", "fields": {"name": "Ada", "score": 10}},
                        {"record_id": "rec_2", "fields": {"name": "Lin", "score": 9}},
                    ],
                    "has_more": False,
                },
            }
        return {"code": 0, "data": {"records": [{"record_id": "rec_3"}]}}


def test_feishu_reads_records_and_preserves_record_ids() -> None:
    transport = FakeTransport()
    connector = FeishuBitableConnector(transport=transport, tenant_access_token="tenant-token")
    request = TableReadRequest(TableURI("feishu://app-token/table-id"))

    result = connector.read_polars(request)

    assert result.frame.to_dicts() == [
        {"_record_id": "rec_1", "name": "Ada", "score": 10},
        {"_record_id": "rec_2", "name": "Lin", "score": 9},
    ]
    assert transport.calls[0][2]["Authorization"] == "Bearer tenant-token"
    assert result.receipt.mode.value == "base"


def test_feishu_writes_batch_records() -> None:
    transport = FakeTransport()
    connector = FeishuBitableConnector(transport=transport, tenant_access_token="tenant-token")
    result = connector.write(
        TableWriteRequest(TableURI("feishu://app-token/table-id"), pl.DataFrame({"name": ["Ada"], "score": [10]}), if_exists="append")
    )

    assert result.affected_rows == 1
    method, url, headers, body = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/records/batch_create")
    assert headers["Authorization"] == "Bearer tenant-token"
    assert body == {"records": [{"fields": {"name": "Ada", "score": 10}}]}


def test_feishu_inspection_reports_base_identity() -> None:
    inspection = FeishuBitableConnector(transport=FakeTransport(), tenant_access_token="tenant-token").inspect(
        InspectRequest(TableURI("feishu://app-token/table-id"))
    )

    assert inspection.columns == ("_record_id", "name", "score")
    assert inspection.row_count == 2
    assert inspection.coordinate_convention.record_id_field == "_record_id"


def test_feishu_can_select_fields() -> None:
    connector = FeishuBitableConnector(transport=FakeTransport(), tenant_access_token="tenant-token")
    result = connector.read_polars(
        FeishuBitableTableReadRequest(
            TableURI("feishu://app-token/table-id"), options=FeishuBitableReadOptions(("name",))
        )
    )
    assert result.frame.columns == ["_record_id", "name"]
