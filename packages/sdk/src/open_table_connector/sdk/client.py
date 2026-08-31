"""SDK Client surface."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import replace
from time import monotonic_ns
from typing import Any

import polars as pl
from open_table_connector.contract import PluginDescriptor, TableURI, parse_adapter_endpoint

from .config import ClientConfig
from .connector import _destination_uri
from .credentials import CredentialResolver
from .model import DirectDestination, DirectTableAddress, ExistingTableAddress, TableDestination
from .query import Query, QueryLane, SqlResourceLimits
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
from .sql import NativeSql, PolarsPlanMapper, SqlResourceLimitError, execution_receipt
from .sql import sql as prepare_sql
from .table import Table, TableBinding
from .temporal import execute_temporal_query


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
        route_target, address = self._normalize_open_target(target)
        connector = self._registry.connector_for(route_target)
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

    def collect(self, source: object) -> OperationResult[pl.DataFrame]:
        self._assert_open()
        if isinstance(source, pl.DataFrame):
            return OperationResult(
                value=source.clone(),
                outcome=Outcome.SUCCEEDED,
                commit=CommitState.NOT_APPLICABLE,
                verification=VerificationState.NOT_APPLICABLE,
                receipts=(),
            )
        if isinstance(source, Table):
            self._assert_owned(source)
            return source.read()
        if isinstance(source, Query):
            self._assert_query_affinity(source)
            if source.lane is QueryLane.TEMPORAL:
                return execute_temporal_query(self, source)
            started_ns = monotonic_ns()
            mapper = PolarsPlanMapper()
            frames: dict[str, pl.DataFrame] = {}
            receipts = []
            source_rows = 0
            source_bytes = 0
            for name, bound_source in source.sources.items():
                result = self.collect(bound_source)
                frame = result.require_value()
                frame_bytes = int(frame.estimated_size())
                try:
                    self._check_sql_limit(
                        frame.height, source.limits.max_source_rows, "max_source_rows"
                    )
                    self._check_sql_limit(
                        frame_bytes, source.limits.max_source_bytes, "max_source_bytes"
                    )
                    source_rows += frame.height
                    source_bytes += frame_bytes
                    self._check_sql_limit(
                        source_rows,
                        source.limits.max_total_input_rows,
                        "max_total_input_rows",
                    )
                    self._check_sql_limit(
                        source_bytes,
                        source.limits.max_total_input_bytes,
                        "max_total_input_bytes",
                    )
                    self._check_sql_duration(started_ns, source.limits.max_duration_ms)
                except SqlResourceLimitError as exc:
                    raise _failure(str(exc), ErrorCode.RESOURCE_LIMIT) from exc
                frames[name] = frame
                receipts.extend(result.receipts)
            try:
                frame = mapper.execute(source, frames)
                self._check_sql_duration(started_ns, source.limits.max_duration_ms)
            except SqlResourceLimitError as exc:
                raise _failure(str(exc), ErrorCode.RESOURCE_LIMIT) from exc
            except ValueError as exc:
                raise _failure(str(exc), ErrorCode.INVALID_SQL) from exc
            elapsed_ms = (monotonic_ns() - started_ns) // 1_000_000
            return OperationResult(
                value=frame,
                outcome=Outcome.SUCCEEDED,
                commit=CommitState.NOT_APPLICABLE,
                verification=VerificationState.PASSED,
                receipts=(
                    *receipts,
                    execution_receipt(
                        source,
                        frame,
                        source_rows=source_rows,
                        source_bytes=source_bytes,
                        elapsed_ms=elapsed_ms,
                    ),
                ),
            )
        raise _failure(
            "collect expects a DataFrame, Table, or Query source",
            ErrorCode.INVALID_TARGET,
            source_type=type(source).__name__,
        )

    def sql(
        self,
        statement: str,
        *,
        sources: dict[str, object],
        parameters: dict[str, Any] | None = None,
        limits: SqlResourceLimits | None = None,
    ) -> OperationResult[pl.DataFrame]:
        return self.collect(
            prepare_sql(
                statement,
                sources=sources,
                parameters=parameters,
                limits=limits,
            )
        )

    def native_sql(self, target: str | TableURI) -> NativeSql:
        self._assert_open()
        return NativeSql(self, target)

    def close(self) -> None:
        if self._closed:
            return
        self._registry.close()
        self._closed = True

    def _wrap_binding(self, binding: TableBinding) -> Table:
        table = Table(self, binding)
        object.__setattr__(table, "_owner_client_id", self._client_id)
        return table

    def _normalize_open_target(
        self, target: str | TableURI | ExistingTableAddress
    ) -> tuple[str | ExistingTableAddress, str | ExistingTableAddress]:
        if isinstance(target, TableURI):
            address = DirectTableAddress(target)
            return address, address
        if isinstance(target, str):
            endpoint = parse_adapter_endpoint(target)
            if endpoint.path is not None or endpoint.is_stdio:
                return target, target
            address = DirectTableAddress(endpoint.uri)
            return address, address
        return target, target

    def _assert_open(self) -> None:
        if self._closed:
            raise _failure("client is closed", ErrorCode.CLIENT_CLOSED)

    def _assert_owned(self, table: Table) -> None:
        if getattr(table, "_owner_client_id", None) != self._client_id:
            raise _failure(
                "foreign physical handles must be reopened on this client", ErrorCode.INVALID_TARGET
            )

    def _assert_query_affinity(self, query: Query) -> None:
        visited: set[int] = set()
        active: set[int] = set()

        def visit(candidate: Query) -> None:
            identity = id(candidate)
            if identity in active:
                raise _failure("query source graph contains a cycle", ErrorCode.INVALID_SQL)
            if identity in visited:
                return
            active.add(identity)
            for bound_source in candidate.sources.values():
                if isinstance(bound_source, Table):
                    if getattr(bound_source, "_owner_client_id", None) != self._client_id:
                        raise _failure(
                            "query source graph contains a physical handle from another client",
                            ErrorCode.CLIENT_AFFINITY_MISMATCH,
                        )
                elif isinstance(bound_source, Query):
                    visit(bound_source)
            active.remove(identity)
            visited.add(identity)

        visit(query)

    @staticmethod
    def _check_sql_limit(observed: int, allowed: int, label: str) -> None:
        if observed > allowed:
            raise SqlResourceLimitError(f"query exceeded {label}")

    @staticmethod
    def _check_sql_duration(started_ns: int, max_duration_ms: int) -> None:
        elapsed_ms = (monotonic_ns() - started_ns) // 1_000_000
        Client._check_sql_limit(elapsed_ms, max_duration_ms, "max_duration_ms")

    def _connector_for_binding(self, binding: TableBinding):
        self._assert_open()
        return self._registry.connector_for(binding.uri.value)

    def _deliver(self, result):
        if result.outcome in {Outcome.SUCCEEDED, Outcome.PLANNED}:
            return result
        assert result.error is not None
        raise OTCError(result.error.message, result)


__all__ = ["Client"]
