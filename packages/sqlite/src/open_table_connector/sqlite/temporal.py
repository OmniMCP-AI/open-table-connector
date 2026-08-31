"""SQLite prepared lowering and temporal storage backends."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
from open_table_connector.contract import PROVIDER_SQLITE, TableURI
from open_table_connector.timeseries import (
    AbortDisposition,
    AggregateFunction,
    ArrowArtifactReference,
    AsOf,
    BucketAggregate,
    FixedBucket,
    GapFill,
    Latest,
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
    PortableTemporalPlan,
    PreparedTemporalQuery,
    ResourceBounds,
    ScanRange,
    TagOperator,
    TemporalErrorCode,
    TemporalExecutionRequest,
    TemporalExecutionResult,
    TemporalExtensionError,
    TemporalTableDescriptor,
    TimeRange,
    TimestampPrecision,
    VisibilityGuarantee,
    storage_to_timestamp,
    temporal_descriptor_hash,
    timestamp_to_storage,
    validate_stage_retry,
)

from .identity import CONNECTOR_IDENTITY

_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?$")
_SUPPORTED_AGGREGATES = {
    AggregateFunction.COUNT,
    AggregateFunction.MIN,
    AggregateFunction.MAX,
    AggregateFunction.SUM,
    AggregateFunction.AVG,
}


def lower_sqlite(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
    physical_table: str,
) -> PreparedTemporalQuery:
    if not isinstance(plan, PortableTemporalPlan):
        raise TypeError("plan must be a PortableTemporalPlan")
    if not isinstance(descriptor, TemporalTableDescriptor):
        raise TypeError("descriptor must be a TemporalTableDescriptor")
    if not isinstance(physical_table, str) or _TABLE_RE.fullmatch(physical_table) is None:
        raise ValueError("physical_table must be an authorized simple identifier")
    table = ".".join(_quote(part) for part in physical_table.split("."))
    operation = plan.operation
    if isinstance(operation, (BucketAggregate, GapFill)):
        if (
            isinstance(operation, BucketAggregate)
            and not isinstance(operation, GapFill)
            and isinstance(operation.bucket, FixedBucket)
            and all(measure.function in _SUPPORTED_AGGREGATES for measure in operation.measures)
        ):
            return _lower_fixed_aggregate(plan, descriptor, table)
        return _bounded_residual(plan, descriptor, table)
    if isinstance(operation, ScanRange):
        where, parameters = _where(operation, descriptor, numeric_time=False)
        statement = (
            f"SELECT {_columns(operation.projection)} FROM {table} "
            f"WHERE {where}{_order(plan)}"
        )
        return PreparedTemporalQuery(statement, parameters, None)
    if isinstance(operation, (Latest, AsOf)):
        where, parameters = _where(operation, descriptor, numeric_time=False)
        partition = (
            ", ".join(_quote(field) for field in descriptor.series_key_fields) or "1"
        )
        tie_order = [_quote(descriptor.time_field) + " DESC"]
        if descriptor.ingestion_time_field is not None:
            tie_order.append(_quote(descriptor.ingestion_time_field) + " DESC")
        projection = _columns(operation.projection)
        statement = (
            f"SELECT {projection} FROM (SELECT {projection}, "
            f"ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {', '.join(tie_order)}) "
            f"AS \"__otc_rank\" FROM {table} WHERE {where}) AS \"__otc_latest\" "
            f"WHERE \"__otc_rank\" = 1{_order(plan)}"
        )
        return PreparedTemporalQuery(statement, parameters, None)
    raise AssertionError("portable temporal operation union is closed")


def _bounded_residual(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
    table: str,
) -> PreparedTemporalQuery:
    operation = plan.operation
    fields = [*operation.group_by]
    fields.extend(
        measure.value_field for measure in operation.measures if measure.value_field is not None
    )
    fields.extend(descriptor.series_key_fields)
    fields.extend(predicate.field for predicate in operation.tag_predicates)
    fields.append(descriptor.time_field)
    if descriptor.ingestion_time_field is not None:
        fields.append(descriptor.ingestion_time_field)
    projection = tuple(dict.fromkeys(fields))
    where, parameters = _where(operation, descriptor, numeric_time=False)
    order_fields = [*descriptor.series_key_fields, descriptor.time_field]
    if descriptor.ingestion_time_field is not None:
        order_fields.append(descriptor.ingestion_time_field)
    order = ", ".join(_quote(field) + " ASC" for field in order_fields)
    statement = (
        f"SELECT {_columns(projection)} FROM {table} WHERE {where} ORDER BY {order}"
    )
    return PreparedTemporalQuery(statement, parameters, plan)


def _lower_fixed_aggregate(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
    table: str,
) -> PreparedTemporalQuery:
    operation = plan.operation
    bucket = operation.bucket
    nanos_per_unit = {TimestampPrecision.SECOND: 1_000_000_000, TimestampPrecision.MILLISECOND: 1_000_000, TimestampPrecision.MICROSECOND: 1_000, TimestampPrecision.NANOSECOND: 1}[descriptor.precision]
    origin = timestamp_to_storage(bucket.origin, descriptor.precision)
    width = bucket.width_ns // nanos_per_unit
    offset = bucket.offset_ns // nanos_per_unit
    delta = f"(CAST({_quote(descriptor.time_field)} AS INTEGER) - ? - ?)"
    quotient = f"(({delta} / ?) - CAST(({delta} < ? AND {delta} % ? != ?) AS INTEGER))"
    expression = f"({quotient} * ? + ? + ?)"
    select = [_quote(field) for field in operation.group_by]
    select.append(f"{expression} AS \"bucket\"")
    for measure in operation.measures:
        if measure.function is AggregateFunction.COUNT:
            aggregate = "COUNT(*)"
        else:
            aggregate = f"{measure.function.value.upper()}({_quote(measure.value_field)})"
        select.append(f"{aggregate} AS {_quote(measure.output_field)}")
    where, where_parameters = _where(operation, descriptor, numeric_time=True)
    groups = [*(_quote(field) for field in operation.group_by), '"bucket"']
    statement = (
        f"SELECT {', '.join(select)} FROM {table} WHERE {where} "
        f"GROUP BY {', '.join(groups)}{_order(plan)}"
    )
    parameters = (
        origin,
        offset,
        width,
        origin,
        offset,
        0,
        origin,
        offset,
        width,
        0,
        width,
        origin,
        offset,
        *where_parameters,
    )
    return PreparedTemporalQuery(statement, parameters, None)


def _where(operation, descriptor: TemporalTableDescriptor, *, numeric_time: bool):
    clauses: list[str] = []
    parameters: list[object] = []
    time = _quote(descriptor.time_field)
    if isinstance(operation, (ScanRange, BucketAggregate, GapFill)):
        clauses.extend((f"{time} >= ?", f"{time} < ?"))
        parameters.extend(
            (
                timestamp_to_storage(operation.start, descriptor.precision) if numeric_time else operation.start,
                timestamp_to_storage(operation.end, descriptor.precision) if numeric_time else operation.end,
            )
        )
    elif isinstance(operation, Latest) and operation.at_or_before is not None:
        clauses.append(f"{time} <= ?")
        parameters.append(
            timestamp_to_storage(operation.at_or_before, descriptor.precision) if numeric_time else operation.at_or_before
        )
    elif isinstance(operation, AsOf):
        clauses.append(f"{time} <= ?")
        parameters.append(timestamp_to_storage(operation.at, descriptor.precision) if numeric_time else operation.at)
    for predicate in operation.tag_predicates:
        field = _quote(predicate.field)
        if predicate.operator is TagOperator.EQ:
            clauses.append(f"{field} = ?")
        else:
            clauses.append(f"{field} IN ({', '.join('?' for _ in predicate.values)})")
        parameters.extend(predicate.values)
    return (" AND ".join(clauses) or "1 = 1", tuple(parameters))


def _columns(fields) -> str:
    return ", ".join(_quote(field) for field in fields)


def _order(plan: PortableTemporalPlan) -> str:
    if not plan.output_order:
        return ""
    return " ORDER BY " + ", ".join(
        f"{_quote(key.field)} {key.direction.value.upper()}" for key in plan.output_order
    )


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _timestamp_ns(value: str) -> int:
    parsed = value.removesuffix("Z")
    whole, _, fraction = parsed.partition(".")
    moment = datetime.fromisoformat(whole).replace(tzinfo=UTC)
    seconds = int(moment.timestamp())
    return seconds * 1_000_000_000 + int((fraction + "000000000")[:9])


def _check_deadline(started: float, bounds: ResourceBounds, operation: str) -> None:
    elapsed_ms = (time.monotonic() - started) * 1_000
    if elapsed_ms > bounds.max_duration_ms:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            f"{operation} exceeds max_duration_ms",
            {"elapsed_ms": int(elapsed_ms)},
        )


def _check_operation_bounds(
    data: bytes,
    table: pa.Table,
    bounds: ResourceBounds,
    started: float,
    operation: str,
) -> None:
    if len(data) > bounds.max_bytes or table.num_rows > bounds.max_rows:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            f"{operation} exceeds resource bounds",
            {"bytes": len(data), "rows": table.num_rows},
        )
    _check_deadline(started, bounds, operation)


class SQLiteManagedTemporalStore:
    def __init__(
        self,
        database_uri: TableURI,
        artifact_root: str | os.PathLike[str],
        descriptor: TemporalTableDescriptor,
        *,
        connection_factory=None,
        clock=None,
        fault_injector=None,
    ) -> None:
        self.database_uri = database_uri
        self.database_path = _database_path(database_uri)
        if self.database_path == ":memory:":
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "managed SQLite stores require a persistent database",
                {},
            )
        self.artifact_root = Path(artifact_root).absolute()
        self.artifact_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.descriptor = descriptor
        self._connection_factory = connection_factory or sqlite3.connect
        self._clock = clock or (lambda: datetime.now(UTC))
        self._fault_injector = fault_injector
        with self._connection(immediate=True):
            pass

    def stage(self, request: ManagedStageRequest) -> ManagedStageReceipt:
        started = time.monotonic()
        self._bind_target(request.logical_target)
        self._bind_target(request.physical_target)
        data, table = self._read_artifact(request.artifact, request.resource_bounds)
        _check_operation_bounds(data, table, request.resource_bounds, started, "SQLite stage")
        if temporal_descriptor_hash(self.descriptor, table.schema) != request.descriptor_hash:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "staged Arrow schema does not match descriptor_hash",
                {},
            )
        with self._connection(immediate=True) as connection:
            row = connection.execute(
                "SELECT operation_id, physical_target, stage_id, artifact_hash, "
                "descriptor_hash, staged_at FROM _otc_ts_stages "
                "WHERE logical_target = ? AND idempotency_key = ?",
                (request.logical_target.value, request.idempotency_key),
            ).fetchone()
            if row is not None:
                existing = ManagedStageReceipt(
                    "otc.managed-stage-receipt/v1",
                    row[0],
                    request.logical_target,
                    TableURI(row[1]),
                    row[2],
                    request.idempotency_key,
                    row[3],
                    row[4],
                    row[5],
                    False,
                )
                receipt = validate_stage_retry(existing, request)
                _check_deadline(started, request.resource_bounds, "SQLite stage")
                return receipt
            stage_id = "stage:" + hashlib.sha256(
                json.dumps(
                    {
                        "target": request.logical_target.value,
                        "idempotency_key": request.idempotency_key,
                        "artifact_hash": request.artifact.sha256,
                        "descriptor_hash": request.descriptor_hash,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            staged_at = self._now()
            receipt = ManagedStageReceipt(
                "otc.managed-stage-receipt/v1",
                request.operation_id,
                request.logical_target,
                request.physical_target,
                stage_id,
                request.idempotency_key,
                request.artifact.sha256,
                request.descriptor_hash,
                staged_at,
                False,
            )
            connection.execute(
                "INSERT INTO _otc_ts_stages "
                "(stage_id, operation_id, logical_target, physical_target, idempotency_key, "
                "artifact_hash, descriptor_hash, arrow_blob, staged_at, committed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (
                    stage_id,
                    request.operation_id,
                    request.logical_target.value,
                    request.physical_target.value,
                    request.idempotency_key,
                    request.artifact.sha256,
                    request.descriptor_hash,
                    data,
                    staged_at,
                ),
            )
            self._record_receipt(connection, request.operation_id, "stage", receipt.to_wire())
            _check_deadline(started, request.resource_bounds, "SQLite stage")
            return receipt

    def commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt:
        started = time.monotonic()
        self._bind_target(request.logical_target)
        with self._connection(immediate=True) as connection:
            existing = connection.execute(
                "SELECT operation_id, stage_id, snapshot_id, snapshot_reference, committed_at "
                "FROM _otc_ts_commits WHERE logical_target = ? AND idempotency_key = ?",
                (request.logical_target.value, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing[1] != request.stage_id:
                    raise TemporalExtensionError(
                        TemporalErrorCode.IDEMPOTENCY_CONFLICT,
                        "commit idempotency key is bound to another stage",
                        {},
                    )
                receipt = ManagedCommitReceipt(
                    "otc.managed-commit-receipt/v1",
                    existing[0],
                    request.logical_target,
                    existing[1],
                    request.idempotency_key,
                    existing[2],
                    existing[3],
                    existing[4],
                    VisibilityGuarantee.ATOMIC,
                )
                _check_deadline(started, request.resource_bounds, "SQLite commit")
                return receipt
            stage = connection.execute(
                "SELECT idempotency_key, arrow_blob, artifact_hash FROM _otc_ts_stages "
                "WHERE stage_id = ? AND logical_target = ?",
                (request.stage_id, request.logical_target.value),
            ).fetchone()
            if stage is None:
                raise TemporalExtensionError(
                    TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                    "SQLite managed stage is unavailable",
                    {"stage_id": request.stage_id},
                )
            if stage[0] != request.idempotency_key:
                raise TemporalExtensionError(
                    TemporalErrorCode.IDEMPOTENCY_CONFLICT,
                    "commit idempotency key does not match the stage",
                    {},
                )
            data = bytes(stage[1])
            if _sha256(data) != stage[2]:
                raise TemporalExtensionError(
                    TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                    "SQLite staged Arrow hash verification failed",
                    {},
                )
            table = pa.ipc.open_stream(pa.BufferReader(data)).read_all()
            _check_operation_bounds(data, table, request.resource_bounds, started, "SQLite commit")
            snapshot_id = _sha256(data)
            snapshot_reference = "sqlite-snapshot:" + snapshot_id[7:]
            committed_at = self._now()
            connection.execute(
                "INSERT OR IGNORE INTO _otc_ts_snapshots "
                "(snapshot_id, snapshot_reference, arrow_blob, created_at) VALUES (?, ?, ?, ?)",
                (snapshot_id, snapshot_reference, data, committed_at),
            )
            self._inject("before_pointer_update")
            connection.execute(
                "UPDATE _otc_ts_commits SET current = 0 WHERE logical_target = ?",
                (request.logical_target.value,),
            )
            connection.execute(
                "INSERT INTO _otc_ts_commits "
                "(logical_target, idempotency_key, operation_id, stage_id, snapshot_id, "
                "snapshot_reference, committed_at, current) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    request.logical_target.value,
                    request.idempotency_key,
                    request.operation_id,
                    request.stage_id,
                    snapshot_id,
                    snapshot_reference,
                    committed_at,
                ),
            )
            connection.execute(
                "UPDATE _otc_ts_stages SET committed = 1 WHERE stage_id = ?",
                (request.stage_id,),
            )
            receipt = ManagedCommitReceipt(
                "otc.managed-commit-receipt/v1",
                request.operation_id,
                request.logical_target,
                request.stage_id,
                request.idempotency_key,
                snapshot_id,
                snapshot_reference,
                committed_at,
                VisibilityGuarantee.ATOMIC,
            )
            self._record_receipt(connection, request.operation_id, "commit", receipt.to_wire())
            _check_deadline(started, request.resource_bounds, "SQLite commit")
            return receipt

    def readback(self, request: ManagedReadbackRequest) -> ManagedReadbackResult:
        table = self.read_snapshot(
            request.logical_target,
            request.snapshot_reference,
            request.resource_bounds,
            snapshot_id=request.snapshot_id,
        )
        arrow = _arrow_bytes(table)
        receipt = ManagedReadbackReceipt(
            "otc.managed-readback-receipt/v1",
            request.operation_id,
            request.snapshot_id,
            self._now(),
            _sha256(table.schema.serialize().to_pybytes()),
            _sha256(arrow),
            table.num_rows,
            len(arrow),
            _observed_range(table, self.descriptor.time_field, self.descriptor.precision),
        )
        with self._connection(immediate=True) as connection:
            self._record_receipt(connection, request.operation_id, "readback", receipt.to_wire())
        return ManagedReadbackResult(table, None, receipt)

    def read_snapshot(
        self,
        target: TableURI,
        snapshot_reference: str,
        bounds: ResourceBounds,
        *,
        snapshot_id: str | None = None,
    ) -> pa.Table:
        started = time.monotonic()
        self._bind_target(target)
        with self._connection(immediate=False) as connection:
            row = connection.execute(
                "SELECT snapshot_id, arrow_blob FROM _otc_ts_snapshots "
                "WHERE snapshot_reference = ?",
                (snapshot_reference,),
            ).fetchone()
        if row is None or (snapshot_id is not None and row[0] != snapshot_id):
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "SQLite snapshot is unavailable or mismatched",
                {},
            )
        data = bytes(row[1])
        if _sha256(data) != row[0] or len(data) > bounds.max_bytes:
            code = (
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED
                if len(data) > bounds.max_bytes
                else TemporalErrorCode.SNAPSHOT_UNAVAILABLE
            )
            raise TemporalExtensionError(code, "SQLite snapshot verification failed", {})
        table = pa.ipc.open_stream(pa.BufferReader(data)).read_all()
        if table.num_rows > bounds.max_rows:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "SQLite snapshot exceeds max_rows",
                {"rows": table.num_rows},
            )
        _check_deadline(started, bounds, "SQLite snapshot read")
        return table

    def abort(self, request: ManagedAbortRequest) -> ManagedAbortReceipt:
        self._bind_target(request.logical_target)
        with self._connection(immediate=True) as connection:
            row = connection.execute(
                "SELECT committed FROM _otc_ts_stages WHERE stage_id = ? AND logical_target = ?",
                (request.stage_id, request.logical_target.value),
            ).fetchone()
            if row is None:
                disposition = AbortDisposition.ALREADY_ABSENT
            elif row[0]:
                disposition = AbortDisposition.ALREADY_COMMITTED
            else:
                connection.execute(
                    "DELETE FROM _otc_ts_stages WHERE stage_id = ?",
                    (request.stage_id,),
                )
                disposition = AbortDisposition.REMOVED
            receipt = ManagedAbortReceipt(
                "otc.managed-abort-receipt/v1",
                request.operation_id,
                request.logical_target,
                request.stage_id,
                disposition,
                self._now(),
            )
            self._record_receipt(connection, request.operation_id, "abort", receipt.to_wire())
            return receipt

    @contextmanager
    def _connection(self, *, immediate: bool) -> Iterator[sqlite3.Connection]:
        connection = self._connection_factory(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            self._ensure_schema(connection)
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS _otc_ts_stages ("
            "stage_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, logical_target TEXT NOT NULL, "
            "physical_target TEXT NOT NULL, idempotency_key TEXT NOT NULL, artifact_hash TEXT NOT NULL, "
            "descriptor_hash TEXT NOT NULL, arrow_blob BLOB NOT NULL, staged_at TEXT NOT NULL, "
            "committed INTEGER NOT NULL, UNIQUE(logical_target, idempotency_key))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS _otc_ts_snapshots ("
            "snapshot_id TEXT PRIMARY KEY, snapshot_reference TEXT UNIQUE NOT NULL, "
            "arrow_blob BLOB NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS _otc_ts_commits ("
            "logical_target TEXT NOT NULL, idempotency_key TEXT NOT NULL, operation_id TEXT NOT NULL, "
            "stage_id TEXT NOT NULL, snapshot_id TEXT NOT NULL, snapshot_reference TEXT NOT NULL, "
            "committed_at TEXT NOT NULL, current INTEGER NOT NULL, "
            "PRIMARY KEY(logical_target, idempotency_key), UNIQUE(logical_target, stage_id))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS _otc_ts_receipts ("
            "operation_id TEXT PRIMARY KEY, kind TEXT NOT NULL, document TEXT NOT NULL)"
        )

    @staticmethod
    def _record_receipt(connection, operation_id: str, kind: str, document) -> None:
        connection.execute(
            "INSERT OR REPLACE INTO _otc_ts_receipts VALUES (?, ?, ?)",
            (
                operation_id,
                kind,
                json.dumps(document, sort_keys=True, separators=(",", ":")),
            ),
        )

    def _read_artifact(
        self,
        reference: ArrowArtifactReference,
        bounds: ResourceBounds,
    ):
        expected = f"sha256/{reference.sha256[7:]}.arrow"
        if reference.relative_path != expected:
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
        if metadata.st_size > bounds.max_bytes or reference.size_bytes > bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "SQLite Arrow artifact exceeds max_bytes",
                {"bytes": max(metadata.st_size, reference.size_bytes)},
            )
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            current = os.fstat(stream.fileno())
            if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise PermissionError("Arrow artifact changed during secure open")
            data = stream.read(reference.size_bytes + 1)
        if len(data) != reference.size_bytes or _sha256(data) != reference.sha256:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "Arrow artifact verification failed",
                {},
            )
        return data, pa.ipc.open_stream(pa.BufferReader(data)).read_all()

    def _bind_target(self, target: TableURI) -> None:
        if target != self.database_uri:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "managed SQLite target does not match the configured database",
                {},
            )

    def _now(self) -> str:
        value = self._clock()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = datetime.fromtimestamp(value, UTC)
        value = value.astimezone(UTC)
        return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond * 1000:09d}Z"

    def _inject(self, event: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(event)


class _SQLiteTemporalSource:
    def __init__(self, table: pa.Table, descriptor: TemporalTableDescriptor) -> None:
        self._table = table
        self.descriptor = descriptor

    def read_bounded(self, target, projection, predicates, bounds):
        del target, predicates, bounds
        return self._table.select(projection)


class SQLiteTemporalExecutor:
    def __init__(
        self,
        descriptor: TemporalTableDescriptor,
        physical_table: str,
        *,
        managed_store: SQLiteManagedTemporalStore | None = None,
        connection_factory=None,
    ) -> None:
        if _TABLE_RE.fullmatch(physical_table) is None:
            raise ValueError("physical_table must be an authorized simple identifier")
        self.descriptor = descriptor
        self.physical_table = physical_table
        self.managed_store = managed_store
        self._connection_factory = connection_factory or sqlite3.connect

    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult:
        if request.snapshot_reference is not None:
            if self.managed_store is None:
                raise TemporalExtensionError(
                    TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                    "SQLite snapshot execution requires a managed store",
                    {},
                )
            table = self.managed_store.read_snapshot(
                request.target,
                request.snapshot_reference,
                request.plan.resource_bounds,
            )
        else:
            table = self._read_bounded(request)
        return PolarsTemporalExecutor(
            _SQLiteTemporalSource(table, self.descriptor), connector_identity=CONNECTOR_IDENTITY
        ).execute(request)

    def _read_bounded(self, request: TemporalExecutionRequest) -> pa.Table:
        path = _database_path(request.target)
        connection = self._connection_factory(path)
        try:
            fields = self.descriptor.declared_fields
            table = ".".join(_quote(part) for part in self.physical_table.split("."))
            storage_type = connection.execute(
                f"SELECT typeof({_quote(self.descriptor.time_field)}) FROM {table} "
                f"WHERE {_quote(self.descriptor.time_field)} IS NOT NULL LIMIT 1"
            ).fetchone()
            numeric_time = storage_type is not None and storage_type[0] in {"integer", "real"}
            clauses, parameters = _storage_where(
                request.plan,
                self.descriptor,
                numeric_time=numeric_time,
            )
            statement = (
                f"SELECT {_columns(fields)} FROM {table} WHERE {clauses} "
                f"ORDER BY {_quote(self.descriptor.time_field)} ASC"
            )
            cursor = connection.execute(statement, parameters)
            rows = cursor.fetchmany(request.plan.resource_bounds.max_rows + 1)
            if len(rows) > request.plan.resource_bounds.max_rows:
                raise TemporalExtensionError(
                    TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                    "SQLite source exceeds max_rows",
                    {},
                )
            arrays = []
            for index, name in enumerate(fields):
                values = [row[index] for row in rows]
                if name in {
                    self.descriptor.time_field,
                    self.descriptor.ingestion_time_field,
                }:
                    unit = {
                        TimestampPrecision.SECOND: "s",
                        TimestampPrecision.MILLISECOND: "ms",
                        TimestampPrecision.MICROSECOND: "us",
                        TimestampPrecision.NANOSECOND: "ns",
                    }[self.descriptor.precision]
                    timestamp_type = pa.timestamp(unit, tz=self.descriptor.timezone)
                    if values and isinstance(next((item for item in values if item is not None), None), str):
                        arrays.append(pa.array(values).cast(timestamp_type))
                    else:
                        arrays.append(pa.array(values, type=timestamp_type))
                else:
                    array = pa.array(values)
                    arrays.append(array)
            return pa.Table.from_arrays(arrays, names=fields)
        finally:
            connection.close()


def _storage_where(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
    *,
    numeric_time: bool,
):
    operation = plan.operation
    clauses = []
    parameters = []
    field = _quote(descriptor.time_field)
    if isinstance(operation, (ScanRange, BucketAggregate, GapFill)):
        clauses.extend((f"{field} >= ?", f"{field} < ?"))
        parameters.extend(
            (
                timestamp_to_storage(operation.start, descriptor.precision) if numeric_time else operation.start,
                timestamp_to_storage(operation.end, descriptor.precision) if numeric_time else operation.end,
            )
        )
    elif isinstance(operation, Latest) and operation.at_or_before is not None:
        clauses.append(f"{field} <= ?")
        parameters.append(
            timestamp_to_storage(operation.at_or_before, descriptor.precision)
            if numeric_time
            else operation.at_or_before
        )
    elif isinstance(operation, AsOf):
        clauses.append(f"{field} <= ?")
        parameters.append(timestamp_to_storage(operation.at, descriptor.precision) if numeric_time else operation.at)
    for predicate in operation.tag_predicates:
        quoted = _quote(predicate.field)
        if predicate.operator is TagOperator.EQ:
            clauses.append(f"{quoted} = ?")
        else:
            clauses.append(f"{quoted} IN ({', '.join('?' for _ in predicate.values)})")
        parameters.extend(predicate.values)
    return " AND ".join(clauses) or "1 = 1", tuple(parameters)


def _database_path(uri: TableURI) -> str:
    from urllib.parse import unquote, urlsplit

    if uri.scheme != PROVIDER_SQLITE:
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "SQLite temporal target requires sqlite URI",
            {"scheme": uri.scheme},
        )
    parsed = urlsplit(uri.value)
    if parsed.query or parsed.fragment:
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "SQLite temporal URI cannot contain query or fragment",
            {},
        )
    path = unquote(parsed.path)
    return ":memory:" if path == "/:memory:" else path


def _arrow_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _observed_range(table: pa.Table, time_field: str, precision: TimestampPrecision) -> TimeRange | None:
    if table.num_rows == 0:
        return None
    values = table[time_field].cast(pa.int64()).to_pylist()
    return TimeRange(storage_to_timestamp(min(values), precision), storage_to_timestamp(max(values), precision))


def _format_ns(value: int) -> str:
    seconds, nanos = divmod(value, 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{nanos:09d}Z"


__all__ = [
    "SQLiteManagedTemporalStore",
    "SQLiteTemporalExecutor",
    "lower_sqlite",
]
