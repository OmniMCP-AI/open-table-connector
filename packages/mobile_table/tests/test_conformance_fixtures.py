from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import validate
from open_table_connector.contract import TableURI
from open_table_connector.mobile_table.adapter import MobileTableAdapter
from open_table_connector.mobile_table.models import (
    MobileCapabilities,
    MobileError,
    MobileInspection,
    MobileReadPage,
    MobileUpdateResult,
)

from .fakes import FakeMobileHost

ROOT = Path(__file__).parents[3]
FIXTURES = ROOT / "specification" / "fixtures" / "mobile_table"
SCHEMAS = ROOT / "specification" / "schemas"


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_mobile_fixtures_validate_and_round_trip() -> None:
    schema_for = {
        "capabilities-supported.json": "mobile-table-capabilities-v1.schema.json",
        "capabilities-unknown.json": "mobile-table-capabilities-v1.schema.json",
        "inspect-base.json": "mobile-table-inspect-v1.schema.json",
        "inspect-sheet-read-only.json": "mobile-table-inspect-v1.schema.json",
        "read-first-page.json": "mobile-table-read-v1.schema.json",
        "read-continuation.json": "mobile-table-read-v1.schema.json",
        "read-empty.json": "mobile-table-read-v1.schema.json",
        "update-success.json": "mobile-table-update-v1.schema.json",
        "update-unknown.json": "mobile-table-update-v1.schema.json",
        "update-conflict.json": "mobile-table-error-v1.schema.json",
    }
    model_for = {
        "capabilities-supported.json": MobileCapabilities,
        "capabilities-unknown.json": MobileCapabilities,
        "inspect-base.json": MobileInspection,
        "inspect-sheet-read-only.json": MobileInspection,
        "read-first-page.json": MobileReadPage,
        "read-continuation.json": MobileReadPage,
        "read-empty.json": MobileReadPage,
        "update-success.json": MobileUpdateResult,
        "update-unknown.json": MobileUpdateResult,
        "update-conflict.json": MobileError,
    }
    for name, schema_name in schema_for.items():
        payload = _json(FIXTURES / name)
        validate(payload, _json(SCHEMAS / schema_name))
        if name == "update-conflict.json":
            assert MobileError.from_wire(payload["error"]).to_wire() == payload["error"]
        else:
            assert model_for[name].from_wire(payload).to_wire() == payload


def test_reference_adapter_uses_shared_fixture_shapes() -> None:
    host = FakeMobileHost()
    adapter = MobileTableAdapter(host)
    cap = adapter.dispatch(
        "POST",
        "/otc/mobile/v1/capabilities",
        {"contract": "otc.mobile.table/1.0", "request_id": "req_cap_supported", "table_uri": "https://example.invalid/table/123"},
    )
    read = adapter.dispatch(
        "POST",
        "/otc/mobile/v1/read",
        {"contract": "otc.mobile.table/1.0", "request_id": "req_read_first", "table_uri": "https://example.invalid/table/123", "page_size": 25, "page_token": None},
    )
    update = adapter.dispatch(
        "POST",
        "/otc/mobile/v1/records/update",
        {
            "contract": "otc.mobile.table/1.0",
            "request_id": "req_update_success",
            "table_uri": "https://example.invalid/table/123",
            "record_id": "rec_123",
            "patch": {"status": "Done"},
            "expected_table_revision": "sha256:source-base",
            "expected_record_revision": "sha256:record-123",
            "idempotency_key": "idem-123",
        },
    )
    assert cap.body == _json(FIXTURES / "capabilities-supported.json")
    assert read.body == _json(FIXTURES / "read-first-page.json")
    assert update.body == _json(FIXTURES / "update-success.json")
    assert [name for name, _ in host.calls] == ["capabilities", "capabilities", "read", "capabilities", "update"]


def test_host_failure_does_not_expose_credentials_or_record_values() -> None:
    class LeakyHost(FakeMobileHost):
        def capabilities(self, table_uri: TableURI):
            raise RuntimeError("token=secret-value table=https://user:pass@example.invalid/table/123 patch={'status':'private'}")

    response = MobileTableAdapter(LeakyHost()).dispatch(
        "POST",
        "/otc/mobile/v1/capabilities",
        {"contract": "otc.mobile.table/1.0", "request_id": "req-safe", "table_uri": "https://example.invalid/table/123"},
    )
    text = json.dumps(response.body, sort_keys=True)
    assert response.status == 500
    assert "secret-value" not in text
    assert "user:pass" not in text
    assert "private" not in text
