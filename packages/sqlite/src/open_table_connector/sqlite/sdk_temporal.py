"""SDK adapter for the SQLite connector's temporal implementation.

The provider owns the physical SQLite and temporal implementations.  This
module only translates the public SDK values into the lower-level OTC
requests, keeping the SDK dependency at the provider integration boundary.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import polars as pl
import pyarrow as pa
from open_table_connector.contract import (
    ConnectorError,
    ConnectorErrorCode,
    ResolveContext,
    TableURI,
    TableWriteRequest,
)
from open_table_connector.sdk.connector import ArrowTableCarrier
from open_table_connector.sdk.model import (
    BaseModeDestination,
    BaseModeTableAddress,
    DatabaseTableAddress,
    DirectDestination,
    DirectTableAddress,
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
    ManagedCurrentRequest,
    ManagedReadbackRequest,
    ManagedStageRequest,
    ResourceBounds,
    TemporalTableDescriptor,
    temporal_descriptor_hash,
)

from .temporal import SQLiteManagedTemporalStore, SQLiteTemporalExecutor

_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?$")
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
        mapping = {
            ConnectorErrorCode.INVALID_URI: ErrorCode.INVALID_TARGET,
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY: ErrorCode.UNSUPPORTED_CAPABILITY,
            ConnectorErrorCode.CONFLICT: ErrorCode.KEY_CONFLICT,
            ConnectorErrorCode.TIMEOUT: ErrorCode.TIMEOUT,
            ConnectorErrorCode.CANCELLED: ErrorCode.CANCELLED,
            ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED: ErrorCode.RESOURCE_LIMIT,
            ConnectorErrorCode.SNAPSHOT_UNAVAILABLE: ErrorCode.SNAPSHOT_UNAVAILABLE,
        }
        code = mapping.get(error.code, ErrorCode.EXECUTION_FAILED)
        details = dict(error.safe_details)
        message = error.message
    else:
        code = ErrorCode.EXECUTION_FAILED
        details = {}
        message = str(error)
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


def _table_uri(database: TableURI, table_name: str) -> TableURI:
    parsed = urlsplit(database.value)
    return TableURI(
        urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.query,
                urlencode({"table": table_name}),
            )
        )
    )


def _database_uri(binding: TableBinding) -> TableURI:
    parsed = urlsplit(binding.uri.value)
    return TableURI(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")))


def _table_name(uri: TableURI) -> str:
    values = parse_qs(urlsplit(uri.value).fragment, keep_blank_values=True)
    names = values.get("table", [])
    if len(names) != 1 or not _TABLE_RE.fullmatch(names[0]):
        raise ValueError("SQLite SDK table URI must contain one valid table fragment")
    return names[0]


def _address(address: object) -> tuple[TableURI, str]:
    if isinstance(address, DatabaseTableAddress):
        if address.name.catalog is not None:
            raise ValueError("SQLite SDK addresses do not support catalogs")
        name = address.name.table
        if address.name.schema is not None:
            name = f"{address.name.schema}.{name}"
        return address.database, name
    if isinstance(address, BaseModeTableAddress):
        return address.container, address.table_id
    if isinstance(address, DirectTableAddress):
        return _database_uri_from_direct(address.uri), _table_name(address.uri)
    if isinstance(address, str):
        uri = TableURI(address)
        return _database_uri_from_direct(uri), _table_name(uri)
    raise ValueError("SQLite SDK addresses require a database and table name")


def _database_uri_from_direct(uri: TableURI) -> TableURI:
    parsed = urlsplit(uri.value)
    return TableURI(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")))


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
    return ArrowArtifactReference(
        relative_path=f"sha256/{digest}.arrow",
        sha256=f"sha256:{digest}",
        size_bytes=len(data),
    )


class SQLiteSdkTemporalExtension:
    """SDK-shaped facade over SQLite's existing temporal implementations."""

    def __init__(
        self, connector: Any, binding: TableBinding, descriptor: TemporalTableDescriptor
    ) -> None:
        if binding.connector_id != connector.identity.connector_id:
            raise ValueError("SQLite temporal binding belongs to another connector")
        self._connector = connector
        self._binding = binding
        self._descriptor = descriptor
        self._database_uri = _database_uri(binding)
        self._table_name = _table_name(binding.uri)
        database_path = connector.resolve(self._database_uri, ResolveContext()).resource.path
        self._artifact_root = (
            Path(database_path)
            .absolute()
            .with_name(Path(database_path).name + ".otc-sdk-artifacts")
        )
        self._store: SQLiteManagedTemporalStore | None = None

    def descriptor_hash_for(
        self, binding: TableBinding, descriptor: TemporalTableDescriptor
    ) -> str:
        schema = pl.DataFrame(schema=binding.schema).select(list(descriptor.declared_fields)).to_arrow().schema
        return temporal_descriptor_hash(
            descriptor, schema
        )

    def executor_for(
        self, binding: TableBinding, descriptor: TemporalTableDescriptor
    ) -> SQLiteTemporalExecutor:
        self._assert_binding(binding, descriptor)
        return SQLiteTemporalExecutor(
            descriptor,
            self._table_name,
            managed_store=self._managed_store(descriptor),
            connection_factory=self._connector._connection_factory,
        )

    def append_rows(
        self,
        binding: TableBinding,
        descriptor: TemporalTableDescriptor,
        frame: pl.DataFrame,
        *,
        idempotency_key: str,
    ) -> OperationResult[int]:
        self._assert_binding(binding, descriptor)
        try:
            result = self._connector.write(
                TableWriteRequest(
                    self._database_uri, frame, if_exists="append", table=self._table_name
                )
            )
        except BaseException as error:
            return _failure(error, connector_id=self._connector.identity.connector_id)
        return _success(result.affected_rows, receipt=result.receipt, commit=CommitState.COMMITTED)

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
        artifact = _artifact(self._artifact_root, frame)
        return self._managed_store(descriptor).stage(
            ManagedStageRequest(
                operation_id=f"sdk-stage-{idempotency_key}",
                artifact=artifact,
                descriptor_hash=temporal_descriptor_hash(
                    descriptor, frame.select(list(descriptor.declared_fields)).to_arrow().schema
                ),
                logical_target=self._database_uri,
                physical_target=self._database_uri,
                idempotency_key=idempotency_key,
                resource_bounds=_DEFAULT_BOUNDS,
            )
        )

    def commit_stage(self, binding: TableBinding, descriptor: TemporalTableDescriptor, stage: Any):
        self._assert_binding(binding, descriptor)
        return self._managed_store(descriptor).commit(
            ManagedCommitRequest(
                operation_id=f"sdk-commit-{stage.stage_id}",
                logical_target=self._database_uri,
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
                logical_target=self._database_uri,
                snapshot_id=snapshot.snapshot_id,
                snapshot_reference=snapshot.snapshot_reference,
                resource_bounds=_DEFAULT_BOUNDS,
            )
        )

    def current_snapshot(
        self, binding: TableBinding, descriptor: TemporalTableDescriptor
    ):
        self._assert_binding(binding, descriptor)
        return self._managed_store(descriptor).current(
            ManagedCurrentRequest(
                logical_target=self._database_uri,
                descriptor_hash=self.descriptor_hash_for(binding, descriptor),
            )
        )

    def abort_stage(self, binding: TableBinding, descriptor: TemporalTableDescriptor, stage: Any):
        self._assert_binding(binding, descriptor)
        return self._managed_store(descriptor).abort(
            ManagedAbortRequest(
                operation_id=f"sdk-abort-{stage.stage_id}",
                logical_target=self._database_uri,
                stage_id=stage.stage_id,
            )
        )

    def _managed_store(self, descriptor: TemporalTableDescriptor) -> SQLiteManagedTemporalStore:
        if self._store is None:
            self._store = SQLiteManagedTemporalStore(
                self._database_uri,
                self._artifact_root,
                descriptor,
                connection_factory=self._connector._connection_factory,
            )
        elif self._store.descriptor != descriptor:
            raise ValueError("SQLite temporal extension descriptor changed")
        return self._store

    def _assert_binding(self, binding: TableBinding, descriptor: TemporalTableDescriptor) -> None:
        if binding != self._binding or descriptor != self._descriptor:
            raise ValueError("SQLite temporal extension binding or descriptor changed")


class SQLiteSdkConnectorMixin:
    """SDK TableConnector methods shared by the concrete SQLite connector."""

    def open_table(self, address: object) -> OperationResult[TableBinding]:
        try:
            database, name = _address(address)
            result = self.read_arrow(self._sdk_read_request(database, name))
            binding = TableBinding(
                uri=_table_uri(database, name),
                mode=TableMode.BASE_MODE,
                schema=pl.from_arrow(result.table).schema,
                observed_revision=result.receipt.source_revision,
                connector_id=self.identity.connector_id,
            )
            return _success(binding, receipt=result.receipt, commit=CommitState.NOT_APPLICABLE)
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
                modes=(TableMode.BASE_MODE,),
            ),
            commit=CommitState.NOT_APPLICABLE,
        )

    def read_table(
        self, binding: TableBinding, *, limit: int | None = None, continuation: str | None = None
    ) -> OperationResult[ArrowTableCarrier]:
        if continuation is not None:
            return _failure(
                ValueError("SQLite SDK reads do not support continuation tokens"),
                connector_id=self.identity.connector_id,
            )
        try:
            database = _database_uri(binding)
            result = self.read_arrow(
                self._sdk_read_request(database, _table_name(binding.uri), limit=limit)
            )
            return _success(
                ArrowTableCarrier(result.table),
                receipt=result.receipt,
                commit=CommitState.NOT_APPLICABLE,
            )
        except BaseException as error:
            return _failure(error, connector_id=self.identity.connector_id)

    def insert_rows(self, binding: TableBinding, frame: pl.DataFrame) -> OperationResult[int]:
        return self._write_rows(binding, frame, if_exists="append")

    def update_rows(
        self, binding: TableBinding, frame: pl.DataFrame, *, keys: tuple[str, ...]
    ) -> OperationResult[int]:
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "SQLite SDK update_rows is not implemented",
                {},
            ),
            connector_id=self.identity.connector_id,
        )

    def delete_rows(
        self, binding: TableBinding, *, where: Any, parameters: dict[str, Any] | None = None
    ) -> OperationResult[int]:
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "SQLite SDK delete_rows is not implemented",
                {},
            ),
            connector_id=self.identity.connector_id,
        )

    def drop_table(self, binding: TableBinding) -> OperationResult[None]:
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "SQLite SDK drop_table is not implemented",
                {},
            ),
            connector_id=self.identity.connector_id,
        )

    def begin_transaction(self, binding: TableBinding) -> Any:
        return _SdkSQLiteTransaction(self, binding)

    def create_table(self, source: object, destination: object) -> OperationResult[TableBinding]:
        if not isinstance(source, pl.DataFrame):
            return _failure(
                ValueError("SQLite SDK materialization requires a Polars DataFrame"),
                connector_id=self.identity.connector_id,
            )
        try:
            if isinstance(destination, BaseModeDestination):
                database, name = destination.container, destination.table_name
            elif isinstance(destination, DirectDestination):
                database, name = _address(DirectTableAddress(destination.uri))
            else:
                raise ValueError("SQLite SDK materialization requires a base-mode destination")
            result = self.write(TableWriteRequest(database, source, table=name, if_exists="error"))
            return _success(
                TableBinding(
                    uri=_table_uri(database, name),
                    mode=TableMode.BASE_MODE,
                    schema=source.schema,
                    observed_revision=result.receipt.source_revision,
                    connector_id=self.identity.connector_id,
                ),
                receipt=result.receipt,
                commit=CommitState.COMMITTED,
            )
        except BaseException as error:
            return _failure(error, connector_id=self.identity.connector_id)

    def close(self) -> None:
        return None

    def temporal_extension_for(
        self, binding: TableBinding, descriptor: TemporalTableDescriptor
    ) -> SQLiteSdkTemporalExtension:
        return SQLiteSdkTemporalExtension(self, binding, descriptor)

    def _sdk_read_request(self, database: TableURI, name: str, *, limit: int | None = None):
        from open_table_connector.contract import ResourceLimits

        from .reader import SQLiteReadOptions, SQLiteTableReadRequest

        return SQLiteTableReadRequest(
            database,
            resource_limits=ResourceLimits(max_rows=limit),
            options=SQLiteReadOptions(table=name),
        )

    def _write_rows(
        self, binding: TableBinding, frame: pl.DataFrame, *, if_exists: str
    ) -> OperationResult[int]:
        try:
            result = self.write(
                TableWriteRequest(
                    _database_uri(binding),
                    frame,
                    if_exists=if_exists,
                    table=_table_name(binding.uri),
                )
            )
            return _success(
                result.affected_rows, receipt=result.receipt, commit=CommitState.COMMITTED
            )
        except BaseException as error:
            return _failure(error, connector_id=self.identity.connector_id)


class _SdkSQLiteTransaction:
    def __init__(self, connector: Any, binding: TableBinding) -> None:
        self._connector = connector
        self._binding = binding
        self._transaction = connector.begin_for(_database_uri(binding))
        self._closed = False

    def insert(self, frame: pl.DataFrame) -> OperationResult[int]:
        try:
            result = self._transaction.write(
                TableWriteRequest(
                    _database_uri(self._binding),
                    frame,
                    if_exists="append",
                    table=_table_name(self._binding.uri),
                )
            )
            return _success(
                result.affected_rows, receipt=result.receipt, commit=CommitState.NOT_APPLICABLE
            )
        except BaseException as error:
            return _failure(error, connector_id=self._connector.identity.connector_id)

    def update(self, frame: pl.DataFrame, *, keys: tuple[str, ...]) -> OperationResult[int]:
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "SQLite SDK transaction update is not implemented",
                {},
            ),
            connector_id=self._connector.identity.connector_id,
        )

    def delete(
        self, *, where: Any, parameters: dict[str, Any] | None = None
    ) -> OperationResult[int]:
        return _failure(
            ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "SQLite SDK transaction delete is not implemented",
                {},
            ),
            connector_id=self._connector.identity.connector_id,
        )

    def commit(self) -> OperationResult[None]:
        self._transaction.commit()
        self._closed = True
        return _success(None, commit=CommitState.COMMITTED)

    def abort(self) -> OperationResult[None]:
        self._transaction.abort()
        self._closed = True
        return _success(None, commit=CommitState.NOT_APPLICABLE)


__all__ = ["SQLiteSdkConnectorMixin", "SQLiteSdkTemporalExtension"]
