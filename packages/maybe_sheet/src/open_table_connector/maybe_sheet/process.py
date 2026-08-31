"""Credential-safe process transport owned by the neutral MaybeSheet Connector."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from open_table_connector.contract import ConnectorError, ConnectorErrorCode


def _credential_environment(credentials: Mapping[str, str]) -> dict[str, str]:
    """Translate credential keys while rejecting normalized-name collisions."""
    normalized: dict[str, str] = {}
    originals: dict[str, str] = {}
    for raw_key, value in credentials.items():
        original = str(raw_key)
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
        if not command or command[0] != self.binary:
            command = (self.binary, *command)
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in self.environment.items()})
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
                {"returncode": completed.returncode},
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


__all__ = ["SubprocessProcessClient", "_credential_environment"]
