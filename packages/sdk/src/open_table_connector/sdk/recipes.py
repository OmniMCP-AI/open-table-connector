"""SDK facade for capability-gated layout recipe replay."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from open_table_connector.contract import ExecutionOptions, OperationRequest, TargetSelector
from open_table_connector.spreadsheets import LayoutRecipe, RichObjectRequest

from .operations import execute_operation
from .result import CommitState, ErrorCode, ErrorInfo, OperationResult, OperationWarning, Outcome, VerificationState


def _rejected(code, message):
    return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(code, message))


def export_recipe(client, target, selectors: Sequence[Mapping[str, object]], *, allow_incomplete: bool = False):
    operations = []
    omissions = []
    for selector in selectors:
        if not isinstance(selector, Mapping):
            return _rejected(ErrorCode.INVALID_SCHEMA, "recipe selector must be an object")
        try:
            operation = RichObjectRequest(str(selector["operation_id"]), str(selector["target_key"]), selector.get("arguments", {}))
        except (KeyError, ValueError, TypeError):
            omissions.append("invalid selector")
            continue
        operations.append(operation)
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
    if options.dry_run:
        return OperationResult({"operations": len(recipe.operations)}, Outcome.PLANNED, CommitState.NOT_STARTED, VerificationState.SKIPPED, ())
    receipts = []
    for operation in recipe.operations:
        request = OperationRequest("spreadsheet", operation.operation_id, "1.0", TargetSelector(target, operation.target_key), operation.arguments)
        result = execute_operation(client, request, options)
        if result.outcome.value not in {"succeeded", "planned"}:
            return result
        receipts.extend(result.receipts)
    return OperationResult({"operations": len(recipe.operations)}, Outcome.SUCCEEDED, CommitState.COMMITTED, VerificationState.PASSED, tuple(receipts))


__all__ = ["apply_recipe", "export_recipe"]
