"""Credential-safe process transport owned by the neutral MaybeSheet Connector."""

from __future__ import annotations

import json
import re
import stat
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from open_table_connector.contract import ConnectorError, ConnectorErrorCode


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(access[_-]?token|api[_-]?key|apikey|credential|password|secret|token)"
    r"(\s*[=:]\s*)(\S+)"
)
# An authorization header carries an optional scheme word before the value, so
# redacting a single token would leave the credential behind.
_AUTHORIZATION_ASSIGNMENT = re.compile(r"(?i)\b(authorization)(\s*[=:]\s*)(?:\S+\s+)?\S+")


def scrub_secrets(text: str, credentials: Mapping[str, str] | None = None) -> str:
    """Remove credential material from diagnostic text.

    Diagnostic messages are carried through to callers so failures stay
    distinguishable, which means any credential that leaked into a provider or
    transport message has to be removed before it can be reported.
    """
    scrubbed = text
    for value in (credentials or {}).values():
        if isinstance(value, str) and len(value) >= 4:
            scrubbed = scrubbed.replace(value, "<redacted>")
    scrubbed = _AUTHORIZATION_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", scrubbed
    )
    return _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", scrubbed)


_STDERR_EXCERPT_LIMIT = 400


def _stderr_excerpt(stderr: object, credentials: Mapping[str, str] | None = None) -> str:
    """Return a bounded, whitespace-collapsed diagnostic from a failed process.

    Callers (and the connector) need the provider's own message to classify and
    explain a failure; the exit code alone collapses every distinct cause into
    one indistinguishable error.
    """
    if not isinstance(stderr, str):
        return ""
    collapsed = " ".join(stderr.split())
    return scrub_secrets(collapsed, credentials)[:_STDERR_EXCERPT_LIMIT]


def _credential_environment(credentials: Mapping[str, str]) -> dict[str, str]:
    """Translate credential keys while rejecting normalized-name collisions."""
    normalized: dict[str, str] = {}
    originals: dict[str, str] = {}
    for raw_key, value in credentials.items():
        original = str(raw_key)
        if original.lower() == "access_token":
            safe_key = "MAYBEAI_API_TOKEN"
        else:
            safe_key = "MAYBE_SHEET_" + "".join(
                character if character.isalnum() else "_" for character in original.upper()
            )
        previous = originals.get(safe_key)
        if previous is not None and previous != original:
            raise ConnectorError(
                ConnectorErrorCode.CONFLICT,
                "credential names collide after environment normalization",
                {"key": safe_key},
            )
        originals[safe_key] = original
        normalized[safe_key] = str(value)
    return normalized


def _absolute_executable(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or not Path(value).is_absolute():
        raise ValueError("MaybeSheet binary must be an absolute path")
    path = Path(value).resolve()
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or not metadata.st_mode & 0o111:
        raise ValueError("MaybeSheet binary must be an executable regular file")
    return str(path)


@dataclass(frozen=True)
class SubprocessProcessClient:
    """Invoke the MaybeSheet CLI without leaking credentials or diagnostics."""

    binary: str = "mbs"
    timeout_seconds: float = 120.0
    environment: Mapping[str, str] = field(default_factory=dict)

    def run(
        self,
        argv: tuple[str, ...],
        *,
        credentials: Mapping[str, str] | None = None,
        stdin: str | None = None,
        timeout: float | int | None = None,
    ) -> Mapping[str, Any]:
        effective_timeout = self.timeout_seconds if timeout is None else timeout
        command = tuple(argv)
        if command and command[0] == "mbs":
            command = (self.binary, *command[1:])
        elif not command or command[0] != self.binary:
            command = (self.binary, *command)
        env = {str(key): str(value) for key, value in self.environment.items()}
        env.update(_credential_environment(credentials or {}))
        try:
            completed = subprocess.run(
                list(command),
                check=False,
                capture_output=True,
                text=True,
                input=stdin,
                timeout=effective_timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConnectorError(
                ConnectorErrorCode.TIMEOUT,
                "MaybeSheet process timed out",
                {"timeout_seconds": effective_timeout},
            ) from exc
        if completed.returncode != 0:
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "MaybeSheet process failed",
                {
                    "returncode": completed.returncode,
                    "stderr": _stderr_excerpt(completed.stderr, credentials),
                },
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "MaybeSheet process returned invalid JSON",
                {},
            ) from exc
        if not isinstance(payload, Mapping):
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "MaybeSheet process returned a non-object payload",
                {},
            )
        return payload


__all__ = [
    "SubprocessProcessClient",
    "_absolute_executable",
    "_credential_environment",
    "scrub_secrets",
]
