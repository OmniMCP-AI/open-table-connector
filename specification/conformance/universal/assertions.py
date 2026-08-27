from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

import pyarrow as pa

from open_connectors.contract import (
    CapabilityIdentity,
    CapabilityManifest,
    ConnectorError,
    ConnectorIdentity,
    NeutralReceipt,
    TableMode,
    TableURI,
)
from open_connectors.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
)


_RECEIPT_WIRE_KEYS = {
    "contract_version",
    "connector",
    "capability",
    "operation_id",
    "safe_uri",
    "mode",
    "source_revision",
    "schema_fingerprint",
    "content_fingerprint",
    "coordinate_convention",
    "row_count",
    "batch_count",
    "vendor_receipt_ref",
}
_SECRET_DETAIL_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}


def _assert_closed_wire(payload: Mapping[str, Any], expected_keys: set[str], label: str) -> None:
    assert set(payload) == expected_keys, f"{label} wire keys mismatch: {set(payload)!r}"


def _iter_mapping_items(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            yield str(raw_key), item
            yield from _iter_mapping_items(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_mapping_items(item)


def assert_identity_round_trip(identity: ConnectorIdentity) -> None:
    wire = identity.to_wire()

    _assert_closed_wire(
        wire,
        {"connector_id", "connector_version", "contract_version"},
        "ConnectorIdentity",
    )
    assert ConnectorIdentity.from_wire(wire) == identity


def assert_capabilities_are_unique(
    capabilities: tuple[CapabilityIdentity, ...],
    *,
    expected_connector: ConnectorIdentity,
    expected_capabilities: frozenset[str],
    expected_modes: frozenset[TableMode],
    expected_schemes: frozenset[str],
    manifest: CapabilityManifest | None = None,
) -> None:
    capability_ids = tuple(item.capability_id for item in capabilities)

    assert set(capability_ids) == set(expected_capabilities)
    assert len(capability_ids) == len(set(capability_ids))
    assert all(isinstance(mode, TableMode) for mode in expected_modes)
    if manifest is not None:
        wire = manifest.to_wire()

        _assert_closed_wire(
            wire,
            {"connector", "capabilities", "modes", "uri_schemes"},
            "CapabilityManifest",
        )
        assert CapabilityManifest.from_wire(wire) == manifest
        assert manifest.connector == expected_connector
        assert tuple(manifest.capabilities) == capabilities
        assert set(manifest.modes) == set(expected_modes)
        assert set(manifest.uri_schemes) == {item.casefold() for item in expected_schemes}
        assert tuple(manifest.uri_schemes) == tuple(dict.fromkeys(manifest.uri_schemes))


def assert_safe_uri(uri: TableURI, *, allowed_schemes: frozenset[str]) -> None:
    wire = uri.to_wire()
    encoded = json.dumps(wire, ensure_ascii=False, sort_keys=True).casefold()

    _assert_closed_wire(wire, {"value"}, "TableURI")
    assert TableURI.from_wire(wire) == uri
    assert uri.scheme in {item.casefold() for item in allowed_schemes}
    assert "token=" not in encoded
    assert "password=" not in encoded
    assert "access_token=" not in encoded


def assert_receipt_matches_table(
    receipt: NeutralReceipt,
    table: pa.Table,
    *,
    expected_connector: ConnectorIdentity,
    expected_capability: str,
    expected_mode: TableMode,
    expected_safe_uri: TableURI,
    forbidden_values: tuple[str, ...] = ("fixture-token", "fixture-secret"),
) -> None:
    wire = receipt.to_wire()
    encoded = json.dumps(wire, ensure_ascii=False, sort_keys=True)

    _assert_closed_wire(wire, _RECEIPT_WIRE_KEYS, "NeutralReceipt")
    assert NeutralReceipt.from_wire(wire) == receipt
    assert receipt.connector == expected_connector
    assert receipt.capability.capability_id == expected_capability
    assert receipt.safe_uri == expected_safe_uri
    assert receipt.mode == expected_mode
    assert wire["contract_version"] == expected_connector.contract_version
    assert receipt.schema_fingerprint == arrow_schema_fingerprint(table.schema)
    assert receipt.content_fingerprint == arrow_content_fingerprint(table)
    assert receipt.row_count == table.num_rows
    assert receipt.batch_count is None or receipt.batch_count >= 0
    for forbidden in forbidden_values:
        assert forbidden not in encoded


def assert_error_is_safe(
    error: ConnectorError,
    *,
    forbidden_values: tuple[str, ...] = ("fixture-token", "fixture-secret"),
) -> None:
    wire = error.to_wire()
    encoded = json.dumps(wire, ensure_ascii=False, sort_keys=True)

    _assert_closed_wire(wire, {"code", "message", "safe_details"}, "ConnectorError")
    for key, _ in _iter_mapping_items(wire["safe_details"]):
        assert key.casefold() not in _SECRET_DETAIL_KEYS
    for forbidden in forbidden_values:
        assert forbidden not in encoded
