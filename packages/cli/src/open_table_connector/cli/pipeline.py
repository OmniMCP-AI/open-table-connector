"""Arrow-backed orchestration for CLI table operations."""

from __future__ import annotations

from collections.abc import Iterable

import open_table_connector.sdk as otc
import pyarrow as pa
from open_table_connector.contract import (
    SCHEME_FILE,
    ArrowReadResult,
    ConnectorAdapter,
    ConnectorError,
    ConnectorErrorCode,
    PluginDescriptor,
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
    if endpoint.is_stdio or not _should_use_sdk_pipeline(registry):
        return _read_endpoint_legacy(endpoint, registry, options)
    try:
        client = _client_from_registry(registry)
    except otc.OTCError as error:
        if not _should_fallback_to_legacy(error):
            raise
        return _read_endpoint_legacy(endpoint, registry, options)
    try:
        result = client.collect(client.open(_sdk_target(endpoint)).require_value())
        frame = result.require_value()
        receipt = result.receipts[-1] if result.receipts else None
        if receipt is None:
            raise ConnectorError(
                ConnectorErrorCode.PROTOCOL_INVALID,
                "SDK read did not return a receipt for a physical source",
                {"target": _sdk_target(endpoint)},
            )
        return ArrowReadResult(frame.to_arrow(), receipt)
    except otc.OTCError as error:
        if not _should_fallback_to_legacy(error):
            raise
        return _read_endpoint_legacy(endpoint, registry, options)
    finally:
        client.close()


def _read_endpoint_legacy(
    endpoint: Endpoint,
    registry: ConnectorRegistry,
    options: CliOptions,
) -> ArrowReadResult:
    adapter = registry.connector_for(endpoint)
    return adapter.read(endpoint, options)


def inspect_endpoint(
    endpoint: Endpoint, registry: ConnectorRegistry, options: CliOptions
) -> TableInspection:
    """Inspect one endpoint, delegating through the SDK pipeline when enabled."""

    _validate_source_format(endpoint, options, registry)
    if endpoint.is_stdio or not _should_use_sdk_pipeline(registry):
        return _inspect_endpoint_legacy(endpoint, registry, options)
    client = _client_from_registry(registry)
    try:
        table = client.open(_sdk_target(endpoint)).require_value()
        return table.inspect().require_value()
    except otc.OTCError as error:
        if not _should_fallback_to_legacy(error):
            raise
        return _inspect_endpoint_legacy(endpoint, registry, options)
    finally:
        client.close()


def _inspect_endpoint_legacy(
    endpoint: Endpoint,
    registry: ConnectorRegistry,
    options: CliOptions,
) -> TableInspection:
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
    write = getattr(destination_adapter, "write", None)
    if not _should_use_sdk_pipeline(registry) or callable(write):
        result = _read_endpoint_legacy(source, registry, options)
        table = _table_for_destination(result.table, result.receipt, destination_adapter)
        assert callable(write)
        write_result = write(destination, table, options)
        return PipelineSummary(
            status="completed",
            rows_read=result.table.num_rows,
            rows_written=write_result.affected_rows,
            source_receipt=result.receipt,
            destination_receipt=write_result.receipt,
        )
    try:
        client = _client_from_registry(registry)
        source_table = client.open(_sdk_target(source)).require_value()
        source_result = (
            source_table.read_page(limit=options.limit)
            if options.limit is not None
            else source_table.read()
        )
        table = _table_for_destination(
            source_result.require_value().to_arrow(),
            source_result.receipts[-1] if source_result.receipts else None,
            destination_adapter,
        )
        source_receipt = source_result.receipts[-1] if source_result.receipts else None
        materialized = client.materialize(pl_from_arrow(table), to=_sdk_target(destination))
        destination_table = materialized.require_value()
        destination_receipt = materialized.receipts[-1] if materialized.receipts else None
    except otc.OTCError as error:
        if not _should_fallback_to_legacy(error):
            raise
        result = _read_endpoint_legacy(source, registry, options)
        table = _table_for_destination(result.table, result.receipt, destination_adapter)
        write_result = destination_adapter.write(destination, table, options)
        return PipelineSummary(
            status="completed",
            rows_read=result.table.num_rows,
            rows_written=write_result.affected_rows,
            source_receipt=result.receipt,
            destination_receipt=write_result.receipt,
        )
    finally:
        if "client" in locals():
            client.close()
    return PipelineSummary(
        status="completed",
        rows_read=table.num_rows,
        rows_written=table.num_rows,
        source_receipt=source_receipt,
        destination_receipt=destination_receipt or destination_table.uri,
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


def _client_from_registry(registry: ConnectorRegistry) -> otc.Client:
    listed = registry.list()
    if listed and isinstance(listed[0], PluginDescriptor):
        return _client_from_descriptors(registry, listed)
    connectors = [
        item if isinstance(item, otc.TableConnector) else otc.LegacyConnectorAdapterBridge(item)
        for item in listed
    ]
    return otc.Client(registry=otc.ConnectorRegistry(connectors))


def _client_from_descriptors(
    registry: ConnectorRegistry,
    descriptors: tuple[PluginDescriptor, ...],
) -> otc.Client:
    providers = {
        item.config.provider_id: item.config
        for item in getattr(registry, "_plugins", ())
        if hasattr(item, "config")
    }
    resolver_config = getattr(getattr(registry, "_resolver", None), "_config", None)
    credentials = {}
    if resolver_config is not None:
        credentials = {
            reference: {
                field: otc.CredentialBinding(binding.env)
                for field, binding in bindings.items()
            }
            for reference, bindings in resolver_config.credentials.items()
        }
    config = otc.ClientConfig(providers=providers, credentials=credentials)
    environ = getattr(registry, "_environ", {})
    return otc.Client.from_config(
        config,
        descriptors=descriptors,
        resolver=otc.EnvironmentCredentialResolver(config, environ),
        environ=environ,
        transports=getattr(registry, "_transports", {}),
    )


def _sdk_target(endpoint: Endpoint) -> str:
    if endpoint.uri is not None:
        return endpoint.uri.value
    if endpoint.path is not None:
        return endpoint.path.resolve().as_uri()
    return "stdio://stdin"


def pl_from_arrow(table: pa.Table):
    import polars as pl

    return pl.from_arrow(table)


def _should_fallback_to_legacy(error: otc.OTCError) -> bool:
    return error.result.error is not None and error.result.error.code in {
        otc.ErrorCode.PROTOCOL_FAILURE,
        otc.ErrorCode.UNSUPPORTED_CAPABILITY,
    }


def _should_use_sdk_pipeline(registry: object) -> bool:
    listed = registry.list() if hasattr(registry, "list") else ()
    # Explicitly registered CLI adapters are the legacy compatibility seam.
    # Descriptor-backed SDK connectors still use the normalized OTC pipeline,
    # while manually injected adapters retain their Arrow/receipt contract.
    if getattr(registry, "_manual_adapters", ()):
        return False
    return (
        bool(getattr(registry, "_use_sdk_pipeline", False))
        or isinstance(registry, otc.ConnectorRegistry)
        or bool(listed and isinstance(listed[0], PluginDescriptor))
    )


__all__ = ["convert_endpoint", "import_endpoint", "inspect_endpoint", "read_endpoint"]
