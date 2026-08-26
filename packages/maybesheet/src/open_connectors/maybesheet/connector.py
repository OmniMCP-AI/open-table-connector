"""MaybeSheet Connector transport with explicit Base and Sheet capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
import subprocess
from typing import Any, Mapping, Protocol

import polars as pl
import pyarrow as pa

from open_connectors.contract import BaseConvention, ConnectorError, ConnectorErrorCode, NeutralReceipt, PolarsReadResult, ResourceLimits, SheetConvention, TableMode, TableURI
from open_connectors.contract.fingerprints import arrow_content_fingerprint, arrow_schema_fingerprint, operation_identity

from .identity import BASE_READ_CAPABILITY, CONNECTOR_IDENTITY, SHEET_READ_CAPABILITY


class ProcessClient(Protocol):
    def run(self, argv: tuple[str, ...], *, credentials: Mapping[str, str] | None = None) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class SubprocessProcessClient:
    """Small injected process boundary owned by the neutral Connector.

    Credentials never enter the URI or argv. They are passed only as
    explicitly prefixed environment values, and callers may inject a fake
    ProcessClient for cassette/replay or tests.
    """

    binary: str = "mbs"
    timeout_seconds: float = 120.0
    environment: Mapping[str, str] = field(default_factory=dict)

    def run(self, argv: tuple[str, ...], *, credentials: Mapping[str, str] | None = None) -> Mapping[str, Any]:
        command = tuple(argv)
        if not command or command[0] != self.binary:
            command = (self.binary, *command)
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in self.environment.items()})
        for key, value in (credentials or {}).items():
            safe_key = "MAYBESHEET_" + "".join(character if character.isalnum() else "_" for character in str(key).upper())
            env[safe_key] = str(value)
        try:
            completed = subprocess.run(
                list(command),
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConnectorError(ConnectorErrorCode.TIMEOUT, "MaybeSheet process timed out", {"timeout_seconds": self.timeout_seconds}) from exc
        if completed.returncode != 0:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "MaybeSheet process failed", {"returncode": completed.returncode, "stderr": completed.stderr[-500:]})
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "MaybeSheet process returned invalid JSON", {}) from exc
        if not isinstance(payload, Mapping):
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "MaybeSheet process returned a non-object payload", {})
        return payload


@dataclass(frozen=True)
class MaybeSheetReadRequest:
    uri: TableURI
    mode: TableMode
    target: str
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    credentials: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in {TableMode.BASE, TableMode.SHEET}:
            raise ValueError("MaybeSheet mode must be base or sheet")
        if not self.target.strip():
            raise ValueError("MaybeSheet target is required")
        object.__setattr__(self, "credentials", dict(self.credentials))


def _cell(value: Any) -> str | None:
    return None if value is None else value if isinstance(value, str) else str(value)


def _payload_table(payload: Mapping[str, Any]) -> pa.Table:
    rows = payload.get("rows")
    if isinstance(rows, list) and rows and all(isinstance(row, Mapping) for row in rows):
        names: list[str] = []
        for row in rows:
            for name in row:
                if str(name) not in names:
                    names.append(str(name))
        return pa.Table.from_arrays([pa.array([_cell(row.get(name)) for row in rows], type=pa.large_string()) for name in names], names=names)
    values = payload.get("values")
    if isinstance(values, list) and values and isinstance(values[0], list):
        names = [str(value) for value in values[0]]
        records = [list(row) for row in values[1:]]
        return pa.Table.from_arrays([pa.array([_cell(row[index]) if index < len(row) else None for row in records], type=pa.large_string()) for index in range(len(names))], names=names)
    return pa.table({})


class MaybeSheetConnector:
    identity = CONNECTOR_IDENTITY

    def __init__(self, process_client: ProcessClient) -> None:
        self._process = process_client

    def read_arrow(self, request: MaybeSheetReadRequest):
        table, receipt = self._read(request)
        from open_connectors.contract import ArrowReadResult
        return ArrowReadResult(table=table, receipt=receipt)

    def read_polars(self, request: MaybeSheetReadRequest) -> PolarsReadResult:
        table, receipt = self._read(request)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=receipt)

    def inspect(self, request: MaybeSheetReadRequest):
        from open_connectors.contract import TableInspection
        table, receipt = self._read(request)
        return TableInspection(safe_uri=request.uri, mode=request.mode, columns=tuple(table.column_names), schema_fingerprint=receipt.schema_fingerprint, row_count=table.num_rows, coordinate_convention=receipt.coordinate_convention, facts={"transport": "process_client"})

    @staticmethod
    def _unsupported(capability: str) -> None:
        raise ConnectorError(
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            f"MaybeSheet capability is not implemented: {capability}",
            {"capability": capability},
        )

    def write(self, request: Any) -> None:
        """Explicit placeholder until governed Base/Sheet writes are ported."""

        del request
        self._unsupported("table.write")

    def calculate_formulas(self, request: Any) -> None:
        """MaybeSheet formula calculation remains outside this read slice."""

        del request
        self._unsupported("formula.calculate")

    def read_formula_values(self, request: Any) -> None:
        """Value-only reads are never accepted as formula evidence."""

        del request
        self._unsupported("formula.readback")

    def _read(self, request: MaybeSheetReadRequest):
        verb = "db-table" if request.mode is TableMode.BASE else "excel-worksheet"
        argv = ("mbs", verb, "read", "--uri", request.uri.value, "--target", request.target)
        if request.resource_limits.max_rows is not None:
            argv += ("--limit", str(request.resource_limits.max_rows))
        try:
            payload = self._process.run(argv, credentials=request.credentials)
        except Exception as exc:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "MaybeSheet process operation failed", {"reason": str(exc)}) from None
        table = _payload_table(payload)
        source = str(payload.get("source_revision") or "sha256:" + sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest())
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        capability = BASE_READ_CAPABILITY if request.mode is TableMode.BASE else SHEET_READ_CAPABILITY
        convention = BaseConvention(ordinal_snapshot_id=source) if request.mode is TableMode.BASE else SheetConvention(sheet=request.target)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=capability, uri=request.uri, source_revision=source, schema_fingerprint=schema, content_fingerprint=content, parameters={"mode": request.mode.value, "target": request.target, "max_rows": request.resource_limits.max_rows})
        receipt = NeutralReceipt(connector=CONNECTOR_IDENTITY, capability=capability, operation_id=operation, safe_uri=request.uri, mode=request.mode, source_revision=source, schema_fingerprint=schema, content_fingerprint=content, coordinate_convention=convention, row_count=table.num_rows, batch_count=1, vendor_receipt_ref=str(payload["receipt_id"]) if payload.get("receipt_id") is not None else None)
        return table, receipt
