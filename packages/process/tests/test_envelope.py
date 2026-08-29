from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from open_table_connector.process import ConnectorProcessEnvelope, ProcessOperation


ROOT = Path(__file__).parents[3]
ENVELOPE_KEYS = {
    "protocol",
    "message_id",
    "session_id",
    "operation",
    "connector",
    "capability_version",
    "resource_limits",
    "credential_reference",
    "payload",
    "artifact_references",
}


def envelope_wire(**changes):
    wire = {
        "protocol": "otc.connector-process/v1",
        "message_id": "message-1",
        "session_id": "session-1",
        "operation": "hello",
        "connector": {
            "id": "fixture",
            "version": "1.2.3",
            "contract_version": "1.0",
        },
        "capability_version": "1.0",
        "resource_limits": {
            "max_rows": 100,
            "max_bytes": 100000,
            "max_duration_ms": 1000,
        },
        "credential_reference": None,
        "payload": {
            "portable_plan_version": "otc.portable-temporal-plan/v1",
            "capability_versions": {"timeseries.scan.range": "1.0"},
        },
        "artifact_references": [],
    }
    wire.update(changes)
    return wire


def test_envelope_is_closed_and_schema_validated() -> None:
    wire = envelope_wire()
    envelope = ConnectorProcessEnvelope.from_wire(wire)

    assert set(envelope.to_wire()) == ENVELOPE_KEYS
    assert envelope.operation is ProcessOperation.HELLO
    assert envelope.to_wire() == wire
    schema = json.loads(
        (ROOT / "specification/schemas/connector-process-envelope-v1.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(envelope.to_wire())

    with pytest.raises(ValueError, match="unknown envelope fields"):
        ConnectorProcessEnvelope.from_wire({**wire, "secret": "never"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("protocol", "otc.connector-process/v2"),
        ("message_id", ""),
        ("session_id", ""),
        ("operation", "query"),
        ("capability_version", ""),
        ("payload", []),
    ],
)
def test_envelope_rejects_invalid_closed_values(field, value) -> None:
    with pytest.raises((TypeError, ValueError)):
        ConnectorProcessEnvelope.from_wire(envelope_wire(**{field: value}))


def test_execute_snapshot_is_transport_metadata_outside_portable_plan() -> None:
    plan = {"schema_version": "otc.portable-temporal-plan/v1", "opaque": "same"}
    first = ConnectorProcessEnvelope.from_wire(
        envelope_wire(
            operation="execute",
            payload={"target": "json:///ticks.json", "portable_plan": plan},
        )
    )
    second = ConnectorProcessEnvelope.from_wire(
        envelope_wire(
            message_id="message-2",
            operation="execute",
            payload={
                "target": "json:///ticks.json",
                "portable_plan": plan,
                "snapshot_reference": "sha256:" + "a" * 64,
            },
        )
    )

    assert first.payload["portable_plan"] == second.payload["portable_plan"]
    assert "snapshot_reference" not in first.payload["portable_plan"]
