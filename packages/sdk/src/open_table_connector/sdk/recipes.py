"""SDK facade for capability-gated layout recipe replay."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from open_table_connector.contract import ExecutionOptions
from open_table_connector.spreadsheets import LayoutRecipe, RichObjectRequest

from .result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    OperationWarning,
    OTCError,
    Outcome,
    VerificationState,
)


_OBSERVABLE = frozenset({"range.style", "worksheet.config"})


def _rejected(code, message):
    return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(code, message))


def export_recipe(client, target, selectors: Sequence[Mapping[str, object]], *, allow_incomplete: bool = False):
    operations = []
    omissions = []
    book = None
    for selector in selectors:
        if not isinstance(selector, Mapping):
            omissions.append("selector is not an object")
            continue
        try:
            operation = RichObjectRequest(str(selector["operation_id"]), str(selector["target_key"]), selector.get("arguments", {}))
        except (KeyError, ValueError, TypeError):
            omissions.append("invalid selector")
            continue
        if operation.operation_id not in _OBSERVABLE:
            omissions.append(f"{operation.operation_id}: observation is not qualified")
            continue
        try:
            if book is None:
                book = client.workbook(target)
            worksheet = book.worksheet(operation.target_key)
            if operation.operation_id == "range.style":
                address = operation.arguments.get("address")
                worksheet.range(address).read_style()
            else:
                worksheet.read_config(rows=[1], columns=["A"])
            operations.append(operation)
        except Exception as exc:
            omissions.append(f"{operation.operation_id}: {type(exc).__name__}")
    if book is not None:
        book.close()
    if omissions and not allow_incomplete:
        return _rejected(ErrorCode.UNSUPPORTED_CAPABILITY, "requested recipe observation is incomplete")
    recipe = LayoutRecipe(
        "otc.spreadsheet-recipe/1.0",
        "1.0",
        tuple(sorted({f"spreadsheet.{item.operation_id}/1.0" for item in operations})),
        tuple(operations),
    )
    warnings = () if not omissions else (OperationWarning("incomplete_observation", "recipe omits unsupported observations", {"omissions": omissions}),)
    return OperationResult(recipe, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.PASSED, (), warnings=warnings)


def apply_recipe(client, target, recipe: LayoutRecipe, options: ExecutionOptions):
    if not isinstance(recipe, LayoutRecipe):
        return _rejected(ErrorCode.INVALID_SCHEMA, "recipe is invalid")
    book = None
    try:
        book = client.workbook(target)
        for operation in recipe.operations:
            if operation.operation_id not in {"range.style", "range.format", "range.merge", "range.unmerge", "worksheet.config"}:
                return _rejected(ErrorCode.UNSUPPORTED_CAPABILITY, "recipe operation is not an admitted layout mutation")
            book._queue(operation.operation_id, operation.target_key, dict(operation.arguments))
        return book.write(
            dry_run=options.dry_run, allow_partial=options.allow_partial,
            expected_revision=options.expected_revision, idempotency_key=options.idempotency_key)
    except OTCError as exc:
        return exc.result
    except (AttributeError, ValueError, TypeError):
        return _rejected(ErrorCode.INVALID_TARGET, "recipe target could not be bound or validated")
    finally:
        if book is not None:
            book.close()


__all__ = ["apply_recipe", "export_recipe"]
