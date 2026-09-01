"""MaybeSheet Connector transport with explicit Base and Sheet capabilities."""

from __future__ import annotations

import inspect
import json
import math
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

import polars as pl
import pyarrow as pa
from open_table_connector.contract import (
    HOST_MAYBE,
    PROVIDER_JSON,
    SCHEME_HTTPS,
    SCHEME_MAYBE,
    BaseConvention,
    ConnectorError,
    ConnectorErrorCode,
    NeutralReceipt,
    PolarsReadResult,
    ResourceLimits,
    SheetConvention,
    TableMode,
    TableURI,
    TableWriteRequest,
    TableWriteResult,
)
from open_table_connector.contract.fingerprints import (
    arrow_content_fingerprint,
    arrow_schema_fingerprint,
    operation_identity,
)

from .identity import (
    BASE_READ_CAPABILITY,
    CONNECTOR_IDENTITY,
    SHEET_READ_CAPABILITY,
    TABLE_WRITE_CAPABILITY,
)


class ProcessClient(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        *,
        credentials: Mapping[str, str] | None = None,
        stdin: str | None = None,
        timeout: float | int | None = None,
    ) -> Mapping[str, Any]: ...


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


def _strict_json_value(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _strict_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_json_value(item) for item in value]
    return value


def _payload_result(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    result = payload.get("result")
    return result if isinstance(result, Mapping) else payload


def _payload_value(payload: Mapping[str, Any], key: str) -> Any:
    result = payload.get("result")
    if isinstance(result, Mapping) and key in result:
        return result[key]
    return payload.get(key)


def _payload_table(payload: Mapping[str, Any]) -> pa.Table:
    result = _payload_result(payload)
    rows = result.get("rows")
    if isinstance(rows, list) and rows and all(isinstance(row, Mapping) for row in rows):
        names: list[str] = []
        for row in rows:
            for name in row:
                if str(name) not in names:
                    names.append(str(name))
        return pa.Table.from_arrays([pa.array([_cell(row.get(name)) for row in rows], type=pa.large_string()) for name in names], names=names)
    values = result.get("values")
    if isinstance(values, list) and values and isinstance(values[0], list):
        names = [str(value) for value in values[0]]
        records = [list(row) for row in values[1:]]
        return pa.Table.from_arrays([pa.array([_cell(row[index]) if index < len(row) else None for row in records], type=pa.large_string()) for index in range(len(names))], names=names)
    return pa.table({})


def _mbs_target(uri: TableURI) -> str:
    """Translate OTC's opaque maybe:// identity to mbs' canonical HTTP target."""

    if uri.scheme != SCHEME_MAYBE:
        return uri.value
    document_id = urlsplit(uri.value).netloc
    return f"{SCHEME_HTTPS}://{HOST_MAYBE}/docs/spreadsheets/d/{quote(document_id, safe='')}"


class MaybeSheetConnector:
    identity = CONNECTOR_IDENTITY

    def formula_extension_for(self):
        from open_table_connector.formulas import CompositeFormulaConnectorExtension

        from .field_formula import MaybeSheetFieldFormulaExtension
        from .grid_formula import MaybeSheetGridFormulaExtension

        return CompositeFormulaConnectorExtension(
            grid=MaybeSheetGridFormulaExtension(self),
            field=MaybeSheetFieldFormulaExtension(self),
        )

    def __init__(self, process_client: ProcessClient) -> None:
        self._process = process_client

    def read_arrow(self, request: MaybeSheetReadRequest):
        table, receipt = self._read(request)
        from open_table_connector.contract import ArrowReadResult
        return ArrowReadResult(table=table, receipt=receipt)

    def read_polars(self, request: MaybeSheetReadRequest) -> PolarsReadResult:
        table, receipt = self._read(request)
        return PolarsReadResult(frame=pl.from_arrow(table), receipt=receipt)

    def inspect(self, request: MaybeSheetReadRequest):
        from open_table_connector.contract import TableInspection
        table, receipt = self._read(request)
        return TableInspection(safe_uri=request.uri, mode=request.mode, columns=tuple(table.column_names), schema_fingerprint=receipt.schema_fingerprint, row_count=table.num_rows, coordinate_convention=receipt.coordinate_convention, facts={"transport": "process_client"})

    @staticmethod
    def _unsupported(capability: str) -> None:
        raise ConnectorError(
            ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
            f"MaybeSheet capability is not implemented: {capability}",
            {"capability": capability},
        )

    def write(
        self,
        request: TableWriteRequest,
        *,
        credentials: Mapping[str, str] | None = None,
    ) -> TableWriteResult:
        if request.if_exists in {"replace", "error"}:
            raise ConnectorError(
                ConnectorErrorCode.UNSUPPORTED_CAPABILITY,
                "MaybeSheet table writes support append only",
                {"if_exists": request.if_exists},
            )
        if request.if_exists != "append":
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "if_exists must be append for MaybeSheet table writes",
                {"if_exists": request.if_exists},
            )
        if request.table is None or not request.table.strip():
            raise ConnectorError(
                ConnectorErrorCode.INVALID_URI,
                "MaybeSheet table writes require an explicit table",
                {},
            )
        try:
            payload = json.dumps(
                [_strict_json_value(row) for row in request.frame.to_dicts()],
                allow_nan=False,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "MaybeSheet table write serialization failed",
                {"reason": "unexpected serialization exception"},
            ) from None
        try:
            with tempfile.TemporaryDirectory(prefix="otc-mbs-rows-") as directory:
                rows_path = Path(directory) / "rows.json"
                rows_path.write_text(payload, encoding="utf-8")
                argv = (
                    "mbs",
                    "table",
                    "insert",
                    "--target",
                    _mbs_target(request.uri),
                    "--table-name",
                    request.table,
                    "--frame-in",
                    str(rows_path),
                    "--output",
                    PROVIDER_JSON,
                )
                response = self._run_process(argv, credentials=credentials)
        except ConnectorError:
            raise
        except Exception:
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "MaybeSheet process operation failed",
                {"reason": "unexpected process-client exception"},
            ) from None
        revision = "sha256:" + sha256(json.dumps(response, sort_keys=True, default=str).encode()).hexdigest()
        table = request.frame.to_arrow()
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        operation = operation_identity(
            connector=CONNECTOR_IDENTITY,
            capability=TABLE_WRITE_CAPABILITY,
            uri=request.uri,
            source_revision=revision,
            schema_fingerprint=schema,
            content_fingerprint=content,
            parameters={"table": request.table, "if_exists": request.if_exists},
        )
        receipt = NeutralReceipt(
            connector=CONNECTOR_IDENTITY,
            capability=TABLE_WRITE_CAPABILITY,
            operation_id=operation,
            safe_uri=request.uri,
            mode=TableMode.BASE,
            source_revision=revision,
            schema_fingerprint=schema,
            content_fingerprint=content,
            coordinate_convention=BaseConvention(ordinal_snapshot_id=revision),
            row_count=request.frame.height,
            batch_count=1,
            vendor_receipt_ref=(
                str(_payload_value(response, "receipt_id"))
                if _payload_value(response, "receipt_id") is not None
                else str(response["request_id"])
                if response.get("request_id") is not None
                else None
            ),
        )
        inserted_rows = _payload_value(response, "inserted_rows")
        if inserted_rows is None:
            inserted_rows = _payload_value(response, "rows_written")
        return TableWriteResult(
            receipt=receipt,
            affected_rows=int(request.frame.height if inserted_rows is None else inserted_rows),
        )

    def _run_process(
        self,
        argv: tuple[str, ...],
        *,
        credentials: Mapping[str, str] | None = None,
        stdin: str | None = None,
        timeout: float | int | None = None,
    ) -> Mapping[str, Any]:
        kwargs: dict[str, Any] = {"credentials": credentials, "stdin": stdin}
        try:
            parameters = inspect.signature(self._process.run).parameters.values()
        except (TypeError, ValueError):
            parameters = ()
        if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters) or any(
            parameter.name == "timeout" for parameter in parameters
        ):
            kwargs["timeout"] = timeout
        return self._process.run(argv, **kwargs)

    def _read(self, request: MaybeSheetReadRequest):
        verb = "db-table" if request.mode is TableMode.BASE else "excel-worksheet"
        target_option = "--name" if request.mode is TableMode.BASE else "--worksheet-name"
        argv: tuple[str, ...] = (
            "mbs",
            verb,
            "read",
            "--uri",
            _mbs_target(request.uri),
            target_option,
            request.target,
        )
        if request.mode is TableMode.BASE and request.resource_limits.max_rows is not None:
            argv += ("--limit", str(request.resource_limits.max_rows))
        try:
            payload = self._run_process(
                argv,
                credentials=request.credentials,
                timeout=request.resource_limits.timeout_seconds,
            )
        except ConnectorError:
            raise
        except Exception:
            raise ConnectorError(
                ConnectorErrorCode.EXECUTION_FAILED,
                "MaybeSheet process operation failed",
                {"reason": "unexpected process-client exception"},
            ) from None
        table = _payload_table(payload)
        if request.resource_limits.max_rows is not None:
            table = table.slice(0, request.resource_limits.max_rows)
        source = str(_payload_value(payload, "source_revision") or "sha256:" + sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest())
        schema = arrow_schema_fingerprint(table.schema)
        content = arrow_content_fingerprint(table)
        capability = BASE_READ_CAPABILITY if request.mode is TableMode.BASE else SHEET_READ_CAPABILITY
        convention = BaseConvention(ordinal_snapshot_id=source) if request.mode is TableMode.BASE else SheetConvention(sheet=request.target)
        operation = operation_identity(connector=CONNECTOR_IDENTITY, capability=capability, uri=request.uri, source_revision=source, schema_fingerprint=schema, content_fingerprint=content, parameters={"mode": request.mode.value, "target": request.target, "max_rows": request.resource_limits.max_rows})
        receipt = NeutralReceipt(
            connector=CONNECTOR_IDENTITY,
            capability=capability,
            operation_id=operation,
            safe_uri=request.uri,
            mode=request.mode,
            source_revision=source,
            schema_fingerprint=schema,
            content_fingerprint=content,
            coordinate_convention=convention,
            row_count=table.num_rows,
            batch_count=1,
            vendor_receipt_ref=(
                str(_payload_value(payload, "receipt_id"))
                if _payload_value(payload, "receipt_id") is not None
                else str(payload["request_id"])
                if payload.get("request_id") is not None
                else None
            ),
        )
        return table, receipt
