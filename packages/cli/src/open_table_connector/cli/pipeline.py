"""Arrow-backed orchestration for CLI table operations."""

from __future__ import annotations

from collections.abc import Iterable

import pyarrow as pa
from open_table_connector.contract import (
    PROVIDER_CSV,
    PROVIDER_EXCEL,
    PROVIDER_FEISHU_BITABLE,
    PROVIDER_JSON,
    PROVIDER_JSONL,
    SCHEME_FILE,
    SCHEME_MD,
    ArrowReadResult,
    ConnectorError,
    ConnectorErrorCode,
    TableInspection,
)

from .adapters import ConnectorAdapter
from .formats import infer_format, write_local
from .model import CliOptions, Endpoint, FormatName, PipelineSummary
from .registry import ConnectorRegistry


def read_endpoint(
    endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions
) -> ArrowReadResult:
    """Read one endpoint into Arrow, preserving the adapter's receipt."""

    _validate_source_format(endpoint, options)
    adapter = registry.connector_for(endpoint)
    return adapter.read(endpoint, options)


def inspect_endpoint(
    endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions
) -> TableInspection:
    """Delegate inspection to the selected adapter."""

    _validate_source_format(endpoint, options)
    return registry.connector_for(endpoint).inspect(endpoint, options)


def convert_endpoint(
    source: Endpoint,
    destination: Endpoint,
    registry: ConnectorRegistry,
    options: CliOptions,
) -> PipelineSummary:
    """Read once from ``source`` and write once to a local destination."""

    if not _is_local(destination):
        raise _unsupported(destination, "convert destinations must be local files or stdout")

    destination_format = infer_format(destination, options.to_format)
    if (
        destination_format is FormatName.AUTO
        and options.to_format is FormatName.AUTO
        and options.output_format not in {FormatName.AUTO, FormatName.JSONL}
    ):
        # Backward-compatible programmatic callers used output_format for an
        # extensionless destination before --to-format was introduced.
        destination_format = options.output_format
    if destination.is_stdio and destination_format is FormatName.AUTO:
        destination_format = FormatName.JSONL
    if destination_format.value == "auto":
        raise ConnectorError(
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            "local destination format could not be inferred; provide --to-format",
            {"scheme": SCHEME_FILE, "format": destination_format.value},
        )

    _validate_source_format(source, options)
    result = read_endpoint(source, registry, options)
    write_local(result.table, destination, destination_format, sheet=options.sheet)
    return PipelineSummary(
        status="completed",
        rows_read=result.table.num_rows,
        rows_written=result.table.num_rows,
        source_receipt=result.receipt,
    )


def import_endpoint(
    source: Endpoint,
    destination: Endpoint,
    registry: ConnectorRegistry,
    options: CliOptions,
) -> PipelineSummary:
    """Read once from Arrow and write once through a writable connector."""

    if _is_local(destination):
        raise _unsupported(destination, "import destinations must be writable connectors")

    _validate_source_format(source, options)

    # Validate before reading so unsupported imports cannot cause provider I/O.
    destination_adapter = registry.require_capability(destination, "table.write")
    preflight = getattr(destination_adapter, "preflight_write", None)
    if callable(preflight):
        preflight(destination, options)
    result = read_endpoint(source, registry, options)
    table = _table_for_destination(result.table, result.receipt, destination_adapter)
    write_result = destination_adapter.write(destination, table, options)
    return PipelineSummary(
        status="completed",
        rows_read=result.table.num_rows,
        rows_written=write_result.affected_rows,
        source_receipt=result.receipt,
        destination_receipt=write_result.receipt,
    )


def _is_local(endpoint: Endpoint) -> bool:
    return (
        endpoint.is_stdio
        or endpoint.path is not None
        or (
            endpoint.uri is not None
            and endpoint.uri.scheme
            in {PROVIDER_CSV, PROVIDER_EXCEL, PROVIDER_JSON, PROVIDER_JSONL, SCHEME_MD}
        )
    )


def _validate_source_format(endpoint: Endpoint, options: CliOptions) -> None:
    if _is_local(endpoint) or options.from_format is FormatName.AUTO:
        return
    raise ConnectorError(
        ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
        "connector sources do not support --from-format; omit the override",
        {
            "scheme": endpoint.uri.scheme if endpoint.uri is not None else SCHEME_FILE,
            "option": "from-format",
            "format": options.from_format.value,
        },
    )


def _unsupported(endpoint: Endpoint, message: str) -> ConnectorError:
    scheme = endpoint.uri.scheme if endpoint.uri is not None else SCHEME_FILE
    return ConnectorError(
        ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
        message,
        {"scheme": scheme, "capability": "table.write"},
    )


def _table_for_destination(
    table: pa.Table, receipt: object, destination_adapter: ConnectorAdapter
) -> pa.Table:
    """Apply only an explicit destination-owned field policy.

    Provider receipts carry the source convention; the pipeline otherwise
    preserves every Arrow column, including Feishu's ``_record_id``.
    """

    source_identity = getattr(getattr(receipt, "connector", None), "connector_id", None)
    if source_identity != PROVIDER_FEISHU_BITABLE or "_record_id" not in table.column_names:
        return table

    owned = getattr(destination_adapter, "provider_owned_fields", ())
    if not isinstance(owned, Iterable) or "_record_id" not in owned:
        return table
    return table.drop(["_record_id"])


__all__ = ["convert_endpoint", "import_endpoint", "inspect_endpoint", "read_endpoint"]
