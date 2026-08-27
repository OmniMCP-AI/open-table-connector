"""Arrow-backed orchestration for CLI table operations."""

from __future__ import annotations

from collections.abc import Iterable

import pyarrow as pa

from open_connectors.contract import ArrowReadResult, ConnectorError, ConnectorErrorCode, TableInspection

from .adapters import ConnectorAdapter
from .formats import infer_format, write_local
from .model import CliOptions, Endpoint, PipelineSummary
from .registry import ConnectorRegistry


def read_endpoint(
    endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions
) -> ArrowReadResult:
    """Read one endpoint into Arrow, preserving the adapter's receipt."""

    adapter = registry.connector_for(endpoint)
    return adapter.read(endpoint, options)


def inspect_endpoint(
    endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions
) -> TableInspection:
    """Delegate inspection to the selected adapter."""

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

    result = read_endpoint(source, registry, options)
    write_local(result.table, destination, infer_format(destination, options.to_format))
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

    # Validate before reading so unsupported imports cannot cause provider I/O.
    destination_adapter = registry.require_capability(destination, "table.write")
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
    return endpoint.is_stdio or endpoint.path is not None


def _unsupported(endpoint: Endpoint, message: str) -> ConnectorError:
    scheme = endpoint.uri.scheme if endpoint.uri is not None else "file"
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
    if source_identity != "feishu_bitable" or "_record_id" not in table.column_names:
        return table

    owned = getattr(destination_adapter, "provider_owned_fields", ())
    if not isinstance(owned, Iterable) or "_record_id" not in owned:
        return table
    return table.drop(["_record_id"])


__all__ = ["convert_endpoint", "import_endpoint", "inspect_endpoint", "read_endpoint"]
