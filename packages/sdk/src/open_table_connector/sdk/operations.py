"""Closed operation validation and explicit dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib.metadata import entry_points
from typing import Any

from open_table_connector.contract import ExecutionOptions, OperationRequest

from .discovery import OPERATION_HANDLER_GROUP, OperationCatalog
from .result import CommitState, ErrorCode, ErrorInfo, OperationResult, Outcome, VerificationState

Handler = Callable[[Any, OperationRequest, ExecutionOptions], OperationResult[object] | object]
_HANDLERS: dict[tuple[str, str, str], Handler] = {}
_ENTRYPOINTS_LOADED = False


def register_operation_handler(namespace: str, operation_id: str, version: str, handler: Handler) -> None:
    key = (namespace, operation_id, version)
    if key in _HANDLERS:
        raise ValueError("duplicate operation handler")
    _HANDLERS[key] = handler


def discover_operation_handlers() -> tuple[tuple[str, str, str, Handler], ...]:
    """Load explicit handler registrations; callers invoke this at execution only."""

    selected = entry_points()
    if hasattr(selected, "select"):
        selected = selected.select(group=OPERATION_HANDLER_GROUP)
    registrations: list[tuple[str, str, str, Handler]] = []
    for entry in sorted(selected, key=lambda item: (item.name, item.value)):
        loaded = entry.load()
        values = loaded() if callable(loaded) else loaded
        if isinstance(values, Mapping):
            values = tuple((*key, handler) for key, handler in values.items())
        registrations.extend(values)
    return tuple(registrations)


def _rejected(code: ErrorCode, message: str, **details: object) -> OperationResult[object]:
    return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(code, message, details))


def _validate(descriptor, arguments: dict[str, object]) -> str | None:
    try:
        from jsonschema import Draft202012Validator

        errors = sorted(Draft202012Validator(dict(descriptor.arguments_schema)).iter_errors(arguments), key=lambda item: list(item.path))
        return errors[0].message if errors else None
    except ImportError:
        required = tuple(descriptor.arguments_schema.get("required", ()))
        missing = [name for name in required if name not in arguments]
        return f"'{'/'.join(missing)}' is a required property" if missing else None


def _builtin_spreadsheet_handler(client, request: OperationRequest, options: ExecutionOptions):
    """Dispatch the catalog's existing workbook verbs through WorkbookAccess."""

    if request.target is None:
        return _rejected(ErrorCode.INVALID_TARGET, "spreadsheet operation requires a target")
    book = client.workbook(request.target.uri)
    sheet = request.target.sheet
    args = dict(request.arguments)
    operation = request.operation_id
    if operation == "workbook.inspect":
        return book.inspect()
    if operation == "workbook.verify":
        return book.verify(args.get("expected"))
    if operation == "workbook.reconcile":
        return book.reconcile()
    if operation == "workbook.write":
        return book.write(
            dry_run=options.dry_run,
            allow_partial=options.allow_partial,
            expected_revision=options.expected_revision,
            idempotency_key=options.idempotency_key,
        )
    if operation == "worksheet.list":
        return OperationResult(book.worksheet.list(), Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.PASSED, ())
    if not sheet:
        return _rejected(ErrorCode.INVALID_TARGET, "spreadsheet operation requires a worksheet")
    worksheet = book.worksheet(sheet)
    if operation == "worksheet.create":
        return book.worksheet.create(args["name"]).with_results()
    if operation == "worksheet.rename":
        return worksheet.rename(args["name"])
    if operation == "worksheet.delete":
        return worksheet.delete()
    if operation == "worksheet.move":
        return worksheet.move(args["index"])
    address = args.get("address")
    if operation == "range.read":
        return worksheet.range(address).read()
    if operation == "range.write":
        return worksheet.range(address).write(args["values"])
    if operation == "range.clear":
        return worksheet.range(address).clear()
    if operation == "range.sort":
        return worksheet.range(address).sort(key_column=args.get("key_column", 1), reverse=args.get("reverse", False))
    if operation == "range.merge":
        return worksheet.range(address).merge()
    if operation == "range.unmerge":
        return worksheet.range(address).unmerge()
    if operation == "range.style":
        return worksheet.range(address).style(**{key: value for key, value in args.items() if key != "address"})
    if operation == "range.format":
        return worksheet.range(address).format(**{key: value for key, value in args.items() if key != "address"})
    if operation == "range.style.read":
        return worksheet.range(address).read_style(args.get("fields"))
    return _rejected(ErrorCode.UNSUPPORTED_CAPABILITY, "workbook operation is not implemented", operation_id=operation)


def execute_operation(client, request: OperationRequest, options: ExecutionOptions, *, catalog: OperationCatalog | None = None) -> OperationResult[object]:
    selected = catalog or OperationCatalog.default()
    descriptor = selected.get(request.namespace, request.operation_id, request.version)
    if descriptor is None:
        return _rejected(ErrorCode.INVALID_DESCRIPTOR, "operation is not registered", operation_id=request.operation_id)
    error = _validate(descriptor, dict(request.arguments))
    if error is not None:
        return _rejected(ErrorCode.INVALID_SCHEMA, "operation arguments are invalid", reason=error)
    global _ENTRYPOINTS_LOADED
    if not _ENTRYPOINTS_LOADED:
        for namespace, operation_id, version, handler in discover_operation_handlers():
            _HANDLERS.setdefault((namespace, operation_id, version), handler)
        _ENTRYPOINTS_LOADED = True
    handler = _HANDLERS.get((request.namespace, request.operation_id, request.version))
    if handler is None and request.namespace == "spreadsheet":
        handler = _builtin_spreadsheet_handler
    if handler is None:
        return _rejected(ErrorCode.UNSUPPORTED_CAPABILITY, "operation has no execution handler", operation_id=request.operation_id)
    try:
        result = handler(client, request, options)
    except Exception:
        return _rejected(ErrorCode.EXECUTION_FAILED, "operation handler failed", operation_id=request.operation_id)
    if isinstance(result, OperationResult):
        return result
    return OperationResult(result, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.PASSED, ())


__all__ = ["Handler", "discover_operation_handlers", "execute_operation", "register_operation_handler"]
