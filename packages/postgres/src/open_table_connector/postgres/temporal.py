"""Portable temporal lowering and managed storage for plain PostgreSQL."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Iterator, Mapping

import pyarrow as pa

from open_table_connector.contract import ResolveContext, TableURI
from open_table_connector.timeseries import (
    AbortDisposition,
    AggregateFunction,
    AsOf,
    ArrowArtifactReference,
    BucketAggregate,
    CalendarBucket,
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
    temporal_descriptor_hash,
    validate_stage_retry,
)
from open_table_connector.timeseries.capabilities import (
    AGGREGATE_WINDOW,
    AGGREGATE_WINDOW_PUSHDOWN,
    FILL,
    LOOKUP_ASOF,
    LOOKUP_LATEST,
    SCAN_RANGE,
    SCAN_RANGE_PUSHDOWN,
    STORAGE_ABORT,
    STORAGE_COMMIT_IDEMPOTENT,
    STORAGE_READBACK_VERIFY,
    STORAGE_SNAPSHOT_READ,
    STORAGE_STAGE,
    STORAGE_VISIBILITY_ATOMIC,
)

from .reader import PostgresConnector


_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)?$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SUPPORTED_AGGREGATES = {
    AggregateFunction.COUNT,
    AggregateFunction.MIN,
    AggregateFunction.MAX,
    AggregateFunction.SUM,
    AggregateFunction.AVG,
}


def lower_postgres(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
    physical_table: str,
) -> PreparedTemporalQuery:
    """Lower the PostgreSQL-safe subset and preserve everything else as residual work."""

    if not isinstance(plan, PortableTemporalPlan):
        raise TypeError("plan must be a PortableTemporalPlan")
    if not isinstance(descriptor, TemporalTableDescriptor):
        raise TypeError("descriptor must be a TemporalTableDescriptor")
    if not isinstance(physical_table, str) or _TABLE_RE.fullmatch(physical_table) is None:
        raise ValueError("physical_table must be an authorized simple identifier")
    table = ".".join(_quote(part) for part in physical_table.split("."))
    operation = plan.operation
    if isinstance(operation, GapFill):
        return _bounded_residual(plan, descriptor, table)
    if isinstance(operation, BucketAggregate):
        if not all(measure.function in _SUPPORTED_AGGREGATES for measure in operation.measures):
            return _bounded_residual(plan, descriptor, table)
        if isinstance(operation.bucket, FixedBucket):
            return _lower_fixed_aggregate(plan, descriptor, table)
        if isinstance(operation.bucket, CalendarBucket) and _simple_calendar(operation.bucket):
            return _lower_calendar_aggregate(plan, descriptor, table)
        return _bounded_residual(plan, descriptor, table)
    if isinstance(operation, ScanRange):
        where, parameters = _where(operation, descriptor)
        return PreparedTemporalQuery(
            f"SELECT {_columns(operation.projection)} FROM {table} "
            f"WHERE {where}{_order(plan)}",
            parameters,
            None,
        )
    if isinstance(operation, (Latest, AsOf)):
        where, parameters = _where(operation, descriptor)
        partition = ", ".join(_quote(field) for field in descriptor.series_key_fields) or "1"
        tie_order = [_quote(descriptor.time_field) + " DESC"]
        if descriptor.ingestion_time_field is not None:
            tie_order.append(_quote(descriptor.ingestion_time_field) + " DESC")
        projection = _columns(operation.projection)
        return PreparedTemporalQuery(
            f"SELECT {projection} FROM (SELECT {projection}, "
            f"ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {', '.join(tie_order)}) "
            f"AS \"__otc_rank\" FROM {table} WHERE {where}) AS \"__otc_latest\" "
            f"WHERE \"__otc_rank\" = 1{_order(plan)}",
            parameters,
            None,
        )
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
    where, parameters = _where(operation, descriptor)
    ordering = [*descriptor.series_key_fields, descriptor.time_field]
    if descriptor.ingestion_time_field is not None:
        ordering.append(descriptor.ingestion_time_field)
    return PreparedTemporalQuery(
        f"SELECT {_columns(projection)} FROM {table} WHERE {where} ORDER BY "
        + ", ".join(_quote(field) + " ASC" for field in ordering),
        parameters,
        plan,
    )


def _lower_fixed_aggregate(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
    table: str,
) -> PreparedTemporalQuery:
    operation = plan.operation
    bucket = operation.bucket
    origin = _shift_timestamp(bucket.origin, bucket.offset_ns)
    expression = f"date_bin(%s::interval, {_quote(descriptor.time_field)}, %s::timestamptz)"
    select = [_quote(field) for field in operation.group_by]
    select.append(f"{expression} AS \"bucket\"")
    select.extend(_aggregate_expressions(operation))
    where, parameters = _where(operation, descriptor)
    groups = [*(_quote(field) for field in operation.group_by), '"bucket"']
    interval = f"{bucket.width_ns / 1_000_000_000:.9f} seconds"
    return PreparedTemporalQuery(
        f"SELECT {', '.join(select)} FROM {table} WHERE {where} "
        f"GROUP BY {', '.join(groups)}{_order(plan)}",
        (interval, origin, *parameters),
        None,
    )


def _lower_calendar_aggregate(
    plan: PortableTemporalPlan,
    descriptor: TemporalTableDescriptor,
    table: str,
) -> PreparedTemporalQuery:
    operation = plan.operation
    bucket = operation.bucket
    expression = (
        f"date_trunc(%s, {_quote(descriptor.time_field)} AT TIME ZONE %s) AT TIME ZONE %s"
    )
    select = [_quote(field) for field in operation.group_by]
    select.append(f"{expression} AS \"bucket\"")
    select.extend(_aggregate_expressions(operation))
    where, parameters = _where(operation, descriptor)
    groups = [*(_quote(field) for field in operation.group_by), '"bucket"']
    return PreparedTemporalQuery(
        f"SELECT {', '.join(select)} FROM {table} WHERE {where} "
        f"GROUP BY {', '.join(groups)}{_order(plan)}",
        (bucket.unit.value, bucket.timezone, bucket.timezone, *parameters),
        None,
    )


def _aggregate_expressions(operation: BucketAggregate) -> list[str]:
    expressions = []
    for measure in operation.measures:
        if measure.function is AggregateFunction.COUNT:
            aggregate = "COUNT(*)"
        else:
            aggregate = f"{measure.function.value.upper()}({_quote(measure.value_field)})"
        expressions.append(f"{aggregate} AS {_quote(measure.output_field)}")
    return expressions


def _simple_calendar(bucket: CalendarBucket) -> bool:
    return bucket.count == 1 and bucket.offset_ns == 0


def _where(operation, descriptor: TemporalTableDescriptor):
    clauses: list[str] = []
    parameters: list[object] = []
    time = _quote(descriptor.time_field)
    if isinstance(operation, (ScanRange, BucketAggregate, GapFill)):
        clauses.extend((f"{time} >= %s", f"{time} < %s"))
        parameters.extend((operation.start, operation.end))
    elif isinstance(operation, Latest) and operation.at_or_before is not None:
        clauses.append(f"{time} <= %s")
        parameters.append(operation.at_or_before)
    elif isinstance(operation, AsOf):
        clauses.append(f"{time} <= %s")
        parameters.append(operation.at)
    for predicate in operation.tag_predicates:
        field = _quote(predicate.field)
        if predicate.operator is TagOperator.EQ:
            clauses.append(f"{field} = %s")
        else:
            clauses.append(f"{field} IN ({', '.join('%s' for _ in predicate.values)})")
        parameters.extend(predicate.values)
    return " AND ".join(clauses) or "TRUE", tuple(parameters)


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


def _shift_timestamp(value: str, offset_ns: int) -> str:
    if offset_ns == 0:
        return value
    parsed = value.removesuffix("Z")
    whole, _, fraction = parsed.partition(".")
    base = int(datetime.fromisoformat(whole).replace(tzinfo=UTC).timestamp()) * 1_000_000_000
    total = base + int((fraction + "000000000")[:9]) + offset_ns
    seconds, nanos = divmod(total, 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{nanos:09d}Z"


class PostgresManagedTemporalStore:
    """Transactional snapshot lifecycle stored in an isolated PostgreSQL schema."""

    def __init__(
        self,
        database_uri: TableURI,
        artifact_root: str | os.PathLike[str],
        descriptor: TemporalTableDescriptor,
        *,
        connection_factory=None,
        credentials: Mapping[str, object] | None = None,
        metadata_schema: str = "_otc_ts",
        clock=None,
        fault_injector=None,
        stage_id_factory=None,
    ) -> None:
        if _IDENTIFIER_RE.fullmatch(metadata_schema) is None:
            raise ValueError("metadata_schema must be a simple PostgreSQL identifier")
        self.database_uri = database_uri
        self.artifact_root = Path(artifact_root).absolute()
        self.artifact_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.descriptor = descriptor
        self.metadata_schema = metadata_schema
        self._connector = PostgresConnector(connection_factory)
        self._resolved = self._connector.resolve(
            database_uri,
            ResolveContext(credentials=dict(credentials or {})),
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._fault_injector = fault_injector
        self._stage_id_factory = stage_id_factory

    def stage(self, request: ManagedStageRequest) -> ManagedStageReceipt:
        self._bind_target(request.logical_target)
        self._bind_target(request.physical_target)
        data, table = self._read_artifact(request.artifact)
        if temporal_descriptor_hash(self.descriptor, table.schema) != request.descriptor_hash:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "staged Arrow schema does not match descriptor_hash",
                {},
            )
        with self._connection() as (_, cursor):
            self._lock(cursor, request.logical_target)
            cursor.execute(
                f"SELECT operation_id, physical_target, stage_id, artifact_hash, "
                f"descriptor_hash, staged_at FROM {self._table('stages')} "
                "WHERE logical_target = %s AND idempotency_key = %s",
                (request.logical_target.value, request.idempotency_key),
            )
            row = cursor.fetchone()
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
                    _time_text(row[5]),
                    False,
                )
                return validate_stage_retry(existing, request)
            stage_id = (
                self._stage_id_factory(request)
                if self._stage_id_factory is not None
                else "stage:"
                + hashlib.sha256(
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
            )
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
            cursor.execute(
                f"INSERT INTO {self._table('stages')} "
                "(stage_id, operation_id, logical_target, physical_target, idempotency_key, "
                "artifact_hash, descriptor_hash, arrow_blob, staged_at, committed) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE) "
                "ON CONFLICT (logical_target, idempotency_key) DO NOTHING",
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
            self._record_receipt(cursor, request.operation_id, "stage", receipt.to_wire())
            return receipt

    def commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt:
        self._bind_target(request.logical_target)
        try:
            return self._commit_once(request)
        except TemporalExtensionError:
            raise
        except Exception as exc:
            reconciled = self._reconcile_commit(request)
            if reconciled is not None:
                return reconciled
            raise TemporalExtensionError(
                TemporalErrorCode.VISIBILITY_INCOMPLETE,
                "PostgreSQL commit outcome could not be reconciled",
                {"exception_type": type(exc).__name__},
            ) from None

    def _commit_once(self, request: ManagedCommitRequest) -> ManagedCommitReceipt:
        with self._connection() as (_, cursor):
            self._lock(cursor, request.logical_target)
            existing = self._select_commit(cursor, request)
            if existing is not None:
                return existing
            cursor.execute(
                f"SELECT idempotency_key, arrow_blob, artifact_hash "
                f"FROM {self._table('stages')} WHERE stage_id = %s AND logical_target = %s",
                (request.stage_id, request.logical_target.value),
            )
            stage = cursor.fetchone()
            if stage is None:
                raise TemporalExtensionError(
                    TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                    "PostgreSQL managed stage is unavailable",
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
                    "PostgreSQL staged Arrow hash verification failed",
                    {},
                )
            snapshot_id = _sha256(data)
            snapshot_reference = "postgres-snapshot:" + snapshot_id[7:]
            committed_at = self._now()
            cursor.execute(
                f"INSERT INTO {self._table('snapshots')} "
                "(snapshot_id, snapshot_reference, arrow_blob, created_at) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (snapshot_id) DO NOTHING",
                (snapshot_id, snapshot_reference, data, committed_at),
            )
            self._inject("before_pointer_update")
            cursor.execute(
                f"UPDATE {self._table('commits')} SET current = FALSE WHERE logical_target = %s",
                (request.logical_target.value,),
            )
            cursor.execute(
                f"INSERT INTO {self._table('commits')} "
                "(logical_target, idempotency_key, operation_id, stage_id, snapshot_id, "
                "snapshot_reference, committed_at, current) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE) "
                "ON CONFLICT (logical_target, idempotency_key) DO NOTHING",
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
            cursor.execute(
                f"UPDATE {self._table('stages')} SET committed = TRUE WHERE stage_id = %s",
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
            self._record_receipt(cursor, request.operation_id, "commit", receipt.to_wire())
            return receipt

    def _reconcile_commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt | None:
        try:
            with self._connection() as (_, cursor):
                return self._select_commit(cursor, request)
        except Exception:
            return None

    def _select_commit(self, cursor, request: ManagedCommitRequest) -> ManagedCommitReceipt | None:
        cursor.execute(
            f"SELECT operation_id, stage_id, snapshot_id, snapshot_reference, committed_at "
            f"FROM {self._table('commits')} "
            "WHERE logical_target = %s AND idempotency_key = %s",
            (request.logical_target.value, request.idempotency_key),
        )
        existing = cursor.fetchone()
        if existing is None:
            return None
        if existing[1] != request.stage_id:
            raise TemporalExtensionError(
                TemporalErrorCode.IDEMPOTENCY_CONFLICT,
                "commit idempotency key is bound to another stage",
                {},
            )
        return ManagedCommitReceipt(
            "otc.managed-commit-receipt/v1",
            existing[0],
            request.logical_target,
            existing[1],
            request.idempotency_key,
            existing[2],
            existing[3],
            _time_text(existing[4]),
            VisibilityGuarantee.ATOMIC,
        )

    def readback(self, request: ManagedReadbackRequest) -> ManagedReadbackResult:
        self._bind_target(request.logical_target)
        with self._connection() as (_, cursor):
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("SET LOCAL statement_timeout = %s", (request.resource_bounds.max_duration_ms,))
            table = self._read_snapshot(cursor, request.snapshot_reference, request.resource_bounds, request.snapshot_id)
            data = _arrow_bytes(table)
            receipt = ManagedReadbackReceipt(
                "otc.managed-readback-receipt/v1",
                request.operation_id,
                request.snapshot_id,
                self._now(),
                _sha256(table.schema.serialize().to_pybytes()),
                _sha256(data),
                table.num_rows,
                len(data),
                _observed_range(table, self.descriptor.time_field),
            )
            self._record_receipt(cursor, request.operation_id, "readback", receipt.to_wire())
            return ManagedReadbackResult(table, None, receipt)

    def read_snapshot(
        self,
        target: TableURI,
        snapshot_reference: str,
        bounds: ResourceBounds,
        *,
        snapshot_id: str | None = None,
    ) -> pa.Table:
        self._bind_target(target)
        with self._connection() as (_, cursor):
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("SET LOCAL statement_timeout = %s", (bounds.max_duration_ms,))
            return self._read_snapshot(cursor, snapshot_reference, bounds, snapshot_id)

    def _read_snapshot(self, cursor, reference, bounds, snapshot_id):
        cursor.execute(
            f"SELECT snapshot_id, arrow_blob FROM {self._table('snapshots')} "
            "WHERE snapshot_reference = %s",
            (reference,),
        )
        row = cursor.fetchone()
        if row is None or (snapshot_id is not None and row[0] != snapshot_id):
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "PostgreSQL snapshot is unavailable or mismatched",
                {},
            )
        data = bytes(row[1])
        if len(data) > bounds.max_bytes:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "PostgreSQL snapshot exceeds max_bytes",
                {},
            )
        if _sha256(data) != row[0]:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "PostgreSQL snapshot hash verification failed",
                {},
            )
        table = pa.ipc.open_stream(pa.BufferReader(data)).read_all()
        if table.num_rows > bounds.max_rows:
            raise TemporalExtensionError(
                TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                "PostgreSQL snapshot exceeds max_rows",
                {"rows": table.num_rows},
            )
        return table

    def abort(self, request: ManagedAbortRequest) -> ManagedAbortReceipt:
        self._bind_target(request.logical_target)
        with self._connection() as (_, cursor):
            self._lock(cursor, request.logical_target)
            cursor.execute(
                f"SELECT committed FROM {self._table('stages')} "
                "WHERE stage_id = %s AND logical_target = %s",
                (request.stage_id, request.logical_target.value),
            )
            row = cursor.fetchone()
            if row is None:
                disposition = AbortDisposition.ALREADY_ABSENT
            elif row[0]:
                disposition = AbortDisposition.ALREADY_COMMITTED
            else:
                cursor.execute(
                    f"DELETE FROM {self._table('stages')} WHERE stage_id = %s",
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
            self._record_receipt(cursor, request.operation_id, "abort", receipt.to_wire())
            return receipt

    @contextmanager
    def _connection(self) -> Iterator[tuple[object, object]]:
        connection = self._connector._connect(self._resolved.resource)
        cursor = None
        try:
            cursor = connection.cursor()
            self._ensure_schema(cursor)
            yield connection, cursor
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            connection.close()

    def _ensure_schema(self, cursor) -> None:
        schema = _quote(self.metadata_schema)
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table('stages')} ("
            "stage_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, logical_target TEXT NOT NULL, "
            "physical_target TEXT NOT NULL, idempotency_key TEXT NOT NULL, artifact_hash TEXT NOT NULL, "
            "descriptor_hash TEXT NOT NULL, arrow_blob BYTEA NOT NULL, staged_at TIMESTAMPTZ NOT NULL, "
            "committed BOOLEAN NOT NULL, UNIQUE(logical_target, idempotency_key))"
        )
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table('snapshots')} ("
            "snapshot_id TEXT PRIMARY KEY, snapshot_reference TEXT UNIQUE NOT NULL, "
            "arrow_blob BYTEA NOT NULL, created_at TIMESTAMPTZ NOT NULL)"
        )
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table('commits')} ("
            "logical_target TEXT NOT NULL, idempotency_key TEXT NOT NULL, operation_id TEXT NOT NULL, "
            "stage_id TEXT NOT NULL, snapshot_id TEXT NOT NULL, snapshot_reference TEXT NOT NULL, "
            "committed_at TIMESTAMPTZ NOT NULL, current BOOLEAN NOT NULL, "
            "PRIMARY KEY(logical_target, idempotency_key), UNIQUE(logical_target, stage_id))"
        )
        cursor.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_quote(self.metadata_schema + '_current_target')} "
            f"ON {self._table('commits')} (logical_target) WHERE current"
        )
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table('receipts')} ("
            "operation_id TEXT PRIMARY KEY, kind TEXT NOT NULL, document JSONB NOT NULL)"
        )

    def _record_receipt(self, cursor, operation_id: str, kind: str, document) -> None:
        cursor.execute(
            f"INSERT INTO {self._table('receipts')} (operation_id, kind, document) "
            "VALUES (%s, %s, %s::jsonb) ON CONFLICT (operation_id) DO UPDATE "
            "SET kind = EXCLUDED.kind, document = EXCLUDED.document",
            (operation_id, kind, json.dumps(document, sort_keys=True, separators=(",", ":"))),
        )

    @staticmethod
    def _lock(cursor, target: TableURI) -> None:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (target.value,))

    def _table(self, name: str) -> str:
        return f"{_quote(self.metadata_schema)}.{_quote(name)}"

    def _read_artifact(self, reference: ArrowArtifactReference):
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
                "managed PostgreSQL target does not match the configured database",
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


class _PostgresTemporalSource:
    def __init__(self, table: pa.Table, descriptor: TemporalTableDescriptor) -> None:
        self._table = table
        self.descriptor = descriptor

    def read_bounded(self, target, projection, predicates, bounds):
        del target, predicates, bounds
        return self._table.select(projection)


class PostgresTemporalExecutor:
    """Plain PostgreSQL executor; no TimescaleDB identity or gap-fill claim."""

    CAPABILITIES = (
        SCAN_RANGE,
        SCAN_RANGE_PUSHDOWN,
        LOOKUP_LATEST,
        LOOKUP_ASOF,
        AGGREGATE_WINDOW,
        AGGREGATE_WINDOW_PUSHDOWN,
        FILL,
        STORAGE_STAGE,
        STORAGE_COMMIT_IDEMPOTENT,
        STORAGE_SNAPSHOT_READ,
        STORAGE_READBACK_VERIFY,
        STORAGE_VISIBILITY_ATOMIC,
        STORAGE_ABORT,
    )

    def __init__(
        self,
        descriptor: TemporalTableDescriptor,
        physical_table: str,
        *,
        managed_store: PostgresManagedTemporalStore | None = None,
        connection_factory=None,
        credentials: Mapping[str, object] | None = None,
    ) -> None:
        if _TABLE_RE.fullmatch(physical_table) is None:
            raise ValueError("physical_table must be an authorized simple identifier")
        self.descriptor = descriptor
        self.physical_table = physical_table
        self.managed_store = managed_store
        self._connector = PostgresConnector(connection_factory)
        self._credentials = dict(credentials or {})

    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult:
        if request.snapshot_reference is not None:
            if self.managed_store is None:
                raise TemporalExtensionError(
                    TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                    "PostgreSQL snapshot execution requires a managed store",
                    {},
                )
            table = self.managed_store.read_snapshot(
                request.target,
                request.snapshot_reference,
                request.plan.resource_bounds,
            )
        else:
            table = self._read_bounded(request)
        return PolarsTemporalExecutor(_PostgresTemporalSource(table, self.descriptor)).execute(request)

    def _read_bounded(self, request: TemporalExecutionRequest) -> pa.Table:
        resolved = self._connector.resolve(
            request.target,
            ResolveContext(credentials=self._credentials),
        )
        connection = self._connector._connect(resolved.resource)
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("SET LOCAL statement_timeout = %s", (request.plan.resource_bounds.max_duration_ms,))
            fields = _required_fields(request.plan, self.descriptor)
            clauses, parameters = _storage_where(request.plan, self.descriptor)
            table = ".".join(_quote(part) for part in self.physical_table.split("."))
            cursor.execute(
                f"SELECT {_columns(fields)} FROM {table} WHERE {clauses} "
                f"ORDER BY {_quote(self.descriptor.time_field)} ASC",
                parameters,
            )
            rows = cursor.fetchmany(request.plan.resource_bounds.max_rows + 1)
            if len(rows) > request.plan.resource_bounds.max_rows:
                raise TemporalExtensionError(
                    TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                    "PostgreSQL source exceeds max_rows",
                    {},
                )
            result = _rows_to_table(fields, rows, self.descriptor)
            if len(_arrow_bytes(result)) > request.plan.resource_bounds.max_bytes:
                raise TemporalExtensionError(
                    TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                    "PostgreSQL source exceeds max_bytes",
                    {},
                )
            connection.commit()
            return result
        except BaseException:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            connection.close()


def _required_fields(plan: PortableTemporalPlan, descriptor: TemporalTableDescriptor):
    operation = plan.operation
    if isinstance(operation, (ScanRange, Latest, AsOf)):
        fields = list(operation.projection)
    else:
        fields = [*operation.group_by]
        fields.extend(
            measure.value_field for measure in operation.measures if measure.value_field is not None
        )
    fields.extend(predicate.field for predicate in operation.tag_predicates)
    fields.extend(descriptor.series_key_fields)
    fields.append(descriptor.time_field)
    if descriptor.ingestion_time_field is not None:
        fields.append(descriptor.ingestion_time_field)
    return tuple(dict.fromkeys(fields))


def _storage_where(plan: PortableTemporalPlan, descriptor: TemporalTableDescriptor):
    return _where(plan.operation, descriptor)


def _rows_to_table(fields, rows, descriptor: TemporalTableDescriptor) -> pa.Table:
    arrays = []
    temporal_fields = {descriptor.time_field, descriptor.ingestion_time_field}
    unit = {
        TimestampPrecision.SECOND: "s",
        TimestampPrecision.MILLISECOND: "ms",
        TimestampPrecision.MICROSECOND: "us",
        TimestampPrecision.NANOSECOND: "ns",
    }[descriptor.precision]
    for index, field in enumerate(fields):
        values = [row[index] for row in rows]
        if field in temporal_fields:
            timestamp_type = pa.timestamp(unit, tz=descriptor.timezone)
            arrays.append(pa.array(values).cast(timestamp_type))
        else:
            array = pa.array(values)
            if pa.types.is_string(array.type):
                array = pa.array(values, type=pa.large_string())
            arrays.append(array)
    return pa.Table.from_arrays(arrays, names=fields)


def _arrow_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _observed_range(table: pa.Table, time_field: str) -> TimeRange | None:
    if table.num_rows == 0:
        return None
    values = table[time_field].cast(pa.int64()).to_pylist()
    return TimeRange(_format_ns(min(values)), _format_ns(max(values)))


def _format_ns(value: int) -> str:
    seconds, nanos = divmod(value, 1_000_000_000)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{nanos:09d}Z"


def _time_text(value) -> str:
    if isinstance(value, datetime):
        value = value.astimezone(UTC)
        return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond * 1000:09d}Z"
    return str(value)


__all__ = [
    "PostgresManagedTemporalStore",
    "PostgresTemporalExecutor",
    "lower_postgres",
]
