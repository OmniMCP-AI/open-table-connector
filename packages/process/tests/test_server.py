from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import pytest
from open_table_connector.process import (
    ArtifactStore,
    ConnectorProcessEnvelope,
    ConnectorProcessRegistry,
    ConnectorProcessServer,
    ConnectorRegistration,
    CredentialResolver,
    ProcessError,
    ProcessResult,
)

from .test_envelope import envelope_wire


@dataclass
class RecordingHandler:
    calls: list
    aborts: list

    def handle(self, context):
        self.calls.append(context)
        assert context.credentials.values["token"] == "super-secret"
        return ProcessResult({"handled": context.envelope.operation.value})

    def abort_session(self, session_id):
        self.aborts.append(session_id)


def server(tmp_path: Path):
    handler = RecordingHandler([], [])
    registration = ConnectorRegistration(
        connector_id="fixture",
        connector_version="1.2.3",
        contract_version="1.0",
        portable_plan_version="otc.portable-temporal-plan/v1",
        capability_versions={
            "timeseries.scan.range": "1.0",
            "storage.abort": "1.0",
        },
        handler=handler,
    )
    registry = ConnectorProcessRegistry((registration,))
    resolver = CredentialResolver(
        {"fixture": {"credential://fixture/main": {"token": "super-secret"}}}
    )
    return (
        ConnectorProcessServer(registry, ArtifactStore(tmp_path), resolver),
        handler,
        resolver,
    )


def envelope(**changes):
    return ConnectorProcessEnvelope.from_wire(envelope_wire(**changes))


def hello(instance):
    return instance.handle(envelope())


def test_hello_pins_versions_before_dispatch_or_credentials(tmp_path: Path) -> None:
    instance, handler, resolver = server(tmp_path)
    response = hello(instance)

    assert response.payload["ok"] is True
    assert response.payload["result"] == {
        "process_protocol": "otc.connector-process/v1",
        "connector_version": "1.2.3",
        "contract_version": "1.0",
        "portable_plan_version": "otc.portable-temporal-plan/v1",
            "capability_versions": {
                "timeseries.scan.range": "1.0",
            },
    }
    assert handler.calls == []
    assert resolver.resolve_count == 0


def test_operation_requires_hello_capability_and_disposes_credentials(tmp_path: Path) -> None:
    instance, handler, resolver = server(tmp_path)
    execute = envelope(
        message_id="message-2",
        operation="execute",
        credential_reference="credential://fixture/main",
        payload={
            "target": "json:///ticks.json",
            "portable_plan": {
                "required_capabilities": ["timeseries.scan.range/1.0"],
                "operation": {"kind": "scan_range"},
            },
        },
    )
    with pytest.raises(ProcessError, match="hello"):
        instance.handle(execute)
    assert resolver.resolve_count == 0

    hello(instance)
    response = instance.handle(execute)
    assert response.payload == {"ok": True, "result": {"handled": "execute"}}
    assert resolver.resolve_count == 1
    assert resolver.last_lease.disposed is True

    bad_capability = envelope(
        message_id="message-3",
        operation="execute",
        capability_version="9.0",
        payload={
            "target": "json:///ticks.json",
            "portable_plan": {
                "required_capabilities": ["timeseries.scan.range/9.0"],
                "operation": {"kind": "scan_range"},
            },
        },
    )
    with pytest.raises(ProcessError, match="capability"):
        instance.handle(bad_capability)
    assert resolver.resolve_count == 1


def test_message_ids_are_unique_and_cancel_is_a_session_transition(tmp_path: Path) -> None:
    instance, handler, _ = server(tmp_path)
    hello(instance)
    with pytest.raises(ProcessError, match="message_id"):
        hello(instance)

    response = instance.handle(
        envelope(
            message_id="message-cancel",
            session_id="cancel-control",
            operation="cancel",
            payload={"target_session_id": "session-1"},
        )
    )
    assert response.payload["result"]["cancelled"] is True
    assert handler.aborts == ["session-1"]

    with pytest.raises(ProcessError, match="cancelled"):
        instance.handle(
            envelope(
                message_id="message-after-cancel",
                operation="describe",
                payload={},
            )
        )


def test_completed_message_ids_and_sessions_are_bounded(tmp_path: Path) -> None:
    instance, _handler, _resolver = server(tmp_path)
    for index in range(5000):
        instance.handle(
            envelope(
                message_id=f"hello-{index}",
                session_id=f"session-{index}",
            )
        )
        instance.retire_session(f"session-{index}")
    assert instance._state_counts() == {"messages": 4096, "sessions": 0, "cancelled": 0}


def test_cancel_interrupts_an_in_flight_dispatch_and_suppresses_success(tmp_path: Path) -> None:
    started = threading.Event()
    released = threading.Event()
    errors = []

    class BlockingHandler:
        def handle(self, context):
            del context
            started.set()
            assert released.wait(1)
            return ProcessResult({"late": "success"})

        def abort_session(self, session_id):
            assert session_id == "session-1"
            released.set()

    registration = ConnectorRegistration(
        connector_id="fixture",
        connector_version="1.2.3",
        contract_version="1.0",
        portable_plan_version="otc.portable-temporal-plan/v1",
        capability_versions={"timeseries.scan.range": "1.0"},
        handler=BlockingHandler(),
    )
    instance = ConnectorProcessServer(
        ConnectorProcessRegistry((registration,)),
        ArtifactStore(tmp_path),
        CredentialResolver(),
    )
    hello(instance)
    execute = envelope(
        message_id="message-running",
        operation="execute",
        payload={
            "target": "json:///ticks.json",
            "portable_plan": {
                "required_capabilities": [],
                "operation": {"kind": "scan_range"},
            },
        },
    )

    def run_operation():
        try:
            instance.handle(execute)
        except ProcessError as error:
            errors.append(error)

    worker = threading.Thread(target=run_operation)
    worker.start()
    assert started.wait(1)
    cancellation = instance.handle(
        envelope(
            message_id="message-cancel-running",
            session_id="cancel-control",
            operation="cancel",
            payload={"target_session_id": "session-1"},
        )
    )
    worker.join(1)

    assert cancellation.payload["result"]["cancelled"] is True
    assert not worker.is_alive()
    assert len(errors) == 1
    assert errors[0].code == "execution_failed"
