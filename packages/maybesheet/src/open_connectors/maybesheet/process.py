"""Credential-safe process transport owned by the neutral MaybeSheet Connector."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import subprocess
from typing import Any, Mapping

from open_connectors.contract import ConnectorError, ConnectorErrorCode


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
        for key, value in (credentials or {}).items():
            safe_key = "MAYBESHEET_" + "".join(
                character if character.isalnum() else "_"
                for character in str(key).upper()
            )
            env[safe_key] = str(value)
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


__all__ = ["SubprocessProcessClient"]
