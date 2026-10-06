"""Bounded argv-only OfficeCLI process execution."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    truncated: bool = False
    timed_out: bool = False


def runtime_environment() -> dict[str, str]:
    keys = ("PATH", "HOME", "TMPDIR", "SYSTEMROOT", "LANG", "LC_ALL")
    return {**{key: os.environ[key] for key in keys if key in os.environ},
            "OFFICECLI_SKIP_UPDATE": "1", "OFFICECLI_NO_AUTO_RESIDENT": "1"}


def stop_process(process) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=2)


def run_officecli(argv: Sequence[str], *, input_json: object | None, timeout_seconds: float = 120.0, max_output_bytes: int = 1024 * 1024) -> ProcessResult:
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ValueError("OfficeCLI argv must be non-empty strings")
    if timeout_seconds <= 0 or max_output_bytes <= 0:
        raise ValueError("process limits must be positive")
    payload = None if input_json is None else json.dumps(input_json, ensure_ascii=False).encode()
    if payload is not None and len(payload) > 16 * 1024 * 1024:
        raise ValueError("OfficeCLI payload exceeds limit")
    # Spool diagnostics rather than retaining unbounded subprocess output in RAM.
    with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        if payload:
            stdin.write(payload)
        stdin.seek(0)
        process = subprocess.Popen(tuple(argv), stdin=stdin, stdout=stdout, stderr=stderr,
                                   shell=False, env=runtime_environment(), start_new_session=True)
        deadline = time.monotonic() + timeout_seconds
        timed_out = truncated = False
        while process.poll() is None:
            truncated = os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > max_output_bytes
            timed_out = time.monotonic() >= deadline
            if truncated or timed_out:
                stop_process(process)
                break
            time.sleep(0.01)
        truncated = truncated or os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > max_output_bytes
        stdout.seek(0)
        out = stdout.read(max_output_bytes)
        stderr.seek(0)
        err = stderr.read(max_output_bytes - len(out))
        return ProcessResult(process.returncode, out.decode(errors="replace"), err.decode(errors="replace"), truncated, timed_out)


__all__ = ["ProcessResult", "run_officecli", "runtime_environment", "stop_process"]
