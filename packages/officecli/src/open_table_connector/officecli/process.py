"""Bounded argv-only OfficeCLI process execution."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    truncated: bool = False
    timed_out: bool = False


def run_officecli(argv: Sequence[str], *, input_json: object | None, timeout_seconds: float = 120.0, max_output_bytes: int = 1024 * 1024) -> ProcessResult:
    if not argv or any(not isinstance(item, str) for item in argv):
        raise ValueError("OfficeCLI argv must be non-empty strings")
    payload = None if input_json is None else json.dumps(input_json, ensure_ascii=False).encode()
    try:
        completed = subprocess.run(tuple(argv), input=payload, capture_output=True, timeout=timeout_seconds, check=False, shell=False)
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"")[:max_output_bytes]
        stderr = (exc.stderr or b"")[:max_output_bytes]
        return ProcessResult(-1, stdout.decode(errors="replace"), stderr.decode(errors="replace"), True, True)
    combined = completed.stdout + completed.stderr
    truncated = len(combined) > max_output_bytes
    stdout = completed.stdout[:max_output_bytes]
    stderr = completed.stderr[:max_output_bytes]
    return ProcessResult(completed.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace"), truncated)


__all__ = ["ProcessResult", "run_officecli"]
