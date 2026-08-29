from __future__ import annotations

from io import BytesIO, StringIO

from open_table_connector.process import (
    BoundedDiagnostics,
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
