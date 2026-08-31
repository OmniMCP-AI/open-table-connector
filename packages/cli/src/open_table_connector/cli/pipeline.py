"""Arrow-backed orchestration for CLI table operations."""

from __future__ import annotations

from collections.abc import Iterable

import pyarrow as pa
from open_table_connector.contract import (
    SCHEME_FILE,
    ArrowReadResult,
    ConnectorAdapter,
    ConnectorError,
    ConnectorErrorCode,
    TableInspection,
)

from .model import CliOptions, Endpoint, FormatName, PipelineSummary
from .registry import ConnectorRegistry


def infer_format(*args, **kwargs):
    from open_table_connector.local_files.cli_adapter import infer_format as infer

    return infer(*args, **kwargs)


def write_local(*args, **kwargs):
    from open_table_connector.local_files.cli_adapter import write_local as write

    return write(*args, **kwargs)


def read_endpoint(
    endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions
) -> ArrowReadResult:
    """Read one endpoint into Arrow, preserving the adapter's receipt."""

    _validate_source_format(endpoint, options, registry)
    adapter = registry.connector_for(endpoint)
    return adapter.read(endpoint, options)


def inspect_endpoint(
    endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions
) -> TableInspection:
    """Delegate inspection to the selected adapter."""

    _validate_source_format(endpoint, options, registry)
    return registry.connector_for(endpoint).inspect(endpoint, options)


def convert_endpoint(
    source: Endpoint,
    destination: Endpoint,
    registry: ConnectorRegistry,
    options: CliOptions,
) -> PipelineSummary:
    """Read once from ``source`` and write once to a local destination."""

    if not _is_local(destination, registry):
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

    _validate_source_format(source, options, registry)
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

    if _is_local(destination, registry):
        raise _unsupported(destination, "import destinations must be writable connectors")

    _validate_source_format(source, options, registry)

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


def _is_local(endpoint: Endpoint, registry: ConnectorRegistry) -> bool:
    if endpoint.is_stdio or endpoint.path is not None:
        return True
    try:
        return bool(getattr(registry.connector_for(endpoint), "local", False))
    except Exception:
        return False


def _validate_source_format(
    endpoint: Endpoint, options: CliOptions, registry: ConnectorRegistry
) -> None:
    if _is_local(endpoint, registry) or options.from_format is FormatName.AUTO:
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

    owned = getattr(destination_adapter, "provider_owned_fields", ())
    if not isinstance(owned, Iterable):
        return table
    owned_fields = set(str(field) for field in owned)
    return table.drop([field for field in table.column_names if field in owned_fields])


__all__ = ["convert_endpoint", "import_endpoint", "inspect_endpoint", "read_endpoint"]
