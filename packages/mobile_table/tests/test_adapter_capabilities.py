from __future__ import annotations

from open_table_connector.mobile_table.adapter import MobileTableAdapter

from .fakes import FakeMobileHost


def test_capabilities_route_is_exact_and_echoes_request_id() -> None:
    host = FakeMobileHost()
    response = MobileTableAdapter(host).dispatch(
        "POST",
        "/otc/mobile/v1/capabilities",
        {
            "contract": "otc.mobile.table/1.0",
            "request_id": "req_cap",
            "table_uri": "https://example.invalid/table/123",
        },
    )

    assert response.status == 200
    assert response.body["contract"] == "otc.mobile.table/1.0"
    assert response.body["request_id"] == "req_cap"
    assert response.body["read"]["support"] == "supported"
    assert host.calls == [("capabilities", "https://example.invalid/table/123")]


def test_unknown_method_or_path_is_closed() -> None:
    response = MobileTableAdapter(FakeMobileHost()).dispatch("GET", "/otc/mobile/v1/capabilities", {})

    assert response.status == 405
    assert response.body["error"]["code"] == "invalid_request"
