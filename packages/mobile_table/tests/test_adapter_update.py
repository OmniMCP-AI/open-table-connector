from __future__ import annotations

import open_table_connector.sdk as otc
from open_table_connector.mobile_table.adapter import MobileTableAdapter

from .fakes import FakeMobileHost, rejected, success, unknown_capabilities

BASE = {
    "contract": "otc.mobile.table/1.0",
    "request_id": "req_update",
    "table_uri": "https://example.invalid/table/123",
    "record_id": "rec_123",
    "patch": {"status": "Done", "owner": None},
    "expected_table_revision": "sha256:source-base",
    "expected_record_revision": "sha256:record-123",
    "idempotency_key": "mobile-edit-123",
}


def test_update_returns_canonical_result() -> None:
    host = FakeMobileHost()
    response = MobileTableAdapter(host).dispatch("POST", "/otc/mobile/v1/records/update", BASE)

    assert response.status == 200
    assert response.body["outcome"] == "succeeded"
    assert response.body["record"]["values"]["status"] == "Done"
    assert host.calls[0][0] == "capabilities"
    assert host.calls[1][0] == "update"


def test_stale_revision_maps_to_http_409_and_safe_error_envelope() -> None:
    host = FakeMobileHost(
        update_result=rejected(
            otc.ErrorCode.STALE_REVISION,
            "The record changed before it could be saved.",
            {"current_table_revision": "sha256:current", "access_token": "redact-me"},
        )
    )
    response = MobileTableAdapter(host).dispatch("POST", "/otc/mobile/v1/records/update", BASE)

    assert response.status == 409
    assert response.body["request_id"] == BASE["request_id"]
    assert response.body["error"]["code"] == "stale_revision"
    assert "access_token" not in response.body["error"]["details"]


def test_unsupported_capability_is_returned_before_host_update() -> None:
    host = FakeMobileHost(capabilities_result=success(unknown_capabilities()))
    response = MobileTableAdapter(host).dispatch("POST", "/otc/mobile/v1/records/update", BASE)

    assert response.status == 409
    assert response.body["error"]["code"] == "unsupported_capability"
    assert [name for name, _value in host.calls] == ["capabilities"]
