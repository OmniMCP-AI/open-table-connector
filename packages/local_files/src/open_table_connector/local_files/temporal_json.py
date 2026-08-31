"""Portable temporal execution and managed snapshots for JSON and JSONL."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pyarrow as pa

from open_table_connector.contract import ConnectorError, TableURI
from open_table_connector.timeseries import (
    AggregateFunction,
    BucketAggregate,
    GapFill,
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

from .json_codec import (
    encode_json_table,
    encode_jsonl_table,
    parse_json_table,
    parse_jsonl_table,
)
from .json_connector import _json_path
from .managed_snapshots import ManagedSnapshotStore
from .identity import CONNECTOR_IDENTITY


JsonFormat = Literal["json", "jsonl"]


class JsonManagedTemporalStore:
    def __init__(
        self,
        format_name: JsonFormat,
        artifact_root: str | Path,
        descriptor: TemporalTableDescriptor,
        *,
        clock=None,
        fault_injector=None,
    ) -> None:
        if format_name not in {"json", "jsonl"}:
            raise ValueError("format_name must be json or jsonl")
        encoder = encode_json_table if format_name == "json" else encode_jsonl_table
        parser = parse_json_table if format_name == "json" else parse_jsonl_table
        self.format_name: JsonFormat = format_name
        self.snapshots = ManagedSnapshotStore(
            artifact_root,
            descriptor,
            target_scheme=format_name,
            extension=format_name,
            encode_snapshot=lambda table: encoder(table).encode("utf-8"),
            decode_snapshot=lambda data: _decode_temporal_json(
                data,
                parser,
                descriptor,
                source="managed snapshot",
            ),
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


class _JsonTemporalSource:
    def __init__(self, table: pa.Table, descriptor: TemporalTableDescriptor) -> None:
        self._table = table
        self.descriptor = descriptor

    def read_bounded(self, target, projection, predicates, bounds) -> pa.Table:
        del target, predicates, bounds
        return self._table.select(projection)


class JsonTemporalExecutor:
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
        managed_store: JsonManagedTemporalStore | None = None,
    ) -> None:
        if not isinstance(descriptor, TemporalTableDescriptor):
            raise TypeError("descriptor must be a TemporalTableDescriptor")
        self.descriptor = descriptor
        self.managed_store = managed_store

    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult:
        if not isinstance(request, TemporalExecutionRequest):
            raise TypeError("request must be a TemporalExecutionRequest")
        if request.target.scheme not in {"json", "jsonl"}:
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "JSON temporal executor accepts only json and jsonl targets",
                {"scheme": request.target.scheme},
            )
        if request.snapshot_reference is None:
            table = _read_direct(request, self.descriptor)
        else:
            if (
                self.managed_store is None
                or self.managed_store.format_name != request.target.scheme
            ):
                raise TemporalExtensionError(
                    TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
                    "snapshot execution requires a managed store for the target format",
                    {},
                )
            table = self.managed_store.read_snapshot(
                request.target,
                request.snapshot_reference,
                request.plan.resource_bounds,
            )
        _validate_temporal_types(table, request, self.descriptor)
        return PolarsTemporalExecutor(
            _JsonTemporalSource(table, self.descriptor), connector_identity=CONNECTOR_IDENTITY
        ).execute(request)


def _read_direct(
    request: TemporalExecutionRequest,
    descriptor: TemporalTableDescriptor,
) -> pa.Table:
    try:
        path, format_name = _json_path(request.target)
    except ConnectorError as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.PROTOCOL_INVALID,
            exc.message,
            exc.safe_details,
        ) from exc
    max_bytes = request.plan.resource_bounds.max_bytes
    if path.stat().st_size > max_bytes:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            "JSON source exceeds max_bytes",
            {"bytes": path.stat().st_size},
        )
    with path.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise TemporalExtensionError(
            TemporalErrorCode.RESOURCE_LIMIT_EXCEEDED,
            "JSON source exceeds max_bytes",
            {"bytes": len(data)},
        )
    parser = parse_json_table if format_name.value == "json" else parse_jsonl_table
    return _decode_temporal_json(data, parser, descriptor, source=str(path))


def _decode_temporal_json(
    data: bytes,
    parser,
    descriptor: TemporalTableDescriptor,
    *,
    source: str,
) -> pa.Table:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
            "JSON temporal source is not strict UTF-8",
            {"source": source},
        ) from exc
    try:
        table = parser(text, source=source)
    except ConnectorError as exc:
        raise TemporalExtensionError(
            TemporalErrorCode.SNAPSHOT_UNAVAILABLE,
            "JSON temporal source is malformed",
            exc.safe_details,
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
                TemporalErrorCode.PROTOCOL_INVALID,
                "JSON temporal timestamp is incompatible with the descriptor",
                {"field": name},
            ) from exc
        table = table.set_column(index, name, column)
    return table


def _validate_temporal_types(
    table: pa.Table,
    request: TemporalExecutionRequest,
    descriptor: TemporalTableDescriptor,
) -> None:
    for name in (
        descriptor.time_field,
        *descriptor.series_key_fields,
        *descriptor.tag_fields,
    ):
        if name in table.column_names and pa.types.is_nested(table.schema.field(name).type):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "JSON temporal time, series-key, and tag fields must be scalar",
                {"field": name},
            )
    operation = request.plan.operation
    if not isinstance(operation, (BucketAggregate, GapFill)):
        return
    for measure in operation.measures:
        if measure.value_field is None or measure.value_field not in table.column_names:
            continue
        data_type = table.schema.field(measure.value_field).type
        if measure.function in {AggregateFunction.SUM, AggregateFunction.AVG} and not (
            pa.types.is_integer(data_type)
            or pa.types.is_floating(data_type)
            or pa.types.is_decimal(data_type)
        ):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "JSON sum and average aggregate inputs must be numeric",
                {"field": measure.value_field},
            )
        if pa.types.is_nested(data_type):
            raise TemporalExtensionError(
                TemporalErrorCode.PROTOCOL_INVALID,
                "JSON aggregate inputs must be scalar",
                {"field": measure.value_field},
            )


__all__ = ["JsonManagedTemporalStore", "JsonTemporalExecutor"]
