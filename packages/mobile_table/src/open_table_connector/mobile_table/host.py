from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol, cast, runtime_checkable

from open_table_connector.contract import TableURI
from open_table_connector.sdk import OperationResult, RecordUpdateRequest

from .models import (
    FieldType,
    MobileCapabilities,
    MobileInspection,
    MobileReadPage,
    MobileUpdateResult,
)


@runtime_checkable
class MobileTableHost(Protocol):
    def capabilities(self, table_uri: TableURI) -> OperationResult[MobileCapabilities]: ...

    def inspect(
        self, table_uri: TableURI, fields: tuple[str, ...] | None
    ) -> OperationResult[MobileInspection]: ...

    def read(
        self,
        table_uri: TableURI,
        *,
        page_size: int,
        page_token: str | None,
        fields: tuple[str, ...],
    ) -> OperationResult[MobileReadPage]: ...

    def update(
        self, table_uri: TableURI, request: RecordUpdateRequest
    ) -> OperationResult[MobileUpdateResult]: ...


class SdkMobileTableHost:
    """Small SDK bridge; provider-specific capability qualification stays in the host."""

    def __init__(self, table_resolver: Callable[[TableURI], object], *, record_id_field: str | None = None) -> None:
        self._table_resolver = table_resolver
        self._record_id_field = record_id_field.strip() if isinstance(record_id_field, str) and record_id_field.strip() else None

    def _table(self, table_uri: TableURI):
        return self._table_resolver(table_uri)

    def capabilities(self, table_uri: TableURI) -> OperationResult[MobileCapabilities]:
        table = self._table(table_uri)
        advertised = table.capabilities()
        if advertised.outcome is not advertised.outcome.SUCCEEDED:
            return advertised  # type: ignore[return-value]
        values = advertised.require_value()
        supports_read = values.supports("table.read")
        stable_record_ids = self._record_id_field is not None
        supports_update = stable_record_ids and values.supports("table.write") and callable(getattr(table, "update_record", None))
        return OperationResult(
            value=MobileCapabilities(
                contract="otc.mobile.table/1.0",
                request_id="capabilities",
                table_uri=table_uri.value,
                capability="otc.mobile.table/1.0",
                read={"support": "supported" if supports_read else "unsupported", "max_page_size": 100, "stable_record_ids": stable_record_ids},
                record_update={"support": "supported" if supports_update else "unsupported", "requires_expected_revision": True, "max_fields_per_patch": 10, "field_types": ["string", "integer", "number", "boolean", "date", "datetime"]},
                limits={"max_fields": 50, "max_patch_bytes": 16384},
                source={"connector_id": table.connector_id, "connector_version": "unknown"},
            ),
            outcome=advertised.outcome,
            commit=advertised.commit,
            verification=advertised.verification,
            receipts=advertised.receipts,
        )

    def inspect(self, table_uri: TableURI, fields: tuple[str, ...] | None) -> OperationResult[MobileInspection]:
        table = self._table(table_uri)
        result = table.inspect()
        if result.outcome is not result.outcome.SUCCEEDED:
            return result  # type: ignore[return-value]
        inspection = result.require_value()
        selected = set(fields) if fields is not None else None
        mobile_fields = []
        for name, dtype in zip(inspection.schema.names(), inspection.schema.dtypes(), strict=True):
            if selected is not None and name not in selected:
                continue
            type_name = _dtype_name(dtype)
            is_identity = name == self._record_id_field
            mobile_fields.append({
                "id": name,
                "label": name,
                "type": cast(FieldType, type_name),
                "nullable": True,
                "editable": self._record_id_field is not None and not is_identity,
                "read_only_reason": "record_identity" if is_identity else (None if self._record_id_field is not None else "host_must_qualify"),
            })
        from .models import MobileField

        return OperationResult(
            value=MobileInspection(
                table_uri=table_uri.value,
                mode=inspection.mode.value.removesuffix("-mode"),
                schema_fingerprint=inspection.schema_fingerprint or "unknown",
                row_count=inspection.row_count or 0,
                source_revision=inspection.observed_revision or "unknown",
                coordinate_convention={"mode": inspection.mode.value.removesuffix("-mode"), "record_id_field": self._record_id_field, "key_fields": [], "ordinal_snapshot_id": None},
                fields=tuple(MobileField.from_wire(item) for item in mobile_fields),
            ),
            outcome=result.outcome,
            commit=result.commit,
            verification=result.verification,
            receipts=result.receipts,
        )

    def read(self, table_uri: TableURI, *, page_size: int, page_token: str | None, fields: tuple[str, ...]) -> OperationResult[MobileReadPage]:
        table = self._table(table_uri)
        result = table.read_page(limit=page_size, continuation=page_token)
        if result.outcome is not result.outcome.SUCCEEDED:
            return result  # type: ignore[return-value]
        frame = result.require_value()
        from .models import MobileField, MobileRecord

        selected = tuple(fields) or tuple(frame.columns)
        mobile_fields = tuple(
            MobileField(
                name,
                name,
                cast(FieldType, _dtype_name(dtype)),
                True,
                self._record_id_field is not None and name != self._record_id_field,
                "record_identity" if name == self._record_id_field else (None if self._record_id_field is not None else "host_must_qualify"),
            )
            for name, dtype in zip(frame.columns, frame.dtypes, strict=True)
            if not selected or name in selected
        )
        rows_list = []
        for index, row in enumerate(frame.iter_rows(named=True)):
            record_value = row.get(self._record_id_field) if self._record_id_field else index
            if record_value is None:
                raise ValueError("configured record id field contains a null value")
            rows_list.append(MobileRecord(str(record_value), table.observed_revision or "unknown", {name: _wire_value(row[name]) for name in selected if name in row}))
        rows = tuple(rows_list)
        return OperationResult(
            value=MobileReadPage(table_uri.value, table.mode.value.removesuffix("-mode"), table.observed_revision or "unknown", mobile_fields, rows, result.continuation),
            outcome=result.outcome,
            commit=result.commit,
            verification=result.verification,
            receipts=result.receipts,
            continuation=result.continuation,
        )

    def update(self, table_uri: TableURI, request: RecordUpdateRequest) -> OperationResult[MobileUpdateResult]:
        table = self._table(table_uri)
        result = table.update_record(
            request.record_id,
            request.patch,
            expected_table_revision=request.expected_table_revision,
            expected_record_revision=request.expected_record_revision,
            idempotency_key=request.idempotency_key,
        )
        value = result.value
        from .models import MobileRecord

        mobile = None
        if value is not None:
            mobile = MobileRecord(value.record_id, value.record_revision, value.values)
        return OperationResult(
            value=MobileUpdateResult("otc.mobile.table/1.0", "update", None, result.outcome.value, result.commit.value, result.verification.value, None if value is None else value.table_revision, mobile, tuple(receipt.to_wire() for receipt in result.receipts)),
            outcome=result.outcome,
            commit=result.commit,
            verification=result.verification,
            receipts=result.receipts,
            error=result.error,
        )


def _dtype_name(dtype: object) -> str:
    text = str(dtype).lower()
    if "bool" in text:
        return "boolean"
    if "int" in text:
        return "integer"
    if any(item in text for item in ("float", "decimal")):
        return "number"
    if "date" in text and "time" in text:
        return "datetime"
    if text == "date":
        return "date"
    return "string"


def _wire_value(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _wire_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_wire_value(item) for item in value]
    return value


__all__ = ["MobileTableHost", "SdkMobileTableHost"]
