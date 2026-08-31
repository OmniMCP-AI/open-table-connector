"""Portable temporal execution and managed snapshots for CSV."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import io
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pyarrow as pa
import pyarrow.csv as pa_csv

from open_table_connector.contract import PROVIDER_CSV, SCHEME_MANAGED_CSV, TableURI
from open_table_connector.timeseries import (
    ManagedAbortReceipt,
    ManagedAbortRequest,
    ManagedCommitReceipt,
    ManagedCommitRequest,
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
    TimestampPrecision,
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

from .managed_snapshots import ManagedSnapshotStore
from .identity import CONNECTOR_IDENTITY


def _encode_csv(table: pa.Table) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(table.column_names)
    columns: list[list[object]] = []
    for field, column in zip(table.schema, table.columns, strict=True):
        if pa.types.is_timestamp(field.type):
            raw = column.cast(pa.int64()).to_pylist()
            columns.append(
                [
                    None if value is None else _timestamp_text(value, field.type.unit)
                    for value in raw
                ]
            )
        else:
            columns.append(column.to_pylist())
    for row_index in range(table.num_rows):
        writer.writerow(
            [
                _csv_scalar(columns[column_index][row_index], table.schema[column_index].type)
                for column_index in range(table.num_columns)
            ]
        )
    return stream.getvalue().encode("utf-8")


def _decode_csv(data: bytes, descriptor: TemporalTableDescriptor) -> pa.Table:
    try:
        table = pa_csv.read_csv(pa.BufferReader(data))
    except (pa.ArrowInvalid, OSError) as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
            "CSV snapshot could not be decoded",
            {},
        ) from exc
    unit = {
        TimestampPrecision.SECOND: "s",
        TimestampPrecision.MILLISECOND: "ms",
        TimestampPrecision.MICROSECOND: "us",
        TimestampPrecision.NANOSECOND: "ns",
    }[descriptor.precision]
    for name in (
        descriptor.time_field,
        *(() if descriptor.ingestion_time_field is None else (descriptor.ingestion_time_field,)),
    ):
        if name not in table.column_names:
            continue
        index = table.schema.get_field_index(name)
        try:
            column = table[name].cast(pa.timestamp(unit, tz=descriptor.timezone))
        except (pa.ArrowInvalid, pa.ArrowNotImplementedError) as exc:
            raise TemporalExtensionError(
                TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                "CSV timestamp does not match its temporal descriptor",
                {"field": name},
            ) from exc
        table = table.set_column(index, name, column)
    return table


def _csv_scalar(value: object, data_type: pa.DataType) -> object:
    if value is None:
        return ""
    if pa.types.is_floating(data_type):
        return repr(float(value))
    if pa.types.is_boolean(data_type):
        return "true" if value else "false"
    return value


def _timestamp_text(value: int, unit: str) -> str:
    scale = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}[unit]
    nanoseconds = value * scale
    seconds, fraction = divmod(nanoseconds, 1_000_000_000)
    whole = datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{whole}.{fraction:09d}Z"


class CsvManagedTemporalStore:
    def __init__(
        self,
        artifact_root: str | Path,
        descriptor: TemporalTableDescriptor,
        *,
        clock=None,
        fault_injector=None,
    ) -> None:
        self.snapshots = ManagedSnapshotStore(
            artifact_root,
            descriptor,
            target_scheme=SCHEME_MANAGED_CSV,
            extension=PROVIDER_CSV,
            encode_snapshot=_encode_csv,
            decode_snapshot=lambda data: _decode_csv(data, descriptor),
            clock=clock,
            fault_injector=fault_injector,
        )

    @property
    def descriptor(self) -> TemporalTableDescriptor:
        return self.snapshots.descriptor

    def stage(self, request: ManagedStageRequest) -> ManagedStageReceipt:
        return self.snapshots.stage_artifact(request)

    def commit(self, request: ManagedCommitRequest) -> ManagedCommitReceipt:
        return self.snapshots.publish_snapshot(request)

    def readback(self, request: ManagedReadbackRequest) -> ManagedReadbackResult:
        return self.snapshots.readback_snapshot(request)

    def abort(self, request: ManagedAbortRequest) -> ManagedAbortReceipt:
        return self.snapshots.abort_stage(request)

    def resolve_snapshot(self, target: TableURI, snapshot_reference: str) -> Path:
        return self.snapshots.resolve_snapshot(target, snapshot_reference)

    def read_snapshot(
        self,
        target: TableURI,
        snapshot_reference: str,
        bounds: ResourceBounds,
    ) -> pa.Table:
        return self.snapshots.read_snapshot(target, snapshot_reference, bounds)

    def recover(self, target: TableURI) -> None:
        self.snapshots.recover(target)


class _CsvTemporalSource:
    def __init__(self, table: pa.Table, descriptor: TemporalTableDescriptor) -> None:
        self._table = table
        self.descriptor = descriptor

    def read_bounded(self, target, projection, predicates, bounds) -> pa.Table:
        del target, predicates, bounds
        return self._table.select(projection)


class CsvTemporalExecutor:
    CAPABILITIES = (
        DESCRIBE,
        SCAN_RANGE,
        LOOKUP_LATEST,
        LOOKUP_ASOF,
        AGGREGATE_WINDOW,
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
        managed_store: CsvManagedTemporalStore | None = None,
    ) -> None:
        if not isinstance(descriptor, TemporalTableDescriptor):
            raise TypeError("descriptor must be a TemporalTableDescriptor")
        self.descriptor = descriptor
        self.managed_store = managed_store

    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult:
        if not isinstance(request, TemporalExecutionRequest):
            raise TypeError("request must be a TemporalExecutionRequest")
        if request.target.scheme == SCHEME_MANAGED_CSV:
            if self.managed_store is None or request.snapshot_reference is None:
                raise TemporalExtensionError(
                    TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                    "managed CSV execution requires an addressed snapshot",
                    {},
                )
            table = self.managed_store.read_snapshot(
                request.target,
                request.snapshot_reference,
                request.plan.resource_bounds,
            )
        elif request.target.scheme == PROVIDER_CSV:
            path = _direct_csv_path(request.target)
            if path.stat().st_size > request.plan.resource_bounds.max_bytes:
                raise TemporalExtensionError(
                    TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
                    "CSV source exceeds max_bytes",
                    {"bytes": path.stat().st_size},
                )
            table = _decode_csv(path.read_bytes(), self.descriptor)
        else:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "CSV temporal executor accepts " + PROVIDER_CSV + " and " + SCHEME_MANAGED_CSV + " targets",
                {"scheme": request.target.scheme},
            )
        return PolarsTemporalExecutor(
            _CsvTemporalSource(table, self.descriptor), connector_identity=CONNECTOR_IDENTITY
        ).execute(request)


def _direct_csv_path(target: TableURI) -> Path:
    parsed = urlsplit(target.value)
    path = Path(unquote(parsed.path))
    if (
        parsed.netloc not in {"", "localhost"}
        or parsed.query
        or parsed.fragment
        or not path.is_absolute()
        or ".." in path.parts
        or not path.is_file()
    ):
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            "csv target must address one regular absolute file",
            {},
        )
    if path.is_symlink():
        raise PermissionError("CSV source cannot be a symlink")
    return path


__all__ = ["CsvManagedTemporalStore", "CsvTemporalExecutor"]
