"""Closed process dispatch for explicitly registered temporal providers."""

from __future__ import annotations

from types import MappingProxyType
import threading
from typing import Mapping

from open_table_connector.contract import TableURI
from open_table_connector.timeseries import (
    ManagedAbortRequest,
    ManagedCommitRequest,
    ManagedReadbackRequest,
    ManagedStageRequest,
    ManagedTemporalStore,
    PortableTemporalExecutor,
    TemporalExecutionRequest,
    TemporalExtensionError,
    plan_from_wire,
)

from .envelope import ProcessOperation
from .registry import ConnectorRegistration
from .server import ProcessError, ProcessRequestContext, ProcessResult


_PORTABLE = {
    "timeseries.describe": "1.0",
    "timeseries.scan.range": "1.0",
    "timeseries.lookup.latest": "1.0",
    "timeseries.lookup.asof": "1.0",
    "timeseries.aggregate.window": "1.0",
    "timeseries.fill": "1.0",
}
_LIFECYCLE = {
    "storage.stage": "1.0",
    "storage.commit.idempotent": "1.0",
    "storage.snapshot.read": "1.0",
    "storage.readback.verify": "1.0",
    "storage.visibility.atomic": "1.0",
    "storage.abort": "1.0",
}
def _capabilities(*parts: Mapping[str, str]) -> Mapping[str, str]:
    result: dict[str, str] = {}
    for part in parts:
        result.update(part)
    return MappingProxyType(result)


PORTABLE_PROVIDER_CAPABILITIES = MappingProxyType(
    {
        "csv": _capabilities(_PORTABLE, _LIFECYCLE),
        "json": _capabilities(_PORTABLE, _LIFECYCLE),
        "jsonl": _capabilities(_PORTABLE, _LIFECYCLE),
        "sqlite": _capabilities(_PORTABLE, _LIFECYCLE),
        "postgres": _capabilities(_PORTABLE, _LIFECYCLE),
        "excel": _capabilities(_PORTABLE, _LIFECYCLE),
        "maybe_sheet": _capabilities(_PORTABLE),
    }
)


class TemporalProcessHandler:
    """Adapt a bound executor/store pair to ``otc.connector-process/v1``."""

    def __init__(
        self,
        *,
        executor: PortableTemporalExecutor | None,
        store: ManagedTemporalStore | None,
    ) -> None:
        if executor is not None and not isinstance(executor, PortableTemporalExecutor):
            raise TypeError("executor must implement PortableTemporalExecutor")
        if store is not None and not isinstance(store, ManagedTemporalStore):
            raise TypeError("store must implement ManagedTemporalStore")
        if executor is None and store is None:
            raise ValueError("a temporal process handler requires an executor or store")
        self._executor = executor
        self._store = store
        self._cancelled_sessions: set[str] = set()
        self._cancel_lock = threading.Lock()

    @property
    def has_executor(self) -> bool:
        return self._executor is not None

    @property
    def has_store(self) -> bool:
        return self._store is not None

    def handle(self, context: ProcessRequestContext) -> ProcessResult:
        with self._cancel_lock:
            if context.envelope.session_id in self._cancelled_sessions:
                raise ProcessError("execution_failed", "temporal session was cancelled")
        try:
            result = self._handle(context)
        except TemporalExtensionError as exc:
            raise ProcessError(exc.code.value, exc.message, exc.safe_details) from exc
        with self._cancel_lock:
            if context.envelope.session_id in self._cancelled_sessions:
                raise ProcessError("execution_failed", "temporal session was cancelled")
        return result

    def abort_session(self, session_id: str) -> None:
        with self._cancel_lock:
            self._cancelled_sessions.add(session_id)
        for provider in (self._executor, self._store):
            callback = getattr(provider, "abort_session", None)
            if callback is not None:
                callback(session_id)

    def _handle(self, context: ProcessRequestContext) -> ProcessResult:
        operation = context.envelope.operation
        if operation is ProcessOperation.DESCRIBE:
            return ProcessResult({"portable_temporal": True})
        if operation is ProcessOperation.EXECUTE:
            return self._execute(context)
        if operation is ProcessOperation.STAGE:
            return self._stage(context)
        if operation is ProcessOperation.COMMIT:
            return self._commit(context)
        if operation is ProcessOperation.READBACK:
            return self._readback(context)
        if operation is ProcessOperation.ABORT:
            return self._abort(context)
        raise ProcessError("protocol_invalid", "operation is not handled by temporal provider")

    def _execute(self, context: ProcessRequestContext) -> ProcessResult:
        if self._executor is None:
            raise ProcessError("protocol_invalid", "provider has no temporal executor")
        payload = _closed(
            context.envelope.payload,
            {"target", "portable_plan", "snapshot_reference"},
            optional={"snapshot_reference"},
        )
        try:
            request = TemporalExecutionRequest(
                TableURI(str(payload["target"])),
                plan_from_wire(payload["portable_plan"]),
                context.envelope.credential_reference,
                context.envelope.message_id,
                payload.get("snapshot_reference"),
                context.credentials.values,
            )
            result = self._executor.execute(request)
            if result.table is None or result.receipt is None:
                raise ValueError("process executor must return in-process Arrow and receipt")
            artifact = context.artifacts.put_arrow(result.table)
        except ProcessError:
            raise
        except TemporalExtensionError as exc:
            raise ProcessError(exc.code.value, exc.message, exc.safe_details) from exc
        except Exception as exc:
            raise ProcessError("execution_failed", "temporal execute failed") from exc
        return ProcessResult(
            {"receipt": result.receipt.to_wire()},
            (artifact,),
        )

    def _stage(self, context: ProcessRequestContext) -> ProcessResult:
        store = self._require_store()
        payload = _closed(
            context.envelope.payload,
            {
                "operation_id",
                "descriptor_hash",
                "logical_target",
                "physical_target",
                "idempotency_key",
            },
        )
        if len(context.envelope.artifact_references) != 1:
            raise ProcessError("protocol_invalid", "stage requires exactly one Arrow artifact")
        receipt = store.stage(
            ManagedStageRequest(
                str(payload["operation_id"]),
                context.envelope.artifact_references[0],
                str(payload["descriptor_hash"]),
                _table_uri(payload["logical_target"]),
                _table_uri(payload["physical_target"]),
                str(payload["idempotency_key"]),
                context.envelope.resource_limits,
                context.credentials.values,
            )
        )
        return ProcessResult(receipt.to_wire())

    def _commit(self, context: ProcessRequestContext) -> ProcessResult:
        store = self._require_store()
        payload = _closed(
            context.envelope.payload,
            {"operation_id", "logical_target", "stage_id", "idempotency_key"},
        )
        receipt = store.commit(
            ManagedCommitRequest(
                str(payload["operation_id"]),
                _table_uri(payload["logical_target"]),
                str(payload["stage_id"]),
                str(payload["idempotency_key"]),
                context.envelope.resource_limits,
                context.credentials.values,
            )
        )
        return ProcessResult(receipt.to_wire())

    def _readback(self, context: ProcessRequestContext) -> ProcessResult:
        store = self._require_store()
        payload = _closed(
            context.envelope.payload,
            {"operation_id", "logical_target", "snapshot_id", "snapshot_reference"},
        )
        result = store.readback(
            ManagedReadbackRequest(
                str(payload["operation_id"]),
                _table_uri(payload["logical_target"]),
                str(payload["snapshot_id"]),
                str(payload["snapshot_reference"]),
                context.envelope.resource_limits,
                context.credentials.values,
            )
        )
        if result.table is None:
            raise ProcessError("execution_failed", "readback did not return in-process Arrow")
        artifact = context.artifacts.put_arrow(result.table)
        return ProcessResult(result.receipt.to_wire(), (artifact,))

    def _abort(self, context: ProcessRequestContext) -> ProcessResult:
        store = self._require_store()
        payload = _closed(
            context.envelope.payload,
            {"operation_id", "logical_target", "stage_id"},
        )
        receipt = store.abort(
            ManagedAbortRequest(
                str(payload["operation_id"]),
                _table_uri(payload["logical_target"]),
                str(payload["stage_id"]),
                context.credentials.values,
            )
        )
        return ProcessResult(receipt.to_wire())

    def _require_store(self) -> ManagedTemporalStore:
        if self._store is None:
            raise ProcessError("protocol_invalid", "provider has no managed temporal store")
        return self._store


def temporal_registration(
    provider: str,
    handler: TemporalProcessHandler,
) -> ConnectorRegistration:
    try:
        available = PORTABLE_PROVIDER_CAPABILITIES[provider]
    except KeyError as exc:
        raise ValueError(f"unsupported temporal provider: {provider}") from exc
    capabilities: dict[str, str] = {}
    if handler.has_executor:
        capabilities.update(
            (name, version)
            for name, version in available.items()
            if name in _PORTABLE
        )
    if handler.has_store:
        capabilities.update(
            (name, version)
            for name, version in available.items()
            if name in _LIFECYCLE
        )
    return ConnectorRegistration(
        connector_id=provider,
        connector_version="0.1.0",
        contract_version="1.0",
        portable_plan_version="otc.portable-temporal-plan/v1",
        capability_versions=capabilities,
        handler=handler,
    )


def _closed(
    payload: Mapping[str, object],
    fields: set[str],
    *,
    optional: set[str] | None = None,
) -> dict[str, object]:
    optional = optional or set()
    unknown = set(payload).difference(fields)
    missing = fields.difference(optional).difference(payload)
    if unknown or missing:
        raise ProcessError(
            "protocol_invalid",
            "temporal operation payload is not closed",
            {"unknown": sorted(unknown), "missing": sorted(missing)},
        )
    return dict(payload)


def _table_uri(value: object) -> TableURI:
    if isinstance(value, Mapping):
        return TableURI.from_wire(value)
    return TableURI(str(value))


__all__ = [
    "PORTABLE_PROVIDER_CAPABILITIES",
    "TemporalProcessHandler",
    "temporal_registration",
]
