"""SDK Client surface."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from open_table_connector.contract import PluginDescriptor, TableURI

from .config import ClientConfig
from .connector import _address_uri, _destination_uri
from .credentials import CredentialResolver
from .model import DirectDestination, DirectTableAddress, ExistingTableAddress, TableDestination
from .registry import ConnectorRegistry
from .result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    OTCError,
    Outcome,
    VerificationState,
)
from .table import Table, TableBinding


def _failure(message: str, code: ErrorCode, **details: object) -> OTCError:
    result = OperationResult[None](
        value=None,
        outcome=Outcome.REJECTED,
        commit=CommitState.NOT_STARTED,
        verification=VerificationState.SKIPPED,
        receipts=(),
        error=ErrorInfo(code=code, message=message, safe_details=details),
    )
    return OTCError(message, result)


class Client:
    def __init__(self, *, registry: ConnectorRegistry) -> None:
        self._registry = registry
        self._closed = False
        self._client_id = str(uuid.uuid4())

    @classmethod
    def from_config(
        cls,
        config: ClientConfig,
        *,
        descriptors: Iterable[PluginDescriptor],
        resolver: CredentialResolver | None = None,
        environ: dict[str, str] | None = None,
        transports: dict[str, Any] | None = None,
    ) -> Client:
        registry = ConnectorRegistry.from_descriptors(
            descriptors,
            config,
            resolver=resolver,
            environ=environ,
            transports=transports,
        )
        return cls(registry=registry)

    def open(self, target: str | TableURI | ExistingTableAddress):
        self._assert_open()
        address = DirectTableAddress(target) if isinstance(target, (str, TableURI)) else target
        connector = self._registry.connector_for(_address_uri(address).value)
        result = connector.open_table(address)
        delivered = self._deliver(result)
        return replace(delivered, value=self._wrap_binding(delivered.require_value()))

    def materialize(self, source: object, *, to: str | TableDestination):
        self._assert_open()
        destination = DirectDestination(to) if isinstance(to, str) else to
        if isinstance(source, Table):
            self._assert_owned(source)
            source_value = source
        else:
            source_value = source
        connector = self._registry.connector_for(_destination_uri(destination).value)
        result = connector.create_table(
            source_value if not isinstance(source_value, Table) else source_value, destination
        )
        delivered = self._deliver(result)
        return replace(delivered, value=self._wrap_binding(delivered.require_value()))

    def close(self) -> None:
        if self._closed:
            return
        self._registry.close()
        self._closed = True

    def _wrap_binding(self, binding: TableBinding) -> Table:
        table = Table(self, binding)
        object.__setattr__(table, "_owner_client_id", self._client_id)
        return table

    def _assert_open(self) -> None:
        if self._closed:
            raise _failure("client is closed", ErrorCode.CLIENT_CLOSED)

    def _assert_owned(self, table: Table) -> None:
        if getattr(table, "_owner_client_id", None) != self._client_id:
            raise _failure(
                "foreign physical handles must be reopened on this client", ErrorCode.INVALID_TARGET
            )

    def _connector_for_binding(self, binding: TableBinding):
        self._assert_open()
        return self._registry.connector_for(binding.uri.value)

    def _deliver(self, result):
        if result.outcome in {Outcome.SUCCEEDED, Outcome.PLANNED}:
            return result
        assert result.error is not None
        raise OTCError(result.error.message, result)


__all__ = ["Client"]
