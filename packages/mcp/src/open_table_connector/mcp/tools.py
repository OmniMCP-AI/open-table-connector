"""Typed MCP tool functions over the SDK operation contracts."""

from __future__ import annotations

from collections.abc import Mapping

from open_table_connector.contract import ExecutionOptions, OperationRequest
from open_table_connector.sdk import OperationCatalog, execute_operation

from .policy import authorize


def result_payload(result):
    is_error = result.outcome.value in {"rejected", "failed", "partial", "unknown"} or result.verification.value == "failed"
    return {"isError": is_error, "structuredContent": result.to_wire()}


def otc_discover(selector: Mapping[str, object] | None = None):
    selector = selector or {}
    catalog = OperationCatalog.default()
    descriptors = catalog.describe(selector.get("namespace"), selector.get("operation_id"), selector.get("version"))
    if not descriptors:
        return {"isError": True, "structuredContent": {"code": "invalid_descriptor", "message": "operation is not registered"}}
    if len(descriptors) == 1:
        return {"isError": False, "structuredContent": descriptors[0].to_wire()}
    return {"isError": False, "structuredContent": {"operations": [item.to_wire() for item in descriptors]}}


def _request(value) -> OperationRequest:
    if isinstance(value, OperationRequest):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("operation request must be an object")
    return OperationRequest.from_wire(value)


def otc_inspect(request, client, policy):
    try:
        request = _request(request)
        descriptor = OperationCatalog.default().get(request.namespace, request.operation_id, request.version)
        if descriptor is None or "read" not in descriptor.effects or any(effect in descriptor.effects for effect in ("buffered_write", "publish", "session_control")):
            raise ValueError("inspect only accepts read operations")
        if policy is not None:
            authorize(request, policy)
        return result_payload(execute_operation(client, request, ExecutionOptions()))
    except Exception as exc:
        return {"isError": True, "structuredContent": {"code": "invalid_request", "message": str(exc)}}


def otc_execute(request, client, policy):
    try:
        operation = _request(request)
        if policy is not None:
            authorize(operation, policy)
        return result_payload(execute_operation(client, operation, ExecutionOptions()))
    except Exception as exc:
        return {"isError": True, "structuredContent": {"code": "invalid_request", "message": str(exc)}}


__all__ = ["otc_discover", "otc_execute", "otc_inspect", "result_payload"]
