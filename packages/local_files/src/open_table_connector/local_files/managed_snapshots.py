"""Crash-safe managed snapshot lifecycle shared by local formats."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Iterator, Mapping
from urllib.parse import parse_qsl, unquote, urlsplit
import uuid

import pyarrow as pa

from open_table_connector.contract import TableURI
from open_table_connector.timeseries import (
    AbortDisposition,
    ManagedAbortReceipt,
    ManagedAbortRequest,
    ManagedCommitReceipt,
    ManagedCommitRequest,
    ManagedReadbackReceipt,
    ManagedReadbackRequest,
    ManagedReadbackResult,
    ManagedStageReceipt,
    ManagedStageRequest,
    ResourceBounds,
    TemporalErrorCode,
    TemporalExtensionError,
    TemporalTableDescriptor,
    TimeRange,
    VisibilityGuarantee,
    temporal_descriptor_hash,
    validate_stage_retry,
)


_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REFERENCE_RE = re.compile(r"^snapshots/([0-9a-f]{64})\.([a-z0-9]+)$")
_SAFE_FILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_POINTER_FIELDS = {
    "schema_version",
    "logical_target",
    "stage_id",
    "idempotency_key",
    "descriptor_hash",
    "snapshot_id",
    "snapshot_reference",
    "committed_at",
}


def _check_deadline(started_ns: int, bounds: ResourceBounds) -> None:
    elapsed_ms = (time.monotonic_ns() - started_ns) // 1_000_000
    if elapsed_ms > bounds.max_duration_ms:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            "managed operation exceeded max_duration_ms",
            {"elapsed_ms": elapsed_ms},
        )


class ManagedSnapshotStore:
    """Own atomic publication while delegating only physical format encoding."""

    def __init__(
        self,
        artifact_root: str | os.PathLike[str],
        descriptor: TemporalTableDescriptor,
        *,
        target_scheme: str,
        extension: str,
        encode_snapshot: Callable[[pa.Table], bytes],
        decode_snapshot: Callable[[bytes], pa.Table],
        target_fragment: tuple[str, str] | None = None,
        physical_target_validator: Callable[[TableURI], None] | None = None,
        clock: Callable[[], datetime | float] | None = None,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.artifact_root = Path(artifact_root).absolute()
        self.artifact_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.artifact_root.is_symlink():
            raise PermissionError("artifact root cannot be a symlink")
        if not isinstance(descriptor, TemporalTableDescriptor):
            raise TypeError("descriptor must be a TemporalTableDescriptor")
        if not re.fullmatch(r"[a-z][a-z0-9+.-]*", target_scheme):
            raise ValueError("target_scheme is invalid")
        if not re.fullmatch(r"[a-z0-9]+", extension):
            raise ValueError("extension is invalid")
        self.descriptor = descriptor
        self.target_scheme = target_scheme
        self.extension = extension
        self._encode_snapshot = encode_snapshot
        self._decode_snapshot = decode_snapshot
        self._target_fragment = target_fragment
        self._physical_target_validator = physical_target_validator
        self._clock = clock or (lambda: datetime.now(UTC))
        self._fault_injector = fault_injector

    def stage_artifact(self, request: ManagedStageRequest) -> ManagedStageReceipt:
        if not isinstance(request, ManagedStageRequest):
            raise TypeError("request must be a ManagedStageRequest")
        started = time.monotonic_ns()
        if request.artifact.size_bytes > request.resource_bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "stage artifact exceeds max_bytes",
                {"bytes": request.artifact.size_bytes},
            )
        if self._physical_target_validator is not None:
            self._physical_target_validator(request.physical_target)
        layout = self._layout(request.logical_target, create=True)
        if self._physical_target_validator is None:
            self._layout(request.physical_target, create=False)
        with self._locked(layout):
            self._recover_unlocked(layout)
            existing = self._stage_by_idempotency(layout, request.idempotency_key)
            if existing is not None:
                return validate_stage_retry(existing, request)
            artifact_bytes, table = self._read_artifact(request)
            if table.num_rows > request.resource_bounds.max_rows:
                raise TemporalExtensionError(
                    TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                    "stage artifact exceeds max_rows",
                    {"rows": table.num_rows},
                )
            _check_deadline(started, request.resource_bounds)
            actual_descriptor = temporal_descriptor_hash(self.descriptor, table.schema)
            if actual_descriptor != request.descriptor_hash:
                raise TemporalExtensionError(
                    TemporalErrorCode.PROTOCOL_INVALID,
                    "staged artifact schema does not match descriptor_hash",
                    {"descriptor_hash": request.descriptor_hash},
                )
            stage_digest = _sha256(
                _canonical_json(
                    {
                        "logical_target": request.logical_target.value,
                        "physical_target": request.physical_target.value,
                        "artifact_hash": request.artifact.sha256,
                        "descriptor_hash": request.descriptor_hash,
                        "idempotency_key": request.idempotency_key,
                    }
                )
            )[7:]
            stage_id = f"stage:{stage_digest}"
            stage_path = layout / "stages" / f"{stage_digest}.arrow"
            self._write_content_once(stage_path, artifact_bytes)
            receipt = ManagedStageReceipt(
                schema_version="otc.managed-stage-receipt/v1",
                operation_id=request.operation_id,
                logical_target=request.logical_target,
                physical_target=request.physical_target,
                stage_id=stage_id,
                idempotency_key=request.idempotency_key,
                artifact_hash=request.artifact.sha256,
                descriptor_hash=request.descriptor_hash,
                staged_at=self._now(),
                visible=False,
            )
            self._write_receipt(layout, receipt.operation_id, receipt.to_wire())
            return receipt

    def publish_snapshot(self, request: ManagedCommitRequest) -> ManagedCommitReceipt:
        if not isinstance(request, ManagedCommitRequest):
            raise TypeError("request must be a ManagedCommitRequest")
        started = time.monotonic_ns()
        layout = self._layout(request.logical_target, create=True)
        with self._locked(layout):
            self._recover_unlocked(layout)
            existing = self._commit_by_idempotency(layout, request.idempotency_key)
            if existing is not None:
                self._validate_commit_retry(existing, request)
                return existing
            pointer = self._read_pointer(layout, required=False)
            if pointer is not None and pointer["idempotency_key"] == request.idempotency_key:
                if (
                    pointer["stage_id"] != request.stage_id
                    or pointer["logical_target"] != request.logical_target.value
                ):
                    raise TemporalExtensionError(
                        TemporalErrorCode.IDEMPOTENCY_CONFLICT,
                        "commit idempotency key is bound to another stage",
                        {"idempotency_key": request.idempotency_key},
                    )
                reconciled = self._commit_receipt(request, pointer)
                self._write_receipt(layout, request.operation_id, reconciled.to_wire())
                return reconciled
            stage = self._stage_by_id(layout, request.stage_id)
            if stage is None:
                raise TemporalExtensionError(
                    TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                    "managed stage is unavailable",
                    {"stage_id": request.stage_id},
                )
            if (
                stage.logical_target != request.logical_target
                or stage.idempotency_key != request.idempotency_key
            ):
                raise TemporalExtensionError(
                    TemporalErrorCode.IDEMPOTENCY_CONFLICT,
                    "commit does not match the staged target and idempotency key",
                    {"stage_id": request.stage_id},
                )
            stage_path = layout / "stages" / f"{request.stage_id[6:]}.arrow"
            table = self._read_staged(stage_path, stage.artifact_hash)
            snapshot_bytes = self._encode_snapshot(table)
            if (
                table.num_rows > request.resource_bounds.max_rows
                or len(snapshot_bytes) > request.resource_bounds.max_bytes
            ):
                raise TemporalExtensionError(
                    TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                    "commit snapshot exceeds resource bounds",
                    {"rows": table.num_rows, "bytes": len(snapshot_bytes)},
                )
            _check_deadline(started, request.resource_bounds)
            snapshot_id = _sha256(snapshot_bytes)
            snapshot_reference = f"snapshots/{snapshot_id[7:]}.{self.extension}"
            snapshot_path = layout / snapshot_reference
            self._write_content_once(snapshot_path, snapshot_bytes)
            committed_at = self._now()
            pointer = {
                "schema_version": "otc.managed-snapshot-pointer/v1",
                "logical_target": request.logical_target.value,
                "stage_id": request.stage_id,
                "idempotency_key": request.idempotency_key,
                "descriptor_hash": stage.descriptor_hash,
                "snapshot_id": snapshot_id,
                "snapshot_reference": snapshot_reference,
                "committed_at": committed_at,
            }
            temporary = self._write_temporary(
                layout / "current.json",
                _canonical_json(pointer) + b"\n",
            )
            self._inject("before_pointer_replace")
            os.replace(temporary, layout / "current.json")
            self._fsync_directory(layout)
            self._inject("after_pointer_replace")
            receipt = self._commit_receipt(request, pointer)
            self._write_receipt(layout, request.operation_id, receipt.to_wire())
            return receipt

    def resolve_snapshot(self, target: TableURI, snapshot_reference: str) -> Path:
        layout = self._layout(target, create=False)
        match = _REFERENCE_RE.fullmatch(snapshot_reference)
        if match is None or match.group(2) != self.extension:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "snapshot reference is invalid for this managed format",
                {},
            )
        path = layout / snapshot_reference
        try:
            metadata = path.lstat()
        except FileNotFoundError as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "snapshot is unavailable",
                {"snapshot_reference": snapshot_reference},
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PermissionError("snapshot cannot be a symlink")
        if not stat.S_ISREG(metadata.st_mode):
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "snapshot is not a regular file",
                {},
            )
        return path

    def read_snapshot(
        self,
        target: TableURI,
        snapshot_reference: str,
        bounds: ResourceBounds,
    ) -> pa.Table:
        started = time.monotonic_ns()
        path = self.resolve_snapshot(target, snapshot_reference)
        size = path.stat().st_size
        if size > bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "snapshot exceeds max_bytes",
                {"bytes": size, "max_bytes": bounds.max_bytes},
            )
        data = self._secure_read(path)
        if len(data) > bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "snapshot exceeds max_bytes",
                {"bytes": len(data), "max_bytes": bounds.max_bytes},
            )
        expected_hash = "sha256:" + _REFERENCE_RE.fullmatch(snapshot_reference).group(1)
        if _sha256(data) != expected_hash:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "snapshot content does not match its content-addressed reference",
                {"snapshot_reference": snapshot_reference},
            )
        table = self._decode_snapshot(data)
        if table.num_rows > bounds.max_rows:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "snapshot exceeds max_rows",
                {"rows": table.num_rows, "max_rows": bounds.max_rows},
            )
        _check_deadline(started, bounds)
        return table

    def readback_snapshot(self, request: ManagedReadbackRequest) -> ManagedReadbackResult:
        if not isinstance(request, ManagedReadbackRequest):
            raise TypeError("request must be a ManagedReadbackRequest")
        started = time.monotonic_ns()
        path = self.resolve_snapshot(request.logical_target, request.snapshot_reference)
        if path.stat().st_size > request.resource_bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "readback snapshot exceeds max_bytes",
                {"bytes": path.stat().st_size},
            )
        physical = self._secure_read(path)
        physical_hash = _sha256(physical)
        reference_hash = "sha256:" + _REFERENCE_RE.fullmatch(
            request.snapshot_reference
        ).group(1)
        if physical_hash != request.snapshot_id or physical_hash != reference_hash:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "snapshot content hash verification failed",
                {"snapshot_id": request.snapshot_id},
            )
        table = self.read_snapshot(
            request.logical_target,
            request.snapshot_reference,
            request.resource_bounds,
        )
        arrow = _arrow_bytes(table)
        if len(arrow) > request.resource_bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "readback Arrow result exceeds max_bytes",
                {"bytes": len(arrow)},
            )
        _check_deadline(started, request.resource_bounds)
        receipt = ManagedReadbackReceipt(
            schema_version="otc.managed-readback-receipt/v1",
            operation_id=request.operation_id,
            snapshot_id=request.snapshot_id,
            observed_at=self._now(),
            observed_schema_hash=_sha256(table.schema.serialize().to_pybytes()),
            observed_content_hash=_sha256(arrow),
            observed_rows=table.num_rows,
            observed_bytes=len(arrow),
            observed_range=self._observed_range(table),
        )
        layout = self._layout(request.logical_target, create=False)
        self._write_receipt(layout, request.operation_id, receipt.to_wire())
        return ManagedReadbackResult(table=table, artifact=None, receipt=receipt)

    def abort_stage(self, request: ManagedAbortRequest) -> ManagedAbortReceipt:
        if not isinstance(request, ManagedAbortRequest):
            raise TypeError("request must be a ManagedAbortRequest")
        layout = self._layout(request.logical_target, create=True)
        with self._locked(layout):
            if self._commit_by_stage(layout, request.stage_id) is not None:
                disposition = AbortDisposition.ALREADY_COMMITTED
            else:
                path = layout / "stages" / f"{request.stage_id[6:]}.arrow"
                try:
                    metadata = path.lstat()
                except FileNotFoundError:
                    disposition = AbortDisposition.ALREADY_ABSENT
                else:
                    if stat.S_ISLNK(metadata.st_mode):
                        raise PermissionError("managed stage cannot be a symlink")
                    path.unlink()
                    self._fsync_directory(path.parent)
                    disposition = AbortDisposition.REMOVED
            receipt = ManagedAbortReceipt(
                schema_version="otc.managed-abort-receipt/v1",
                operation_id=request.operation_id,
                logical_target=request.logical_target,
                stage_id=request.stage_id,
                disposition=disposition,
                aborted_at=self._now(),
            )
            self._write_receipt(layout, request.operation_id, receipt.to_wire())
            return receipt

    def recover(self, target: TableURI) -> None:
        layout = self._layout(target, create=True)
        with self._locked(layout):
            self._recover_unlocked(layout)

    def _layout(self, target: TableURI, *, create: bool) -> Path:
        if not isinstance(target, TableURI):
            raise TypeError("target must be a TableURI")
        parsed = urlsplit(target.value)
        decoded = unquote(parsed.path)
        path = Path(decoded)
        expected_fragment = self._target_fragment
        fragment_valid = (
            not parsed.fragment
            if expected_fragment is None
            else parse_qsl(parsed.fragment, keep_blank_values=True, strict_parsing=True)
            == [expected_fragment]
        )
        if (
            target.scheme != self.target_scheme
            or parsed.netloc not in {"", "localhost"}
            or parsed.query
            or not fragment_valid
            or not path.is_absolute()
            or ".." in path.parts
            or not path.name
        ):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                f"{self.target_scheme} target must be a clean absolute local namespace",
                {"scheme": target.scheme},
            )
        self._reject_symlink_components(path.parent)
        layout = path.with_name(f"{path.name}.otc")
        if layout.exists() and layout.is_symlink():
            raise PermissionError("managed namespace cannot be a symlink")
        if create:
            for directory in (
                layout,
                layout / "snapshots",
                layout / "stages",
                layout / "receipts",
            ):
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                if directory.is_symlink():
                    raise PermissionError("managed layout directory cannot be a symlink")
                directory.chmod(0o700)
        elif not layout.is_dir():
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "managed namespace is unavailable",
                {},
            )
        return layout

    @staticmethod
    def _reject_symlink_components(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise PermissionError("managed target path cannot traverse a symlink")

    @contextmanager
    def _locked(self, layout: Path) -> Iterator[None]:
        lock_path = layout / "commit.lock"
        if lock_path.is_symlink():
            raise PermissionError("managed commit lock cannot be a symlink")
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_artifact(self, request: ManagedStageRequest) -> tuple[bytes, pa.Table]:
        if request.artifact.size_bytes > request.resource_bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "stage artifact exceeds max_bytes",
                {"bytes": request.artifact.size_bytes},
            )
        expected = f"sha256/{request.artifact.sha256[7:]}.arrow"
        if request.artifact.relative_path != expected:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "artifact path is not canonical for its hash",
                {},
            )
        path = self.artifact_root / expected
        try:
            metadata = path.lstat()
        except FileNotFoundError as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "stage artifact is unavailable",
                {},
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PermissionError("stage artifact cannot be a symlink")
        self._verify_owner_and_mode(metadata, "stage artifact")
        if metadata.st_size != request.artifact.size_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "stage artifact size verification failed",
                {},
            )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            current = os.fstat(stream.fileno())
            if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise PermissionError("stage artifact changed during open")
            data = stream.read(request.artifact.size_bytes + 1)
        if len(data) != request.artifact.size_bytes or _sha256(data) != request.artifact.sha256:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "stage artifact hash verification failed",
                {},
            )
        try:
            table = pa.ipc.open_stream(pa.BufferReader(data)).read_all()
        except pa.ArrowInvalid as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "stage artifact is not an Arrow IPC stream",
                {},
            ) from exc
        return data, table

    @staticmethod
    def _read_staged(path: Path, expected_hash: str) -> pa.Table:
        try:
            metadata = path.lstat()
        except FileNotFoundError as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "managed stage bytes are unavailable",
                {},
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PermissionError("managed stage cannot be a symlink")
        data = ManagedSnapshotStore._secure_read(path)
        if _sha256(data) != expected_hash:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "managed stage hash verification failed",
                {},
            )
        return pa.ipc.open_stream(pa.BufferReader(data)).read_all()

    def _write_content_once(self, destination: Path, data: bytes) -> None:
        if destination.exists():
            if destination.is_symlink():
                raise PermissionError("managed content path cannot be a symlink")
            if destination.read_bytes() != data:
                raise TemporalExtensionError(
                    TemporalErrorCode.VISIBILITY_INCOMPLETE,
                    "content-addressed path contains different bytes",
                    {"path": destination.name},
                )
            return
        temporary = self._write_temporary(destination, data)
        os.replace(temporary, destination)
        self._fsync_directory(destination.parent)

    @staticmethod
    def _write_temporary(destination: Path, data: bytes) -> Path:
        temporary = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return temporary

    def _write_receipt(
        self,
        layout: Path,
        operation_id: str,
        document: Mapping[str, object],
    ) -> None:
        name = (
            operation_id
            if _SAFE_FILE_ID.fullmatch(operation_id)
            else "sha256-" + hashlib.sha256(operation_id.encode()).hexdigest()
        )
        destination = layout / "receipts" / f"{name}.json"
        data = _canonical_json(document) + b"\n"
        if destination.is_symlink():
            raise PermissionError("managed receipt cannot be a symlink")
        if destination.exists() and destination.read_bytes() == data:
            return
        temporary = self._write_temporary(destination, data)
        os.replace(temporary, destination)
        self._fsync_directory(destination.parent)

    def _receipt_documents(self, layout: Path) -> Iterator[dict[str, object]]:
        for path in sorted((layout / "receipts").glob("*.json")):
            if path.is_symlink():
                raise PermissionError("managed receipt cannot be a symlink")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise TemporalExtensionError(
                    TemporalErrorCode.VISIBILITY_INCOMPLETE,
                    "managed receipt is malformed",
                    {"receipt": path.name},
                ) from exc
            if not isinstance(value, dict):
                raise TemporalExtensionError(
                    TemporalErrorCode.VISIBILITY_INCOMPLETE,
                    "managed receipt is not an object",
                    {"receipt": path.name},
                )
            yield value

    def _stage_by_idempotency(
        self,
        layout: Path,
        idempotency_key: str,
    ) -> ManagedStageReceipt | None:
        for document in self._receipt_documents(layout):
            if (
                document.get("schema_version") == "otc.managed-stage-receipt/v1"
                and document.get("idempotency_key") == idempotency_key
            ):
                return ManagedStageReceipt.from_wire(document)
        return None

    def _stage_by_id(self, layout: Path, stage_id: str) -> ManagedStageReceipt | None:
        for document in self._receipt_documents(layout):
            if (
                document.get("schema_version") == "otc.managed-stage-receipt/v1"
                and document.get("stage_id") == stage_id
            ):
                return ManagedStageReceipt.from_wire(document)
        return None

    def _commit_by_idempotency(
        self,
        layout: Path,
        idempotency_key: str,
    ) -> ManagedCommitReceipt | None:
        for document in self._receipt_documents(layout):
            if (
                document.get("schema_version") == "otc.managed-commit-receipt/v1"
                and document.get("idempotency_key") == idempotency_key
            ):
                return ManagedCommitReceipt.from_wire(document)
        return None

    def _commit_by_stage(
        self,
        layout: Path,
        stage_id: str,
    ) -> ManagedCommitReceipt | None:
        for document in self._receipt_documents(layout):
            if (
                document.get("schema_version") == "otc.managed-commit-receipt/v1"
                and document.get("stage_id") == stage_id
            ):
                return ManagedCommitReceipt.from_wire(document)
        pointer = self._read_pointer(layout, required=False)
        if pointer is not None and pointer["stage_id"] == stage_id:
            request = ManagedCommitRequest(
                operation_id="reconciled-abort-check",
                logical_target=TableURI(pointer["logical_target"]),
                stage_id=pointer["stage_id"],
                idempotency_key=pointer["idempotency_key"],
                resource_bounds=ResourceBounds(1, 1, 1),
            )
            return self._commit_receipt(request, pointer)
        return None

    @staticmethod
    def _validate_commit_retry(
        existing: ManagedCommitReceipt,
        request: ManagedCommitRequest,
    ) -> None:
        if (
            existing.logical_target != request.logical_target
            or existing.stage_id != request.stage_id
            or existing.idempotency_key != request.idempotency_key
        ):
            raise TemporalExtensionError(
                TemporalErrorCode.IDEMPOTENCY_CONFLICT,
                "commit idempotency key is bound to another outcome",
                {"idempotency_key": request.idempotency_key},
            )

    @staticmethod
    def _commit_receipt(
        request: ManagedCommitRequest,
        pointer: Mapping[str, object],
    ) -> ManagedCommitReceipt:
        return ManagedCommitReceipt(
            schema_version="otc.managed-commit-receipt/v1",
            operation_id=request.operation_id,
            logical_target=request.logical_target,
            stage_id=request.stage_id,
            idempotency_key=request.idempotency_key,
            snapshot_id=pointer["snapshot_id"],
            snapshot_reference=pointer["snapshot_reference"],
            committed_at=pointer["committed_at"],
            visibility=VisibilityGuarantee.ATOMIC,
        )

    def _read_pointer(self, layout: Path, *, required: bool) -> dict[str, object] | None:
        path = layout / "current.json"
        if path.is_symlink():
            raise PermissionError("managed current pointer cannot be a symlink")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if not required:
                return None
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "managed current pointer is unavailable",
                {},
            ) from None
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.VISIBILITY_INCOMPLETE,
                "managed current pointer is malformed",
                {},
            ) from exc
        if not isinstance(document, dict) or set(document) != _POINTER_FIELDS:
            raise TemporalExtensionError(
                TemporalErrorCode.VISIBILITY_INCOMPLETE,
                "managed current pointer is not a closed v1 document",
                {},
            )
        if (
            document["schema_version"] != "otc.managed-snapshot-pointer/v1"
            or not isinstance(document["logical_target"], str)
            or not isinstance(document["stage_id"], str)
            or not isinstance(document["idempotency_key"], str)
            or not isinstance(document["descriptor_hash"], str)
            or not isinstance(document["snapshot_id"], str)
            or not isinstance(document["snapshot_reference"], str)
            or not isinstance(document["committed_at"], str)
            or _HASH_RE.fullmatch(document["snapshot_id"]) is None
        ):
            raise TemporalExtensionError(
                TemporalErrorCode.VISIBILITY_INCOMPLETE,
                "managed current pointer values are invalid",
                {},
            )
        return document

    def _recover_unlocked(self, layout: Path) -> None:
        for directory in (layout, layout / "snapshots", layout / "stages", layout / "receipts"):
            for path in directory.glob("*.tmp"):
                if path.is_symlink():
                    raise PermissionError("managed temporary path cannot be a symlink")
                path.unlink()

    def _observed_range(self, table: pa.Table) -> TimeRange | None:
        if table.num_rows == 0:
            return None
        values = table[self.descriptor.time_field]
        if values.null_count:
            raise TemporalExtensionError(
                TemporalErrorCode.VISIBILITY_INCOMPLETE,
                "readback event-time field contains null values",
                {},
            )
        if not pa.types.is_timestamp(values.type):
            raise TemporalExtensionError(
                TemporalErrorCode.VISIBILITY_INCOMPLETE,
                "readback event-time field is not a timestamp",
                {},
            )
        multiplier = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}[
            values.type.unit
        ]
        casted = [value * multiplier for value in values.cast(pa.int64()).to_pylist()]
        return TimeRange(_format_ns(min(casted)), _format_ns(max(casted)))

    def _now(self) -> str:
        value = self._clock()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = datetime.fromtimestamp(value, UTC)
        if not isinstance(value, datetime):
            raise TypeError("clock must return datetime or Unix seconds")
        if value.tzinfo is None:
            raise ValueError("clock datetime must be timezone-aware")
        utc = value.astimezone(UTC)
        return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond * 1000:09d}Z"

    def _inject(self, event: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(event)

    @staticmethod
    def _secure_read(path: Path) -> bytes:
        try:
            before = path.lstat()
        except FileNotFoundError as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "managed content is unavailable",
                {"path": path.name},
            ) from exc
        if stat.S_ISLNK(before.st_mode):
            raise PermissionError("managed content cannot be a symlink")
        ManagedSnapshotStore._verify_owner_and_mode(before, "managed content")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            current = os.fstat(stream.fileno())
            if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
                raise PermissionError("managed content changed during secure open")
            return stream.read()

    @staticmethod
    def _verify_owner_and_mode(metadata: os.stat_result, name: str) -> None:
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise PermissionError(f"{name} ownership is not trusted")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise PermissionError(f"{name} permissions are too broad")

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _arrow_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _format_ns(value: int) -> str:
    seconds, nanos = divmod(value, 1_000_000_000)
    whole = datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{whole}.{nanos:09d}Z"


__all__ = ["ManagedSnapshotStore"]
