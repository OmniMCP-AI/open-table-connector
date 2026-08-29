"""Synchronous connector-process session supervisor."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from types import MappingProxyType
from typing import BinaryIO, Iterable, Mapping, TextIO

from open_table_connector.timeseries import ArrowArtifactReference

from .artifacts import ArtifactStore
from .credentials import CredentialLease, CredentialResolver
from .envelope import (
    ConnectorProcessEnvelope,
    PORTABLE_PLAN_VERSION,
    PROCESS_PROTOCOL,
    ProcessOperation,
)
from .framing import FrameError, read_frame, write_frame
from .registry import ConnectorProcessRegistry, ConnectorRegistration


class ProcessError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        safe_details: Mapping[str, object] | None = None,
    ) -> None:
        self.code = str(code)
        self.message = str(message)
        self.safe_details = dict(safe_details or {})
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class ProcessResult:
    payload: Mapping[str, object]
    artifact_references: tuple[ArrowArtifactReference, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.payload, Mapping):
            raise TypeError("process result payload must be an object")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        if not isinstance(self.artifact_references, tuple):
            object.__setattr__(self, "artifact_references", tuple(self.artifact_references))
        if not all(
            isinstance(item, ArrowArtifactReference) for item in self.artifact_references
        ):
            raise TypeError("process result artifacts must be ArrowArtifactReference values")


@dataclass(frozen=True, slots=True)
class ProcessRequestContext:
    envelope: ConnectorProcessEnvelope
    artifacts: ArtifactStore
    credentials: CredentialLease


class ConnectorProcessServer:
    def __init__(
        self,
        registry: ConnectorProcessRegistry,
        artifact_store: ArtifactStore,
        credential_resolver: CredentialResolver,
        clock: object | None = None,
    ) -> None:
        del clock
        self._registry = registry
        self._artifacts = artifact_store
        self._credentials = credential_resolver
        self._messages: set[str] = set()
        self._sessions: dict[str, ConnectorRegistration] = {}
        self._cancelled: set[str] = set()

    def handle(self, envelope: ConnectorProcessEnvelope) -> ConnectorProcessEnvelope:
        if not isinstance(envelope, ConnectorProcessEnvelope):
            raise TypeError("envelope must be a ConnectorProcessEnvelope")
        if envelope.message_id in self._messages:
            raise ProcessError("protocol_invalid", "message_id has already been used")
        if envelope.operation is ProcessOperation.HELLO:
            result = self._hello(envelope)
        elif envelope.operation is ProcessOperation.CANCEL:
            result = self._cancel(envelope)
        else:
            result = self._dispatch(envelope)
        self._messages.add(envelope.message_id)
        return self._response(envelope, result)

    def error_response(
        self,
        envelope: ConnectorProcessEnvelope,
        error: ProcessError,
    ) -> ConnectorProcessEnvelope:
        return self._response(
            envelope,
            ProcessResult(
                {
                    "ok": False,
                    "error": {
                        "code": error.code,
                        "message": error.message,
                        "safe_details": error.safe_details,
                    },
                }
            ),
            wrapped=True,
        )

    def _hello(self, envelope: ConnectorProcessEnvelope) -> ProcessResult:
        try:
            registration = self._registry.resolve(envelope.connector["id"])
        except KeyError as exc:
            raise ProcessError("protocol_invalid", "connector is not registered") from exc
        expected_connector = {
            "id": registration.connector_id,
            "version": registration.connector_version,
            "contract_version": registration.contract_version,
        }
        if dict(envelope.connector) != expected_connector:
            raise ProcessError("protocol_version_unsupported", "connector versions do not match")
        portable = envelope.payload.get("portable_plan_version")
        if portable != registration.portable_plan_version or portable != PORTABLE_PLAN_VERSION:
            raise ProcessError(
                "protocol_version_unsupported",
                "portable plan version is not supported",
            )
        requested = envelope.payload.get("capability_versions")
        if not isinstance(requested, Mapping):
            raise ProcessError("protocol_invalid", "hello capability_versions must be an object")
        for capability, version in requested.items():
            if registration.capability_versions.get(capability) != version:
                raise ProcessError(
                    "protocol_version_unsupported",
                    "hello capability version is not supported",
                    {"capability": str(capability)},
                )
        existing = self._sessions.get(envelope.session_id)
        if existing is not None and existing is not registration:
            raise ProcessError("protocol_invalid", "session_id is already bound")
        self._sessions[envelope.session_id] = registration
        return ProcessResult(
            {
                "process_protocol": PROCESS_PROTOCOL,
                "connector_version": registration.connector_version,
                "contract_version": registration.contract_version,
                "portable_plan_version": registration.portable_plan_version,
                "capability_versions": dict(sorted(registration.capability_versions.items())),
            }
        )

    def _dispatch(self, envelope: ConnectorProcessEnvelope) -> ProcessResult:
        registration = self._session(envelope.session_id)
        self._verify_connector(envelope, registration)
        if envelope.capability_version not in registration.capability_versions.values():
            raise ProcessError(
                "protocol_version_unsupported",
                "capability version is not supported",
            )
        try:
            lease = self._credentials.resolve(
                envelope.credential_reference,
                registration.connector_id,
            )
        except PermissionError as exc:
            raise ProcessError("protocol_invalid", "credential reference is not authorized") from exc
        try:
            context = ProcessRequestContext(envelope, self._artifacts, lease)
            try:
                raw_result = registration.handler.handle(context)
            except ProcessError:
                raise
            except Exception as exc:
                raise ProcessError("execution_failed", "connector operation failed") from exc
            if isinstance(raw_result, ProcessResult):
                return raw_result
            if isinstance(raw_result, Mapping):
                return ProcessResult(raw_result)
            raise ProcessError("execution_failed", "connector returned an invalid result")
        finally:
            lease.dispose()

    def _cancel(self, envelope: ConnectorProcessEnvelope) -> ProcessResult:
        target = envelope.payload.get("target_session_id")
        if not isinstance(target, str) or not target:
            raise ProcessError("protocol_invalid", "cancel requires target_session_id")
        registration = self._sessions.get(target)
        if registration is None:
            return ProcessResult({"cancelled": False, "target_session_id": target})
        self._cancelled.add(target)
        callback = getattr(registration.handler, "abort_session", None)
        if callback is not None:
            try:
                callback(target)
            except Exception:
                pass
        return ProcessResult({"cancelled": True, "target_session_id": target})

    def _session(self, session_id: str) -> ConnectorRegistration:
        if session_id in self._cancelled:
            raise ProcessError("protocol_invalid", "session is cancelled")
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise ProcessError("protocol_invalid", "hello is required before operation") from exc

    @staticmethod
    def _verify_connector(
        envelope: ConnectorProcessEnvelope,
        registration: ConnectorRegistration,
    ) -> None:
        if envelope.connector["id"] != registration.connector_id:
            raise ProcessError("protocol_invalid", "session connector does not match")
        if (
            envelope.connector["version"] != registration.connector_version
            or envelope.connector["contract_version"] != registration.contract_version
        ):
            raise ProcessError("protocol_version_unsupported", "connector versions do not match")

    @staticmethod
    def _response(
        request: ConnectorProcessEnvelope,
        result: ProcessResult,
        *,
        wrapped: bool = False,
    ) -> ConnectorProcessEnvelope:
        payload = dict(result.payload) if wrapped else {"ok": True, "result": dict(result.payload)}
        return ConnectorProcessEnvelope(
            protocol=PROCESS_PROTOCOL,
            message_id=f"{request.message_id}:response",
            session_id=request.session_id,
            operation=request.operation,
            connector=request.connector,
            capability_version=request.capability_version,
            resource_limits=request.resource_limits,
            credential_reference=None,
            payload=payload,
            artifact_references=result.artifact_references,
        )


def redact_text(value: str, secrets: Iterable[str] = ()) -> str:
    result = str(value)
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    result = re.sub(
        r"(?i)\b(token|password|secret|api[_-]?key)=\S+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        result,
    )
    return result


class BoundedDiagnostics:
    def __init__(
        self,
        stream: TextIO,
        *,
        max_bytes: int = 16_384,
        secrets: Iterable[str] = (),
    ) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self._stream = stream
        self._remaining = max_bytes
        self._secrets = tuple(secrets)

    def write(self, message: str) -> None:
        if self._remaining <= 0:
            return
        encoded = redact_text(message, self._secrets).encode("utf-8")[: self._remaining]
        while encoded:
            try:
                rendered = encoded.decode("utf-8")
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
        else:
            return
        self._stream.write(rendered)
        self._stream.flush()
        self._remaining -= len(encoded)


def run_server(
    stdin: BinaryIO,
    stdout: BinaryIO,
    stderr: TextIO,
    *,
    artifact_root: str | os.PathLike[str],
    registry: ConnectorProcessRegistry | None = None,
    credential_resolver: CredentialResolver | None = None,
    max_frame_bytes: int = 16 * 1024 * 1024,
) -> int:
    diagnostics = BoundedDiagnostics(stderr)
    server = ConnectorProcessServer(
        registry or ConnectorProcessRegistry(),
        ArtifactStore(artifact_root),
        credential_resolver or CredentialResolver(),
    )
    while True:
        try:
            wire = read_frame(stdin, max_frame_bytes)
        except FrameError as exc:
            diagnostics.write(f"fatal framing error: {exc}")
            return 2
        if wire is None:
            return 0
        try:
            envelope = ConnectorProcessEnvelope.from_wire(wire)
        except (TypeError, ValueError) as exc:
            diagnostics.write(f"fatal envelope error: {exc}")
            return 2
        try:
            response = server.handle(envelope)
        except ProcessError as exc:
            response = server.error_response(envelope, exc)
        write_frame(stdout, response)


__all__ = [
    "BoundedDiagnostics",
    "ConnectorProcessServer",
    "ProcessError",
    "ProcessRequestContext",
    "ProcessResult",
    "redact_text",
    "run_server",
]
