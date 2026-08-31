from __future__ import annotations

from io import BytesIO, StringIO

from open_table_connector.process import (
    BoundedDiagnostics,
    ConnectorProcessRegistry,
    ConnectorRegistration,
    ProcessResult,
    read_frame,
    redact_text,
    run_server,
    write_frame,
)

from .test_envelope import envelope_wire


def test_diagnostics_are_bounded_and_redact_registered_secrets() -> None:
    assert redact_text("token=abc password=hunter2", ("abc", "hunter2")) == (
        "token=[REDACTED] password=[REDACTED]"
    )
    target = StringIO()
    diagnostics = BoundedDiagnostics(target, max_bytes=24, secrets=("hunter2",))
    diagnostics.write("failure hunter2 and a long diagnostic")
    assert "hunter2" not in target.getvalue()
    assert len(target.getvalue().encode()) <= 24


def test_redact_text_covers_json_assignments_without_touching_safe_names() -> None:
    assert redact_text('{"token": "fixture-secret", "ok": true}') == (
        '{"token": "[REDACTED]", "ok": true}'
    )
    assert redact_text("table=tokens") == "table=tokens"


def test_diagnostics_apply_the_limit_per_message() -> None:
    target = StringIO()
    diagnostics = BoundedDiagnostics(target, max_bytes_per_message=8)
    diagnostics.write("first message")
    diagnostics.write("second message")
    assert len(target.getvalue().encode()) == 16


def test_empty_process_loop_keeps_stdout_frame_only_channel_clean(tmp_path) -> None:
    stdout = BytesIO()
    stderr = StringIO()
    status = run_server(BytesIO(), stdout, stderr, artifact_root=tmp_path)
    assert status == 0
    assert stdout.getvalue() == b""
    assert stderr.getvalue() == ""


def test_operation_failures_are_safe_frames_not_process_failures(tmp_path) -> None:
    stdin = BytesIO()
    write_frame(stdin, envelope_wire())
    stdin.seek(0)
    stdout = BytesIO()
    stderr = StringIO()

    assert run_server(stdin, stdout, stderr, artifact_root=tmp_path) == 0
    stdout.seek(0)
    response = read_frame(stdout, 1_000_000)
    assert response["payload"] == {
        "ok": False,
        "error": {
            "code": "protocol_invalid",
            "message": "connector is not registered",
            "safe_details": {},
        },
    }
    assert read_frame(stdout, 1_000_000) is None
    assert stderr.getvalue() == ""


def test_worker_serialization_failure_returns_redacted_error(tmp_path) -> None:
    class Handler:
        def handle(self, _context):
            return ProcessResult({"bad": object()})

    registration = ConnectorRegistration(
        connector_id="fixture",
        connector_version="1.2.3",
        contract_version="1.0",
        portable_plan_version="otc.portable-temporal-plan/v1",
        capability_versions={"timeseries.scan.range": "1.0"},
        handler=Handler(),
    )
    registry = ConnectorProcessRegistry((registration,))
    stdin = BytesIO()
    write_frame(stdin, envelope_wire())
    write_frame(
        stdin,
        envelope_wire(
            message_id="execute",
            operation="execute",
            payload={
                "target": "json:///ticks.json",
                "portable_plan": {
                    "required_capabilities": ["timeseries.scan.range/1.0"],
                    "operation": {"kind": "scan_range"},
                },
            },
        ),
    )
    stdin.seek(0)
    stdout = BytesIO()
    stderr = StringIO()
    assert run_server(stdin, stdout, stderr, artifact_root=tmp_path, registry=registry) == 0
    stdout.seek(0)
    assert read_frame(stdout, 1_000_000)["payload"]["ok"] is True
    failed = read_frame(stdout, 1_000_000)
    assert failed["payload"]["ok"] is False
    assert failed["payload"]["error"]["code"] == "execution_failed"
    assert "object at 0x" not in stderr.getvalue()
