"""SDK facade over the provider-neutral formula contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from math import isfinite
from typing import TYPE_CHECKING, Any, TypeVar, overload

from open_table_connector.contract import CapabilityIdentity, TableURI
from open_table_connector.formulas import (
    FIELD_READ,
    FIELD_RECALCULATE,
    FIELD_SET,
    FIELD_VALUES_READ,
    GRID_READ,
    GRID_RECALCULATE,
    GRID_SET,
    GRID_VALUES_READ,
    A1Rectangle,
    BoundFieldFormulaTarget,
    BoundGridFormulaTarget,
    FieldFormulaBinding,
    FieldFormulaBindRequest,
    FieldFormulaObservation,
    FieldFormulaReadRequest,
    FieldFormulaRecalculateRequest,
    FieldFormulaSetRequest,
    FieldFormulaTarget,
    FieldFormulaValueObservation,
    FieldFormulaValueReadRequest,
    FieldRecalculationScope,
    FormulaCapabilitySet,
    FormulaConnectorExtension,
    FormulaExpression,
    FormulaExtensionResult,
    FormulaMutation,
    FormulaReceiptDetails,
    FormulaResourceLimits,
    GridFormulaBinding,
    GridFormulaBindRequest,
    GridFormulaObservation,
    GridFormulaReadRequest,
    GridFormulaRecalculateRequest,
    GridFormulaSetRequest,
    GridFormulaTarget,
    GridFormulaValueObservation,
    GridFormulaValueReadRequest,
    GridRecalculationScope,
    RecalculationObservation,
)

from .model import TableMode
from .result import (
    CommitState,
    ErrorCode,
    ErrorInfo,
    OperationResult,
    OTCError,
    Outcome,
    Receipt,
    VerificationState,
)
from .table import Table, TableBinding

if TYPE_CHECKING:
    from .client import Client

_T = TypeVar("_T")


def _error(message: str, code: ErrorCode, **details: object) -> OTCError:
    return OTCError(
        message,
        OperationResult[None](
            value=None,
            outcome=Outcome.REJECTED,
            commit=CommitState.NOT_STARTED,
            verification=VerificationState.SKIPPED,
            receipts=(),
            error=ErrorInfo(code=code, message=message, safe_details=details),
        ),
    )


def _connector_id(connector: object) -> str:
    identity = getattr(connector, "identity", None)
    connector_id = getattr(identity, "connector_id", None)
    if not isinstance(connector_id, str) or not connector_id.strip():
        raise _error("connector identity is invalid", ErrorCode.PROTOCOL_FAILURE)
    return connector_id.strip()


def _receipt_mode(table_mode: str) -> TableMode:
    if table_mode == "sheet":
        return TableMode.SHEET_MODE
    if table_mode == "base":
        return TableMode.BASE_MODE
    raise _error("formula receipt table mode is invalid", ErrorCode.PROTOCOL_FAILURE)


def _normalize_receipts(
    receipts: tuple[object, ...],
    *,
    connector_id: str,
) -> tuple[Receipt, ...]:
    normalized: list[Receipt] = []
    for receipt in receipts:
        if not isinstance(receipt, FormulaReceiptDetails):
            raise _error("connector formula extension returned an invalid receipt", ErrorCode.PROTOCOL_FAILURE)
        normalized.append(
            Receipt(
                kind="formula",
                operation=receipt.capability,
                connector_id=connector_id,
                capability=receipt.capability,
                safe_target=TableURI(receipt.target),
                mode=_receipt_mode(receipt.table_mode),
                details=receipt.to_wire(),
            )
        )
    return tuple(normalized)


def _formula_result(
    client: Client,
    result: FormulaExtensionResult[_T],
    *,
    connector_id: str,
    expected_type: type[_T],
) -> OperationResult[_T]:
    try:
        value = result.value
        if value is not None and not isinstance(value, expected_type):
            raise TypeError("formula extension returned an invalid value")
        error = None
        if result.error is not None:
            error = ErrorInfo(
                code=ErrorCode(result.error.code.value),
                message="formula extension reported an operation error",
                safe_details=dict(result.error.safe_details),
            )
        normalized = OperationResult(
            value=value,
            outcome=Outcome(result.outcome.value),
            commit=CommitState(result.commit.value),
            verification=VerificationState(result.verification.value),
            receipts=_normalize_receipts(result.receipts, connector_id=connector_id),
            error=error,
        )
    except OTCError:
        raise
    except Exception:
        pass
    else:
        return client._deliver(normalized)
    raise _error(
        "connector formula extension returned an invalid result",
        ErrorCode.PROTOCOL_FAILURE,
        connector_id=connector_id,
    )


def _invoke_formula(
    client: Client,
    invocation: Callable[[], FormulaExtensionResult[_T]],
    *,
    connector_id: str,
    expected_type: type[_T],
) -> OperationResult[_T]:
    try:
        result = invocation()
    except Exception:
        pass
    else:
        return _formula_result(
            client,
            result,
            connector_id=connector_id,
            expected_type=expected_type,
        )
    raise _error(
        "connector formula extension invocation failed",
        ErrorCode.PROTOCOL_FAILURE,
        connector_id=connector_id,
    )


def _formula_extension_for(connector: object, *, connector_id: str) -> FormulaConnectorExtension:
    factory = getattr(connector, "formula_extension_for", None)
    if not callable(factory):
        raise _error(
            "connector does not expose the formula extension",
            ErrorCode.UNSUPPORTED_CAPABILITY,
            connector_id=connector_id,
        )
    missing = False
    try:
        extension = factory()
        valid = isinstance(extension, FormulaConnectorExtension)
    except AttributeError:
        missing = True
    except Exception:
        pass
    else:
        if valid:
            return extension
    if missing:
        raise _error(
            "connector does not expose the formula extension",
            ErrorCode.UNSUPPORTED_CAPABILITY,
            connector_id=connector_id,
        )
    raise _error(
        "connector formula extension is invalid",
        ErrorCode.PROTOCOL_FAILURE,
        connector_id=connector_id,
    )


class _FormulaViewBase:
    def __init__(
        self,
        client: Client,
        *,
        owner_token: object,
        connector_id: str,
        extension: FormulaConnectorExtension,
        capabilities: FormulaCapabilitySet,
        observed_revision: str | None,
    ) -> None:
        self._client = client
        self._owner_token = owner_token
        self._connector_id = connector_id
        self._extension = extension
        self.capabilities = capabilities
        self.observed_revision = observed_revision

    def _assert_ready(self) -> None:
        self._client._assert_open()
        if self._owner_token is not self._client._formula_owner_token:
            raise _error(
                "formula views must be used by the Client that created them",
                ErrorCode.CLIENT_AFFINITY_MISMATCH,
                connector_id=self._connector_id,
            )

    def _require_capability(self, capability: CapabilityIdentity) -> None:
        reference = capability.to_reference()
        if not any(item.to_reference() == reference for item in self.capabilities.capabilities):
            raise _error(
                "formula capability is not available for this target",
                ErrorCode.UNSUPPORTED_CAPABILITY,
                capability=reference,
                connector_id=self._connector_id,
            )

    def _validate_expected_revision(self, expected_revision: str | None) -> str | None:
        if expected_revision is None:
            return None
        if self.capabilities.details.revision_enforcement.value == "unavailable":
            raise _error(
                "formula revision checks are unavailable for this target",
                ErrorCode.UNSUPPORTED_CAPABILITY,
                connector_id=self._connector_id,
            )
        if self.observed_revision is not None and expected_revision != self.observed_revision:
            raise _error(
                "expected revision does not match the bound formula view",
                ErrorCode.STALE_REVISION,
                connector_id=self._connector_id,
                revision_hash=self.observed_revision,
            )
        return expected_revision

    def _validate_limits(
        self, limits: FormulaResourceLimits | None
    ) -> FormulaResourceLimits | None:
        if limits is not None and not isinstance(limits, FormulaResourceLimits):
            raise TypeError("limits must be a FormulaResourceLimits when provided")
        if limits is None:
            return None
        for field_name in ("max_cells", "max_records", "max_response_bytes"):
            value = getattr(limits, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
            ):
                raise _error(
                    "formula resource limits must be positive integers",
                    ErrorCode.RESOURCE_LIMIT,
                    connector_id=self._connector_id,
                    limit=field_name,
                )
        timeout = limits.timeout_seconds
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not isfinite(timeout)
            or timeout <= 0
        ):
            raise _error(
                "formula timeout limit must be a positive finite number",
                ErrorCode.RESOURCE_LIMIT,
                connector_id=self._connector_id,
                limit="timeout_seconds",
            )
        return limits

    def _validate_expression(self, expression: FormulaExpression) -> None:
        if not isinstance(expression, FormulaExpression):
            raise TypeError("expression must be a FormulaExpression")
        if expression.dialect not in self.capabilities.details.dialects:
            raise _error(
                "formula dialect is not supported for this target",
                ErrorCode.INVALID_FORMULA,
                connector_id=self._connector_id,
                dialect=expression.dialect,
            )
        if expression.byte_count > self.capabilities.details.max_expression_bytes:
            raise _error(
                "formula expression exceeds the target byte limit",
                ErrorCode.INVALID_FORMULA,
                connector_id=self._connector_id,
                dialect=expression.dialect,
                limit=self.capabilities.details.max_expression_bytes,
            )

    def _remember_observed_revision(self, value: object) -> None:
        revision: str | None
        if isinstance(
            value,
            (
                GridFormulaObservation,
                GridFormulaValueObservation,
                FieldFormulaObservation,
                FieldFormulaValueObservation,
            ),
        ):
            revision = value.observed_revision
        elif isinstance(value, (FormulaMutation, RecalculationObservation)):
            revision = value.revision_after
        else:
            return
        if revision is not None:
            self.observed_revision = revision


class GridFormulaView(_FormulaViewBase):
    def __init__(
        self,
        client: Client,
        *,
        owner_token: object,
        connector_id: str,
        extension: FormulaConnectorExtension,
        binding: GridFormulaBinding,
    ) -> None:
        super().__init__(
            client,
            owner_token=owner_token,
            connector_id=connector_id,
            extension=extension,
            capabilities=binding.capabilities,
            observed_revision=binding.observed_revision,
        )
        self._binding = binding
        self.target: BoundGridFormulaTarget = binding.target

    def _validate_range(
        self,
        cell_range: str,
        *,
        limits: FormulaResourceLimits | None = None,
    ) -> str:
        try:
            rectangle = A1Rectangle.parse(cell_range)
        except ValueError as exc:
            raise _error(str(exc), ErrorCode.INVALID_TARGET, connector_id=self._connector_id) from exc
        provider_limit = self.capabilities.details.max_cells_per_operation
        caller_limit = None if limits is None else limits.max_cells
        limit = (
            caller_limit
            if provider_limit is None
            else provider_limit
            if caller_limit is None
            else min(provider_limit, caller_limit)
        )
        if limit is not None and rectangle.cell_count > limit:
            raise _error(
                "formula range exceeded the target cell limit",
                ErrorCode.RESOURCE_LIMIT,
                connector_id=self._connector_id,
                range=cell_range.strip(),
                limit=limit,
            )
        return cell_range.strip()

    def read(
        self,
        cell_range: str,
        *,
        limits: FormulaResourceLimits | None = None,
    ) -> OperationResult[GridFormulaObservation]:
        self._assert_ready()
        self._require_capability(GRID_READ)
        validated_limits = self._validate_limits(limits)
        request = GridFormulaReadRequest(
            target=self.target,
            cell_range=self._validate_range(cell_range, limits=validated_limits),
            limits=validated_limits,
        )
        result = _invoke_formula(
            self._client,
            lambda: self._extension.read_grid(request),
            connector_id=self._connector_id,
            expected_type=GridFormulaObservation,
        )
        self._remember_observed_revision(result.require_value())
        return result

    def set(
        self,
        cell_range: str,
        expression: FormulaExpression,
        *,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
        limits: FormulaResourceLimits | None = None,
    ) -> OperationResult[FormulaMutation]:
        self._assert_ready()
        self._require_capability(GRID_SET)
        self._validate_expression(expression)
        validated_limits = self._validate_limits(limits)
        request = GridFormulaSetRequest(
            target=self.target,
            cell_range=self._validate_range(cell_range, limits=validated_limits),
            expression=expression,
            expected_revision=self._validate_expected_revision(expected_revision),
            idempotency_key=idempotency_key,
            limits=validated_limits,
        )
        result = _invoke_formula(
            self._client,
            lambda: self._extension.set_grid(request),
            connector_id=self._connector_id,
            expected_type=FormulaMutation,
        )
        self._remember_observed_revision(result.require_value())
        return result

    def read_values(
        self,
        cell_range: str,
        *,
        limits: FormulaResourceLimits | None = None,
    ) -> OperationResult[GridFormulaValueObservation]:
        self._assert_ready()
        self._require_capability(GRID_VALUES_READ)
        validated_limits = self._validate_limits(limits)
        request = GridFormulaValueReadRequest(
            target=self.target,
            cell_range=self._validate_range(cell_range, limits=validated_limits),
            limits=validated_limits,
        )
        result = _invoke_formula(
            self._client,
            lambda: self._extension.read_grid_values(request),
            connector_id=self._connector_id,
            expected_type=GridFormulaValueObservation,
        )
        self._remember_observed_revision(result.require_value())
        return result

    def recalculate(
        self,
        *,
        scope: GridRecalculationScope,
        cell_range: str | None = None,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
    ) -> OperationResult[RecalculationObservation]:
        self._assert_ready()
        self._require_capability(GRID_RECALCULATE)
        if scope.value not in self.capabilities.details.recalculation_scopes:
            raise _error(
                "formula recalculation scope is not available for this target",
                ErrorCode.UNSUPPORTED_CAPABILITY,
                connector_id=self._connector_id,
                scope=scope.value,
            )
        normalized_range = None if cell_range is None else self._validate_range(cell_range)
        try:
            request = GridFormulaRecalculateRequest(
                target=self.target,
                scope=scope,
                cell_range=normalized_range,
                expected_revision=self._validate_expected_revision(expected_revision),
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            raise _error(str(exc), ErrorCode.INVALID_TARGET, connector_id=self._connector_id) from exc
        result = _invoke_formula(
            self._client,
            lambda: self._extension.recalculate_grid(request),
            connector_id=self._connector_id,
            expected_type=RecalculationObservation,
        )
        self._remember_observed_revision(result.require_value())
        return result


class FieldFormulaView(_FormulaViewBase):
    def __init__(
        self,
        client: Client,
        *,
        owner_token: object,
        connector_id: str,
        extension: FormulaConnectorExtension,
        table_binding: TableBinding,
        binding: FieldFormulaBinding[Table],
    ) -> None:
        super().__init__(
            client,
            owner_token=owner_token,
            connector_id=connector_id,
            extension=extension,
            capabilities=binding.capabilities,
            observed_revision=binding.observed_revision,
        )
        self._table_binding = table_binding
        self._binding = binding
        self.target: BoundFieldFormulaTarget[Table] = binding.target

    def read(self) -> OperationResult[FieldFormulaObservation]:
        self._assert_ready()
        self._require_capability(FIELD_READ)
        request = FieldFormulaReadRequest(target=self.target)
        result = _invoke_formula(
            self._client,
            lambda: self._extension.read_field(request),
            connector_id=self._connector_id,
            expected_type=FieldFormulaObservation,
        )
        self._remember_observed_revision(result.require_value())
        return result

    def set(
        self,
        expression: FormulaExpression,
        *,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
    ) -> OperationResult[FormulaMutation]:
        self._assert_ready()
        self._require_capability(FIELD_SET)
        self._validate_expression(expression)
        request = FieldFormulaSetRequest(
            target=self.target,
            expression=expression,
            expected_revision=self._validate_expected_revision(expected_revision),
            idempotency_key=idempotency_key,
        )
        result = _invoke_formula(
            self._client,
            lambda: self._extension.set_field(request),
            connector_id=self._connector_id,
            expected_type=FormulaMutation,
        )
        self._remember_observed_revision(result.require_value())
        return result

    def read_values(
        self,
        *,
        limits: FormulaResourceLimits | None = None,
    ) -> OperationResult[FieldFormulaValueObservation]:
        self._assert_ready()
        self._require_capability(FIELD_VALUES_READ)
        request = FieldFormulaValueReadRequest(
            target=self.target,
            limits=self._validate_limits(limits),
        )
        result = _invoke_formula(
            self._client,
            lambda: self._extension.read_field_values(request),
            connector_id=self._connector_id,
            expected_type=FieldFormulaValueObservation,
        )
        self._remember_observed_revision(result.require_value())
        return result

    def recalculate(
        self,
        *,
        scope: FieldRecalculationScope,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
    ) -> OperationResult[RecalculationObservation]:
        self._assert_ready()
        self._require_capability(FIELD_RECALCULATE)
        if scope.value not in self.capabilities.details.recalculation_scopes:
            raise _error(
                "formula recalculation scope is not available for this target",
                ErrorCode.UNSUPPORTED_CAPABILITY,
                connector_id=self._connector_id,
                scope=scope.value,
            )
        request = FieldFormulaRecalculateRequest(
            target=self.target,
            scope=scope,
            expected_revision=self._validate_expected_revision(expected_revision),
            idempotency_key=idempotency_key,
        )
        result = _invoke_formula(
            self._client,
            lambda: self._extension.recalculate_field(request),
            connector_id=self._connector_id,
            expected_type=RecalculationObservation,
        )
        self._remember_observed_revision(result.require_value())
        return result


def _grid_view_from_binding(
    client: Client,
    target: GridFormulaTarget,
    connector_id: str,
    extension: FormulaConnectorExtension,
    binding_result: OperationResult[Any],
) -> OperationResult[GridFormulaView]:
    binding = binding_result.require_value()
    if not isinstance(binding, GridFormulaBinding):
        raise _error("connector formula binding is invalid", ErrorCode.PROTOCOL_FAILURE)
    bound_worksheet_id = binding.target.worksheet.worksheet_id
    requested_worksheet_id = target.worksheet.worksheet_id
    if (
        binding.target.grid != target.grid
        or bound_worksheet_id is None
        or (
            requested_worksheet_id is not None
            and bound_worksheet_id != requested_worksheet_id
        )
    ):
        raise _error("connector formula binding does not match the requested grid target", ErrorCode.PROTOCOL_FAILURE)
    return replace(
        binding_result,
        value=GridFormulaView(
            client,
            owner_token=client._formula_owner_token,
            connector_id=connector_id,
            extension=extension,
            binding=binding,
        ),
    )


def _field_view_from_binding(
    client: Client,
    target: FieldFormulaTarget[Table],
    connector_id: str,
    extension: FormulaConnectorExtension,
    binding_result: OperationResult[Any],
) -> OperationResult[FieldFormulaView]:
    binding = binding_result.require_value()
    if not isinstance(binding, FieldFormulaBinding):
        raise _error("connector formula binding is invalid", ErrorCode.PROTOCOL_FAILURE)
    bound_field_id = binding.target.field.field_id
    requested_field_id = target.field.field_id
    if (
        binding.target.table is not target.table
        or bound_field_id is None
        or (requested_field_id is not None and bound_field_id != requested_field_id)
    ):
        raise _error("connector formula binding does not match the requested field target", ErrorCode.PROTOCOL_FAILURE)
    return replace(
        binding_result,
        value=FieldFormulaView(
            client,
            owner_token=client._formula_owner_token,
            connector_id=connector_id,
            extension=extension,
            table_binding=target.table._binding,
            binding=binding,
        ),
    )


@overload
def bind_formulas(client: Client, target: GridFormulaTarget) -> OperationResult[GridFormulaView]: ...


@overload
def bind_formulas(
    client: Client, target: FieldFormulaTarget[Table]
) -> OperationResult[FieldFormulaView]: ...


def bind_formulas(client: Client, target: object):
    if isinstance(target, GridFormulaTarget):
        grid_uri = target.grid if isinstance(target.grid, TableURI) else TableURI(target.grid)
        connector = client._registry.connector_for(grid_uri.value)
        connector_id = _connector_id(connector)
        if TableMode.SHEET_MODE not in tuple(getattr(connector, "modes", ())):
            raise _error(
                "grid formulas require a sheet-mode connector",
                ErrorCode.UNSUPPORTED_MODE,
                connector_id=connector_id,
            )
        extension = _formula_extension_for(connector, connector_id=connector_id)
        grid_request = GridFormulaBindRequest(target=target)
        grid_bound_result = _invoke_formula(
            client,
            lambda: extension.bind_grid(grid_request),
            connector_id=connector_id,
            expected_type=GridFormulaBinding,
        )
        return _grid_view_from_binding(client, target, connector_id, extension, grid_bound_result)
    if isinstance(target, FieldFormulaTarget):
        if not isinstance(target.table, Table):
            raise _error("field formula targets require a bound Table", ErrorCode.INVALID_TARGET)
        client._assert_owned(target.table)
        if target.table.mode is not TableMode.BASE_MODE:
            raise _error(
                "field formulas require base-mode Tables",
                ErrorCode.UNSUPPORTED_MODE,
                connector_id=target.table.connector_id,
            )
        connector = client._connector_for_binding(target.table._binding)
        connector_id = target.table.connector_id
        extension = _formula_extension_for(connector, connector_id=connector_id)
        field_request = FieldFormulaBindRequest(target=target)
        field_bound_result = _invoke_formula(
            client,
            lambda: extension.bind_field(field_request),
            connector_id=connector_id,
            expected_type=FieldFormulaBinding,
        )
        return _field_view_from_binding(client, target, connector_id, extension, field_bound_result)
    raise _error("formulas expects a GridFormulaTarget or FieldFormulaTarget", ErrorCode.INVALID_TARGET)


__all__ = ["FieldFormulaView", "GridFormulaView", "bind_formulas"]
