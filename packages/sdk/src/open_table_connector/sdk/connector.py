"""Connector protocols and legacy adapter bridge."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

import polars as pl
from open_table_connector.contract import (
    AdapterOptions,
    ConnectorAdapter,
    NeutralReceipt,
    TableWriteResult,
    parse_adapter_endpoint,
)
from open_table_connector.contract import (
    TableInspection as LegacyInspection,
)
from open_table_connector.contract import (
    TableMode as LegacyTableMode,
)

from .model import (
    BaseModeDestination,
    BaseModeTableAddress,
    DatabaseTableAddress,
    DirectDestination,
    DirectTableAddress,
    SheetModeDestination,
    SheetModeTableAddress,
    TableDestination,
    TableMode,
)
from .result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    Outcome,
    Receipt,
    VerificationState,
)
from .table import CapabilitySet, TableBinding, TableInspection


def _legacy_mode_to_sdk(mode: LegacyTableMode) -> TableMode:
    return TableMode.from_wire(mode.value)


def _sdk_mode_to_legacy(mode: TableMode) -> LegacyTableMode:
    return LegacyTableMode.BASE if mode is TableMode.BASE_MODE else LegacyTableMode.SHEET


def _receipt_from_legacy(receipt: NeutralReceipt) -> Receipt:
    return Receipt(
        kind="legacy-physical",
        operation=receipt.capability.capability_id,
        connector_id=receipt.connector.connector_id,
        capability=receipt.capability.to_reference(),
        safe_target=receipt.safe_uri,
        mode=_legacy_mode_to_sdk(receipt.mode),
        details={
            "operation_id": receipt.operation_id,
            "row_count": receipt.row_count,
            "batch_count": receipt.batch_count,
            "source_revision": receipt.source_revision,
            "schema_fingerprint": receipt.schema_fingerprint,
            "content_fingerprint": receipt.content_fingerprint,
        },
    )


def _address_uri(address: object):
    if isinstance(address, DirectTableAddress):
        return address.uri
    if isinstance(address, DatabaseTableAddress):
        return address.database
    if isinstance(address, BaseModeTableAddress):
        return address.container
    if isinstance(address, SheetModeTableAddress):
        return address.grid
    raise TypeError("unsupported table address")


def _destination_uri(destination: TableDestination):
    if isinstance(destination, DirectDestination):
        return destination.uri
    if isinstance(destination, BaseModeDestination):
        return destination.container
    if isinstance(destination, SheetModeDestination):
        return destination.grid
    raise TypeError("unsupported table destination")


def _rejected(message: str, code: ErrorCode, **details: object) -> OperationResult[Any]:
    return OperationResult(
        value=None,
        outcome=Outcome.REJECTED,
        commit=CommitState.NOT_STARTED,
        verification=VerificationState.SKIPPED,
        receipts=(),
        error=ErrorInfo(code=code, message=message, safe_details=details),
    )


@runtime_checkable
class TableConnector(Protocol):
    identity: object
    schemes: tuple[str, ...]
    hosts: tuple[str, ...]
    capabilities: tuple[object, ...]
    modes: tuple[TableMode, ...]
    local: bool
    handles_paths: bool

    def open_table(self, address: object) -> OperationResult[TableBinding]: ...

    def inspect_table(self, binding: TableBinding) -> OperationResult[TableInspection]: ...

    def capabilities_for(self, binding: TableBinding) -> OperationResult[CapabilitySet]: ...

    def read_table(
        self,
        binding: TableBinding,
        *,
        limit: int | None = None,
        continuation: str | None = None,
    ) -> OperationResult[pl.DataFrame]: ...

    def insert_rows(self, binding: TableBinding, frame: pl.DataFrame) -> OperationResult[int]: ...

    def update_rows(
        self,
        binding: TableBinding,
        frame: pl.DataFrame,
        *,
        keys: tuple[str, ...],
    ) -> OperationResult[int]: ...

    def delete_rows(
        self,
        binding: TableBinding,
        *,
        where,
        parameters: Mapping[str, Any] | None = None,
    ) -> OperationResult[int]: ...

    def drop_table(self, binding: TableBinding) -> OperationResult[None]: ...

    def begin_transaction(self, binding: TableBinding) -> object: ...

    def create_table(
        self, source: object, destination: TableDestination
    ) -> OperationResult[TableBinding]: ...

    def close(self) -> None: ...


class LegacyConnectorAdapterBridge:
    def __init__(self, adapter: ConnectorAdapter) -> None:
        self._adapter = adapter
        self.identity = adapter.identity
        self.schemes = tuple(adapter.schemes)
        self.hosts = tuple(getattr(adapter, "hosts", ()))
        self.capabilities = tuple(getattr(adapter, "capabilities", ()))
        self.modes = tuple(_legacy_mode_to_sdk(mode) for mode in getattr(adapter, "modes", ()))
        self.local = bool(getattr(adapter, "local", False))
        self.handles_paths = bool(getattr(adapter, "handles_paths", False))

    def open_table(self, address: object) -> OperationResult[TableBinding]:
        if not isinstance(address, DirectTableAddress):
            return _rejected(
                "legacy adapters only support direct table addresses",
                ErrorCode.UNSUPPORTED_CAPABILITY,
            )
        inspection = self._adapter.inspect(
            parse_adapter_endpoint(address.uri.value), AdapterOptions()
        )
        if not isinstance(inspection, LegacyInspection):
            return _rejected(
                "legacy adapter returned an invalid inspection", ErrorCode.PROTOCOL_FAILURE
            )
        return _rejected(
            "legacy adapter inspection does not expose an exact typed schema for open()",
            ErrorCode.PROTOCOL_FAILURE,
            connector_id=self.identity.connector_id,
            columns=list(inspection.columns),
        )

    def inspect_table(self, binding: TableBinding) -> OperationResult[TableInspection]:
        return OperationResult(
            value=TableInspection(
                uri=binding.uri,
                mode=binding.mode,
                schema=binding.schema,
                observed_revision=binding.observed_revision,
            ),
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.PASSED,
            receipts=(),
        )

    def capabilities_for(self, binding: TableBinding) -> OperationResult[CapabilitySet]:
        del binding
        return OperationResult(
            value=CapabilitySet(
                capability_ids=tuple(capability.capability_id for capability in self.capabilities),
                modes=self.modes,
            ),
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.PASSED,
            receipts=(),
        )

    def read_table(
        self,
        binding: TableBinding,
        *,
        limit: int | None = None,
        continuation: str | None = None,
    ) -> OperationResult[pl.DataFrame]:
        del continuation
        result = self._adapter.read(
            parse_adapter_endpoint(binding.uri.value), AdapterOptions(limit=limit)
        )
        return OperationResult(
            value=pl.from_arrow(result.table),
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.NOT_APPLICABLE,
            verification=VerificationState.PASSED,
            receipts=(_receipt_from_legacy(result.receipt),),
        )

    def insert_rows(self, binding: TableBinding, frame: pl.DataFrame) -> OperationResult[int]:
        del binding
        return _rejected(
            "legacy adapters do not support insert_rows", ErrorCode.UNSUPPORTED_CAPABILITY
        )

    def update_rows(
        self,
        binding: TableBinding,
        frame: pl.DataFrame,
        *,
        keys: tuple[str, ...],
    ) -> OperationResult[int]:
        del binding, frame, keys
        return _rejected(
            "legacy adapters do not support update_rows", ErrorCode.UNSUPPORTED_CAPABILITY
        )

    def delete_rows(
        self,
        binding: TableBinding,
        *,
        where,
        parameters: Mapping[str, Any] | None = None,
    ) -> OperationResult[int]:
        del binding, where, parameters
        return _rejected(
            "legacy adapters do not support delete_rows", ErrorCode.UNSUPPORTED_CAPABILITY
        )

    def drop_table(self, binding: TableBinding) -> OperationResult[None]:
        del binding
        return _rejected(
            "legacy adapters do not support drop_table", ErrorCode.UNSUPPORTED_CAPABILITY
        )

    def begin_transaction(self, binding: TableBinding) -> object:
        del binding
        raise RuntimeError("legacy adapters do not support transactions")

    def create_table(
        self, source: object, destination: TableDestination
    ) -> OperationResult[TableBinding]:
        if not isinstance(destination, DirectDestination):
            return _rejected(
                "legacy adapters only support direct destinations",
                ErrorCode.UNSUPPORTED_CAPABILITY,
            )
        if not isinstance(source, pl.DataFrame):
            return _rejected(
                "legacy adapters currently materialize only DataFrame sources",
                ErrorCode.UNSUPPORTED_CAPABILITY,
            )
        result: TableWriteResult = self._adapter.write(
            parse_adapter_endpoint(destination.uri.value),
            source.to_arrow(),
            AdapterOptions(if_exists="error"),
        )
        return OperationResult(
            value=TableBinding(
                uri=result.receipt.safe_uri,
                mode=_legacy_mode_to_sdk(result.receipt.mode),
                schema=source.schema,
                observed_revision=result.receipt.source_revision,
                connector_id=result.receipt.connector.connector_id,
            ),
            outcome=Outcome.SUCCEEDED,
            commit=CommitState.COMMITTED,
            verification=VerificationState.PASSED,
            receipts=(_receipt_from_legacy(result.receipt),),
        )

    def close(self) -> None:
        close = getattr(self._adapter, "close", None)
        if callable(close):
            close()


__all__ = [
    "LegacyConnectorAdapterBridge",
    "TableConnector",
    "_address_uri",
    "_destination_uri",
    "_sdk_mode_to_legacy",
]
