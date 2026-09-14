"""Native, create-only Maybe Base materialization over the ``mbs`` process API."""

from __future__ import annotations

import inspect
import json
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import polars as pl
from open_table_connector.contract import (
    HOST_MAYBE,
    PROVIDER_JSON,
    SCHEME_HTTPS,
    ConnectorError,
    ConnectorErrorCode,
    MaterializationCapability,
    TableURI,
)
from open_table_connector.contract import (
    TableMode as ContractTableMode,
)
from open_table_connector.sdk.connector import ArrowTableCarrier, LegacyConnectorAdapterBridge
from open_table_connector.sdk.materialization import (
    MATERIALIZE_CREATE_CAPABILITY,
    PORTABLE_TABLE_PROFILE_V1,
    MaterializationRequest,
)
from open_table_connector.sdk.model import BaseModeDestination, BaseModeTableAddress, TableMode
from open_table_connector.sdk.result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    Outcome,
    Receipt,
    ReconciliationReference,
    VerificationState,
)
from open_table_connector.sdk.table import TableBinding

from .connector import ProcessClient
from .identity import CONNECTOR_IDENTITY

_CAPABILITIES = frozenset(
    {
        "db-table.create.typed/v1",
        "db-table.read-by-id/v1",
        "db-table.idempotency/v1",
        "db-table.reconcile/v1",
    }
)
_CREATE_COMMAND = {"version": "1.0", "schema": "mbs.db-table-create-result/v1"}
_RECONCILE_COMMAND = {"version": "1.0", "schema": "mbs.db-table-reconcile-result/v1"}
_DOCUMENT_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_ROWS = 1_000_000
_MAX_BYTES = 256 * 1024 * 1024


def probe_native_materialization(client: ProcessClient) -> bool:
    """Prove every provider guarantee required for portable Base creation."""

    try:
        payload = _run(client, ("mbs", "db-table", "describe", "--format", PROVIDER_JSON))
    except Exception:
        return False
    if not isinstance(payload, Mapping) or set(payload) != {
        "schema_version",
        "provider_identity",
        "capabilities",
        "commands",
    }:
        return False
    return (
        payload.get("schema_version") == "mbs.db-table-describe/v1"
        and isinstance(payload.get("provider_identity"), str)
        and bool(payload["provider_identity"].strip())
        and isinstance(payload.get("capabilities"), list)
        and _CAPABILITIES.issubset(set(payload["capabilities"]))
        and isinstance(payload.get("commands"), Mapping)
        and payload["commands"].get("create") == _CREATE_COMMAND
        and payload["commands"].get("reconcile") == _RECONCILE_COMMAND
    )


def _run(client: ProcessClient, argv: tuple[str, ...]) -> Mapping[str, Any]:
    kwargs: dict[str, Any] = {"credentials": None, "stdin": None}
    try:
        parameters = inspect.signature(client.run).parameters.values()
    except (TypeError, ValueError):
        parameters = ()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters) or any(
        parameter.name == "timeout" for parameter in parameters
    ):
        kwargs["timeout"] = None
    result = client.run(argv, **kwargs)
    if not isinstance(result, Mapping):
        raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "MaybeSheet returned a non-object payload", {})
    return result


def _canonical_destination(destination: BaseModeDestination) -> tuple[TableURI, str]:
    uri = destination.container
    parsed = urlsplit(uri.value)
    document_id = parsed.path.removeprefix("/docs/spreadsheets/d/")
    canonical = f"https://{HOST_MAYBE}/docs/spreadsheets/d/{quote(document_id, safe='')}"
    if (
        parsed.scheme != SCHEME_HTTPS
        or parsed.hostname != HOST_MAYBE
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not _DOCUMENT_ID.fullmatch(document_id)
        or parsed.path != f"/docs/spreadsheets/d/{document_id}"
        or uri.value != canonical
    ):
        raise ValueError("Maybe Base materialization requires a canonical Maybe document HTTPS URL")
    name = destination.table_name
    if len(name) > 256 or any(ord(character) < 32 for character in name):
        raise ValueError("Maybe Base materialization table_name is invalid")
    return TableURI(canonical), document_id


def _value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise ValueError(f"Maybe native create cannot represent {type(value).__name__}")


def _native_payload(request: MaterializationRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    if request.row_count > _MAX_ROWS or request.source.estimated_size() > _MAX_BYTES:
        raise OverflowError("Maybe Base materialization exceeds provider resource limits")
    schema = {"fields": [{"name": name, "type": str(dtype)} for name, dtype in request.source.schema.items()]}
    rows = {"rows": [[_value(value) for value in row] for row in request.source.iter_rows()]}
    return schema, rows


def _result(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    result = payload.get("result")
    return result if isinstance(result, Mapping) else payload


def _provider_error(payload: Mapping[str, Any]) -> str | None:
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("code")
    return code if isinstance(code, str) else None


def _provider_pre_effect(payload: Mapping[str, Any]) -> bool:
    error = payload.get("error")
    return isinstance(error, Mapping) and error.get("pre_mutation") is True


def _create_result(payload: Mapping[str, Any], *, document_id: str, key: str, row_count: int) -> dict[str, Any]:
    if payload.get("schema_version") != "mbs.db-table-create-result/v1":
        raise ValueError("Maybe create response has an unsupported schema version")
    result = _result(payload)
    required = {
        "document_id",
        "table_id",
        "provider_revision",
        "affected_rows",
        "idempotency_key",
        "receipt_id",
    }
    if set(result) != required:
        raise ValueError("Maybe create response fields are invalid")
    if (
        result["document_id"] != document_id
        or result["idempotency_key"] != key
        or result["affected_rows"] != row_count
        or not all(isinstance(result[name], str) and result[name].strip() for name in required - {"affected_rows"})
    ):
        raise ValueError("Maybe create response does not match the request")
    return dict(result)


def _reconcile_result(
    payload: Mapping[str, Any], *, document_id: str, key: str
) -> dict[str, Any]:
    if payload.get("schema_version") != "mbs.db-table-reconcile-result/v1":
        raise ValueError("Maybe reconcile response has an unsupported schema version")
    result = _result(payload)
    required = {
        "document_id",
        "table_id",
        "provider_revision",
        "affected_rows",
        "idempotency_key",
        "receipt_id",
    }
    if set(result) != required or result.get("document_id") != document_id or result.get("idempotency_key") != key:
        raise ValueError("Maybe reconcile response does not match the reference")
    if not isinstance(result.get("affected_rows"), int) or result["affected_rows"] < 0:
        raise ValueError("Maybe reconcile response has an invalid affected row count")
    if not all(isinstance(result[name], str) and result[name].strip() for name in required - {"affected_rows"}):
        raise ValueError("Maybe reconcile response fields are invalid")
    return dict(result)


def _read_result(payload: Mapping[str, Any], address: BaseModeTableAddress) -> tuple[pl.DataFrame, str, str | None]:
    if payload.get("schema_version") != "mbs.db-table-read-result/v1":
        raise ValueError("Maybe stable-ID read response has an unsupported schema version")
    result = _result(payload)
    required = {
        "document_id",
        "table_id",
        "provider_revision",
        "source_revision",
        "schema",
        "rows",
        "receipt_id",
    }
    document_id = urlsplit(address.container.value).path.rsplit("/", 1)[-1]
    if set(result) != required or result.get("document_id") != document_id or result.get("table_id") != address.table_id:
        raise ValueError("Maybe stable-ID read identity does not match the requested table")
    revision = result.get("provider_revision")
    if not isinstance(revision, str) or not revision.strip() or result.get("source_revision") != revision:
        raise ValueError("Maybe stable-ID read revision is invalid")
    schema = result.get("schema")
    rows = result.get("rows")
    if not isinstance(schema, Mapping) or set(schema) != {"fields"} or not isinstance(schema["fields"], list) or not isinstance(rows, list):
        raise ValueError("Maybe stable-ID read typed carrier is malformed")
    fields = schema["fields"]
    if not fields or not all(isinstance(field, Mapping) and set(field) == {"name", "type"} for field in fields):
        raise ValueError("Maybe stable-ID read schema fields are malformed")
    if not all(isinstance(field["name"], str) and field["name"].strip() and isinstance(field["type"], str) for field in fields):
        raise ValueError("Maybe stable-ID read schema field values are malformed")
    if len({field["name"] for field in fields}) != len(fields) or not all(isinstance(row, list) and len(row) == len(fields) for row in rows):
        raise ValueError("Maybe stable-ID read rows are malformed")
    try:
        from open_table_connector.sdk.model import _dtype_from_wire

        frame = pl.DataFrame(
            {
                field["name"]: pl.Series(
                    field["name"],
                    [row[index] for row in rows],
                    dtype=_dtype_from_wire(field["type"]),
                )
                for index, field in enumerate(fields)
            }
        )
    except Exception as exc:
        raise ValueError("Maybe stable-ID typed values are invalid") from exc
    receipt_id = result.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id.strip():
        raise ValueError("Maybe stable-ID read receipt is invalid")
    return frame, revision, receipt_id


def _receipt(operation: str, uri: TableURI, *, details: Mapping[str, Any]) -> Receipt:
    return Receipt(
        "physical",
        operation,
        CONNECTOR_IDENTITY.connector_id,
        f"{operation}/1.0",
        uri,
        TableMode.BASE_MODE,
        details,
    )


@dataclass
class MaybeSheetSdkConnector:
    """SDK connector that adds native create/reconcile to the legacy read facade."""

    adapter: Any

    def __post_init__(self) -> None:
        self._legacy = LegacyConnectorAdapterBridge(self.adapter)
        self.identity = self.adapter.identity
        self.schemes = tuple(self.adapter.schemes)
        self.hosts = tuple(self.adapter.hosts)
        self.modes = self._legacy.modes
        self.local = False
        self.handles_paths = False
        self._native: bool | None = None

    def _native_supported(self) -> bool:
        if self._native is None:
            self._native = probe_native_materialization(self.adapter.connector._process)
        return self._native

    @property
    def capabilities(self):
        return tuple(self._legacy.capabilities) + (
            (MATERIALIZE_CREATE_CAPABILITY,) if self._native_supported() else ()
        )

    @property
    def materialization(self):
        return (
            (
                MaterializationCapability(
                    MATERIALIZE_CREATE_CAPABILITY,
                    (PORTABLE_TABLE_PROFILE_V1,),
                    (ContractTableMode.BASE,),
                ),
            )
            if self._native_supported()
            else ()
        )

    def __getattr__(self, name: str):
        return getattr(self._legacy, name)

    def _unsupported(self) -> OperationResult[TableBinding]:
        return OperationResult(
            None,
            Outcome.REJECTED,
            CommitState.NOT_STARTED,
            VerificationState.SKIPPED,
            (),
            error=ErrorInfo(ErrorCode.UNSUPPORTED_CAPABILITY, "Maybe process did not prove native Base create support"),
        )

    def _read_by_id(self, address: BaseModeTableAddress) -> tuple[TableBinding, pl.DataFrame, Receipt]:
        payload = self.adapter.connector._run_process(
            (
                "mbs",
                "db-table",
                "read",
                "--uri",
                address.container.value,
                "--table-id",
                address.table_id,
            ),
            credentials=self.adapter.credentials,
            timeout=self.adapter.timeout_seconds,
        )
        frame, revision, vendor_receipt_id = _read_result(payload, address)
        binding = TableBinding(
            address.container,
            TableMode.BASE_MODE,
            frame.schema,
            revision,
            self.identity.connector_id,
            PORTABLE_TABLE_PROFILE_V1,
            frame.height,
            None,
            None,
            address,
        )
        return binding, frame, _receipt(
            "table.read",
            address.container,
            details={
                "table_id": address.table_id,
                "provider_revision": revision,
                "vendor_receipt_id": vendor_receipt_id,
            },
        )

    def open_table(self, address: object) -> OperationResult[TableBinding]:
        if isinstance(address, BaseModeTableAddress) and address.container.scheme == SCHEME_HTTPS:
            try:
                binding, _, receipt = self._read_by_id(address)
            except Exception as exc:
                return OperationResult(
                    None,
                    Outcome.REJECTED,
                    CommitState.NOT_APPLICABLE,
                    VerificationState.SKIPPED,
                    (),
                    error=ErrorInfo(ErrorCode.EXECUTION_FAILED, "Maybe stable-ID read failed", {"reason": type(exc).__name__}),
                )
            return OperationResult(binding, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.PASSED, (receipt,))
        return self._legacy.open_table(address)

    def read_table(self, binding: TableBinding, *, limit: int | None = None, continuation: str | None = None):
        if isinstance(binding.address, BaseModeTableAddress):
            try:
                _, frame, receipt = self._read_by_id(binding.address)
                if limit is not None:
                    frame = frame.head(limit)
                return OperationResult(ArrowTableCarrier(frame.to_arrow()), Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.PASSED, (receipt,))
            except Exception as exc:
                return OperationResult(None, Outcome.REJECTED, CommitState.NOT_APPLICABLE, VerificationState.SKIPPED, (), error=ErrorInfo(ErrorCode.EXECUTION_FAILED, "Maybe stable-ID read failed", {"reason": type(exc).__name__}))
        return self._legacy.read_table(binding, limit=limit, continuation=continuation)

    def create_table(self, source: object, destination: object = None) -> OperationResult[TableBinding]:
        if not isinstance(source, MaterializationRequest):
            return self._legacy.create_table(source, destination)
        if not self._native_supported():
            return self._unsupported()
        try:
            if not isinstance(source.destination, BaseModeDestination):
                raise ValueError("Maybe native create requires a BaseModeDestination")
            uri, document_id = _canonical_destination(source.destination)
            schema, rows = _native_payload(source)
        except OverflowError as exc:
            return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(ErrorCode.RESOURCE_LIMIT, str(exc)))
        except Exception as exc:
            return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(ErrorCode.INVALID_SCHEMA if "represent" in str(exc) else ErrorCode.INVALID_TARGET, str(exc)))
        operation_id = f"maybe-create:{source.content_fingerprint}"
        reconciliation = ReconciliationReference(operation_id, self.identity.connector_id, source.idempotency_key)
        try:
            with tempfile.TemporaryDirectory(prefix="otc-mbs-create-") as directory:
                schema_path = Path(directory) / "schema.json"
                rows_path = Path(directory) / "rows.json"
                schema_path.write_text(json.dumps(schema, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                rows_path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
                payload = self.adapter.connector._run_process(
                    (
                        "mbs", "db-table", "create", "--uri", uri.value,
                        "--table-name", source.destination.table_name,
                        "--schema-in", str(schema_path), "--frame-in", str(rows_path),
                        "--idempotency-key", source.idempotency_key,
                    ),
                    credentials=self.adapter.credentials,
                    timeout=self.adapter.timeout_seconds,
                )
        except ConnectorError:
            return OperationResult(None, Outcome.UNKNOWN, CommitState.UNKNOWN, VerificationState.UNAVAILABLE, (), error=ErrorInfo(ErrorCode.UNCERTAIN_MUTATION, "Maybe create response was lost; reconcile with the same idempotency key", reconciliation=reconciliation))
        except Exception as exc:
            return OperationResult(None, Outcome.UNKNOWN, CommitState.UNKNOWN, VerificationState.UNAVAILABLE, (), error=ErrorInfo(ErrorCode.UNCERTAIN_MUTATION, "Maybe create response is unavailable; reconcile with the same idempotency key", {"reason": type(exc).__name__}, reconciliation))
        code = _provider_error(payload)
        if code == "duplicate_name" and _provider_pre_effect(payload):
            return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(ErrorCode.DESTINATION_EXISTS, "Maybe table name already exists"))
        if code == "idempotency_conflict" and _provider_pre_effect(payload):
            return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(ErrorCode.IDEMPOTENCY_CONFLICT, "Maybe idempotency key is bound to a different request"))
        if code == "unsupported_schema" and _provider_pre_effect(payload):
            return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(ErrorCode.INVALID_SCHEMA, "Maybe provider rejected the typed schema before creating a table"))
        if code == "resource_limit" and _provider_pre_effect(payload):
            return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(ErrorCode.RESOURCE_LIMIT, "Maybe provider rejected the request before creating a table"))
        if code == "partial_effect":
            error = payload.get("error")
            receipt_id = error.get("receipt_id") if isinstance(error, Mapping) else None
            receipts = (
                (
                    _receipt(
                        "table.materialize.create",
                        uri,
                        details={"vendor_receipt_id": receipt_id},
                    ),
                )
                if isinstance(receipt_id, str) and receipt_id
                else ()
            )
            return OperationResult(None, Outcome.PARTIAL, CommitState.PARTIAL, VerificationState.FAILED, receipts, error=ErrorInfo(ErrorCode.PARTIAL_EFFECT, "Maybe provider reported a partial create effect", reconciliation=reconciliation))
        try:
            created = _create_result(payload, document_id=document_id, key=source.idempotency_key, row_count=source.row_count)
        except Exception as exc:
            return OperationResult(None, Outcome.UNKNOWN, CommitState.UNKNOWN, VerificationState.UNAVAILABLE, (), error=ErrorInfo(ErrorCode.UNCERTAIN_MUTATION, "Maybe create response cannot be validated; reconcile with the same idempotency key", {"reason": type(exc).__name__}, reconciliation))
        address = BaseModeTableAddress(uri, created["table_id"])
        mutation = _receipt("table.materialize.create", uri, details={
            "document_id": created["document_id"], "table_id": created["table_id"],
            "provider_revision": created["provider_revision"], "affected_rows": created["affected_rows"],
            "vendor_receipt_id": created["receipt_id"],
        })
        try:
            read_binding, observed, read = self._read_by_id(address)
            binding = TableBinding(uri, TableMode.BASE_MODE, observed.schema, created["provider_revision"], self.identity.connector_id, source.profile, source.row_count, source.schema_fingerprint, source.content_fingerprint, address)
            if read_binding.observed_revision != created["provider_revision"] or not observed.equals(source.source):
                return OperationResult(None, Outcome.FAILED, CommitState.COMMITTED, VerificationState.FAILED, (mutation, read), error=ErrorInfo(ErrorCode.READBACK_MISMATCH, "Maybe native readback differs from submitted table", {"table_id": created["table_id"]}))
            return OperationResult(binding, Outcome.SUCCEEDED, CommitState.COMMITTED, VerificationState.PASSED, (mutation, read))
        except Exception as exc:
            read = _receipt(
                "table.read",
                uri,
                details={"table_id": address.table_id, "readback": "invalid"},
            )
            return OperationResult(None, Outcome.FAILED, CommitState.COMMITTED, VerificationState.FAILED, (mutation, read), error=ErrorInfo(ErrorCode.READBACK_MISMATCH, "Maybe create committed but stable-ID readback failed", {"reason": type(exc).__name__}))

    def reconcile_materialization(
        self, destination: BaseModeDestination, reference: ReconciliationReference
    ) -> OperationResult[TableBinding]:
        if not self._native_supported():
            return self._unsupported()
        try:
            if reference.connector_id not in {None, self.identity.connector_id} or not reference.idempotency_key:
                raise ValueError("reconciliation reference does not belong to MaybeSheet")
            uri, document_id = _canonical_destination(destination)
            payload = self.adapter.connector._run_process(("mbs", "db-table", "reconcile", "--uri", uri.value, "--idempotency-key", reference.idempotency_key), credentials=self.adapter.credentials, timeout=self.adapter.timeout_seconds)
            created = _reconcile_result(payload, document_id=document_id, key=reference.idempotency_key)
            binding, _, read = self._read_by_id(BaseModeTableAddress(uri, created["table_id"]))
            return OperationResult(binding, Outcome.SUCCEEDED, CommitState.COMMITTED, VerificationState.PASSED, (read,))
        except Exception as exc:
            return OperationResult(None, Outcome.UNKNOWN, CommitState.UNKNOWN, VerificationState.UNAVAILABLE, (), error=ErrorInfo(ErrorCode.RECONCILIATION_UNAVAILABLE, "Maybe reconciliation is unavailable", {"reason": type(exc).__name__}))


__all__ = ["MaybeSheetSdkConnector", "probe_native_materialization"]
