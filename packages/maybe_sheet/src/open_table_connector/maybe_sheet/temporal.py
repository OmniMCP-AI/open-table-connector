"""Capability-gated MaybeSheet bridge for portable temporal execution."""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
from threading import Lock
from typing import Callable, Mapping
import weakref

import pyarrow as pa

from open_table_connector.contract import ConnectorError, ConnectorErrorCode, TableURI
from open_table_connector.timeseries import (
    ManagedAbortReceipt,
    ManagedAbortRequest,
    ManagedCommitReceipt,
    ManagedCommitRequest,
    ManagedReadbackReceipt,
    ManagedReadbackRequest,
    ManagedReadbackResult,
    ManagedStageReceipt,
    ManagedStageRequest,
    PolarsTemporalExecutor,
    ResourceBounds,
    TemporalErrorCode,
    TemporalExecutionRequest,
    TemporalExecutionResult,
    TemporalExtensionError,
    TemporalTableDescriptor,
    temporal_descriptor_hash,
    validate_stage_retry,
)
from open_table_connector.timeseries.capabilities import (
    AGGREGATE_WINDOW,
    DESCRIBE,
    FILL,
    LOOKUP_ASOF,
    LOOKUP_LATEST,
    SCAN_RANGE,
    STORAGE_ABORT,
    STORAGE_COMMIT_IDEMPOTENT,
    STORAGE_READBACK_VERIFY,
    STORAGE_SNAPSHOT_READ,
    STORAGE_STAGE,
    STORAGE_VISIBILITY_ATOMIC,
)

from .connector import ProcessClient


_SEMANTIC_CAPABILITIES = {
    DESCRIBE,
    SCAN_RANGE,
    LOOKUP_LATEST,
    LOOKUP_ASOF,
    AGGREGATE_WINDOW,
    FILL,
}
_LIFECYCLE_CAPABILITIES = {
    STORAGE_STAGE,
    STORAGE_COMMIT_IDEMPOTENT,
    STORAGE_SNAPSHOT_READ,
    STORAGE_READBACK_VERIFY,
    STORAGE_VISIBILITY_ATOMIC,
    STORAGE_ABORT,
}
_COMMANDS = {
    "read": {
        "version": "1.0",
        "result_schema": "mbs.temporal-read-result/v1",
        "receipt_schema": "mbs.temporal-read-receipt/v1",
    },
    "stage": {"version": "1.0", "receipt_schema": "otc.managed-stage-receipt/v1"},
    "commit": {"version": "1.0", "receipt_schema": "otc.managed-commit-receipt/v1"},
    "snapshot-read": {
        "version": "1.0",
        "result_schema": "mbs.temporal-snapshot-result/v1",
        "media_type": "application/vnd.apache.arrow.stream",
    },
    "readback": {
        "version": "1.0",
        "receipt_schema": "otc.managed-readback-receipt/v1",
    },
    "abort": {"version": "1.0", "receipt_schema": "otc.managed-abort-receipt/v1"},
}
_VISIBILITY = {
    "guarantee": "atomic",
    "evidence_schema": "mbs.atomic-pointer-evidence/v1",
}
_PROBE_FIELDS = {
    "schema_version",
    "provider_identity",
    "capabilities",
    "commands",
    "visibility",
}
_CACHE: dict[int, tuple[weakref.ReferenceType | None, frozenset[str]]] = {}
_CACHE_LOCK = Lock()


def probe_temporal_capabilities(client: ProcessClient) -> frozenset[str]:
    """Return only immutable capabilities proven by the exact v1 description."""

    return _probe(client)


def _probe(client: ProcessClient) -> frozenset[str]:
    identity = id(client)
    with _CACHE_LOCK:
        cached = _CACHE.get(identity)
        if cached is not None and (cached[0] is None or cached[0]() is client):
            return cached[1]
    description = _run(
        client,
        ("mbs", "timeseries", "describe", "--format", "json"),
        credentials=None,
        stdin=None,
        timeout=5,
    )
    result = _capabilities(description)
    try:
        reference = weakref.ref(client, lambda _ref, key=identity: _drop_cache(key))
    except TypeError:
        reference = None
    with _CACHE_LOCK:
        _CACHE[identity] = (reference, result)
    return result


def _drop_cache(identity: int) -> None:
    with _CACHE_LOCK:
        _CACHE.pop(identity, None)


def _capabilities(description: Mapping) -> frozenset[str]:
    if (
        not isinstance(description, Mapping)
        or set(description) != _PROBE_FIELDS
        or description.get("schema_version") != "mbs.temporal-describe/v1"
        or not isinstance(description.get("provider_identity"), str)
        or not description["provider_identity"].strip()
        or not isinstance(description.get("commands"), Mapping)
        or not isinstance(description.get("capabilities"), list)
    ):
        return frozenset()
    commands = description["commands"]
    advertised = {
        value for value in description["capabilities"] if isinstance(value, str)
    }
    result = {DESCRIBE}
    if commands.get("read") == _COMMANDS["read"]:
        result.update(advertised & _SEMANTIC_CAPABILITIES)
    if (
        all(commands.get(name) == _COMMANDS[name] for name in _COMMANDS if name != "read")
        and description.get("visibility") == _VISIBILITY
    ):
        result.update(_LIFECYCLE_CAPABILITIES)
    return frozenset(result)


class _MaybeSheetTemporalSource:
    def __init__(self, table: pa.Table, descriptor: TemporalTableDescriptor) -> None:
        self._table = table
        self.descriptor = descriptor

    def read_bounded(self, target, projection, predicates, bounds) -> pa.Table:
        del target, predicates, bounds
        return self._table.select(projection)


class MaybeSheetTemporalExecutor:
    def __init__(
        self,
        process_client: ProcessClient,
        descriptor: TemporalTableDescriptor,
        *,
        credential_resolver: Callable[[str], Mapping[str, str]] | None = None,
    ) -> None:
        if not isinstance(descriptor, TemporalTableDescriptor):
            raise TypeError("descriptor must be a TemporalTableDescriptor")
        self._process = process_client
        self.descriptor = descriptor
        self.capabilities = probe_temporal_capabilities(process_client)
        self._credential_resolver = credential_resolver

    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult:
        required = _operation_capability(request)
        if required not in self.capabilities:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "MaybeSheet did not prove the requested temporal capability",
                {"capability": required},
            )
        credentials = None
        if request.credential_reference is not None:
            if self._credential_resolver is None:
                raise TemporalExtensionError(
                    TemporalErrorCode.PROTOCOL_INVALID,
                    "credential_reference requires a configured resolver",
                    {},
                )
            credentials = dict(self._credential_resolver(request.credential_reference))
        payload = {
            "schema_version": "mbs.temporal-read-request/v1",
            "operation_id": request.operation_id,
            "target": request.target.to_wire(),
            "descriptor": self.descriptor.to_wire(),
            "plan": request.plan.to_wire(),
            "resource_bounds": request.plan.resource_bounds.to_wire(),
            "snapshot_reference": request.snapshot_reference,
        }
        response = _run(
            self._process,
            ("mbs", "timeseries", "read", "--input", "-"),
            credentials=credentials,
            stdin=_jsonl(payload),
            timeout=request.plan.resource_bounds.max_duration_ms / 1000,
        )
        table, carrier = _decode_arrow_result(
            response,
            "mbs.temporal-read-result/v1",
            request.plan.resource_bounds,
            receipt_schema="mbs.temporal-read-receipt/v1",
        )
        receipt = response["receipt"]
        if receipt.get("rows") != table.num_rows or not isinstance(
            receipt.get("source_revision"), str
        ):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "MaybeSheet temporal read receipt does not match its Arrow carrier",
                {},
            )
        del carrier
        return PolarsTemporalExecutor(
            _MaybeSheetTemporalSource(table, self.descriptor)
        ).execute(request)


class MaybeSheetManagedTemporalStore:
    def __init__(
        self,
        process_client: ProcessClient,
        artifact_root: str | os.PathLike[str],
        descriptor: TemporalTableDescriptor,
        *,
        credentials: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(descriptor, TemporalTableDescriptor):
            raise TypeError("descriptor must be a TemporalTableDescriptor")
        self._process = process_client
        self.artifact_root = Path(artifact_root).absolute()
        if self.artifact_root.is_symlink():
            raise PermissionError("artifact root cannot be a symlink")
        self.descriptor = descriptor
        self.credentials = dict(credentials or {})
        self.capabilities = probe_temporal_capabilities(process_client)
        missing = sorted(_LIFECYCLE_CAPABILITIES - self.capabilities)
        if missing:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "MaybeSheet did not prove the complete managed lifecycle",
                {"missing_capabilities": missing},
            )

    def stage(self, request: ManagedStageRequest) -> ManagedStageReceipt:
        data, table, path = self._read_artifact(request)
        del data
        if temporal_descriptor_hash(self.descriptor, table.schema) != request.descriptor_hash:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "staged Arrow schema does not match descriptor_hash",
                {},
            )
        response = self._invoke(
            "stage",
            {
                "schema_version": "mbs.temporal-stage-request/v1",
                "operation_id": request.operation_id,
                "artifact": request.artifact.to_wire(),
                "artifact_path": str(path),
                "descriptor_hash": request.descriptor_hash,
                "logical_target": request.logical_target.to_wire(),
                "physical_target": request.physical_target.to_wire(),
                "idempotency_key": request.idempotency_key,
            },
        )
        receipt = _receipt(response, ManagedStageReceipt)
        return validate_stage_retry(receipt, request)

    def commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt:
        response = self._invoke(
            "commit",
            {
                "schema_version": "mbs.temporal-commit-request/v1",
                "operation_id": request.operation_id,
                "logical_target": request.logical_target.to_wire(),
                "stage_id": request.stage_id,
                "idempotency_key": request.idempotency_key,
            },
        )
        receipt = _receipt(response, ManagedCommitReceipt)
        if (
            receipt.logical_target != request.logical_target
            or receipt.stage_id != request.stage_id
            or receipt.idempotency_key != request.idempotency_key
        ):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "MaybeSheet commit receipt does not match the request",
                {},
            )
        return receipt

    def read_snapshot(
        self,
        target: TableURI,
        snapshot_reference: str,
        bounds: ResourceBounds,
        *,
        snapshot_id: str | None = None,
    ) -> pa.Table:
        table, _ = self._snapshot_carrier(
            target, snapshot_reference, bounds, snapshot_id=snapshot_id
        )
        return table

    def _snapshot_carrier(
        self,
        target: TableURI,
        snapshot_reference: str,
        bounds: ResourceBounds,
        *,
        snapshot_id: str | None,
    ) -> tuple[pa.Table, bytes]:
        response = self._invoke(
            "snapshot-read",
            {
                "schema_version": "mbs.temporal-snapshot-read-request/v1",
                "logical_target": target.to_wire(),
                "snapshot_id": snapshot_id,
                "snapshot_reference": snapshot_reference,
                "resource_bounds": bounds.to_wire(),
            },
            timeout=bounds.max_duration_ms / 1000,
        )
        table, data = _decode_arrow_result(
            response,
            "mbs.temporal-snapshot-result/v1",
            bounds,
            receipt_schema=None,
        )
        if snapshot_id is not None and _sha256(data) != snapshot_id:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "MaybeSheet snapshot carrier does not match snapshot_id",
                {},
            )
        return table, data

    def readback(self, request: ManagedReadbackRequest) -> ManagedReadbackResult:
        table, data = self._snapshot_carrier(
            request.logical_target,
            request.snapshot_reference,
            request.resource_bounds,
            snapshot_id=request.snapshot_id,
        )
        response = self._invoke(
            "readback",
            {
                "schema_version": "mbs.temporal-readback-request/v1",
                "operation_id": request.operation_id,
                "logical_target": request.logical_target.to_wire(),
                "snapshot_id": request.snapshot_id,
                "snapshot_reference": request.snapshot_reference,
                "resource_bounds": request.resource_bounds.to_wire(),
            },
            timeout=request.resource_bounds.max_duration_ms / 1000,
        )
        receipt = _receipt(response, ManagedReadbackReceipt)
        expected_schema = _sha256(table.schema.serialize().to_pybytes())
        if (
            receipt.operation_id != request.operation_id
            or receipt.snapshot_id != request.snapshot_id
            or receipt.observed_schema_hash != expected_schema
            or receipt.observed_content_hash != _sha256(data)
            or receipt.observed_rows != table.num_rows
            or receipt.observed_bytes != len(data)
        ):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "MaybeSheet readback receipt does not independently match the snapshot",
                {},
            )
        return ManagedReadbackResult(table, None, receipt)

    def abort(self, request: ManagedAbortRequest) -> ManagedAbortReceipt:
        response = self._invoke(
            "abort",
            {
                "schema_version": "mbs.temporal-abort-request/v1",
                "operation_id": request.operation_id,
                "logical_target": request.logical_target.to_wire(),
                "stage_id": request.stage_id,
            },
        )
        receipt = _receipt(response, ManagedAbortReceipt)
        if (
            receipt.operation_id != request.operation_id
            or receipt.logical_target != request.logical_target
            or receipt.stage_id != request.stage_id
        ):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "MaybeSheet abort receipt does not match the request",
                {},
            )
        return receipt

    def _invoke(self, command: str, document: Mapping, *, timeout=None) -> Mapping:
        return _run(
            self._process,
            ("mbs", "timeseries", command, "--input", "-"),
            credentials=self.credentials,
            stdin=_jsonl(document),
            timeout=timeout,
        )

    def _read_artifact(self, request: ManagedStageRequest):
        expected = f"sha256/{request.artifact.sha256[7:]}.arrow"
        if request.artifact.relative_path != expected:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "Arrow artifact path is not canonical",
                {},
            )
        path = self.artifact_root / expected
        try:
            metadata = path.lstat()
        except FileNotFoundError as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "Arrow artifact is unavailable",
                {},
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PermissionError("Arrow artifact cannot be a symlink")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise PermissionError("Arrow artifact ownership is not trusted")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise PermissionError("Arrow artifact permissions are too broad")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            current = os.fstat(stream.fileno())
            if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise PermissionError("Arrow artifact changed during secure open")
            data = stream.read(request.artifact.size_bytes + 1)
        if len(data) != request.artifact.size_bytes or _sha256(data) != request.artifact.sha256:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "Arrow artifact verification failed",
                {},
            )
        try:
            table = pa.ipc.open_stream(pa.BufferReader(data)).read_all()
        except pa.ArrowInvalid as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "Arrow artifact is not an IPC stream",
                {},
            ) from exc
        return data, table, path


def _operation_capability(request: TemporalExecutionRequest) -> str:
    from open_table_connector.timeseries import AsOf, BucketAggregate, GapFill, Latest, ScanRange

    return {
        ScanRange: SCAN_RANGE,
        Latest: LOOKUP_LATEST,
        AsOf: LOOKUP_ASOF,
        BucketAggregate: AGGREGATE_WINDOW,
        GapFill: FILL,
    }[type(request.plan.operation)]


def _run(client, argv, *, credentials, stdin, timeout):
    kwargs = {"credentials": credentials, "stdin": stdin}
    try:
        parameters = inspect.signature(client.run).parameters.values()
    except (TypeError, ValueError):
        parameters = ()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters) or any(
        parameter.name == "timeout" for parameter in parameters
    ):
        kwargs["timeout"] = timeout
    try:
        response = client.run(argv, **kwargs)
    except ConnectorError:
        raise
    except Exception:
        raise ConnectorError(
            ConnectorErrorCode.EXECUTION_FAILED,
            "MaybeSheet temporal process operation failed",
            {"command": argv[2]},
        ) from None
    if not isinstance(response, Mapping):
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "MaybeSheet temporal response must be an object",
            {},
        )
    return response


def _decode_arrow_result(response, schema_version, bounds, *, receipt_schema):
    expected = {"schema_version", "arrow_ipc_base64"}
    if receipt_schema is not None:
        expected.add("receipt")
    if set(response) != expected or response.get("schema_version") != schema_version:
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "MaybeSheet Arrow result does not match its closed schema",
            {},
        )
    if receipt_schema is not None:
        receipt = response.get("receipt")
        if not isinstance(receipt, Mapping) or receipt.get("schema_version") != receipt_schema:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "MaybeSheet temporal receipt version is unsupported",
                {},
            )
    try:
        data = base64.b64decode(response["arrow_ipc_base64"], validate=True)
    except (TypeError, ValueError) as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "MaybeSheet Arrow carrier is invalid base64",
            {},
        ) from exc
    if len(data) > bounds.max_bytes:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            "MaybeSheet Arrow carrier exceeds max_bytes",
            {"bytes": len(data)},
        )
    try:
        table = pa.ipc.open_stream(pa.BufferReader(data)).read_all()
    except pa.ArrowInvalid as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "MaybeSheet Arrow carrier is not an IPC stream",
            {},
        ) from exc
    if table.num_rows > bounds.max_rows:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            "MaybeSheet Arrow carrier exceeds max_rows",
            {"rows": table.num_rows},
        )
    return table, data


def _receipt(response: Mapping, receipt_type):
    if set(response) != {"receipt"} or not isinstance(response["receipt"], Mapping):
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "MaybeSheet lifecycle response requires one receipt",
            {},
        )
    try:
        return receipt_type.from_wire(response["receipt"])
    except (TypeError, ValueError) as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "MaybeSheet lifecycle receipt is invalid",
            {},
        ) from exc


def _jsonl(document: Mapping) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


__all__ = [
    "MaybeSheetManagedTemporalStore",
    "MaybeSheetTemporalExecutor",
    "probe_temporal_capabilities",
]
