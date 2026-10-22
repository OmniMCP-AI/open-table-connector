from __future__ import annotations

from open_table_connector.mobile_table.adapter import MobileTableAdapter

from .fakes import FakeMobileHost

BASE = {
    "contract": "otc.mobile.table/1.0",
    "request_id": "req_read",
    "table_uri": "https://example.invalid/table/123",
}


def test_read_rejects_page_size_above_provider_capability() -> None:
    response = MobileTableAdapter(FakeMobileHost()).dispatch(
        "POST", "/otc/mobile/v1/read", {**BASE, "page_size": 101, "fields": ["status"]}
    )

    assert response.status == 400
    assert response.body["error"]["code"] == "resource_limit"


def test_read_rejects_unknown_request_fields_before_host_io() -> None:
    host = FakeMobileHost()
    response = MobileTableAdapter(host).dispatch(
        "POST", "/otc/mobile/v1/read", {**BASE, "fields": ["status"], "extra": True}
    )

    assert response.status == 400
    assert response.body["error"]["code"] == "invalid_request"
    assert host.calls == []


def test_read_returns_a_bounded_page_and_opaque_cursor() -> None:
    host = FakeMobileHost()
    response = MobileTableAdapter(host).dispatch(
        "POST",
        "/otc/mobile/v1/read",
        {**BASE, "page_size": 25, "page_token": "cursor%2Fopaque", "fields": ["status", "code"]},
    )

    assert response.status == 200
    assert response.body["next_page_token"] == "opaque.cursor/2"
    assert host.calls[-1] == ("read", (BASE["table_uri"], 25, "cursor%2Fopaque", ("status", "code")))
