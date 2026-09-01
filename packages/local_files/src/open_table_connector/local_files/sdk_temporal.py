"""SDK adapter for temporal reads over captured local CSV files."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import polars as pl
import pyarrow as pa
from open_table_connector.contract import (
    PROVIDER_CSV,
    SCHEME_FILE,
    SCHEME_MANAGED_CSV,
    ConnectorError,
    ConnectorErrorCode,
    ResolveContext,
    TableURI,
)
from open_table_connector.sdk.connector import ArrowTableCarrier
from open_table_connector.sdk.model import (
    BaseModeTableAddress,
    DirectTableAddress,
    SheetModeTableAddress,
    TableMode,
)
from open_table_connector.sdk.result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    Outcome,
    Receipt,
    VerificationState,
)
from open_table_connector.sdk.table import CapabilitySet, TableBinding, TableInspection
from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ManagedAbortRequest,
    ManagedCommitRequest,
    ManagedReadbackRequest,
    ManagedStageRequest,
    ResourceBounds,
    TemporalExecutionRequest,
    TemporalExecutionResult,
    TemporalExtensionError,
    TemporalTableDescriptor,
    temporal_descriptor_hash,
)

from .temporal_csv import CsvManagedTemporalStore, CsvTemporalExecutor, _decode_csv

_DEFAULT_BOUNDS = ResourceBounds(
    max_rows=100_000,
    max_bytes=128 * 1024 * 1024,
    max_duration_ms=30_000,
)


def _receipt(receipt: Any) -> Receipt:
    return Receipt(
        kind="physical",
        operation=receipt.capability.capability_id,
        connector_id=receipt.connector.connector_id,
        capability=receipt.capability.to_reference(),
        safe_target=receipt.safe_uri,
        mode=receipt.mode.value,
        details={
            "operation_id": receipt.operation_id,
            "source_revision": receipt.source_revision,
            "schema_fingerprint": receipt.schema_fingerprint,
            "content_fingerprint": receipt.content_fingerprint,
            "row_count": receipt.row_count,
            "batch_count": receipt.batch_count,
        },
    )


def _success(value: Any, *, receipt: Any | None = None, commit: CommitState) -> OperationResult:
    return OperationResult(
        value=value,
        outcome=Outcome.SUCCEEDED,
        commit=commit,
        verification=VerificationState.PASSED,
        receipts=() if receipt is None else (_receipt(receipt),),
    )


def _failure(error: BaseException, *, connector_id: str) -> OperationResult:
    if isinstance(error, ConnectorError):
        code = (
            ErrorCode.UNSUPPORTED_CAPABILITY
            if error.code is ConnectorErrorCode.UNSUPPORTED_CAPABILITY
            else ErrorCode.EXECUTION_FAILED
        )
        message = error.message
        details = dict(error.safe_details)
    else:
        code = ErrorCode.EXECUTION_FAILED
        message = str(error)
        details = {}
    return OperationResult(
        value=None,
        outcome=Outcome.REJECTED,
        commit=CommitState.NOT_STARTED,
        verification=VerificationState.SKIPPED,
        receipts=(),
        error=ErrorInfo(
            code=code, message=message, safe_details={**details, "connector_id": connector_id}
        ),
    )


def _as_file_uri(address: object) -> TableURI:
    if isinstance(address, DirectTableAddress):
        return address.uri
    if isinstance(address, str):
        parsed = urlsplit(address)
        if parsed.scheme:
            return TableURI(address)
        return TableURI(Path(address).absolute().as_uri())
    if isinstance(address, (BaseModeTableAddress, SheetModeTableAddress)):
        return address.container if isinstance(address, BaseModeTableAddress) else address.grid
    raise ValueError("local-files SDK addresses require a direct file endpoint")


def _csv_uri(path: Path) -> TableURI:
    return TableURI(path.absolute().as_uri().replace(f"{SCHEME_FILE}://", f"{PROVIDER_CSV}://", 1))


def _managed_uri(path: Path) -> TableURI:
    return TableURI(
        path.absolute().as_uri().replace(f"{SCHEME_FILE}://", f"{SCHEME_MANAGED_CSV}://", 1)
    )


def _artifact(root: Path, frame: pl.DataFrame) -> ArrowArtifactReference:
    root = root.absolute()
    directory = root / "sha256"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    directory.chmod(0o700)
    sink = pa.BufferOutputStream()
    table = frame.to_arrow()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    data = sink.getvalue().to_pybytes()
    digest = hashlib.sha256(data).hexdigest()
    destination = directory / f"{digest}.arrow"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{digest}.", dir=directory)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return ArrowArtifactReference(f"sha256/{digest}.arrow", f"sha256:{digest}", len(data))


class LocalFilesSdkTemporalExtension:
    """Temporal extension using OTC's CSV executor and managed store."""

    def __init__(
        self, connector: Any, binding: TableBinding, descriptor: TemporalTableDescriptor
    ) -> None:
        if binding.connector_id != connector.identity.connector_id:
            raise ValueError("local-files temporal binding belongs to another connector")
        resource = connector.resolve(binding.uri, ResolveContext()).resource
        if resource.format.value != "csv":
            raise ValueError("local-files temporal SDK supports CSV sources only")
        self._connector = connector
        self._binding = binding
        self._descriptor = descriptor
        self._source_uri = binding.uri
        self._path = Path(resource.path)
        self._csv_uri = _csv_uri(self._path)
        self._managed_uri = _managed_uri(self._path)
        self._artifact_root = self._path.with_name(self._path.name + ".otc-sdk-artifacts")
        self._store: CsvManagedTemporalStore | None = None

    def descriptor_hash_for(
        self, binding: TableBinding, descriptor: TemporalTableDescriptor
    ) -> str:
        del binding
        return temporal_descriptor_hash(
            descriptor, _decode_csv(self._path.read_bytes(), descriptor).schema
        )

    def executor_for(self, binding: TableBinding, descriptor: TemporalTableDescriptor) -> Any:
        self._assert_binding(binding, descriptor)
        executor = CsvTemporalExecutor(descriptor, self._managed_store(descriptor))
        return _CsvSdkExecutor(executor, self._csv_uri, self._managed_uri)

    def append_rows(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        frame: pl.DataFrame,
        *,
        idempotency_key: str,
    ) -> OperationResult[int]:
        del binding, descriptor, frame, idempotency_key
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "local-file temporal append is not supported",
                {},
            ),
            connector_id=self._connector.identity.connector_id,
        )

    def upsert_rows(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        frame: pl.DataFrame,
        *,
        idempotency_key: str,
    ) -> OperationResult[int]:
        return self.append_rows(binding, descriptor, frame, idempotency_key=idempotency_key)

    def stage_rows(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        frame: pl.DataFrame,
        *,
        idempotency_key: str,
    ):
        self._assert_binding(binding, descriptor)
        return self._managed_store(descriptor).stage(
            ManagedStageRequest(
                operation_id=f"sdk-stage-{idempotency_key}",
                artifact=_artifact(self._artifact_root, frame),
                descriptor_hash=self.descriptor_hash_for(binding, descriptor),
                logical_target=self._managed_uri,
                physical_target=self._csv_uri,
                idempotency_key=idempotency_key,
                resource_bounds=_DEFAULT_BOUNDS,
            )
        )

    def commit_stage(self, binding: TableBinding, descriptor: TemporalTableDescriptor, stage: Any):
        self._assert_binding(binding, descriptor)
        return self._managed_store(descriptor).commit(
            ManagedCommitRequest(
                operation_id=f"sdk-commit-{stage.stage_id}",
                logical_target=self._managed_uri,
                stage_id=stage.stage_id,
                idempotency_key=stage.idempotency_key,
                resource_bounds=_DEFAULT_BOUNDS,
            )
        )

    def readback_snapshot(
        self, binding: TableBinding, descriptor: TemporalTableDescriptor, snapshot: Any
    ):
        self._assert_binding(binding, descriptor)
        return self._managed_store(descriptor).readback(
            ManagedReadbackRequest(
                operation_id=f"sdk-readback-{snapshot.snapshot_id}",
                logical_target=self._managed_uri,
                snapshot_id=snapshot.snapshot_id,
                snapshot_reference=snapshot.snapshot_reference,
                resource_bounds=_DEFAULT_BOUNDS,
            )
        )

    def current_snapshot(self, binding: TableBinding, descriptor: TemporalTableDescriptor) -> None:
        self._assert_binding(binding, descriptor)
        raise TemporalExtensionError(
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            "local-file temporal current recovery is not supported",
            {},
        )

    def abort_stage(self, binding: TableBinding, descriptor: TemporalTableDescriptor, stage: Any):
        self._assert_binding(binding, descriptor)
        return self._managed_store(descriptor).abort(
            ManagedAbortRequest(
                operation_id=f"sdk-abort-{stage.stage_id}",
                logical_target=self._managed_uri,
                stage_id=stage.stage_id,
            )
        )

    def _managed_store(self, descriptor: TemporalTableDescriptor) -> CsvManagedTemporalStore:
        if self._store is None:
            self._store = CsvManagedTemporalStore(self._artifact_root, descriptor)
        elif self._store.descriptor != descriptor:
            raise ValueError("local-file temporal extension descriptor changed")
        return self._store

    def _assert_binding(self, binding: TableBinding, descriptor: TemporalTableDescriptor) -> None:
        if binding != self._binding or descriptor != self._descriptor:
            raise ValueError("local-file temporal extension binding or descriptor changed")


class _CsvSdkExecutor:
    def __init__(
        self, executor: CsvTemporalExecutor, source_uri: TableURI, managed_uri: TableURI
    ) -> None:
        self._executor = executor
        self._source_uri = source_uri
        self._managed_uri = managed_uri

    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult:
        target = self._managed_uri if request.snapshot_reference is not None else self._source_uri
        return self._executor.execute(replace(request, target=target))


class LocalFilesSdkConnectorMixin:
    """SDK TableConnector methods for the local-files compatibility facade."""

    def open_table(self, address: object) -> OperationResult[TableBinding]:
        try:
            uri = _as_file_uri(address)
            result = self.read_arrow(self._sdk_read_request(uri))
            mode = (
                TableMode.SHEET_MODE
                if result.receipt.mode.value == "sheet"
                else TableMode.BASE_MODE
            )
            return _success(
                TableBinding(
                    uri=result.receipt.safe_uri,
                    mode=mode,
                    schema=pl.from_arrow(result.table).schema,
                    observed_revision=result.receipt.source_revision,
                    connector_id=self.identity.connector_id,
                ),
                receipt=result.receipt,
                commit=CommitState.NOT_APPLICABLE,
            )
        except BaseException as error:
            return _failure(error, connector_id=self.identity.connector_id)

    def inspect_table(self, binding: TableBinding) -> OperationResult[TableInspection]:
        try:
            result = self.read_table(binding)
            frame = result.require_value().to_polars()
            return _success(
                TableInspection(
                    uri=binding.uri,
                    mode=binding.mode,
                    schema=frame.schema,
                    row_count=frame.height,
                    observed_revision=binding.observed_revision,
                ),
                commit=CommitState.NOT_APPLICABLE,
            )
        except BaseException as error:
            return _failure(error, connector_id=self.identity.connector_id)

    def capabilities_for(self, binding: TableBinding) -> OperationResult[CapabilitySet]:
        return _success(
            CapabilitySet(
                capability_ids=tuple(item.capability_id for item in self.capabilities),
                modes=(TableMode.SHEET_MODE,),
            ),
            commit=CommitState.NOT_APPLICABLE,
        )

    def read_table(
        self, binding: TableBinding, *, limit: int | None = None, continuation: str | None = None
    ) -> OperationResult[ArrowTableCarrier]:
        if continuation is not None:
            return _failure(
                ValueError("local-files SDK reads do not support continuation tokens"),
                connector_id=self.identity.connector_id,
            )
        try:
            result = self.read_arrow(self._sdk_read_request(binding.uri, limit=limit))
            return _success(
                ArrowTableCarrier(result.table),
                receipt=result.receipt,
                commit=CommitState.NOT_APPLICABLE,
            )
        except BaseException as error:
            return _failure(error, connector_id=self.identity.connector_id)

    def insert_rows(self, binding: TableBinding, frame: pl.DataFrame) -> OperationResult[int]:
        del binding, frame
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "local-files SDK insert_rows is not implemented",
                {},
            ),
            connector_id=self.identity.connector_id,
        )

    def update_rows(
        self, binding: TableBinding, frame: pl.DataFrame, *, keys: tuple[str, ...]
    ) -> OperationResult[int]:
        del binding, frame, keys
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "local-files SDK update_rows is not implemented",
                {},
            ),
            connector_id=self.identity.connector_id,
        )

    def delete_rows(
        self, binding: TableBinding, *, where: Any, parameters: dict[str, Any] | None = None
    ) -> OperationResult[int]:
        del binding, where, parameters
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "local-files SDK delete_rows is not implemented",
                {},
            ),
            connector_id=self.identity.connector_id,
        )

    def drop_table(self, binding: TableBinding) -> OperationResult[None]:
        del binding
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "local-files SDK drop_table is not implemented",
                {},
            ),
            connector_id=self.identity.connector_id,
        )

    def begin_transaction(self, binding: TableBinding) -> Any:
        del binding
        raise RuntimeError("local-files SDK does not support transactions")

    def create_table(self, source: object, destination: object) -> OperationResult[TableBinding]:
        del source, destination
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "local-files SDK materialization is not implemented",
                {},
            ),
            connector_id=self.identity.connector_id,
        )

    def close(self) -> None:
        return None

    def temporal_extension_for(
        self, binding: TableBinding, descriptor: TemporalTableDescriptor
    ) -> LocalFilesSdkTemporalExtension:
        return LocalFilesSdkTemporalExtension(self, binding, descriptor)

    def _sdk_read_request(self, uri: TableURI, *, limit: int | None = None):
        from open_table_connector.contract import ResourceLimits

        from .local_files_connector import LocalReadOptions, LocalTableReadRequest

        return LocalTableReadRequest(
            uri,
            resource_limits=ResourceLimits(max_rows=limit),
            options=LocalReadOptions(),
        )


__all__ = ["LocalFilesSdkConnectorMixin", "LocalFilesSdkTemporalExtension"]
