from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from open_table_connector.contract import TableURI
from open_table_connector.sdk import ErrorCode, OperationResult, RecordUpdateRequest

from .host import MobileTableHost
from .models import (
    MobileError,
)
from .validation import (
    CONTRACT,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    parse_request,
    validate_field_selection,
    validate_patch_size,
)


@dataclass(frozen=True, slots=True)
class MobileHttpResponse:
    status: int
    body: Mapping[str, object]


class MobileTableAdapter:
    def __init__(self, host: MobileTableHost) -> None:
        self._host = host

    def dispatch(self, method: str, path: str, payload: Mapping[str, object]) -> MobileHttpResponse:
        if method != "POST":
            return self._error(payload.get("request_id") if isinstance(payload, Mapping) else None, 405, "invalid_request", "mobile table operations require POST")
        try:
            if path == "/otc/mobile/v1/capabilities":
                return self._capabilities(payload)
            if path == "/otc/mobile/v1/inspect":
                return self._inspect(payload)
            if path == "/otc/mobile/v1/read":
                return self._read(payload)
            if path == "/otc/mobile/v1/records/update":
                return self._update(payload)
            return self._error(payload.get("request_id") if isinstance(payload, Mapping) else None, 404, "invalid_request", "unknown mobile table operation")
        except (TypeError, ValueError) as exc:
            return self._error(payload.get("request_id") if isinstance(payload, Mapping) else None, 400, "invalid_request", str(exc))
        except Exception:
            return self._error(payload.get("request_id") if isinstance(payload, Mapping) else None, 500, "execution_failed", "mobile table host operation failed")

    def _capabilities(self, payload: Mapping[str, object]) -> MobileHttpResponse:
        request = parse_request(payload, frozenset({"contract", "request_id", "table_uri"}))
        return self._result(request.request_id, self._host.capabilities(TableURI(request.table_uri)))

    def _inspect(self, payload: Mapping[str, object]) -> MobileHttpResponse:
        request = parse_request(payload, frozenset({"contract", "request_id", "table_uri", "fields"}))
        raw_fields = payload.get("fields")
        fields = None if raw_fields is None else validate_field_selection(cast(list[str], raw_fields))
        return self._result(request.request_id, self._host.inspect(TableURI(request.table_uri), fields))

    def _read(self, payload: Mapping[str, object]) -> MobileHttpResponse:
        request = parse_request(payload, frozenset({"contract", "request_id", "table_uri", "page_size", "page_token", "fields"}))
        fields = validate_field_selection(cast(list[str], payload.get("fields", ())))
        page_size = payload.get("page_size", DEFAULT_PAGE_SIZE)
        if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
            raise ValueError("page_size must be a positive integer")
        table_uri = TableURI(request.table_uri)
        capabilities = self._host.capabilities(table_uri)
        if capabilities.outcome is not capabilities.outcome.SUCCEEDED:
            return self._result(request.request_id, capabilities)
        capability = capabilities.require_value()
        read_support = capability.read.get("support")
        if read_support != "supported":
            return self._error(request.request_id, 409, "unsupported_capability", "table read is not supported")
        advertised = capability.read.get("max_page_size", MAX_PAGE_SIZE)
        if isinstance(advertised, bool) or not isinstance(advertised, int):
            raise ValueError("capability max_page_size must be an integer")
        if page_size > min(MAX_PAGE_SIZE, advertised):
            return self._error(request.request_id, 400, "resource_limit", "page_size exceeds the provider limit", {"max_page_size": min(MAX_PAGE_SIZE, advertised)})
        token = payload.get("page_token")
        if token is not None and (not isinstance(token, str) or not token):
            raise ValueError("page_token must be a non-empty opaque string or null")
        return self._result(request.request_id, self._host.read(table_uri, page_size=page_size, page_token=token, fields=fields))

    def _update(self, payload: Mapping[str, object]) -> MobileHttpResponse:
        request = parse_request(payload, frozenset({"contract", "request_id", "table_uri", "record_id", "patch", "expected_table_revision", "expected_record_revision", "idempotency_key"}))
        record_id = payload.get("record_id")
        expected_table = payload.get("expected_table_revision")
        expected_record = payload.get("expected_record_revision")
        key = payload.get("idempotency_key")
        if not all(isinstance(item, str) and item.strip() for item in (record_id, expected_table, expected_record, key)):
            raise ValueError("record_id, expected revisions, and idempotency_key are required strings")
        patch = validate_patch_size(cast(Mapping[str, object], payload.get("patch", {})))
        table_uri = TableURI(request.table_uri)
        capabilities = self._host.capabilities(table_uri)
        if capabilities.outcome is not capabilities.outcome.SUCCEEDED:
            return self._result(request.request_id, capabilities)
        capability = capabilities.require_value()
        if capability.record_update.get("support") != "supported":
            return self._error(request.request_id, 409, "unsupported_capability", "record updates are not qualified for this table")
        advertised_fields = capability.record_update.get("max_fields_per_patch", 10)
        if isinstance(advertised_fields, int) and len(patch) > advertised_fields:
            return self._error(request.request_id, 400, "resource_limit", "patch exceeds the provider field limit", {"max_fields_per_patch": advertised_fields})
        update_request = RecordUpdateRequest(
            record_id=cast(str, record_id),
            patch=patch,
            expected_table_revision=cast(str, expected_table),
            expected_record_revision=cast(str, expected_record),
            idempotency_key=cast(str, key),
        )
        return self._result(request.request_id, self._host.update(table_uri, update_request))

    def _result(self, request_id: str, result: OperationResult[Any]) -> MobileHttpResponse:
        if result.outcome in {result.outcome.SUCCEEDED, result.outcome.PLANNED} and result.value is not None:
            body = dict(result.value.to_wire())
            body["contract"] = CONTRACT
            body["request_id"] = request_id
            return MobileHttpResponse(200, body)
        error = result.error
        if error is None:
            return self._error(request_id, 500, "execution_failed", "mobile table host returned no result")
        code = error.code.value
        status = 409 if code in {ErrorCode.STALE_REVISION.value, ErrorCode.UNSUPPORTED_CAPABILITY.value, ErrorCode.IDEMPOTENCY_CONFLICT.value} else 400 if result.outcome is result.outcome.REJECTED else 500
        return self._error(request_id, status, code, error.message, dict(error.safe_details))

    @staticmethod
    def _error(request_id: object, status: int, code: str, message: str, details: Mapping[str, object] | None = None) -> MobileHttpResponse:
        safe_request_id = request_id if isinstance(request_id, str) and request_id.strip() else "unknown"
        return MobileHttpResponse(status, {"contract": CONTRACT, "request_id": safe_request_id, "error": MobileError(code, message, details or {}).to_wire()})


__all__ = ["MobileHttpResponse", "MobileTableAdapter"]
