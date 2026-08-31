from __future__ import annotations

import polars as pl
import pytest
from urllib.error import URLError
from open_table_connector.contract import (
    ConnectorError,
    ConnectorErrorCode,
    InspectRequest,
    TableReadRequest,
    TableURI,
    TableWriteRequest,
)
from open_table_connector.feishu_bitable import (
    FEISHU_BATCH_CREATE_LIMIT,
    FeishuBitableConnector,
    FeishuBitableReadOptions,
    FeishuBitableTableReadRequest,
)
from open_table_connector.feishu_bitable.connector import (
    FEISHU_MAX_RESPONSE_BYTES,
    UrllibFeishuTransport,
)


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


def test_feishu_transport_redacts_credentials_from_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = "provider-credential-secret"

    def fail_request(*_args, **_kwargs):
        raise RuntimeError(f"provider rejected credential {credential}")

    monkeypatch.setattr(
        "open_table_connector.feishu_bitable.connector.urlopen",
        fail_request,
    )

    with pytest.raises(ConnectorError) as raised:
        UrllibFeishuTransport().request(
            "GET",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/fixture/tables/orders/records",
            headers={"Authorization": f"Bearer {credential}"},
        )

    assert raised.value.code is ConnectorErrorCode.EXECUTION_FAILED
    assert raised.value.message == "Feishu Bitable request failed"
    assert raised.value.safe_details == {
        "reason": "unexpected transport exception"
    }
    assert credential not in repr(raised.value.to_wire())


def test_feishu_transport_bounds_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size):
            assert size == FEISHU_MAX_RESPONSE_BYTES + 1
            return b"x" * size

    monkeypatch.setattr("open_table_connector.feishu_bitable.connector.urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(ConnectorError) as raised:
        UrllibFeishuTransport().request("GET", "https://example.test", headers={})
    assert raised.value.code is ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED


def test_feishu_transport_classifies_url_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "open_table_connector.feishu_bitable.connector.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError(TimeoutError("read timed out"))),
    )

    with pytest.raises(ConnectorError) as raised:
        UrllibFeishuTransport().request("GET", "https://example.test", headers={})

    assert raised.value.code is ConnectorErrorCode.TIMEOUT


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
    assert transport.calls[0][3] is None
    assert result.receipt.mode.value == "base"
    assert result.receipt.vendor_receipt_ref is None


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
    assert result.receipt.vendor_receipt_ref is None


def test_feishu_writes_are_chunked_at_provider_limit() -> None:
    transport = FakeTransport()
    connector = FeishuBitableConnector(transport=transport, tenant_access_token="tenant-token")
    frame = pl.DataFrame({"id": list(range(FEISHU_BATCH_CREATE_LIMIT + 1))})

    result = connector.write(
        TableWriteRequest(TableURI("feishu://app-token/table-id"), frame, if_exists="append")
    )

    writes = [call for call in transport.calls if call[0] == "POST"]
    assert [len(call[3]["records"]) for call in writes] == [FEISHU_BATCH_CREATE_LIMIT, 1]
    assert result.affected_rows == FEISHU_BATCH_CREATE_LIMIT + 1


def test_feishu_error_policy_rejected_before_provider_io() -> None:
    transport = FakeTransport()
    connector = FeishuBitableConnector(transport=transport, tenant_access_token="tenant-token")
    with pytest.raises(ConnectorError) as raised:
        connector.write(TableWriteRequest(TableURI("feishu://app-token/table-id"), pl.DataFrame({"id": [1]}), if_exists="error"))
    assert raised.value.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
    assert transport.calls == []


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
