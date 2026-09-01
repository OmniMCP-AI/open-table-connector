"""Maybe Sheet sheet-mode grid Formula extension.

Formula operations intentionally use the canonical ``mbs`` JSON commands.  They
are separate from the ordinary table reader/writer so a value that happens to
begin with ``=`` can never become a formula through a Table path.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Mapping
from typing import Any

import open_table_connector.formulas as otf
from open_table_connector.contract import ConnectorError, ConnectorErrorCode

from .connector import MaybeSheetConnector, ProcessClient, _mbs_target

_CAPABILITIES = (otf.GRID_READ, otf.GRID_SET, otf.GRID_VALUES_READ, otf.GRID_RECALCULATE)
_MAX_CELLS = 10_000
_MAX_EXPRESSION_BYTES = 64 * 1024
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_DEFAULT_LEDGER_LIMIT = 1024
_ENVELOPE_KEYS = {
    "contract_version",
    "ok",
    "operation",
    "target",
    "warnings",
    "request_id",
    "result",
    "verification",
    "trace",
}
_ERROR_ENVELOPE_KEYS = (_ENVELOPE_KEYS - {"result"}) | {"error"}
_CELL_REFERENCE = re.compile(r"(?P<column>\$?[A-Za-z]{1,3})(?P<row>\$?[1-9]\d*)")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class _ProtocolFailure(Exception):
    pass


class _LimitFailure(Exception):
    def __init__(self, message: str, limit: int) -> None:
        super().__init__(message)
        self.limit = limit


class _BindingFailure(Exception):
    pass


class _ProviderFailure(Exception):
    def __init__(self, code: otf.FormulaErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _address(column: int, row: int) -> str:
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return f"{letters}{row}"


def _result(value: object, receipts: tuple[object, ...] = ()) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(
        value=value,
        outcome=otf.FormulaOutcome.SUCCEEDED,
        commit=otf.FormulaCommitState.NOT_APPLICABLE,
        verification=otf.FormulaVerificationState.PASSED,
        receipts=receipts,
    )


def _rejected(code: otf.FormulaErrorCode, message: str, details: Mapping[str, Any] | None = None) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(
        value=None,
        outcome=otf.FormulaOutcome.REJECTED,
        commit=otf.FormulaCommitState.NOT_STARTED,
        verification=otf.FormulaVerificationState.SKIPPED,
        receipts=(),
        error=otf.FormulaExtensionErrorInfo(code, message, details or {}),
    )


def _failed(
    code: otf.FormulaErrorCode,
    message: str,
    *,
    commit: otf.FormulaCommitState = otf.FormulaCommitState.NOT_COMMITTED,
    verification: otf.FormulaVerificationState = otf.FormulaVerificationState.SKIPPED,
) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(
        value=None,
        outcome=otf.FormulaOutcome.FAILED,
        commit=commit,
        verification=verification,
        receipts=(),
        error=otf.FormulaExtensionErrorInfo(code, message, {}),
    )


def _unknown(message: str) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(
        value=None,
        outcome=otf.FormulaOutcome.UNKNOWN,
        commit=otf.FormulaCommitState.UNKNOWN,
        verification=otf.FormulaVerificationState.UNAVAILABLE,
        receipts=(),
        error=otf.FormulaExtensionErrorInfo(otf.FormulaErrorCode.UNCERTAIN_MUTATION, message, {}),
    )


class MaybeSheetGridFormulaExtension(otf.GridFormulaConnectorExtension):
    """Provider Formula operations over Maybe Sheet's process transport."""

    def __init__(
        self,
        connector_or_process: MaybeSheetConnector | ProcessClient,
        credentials: Mapping[str, str] | None = None,
        timeout: float | int = 120,
    ) -> None:
        self._connector = connector_or_process if isinstance(connector_or_process, MaybeSheetConnector) else None
        self._process = connector_or_process if self._connector is None else None
        self._credentials = dict(credentials or {})
        self._timeout = timeout
        self._bindings: dict[tuple[str, str], tuple[str, otf.FormulaCapabilityDetails]] = {}
        self._ledger = otf.FormulaIdempotencyLedger(limit=_DEFAULT_LEDGER_LIMIT)
        self._completed: dict[str, otf.FormulaExtensionResult[Any]] = {}
        self._lock = threading.RLock()

    def bind_grid(self, request: otf.GridFormulaBindRequest) -> otf.FormulaExtensionResult[otf.GridFormulaBinding]:
        try:
            payload = self._call(
                ("mbs", "worksheet", "list", "--uri", _mbs_target(request.target.grid), "--output", "json"),
                operation="worksheet.list",
            )
            result = payload["result"]
            worksheets = result.get("worksheets")
            if not isinstance(worksheets, list):
                raise _ProtocolFailure
            reference = request.target.worksheet
            matches: list[tuple[str, str]] = []
            for item in worksheets:
                if not isinstance(item, Mapping):
                    raise _ProtocolFailure
                gid = item.get("gid", item.get("id"))
                name = item.get("name", item.get("title"))
                kind = item.get("type", item.get("kind"))
                if not isinstance(gid, str) or not gid or not isinstance(name, str) or not name:
                    raise _ProtocolFailure
                if kind not in {"sheet", "worksheet"}:
                    continue
                if reference.worksheet_id is not None and gid != reference.worksheet_id:
                    continue
                if reference.name is not None and name != reference.name:
                    continue
                matches.append((gid, name))
            if len(matches) != 1:
                return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet worksheet does not identify exactly one sheet")
            gid, name = matches[0]
            details = self._capability_details(result)
            key = (request.target.grid.value, gid)
            with self._lock:
                self._bindings[key] = (name, details)
            binding = otf.GridFormulaBinding(
                target=otf.BoundGridFormulaTarget(request.target.grid.value, otf.WorksheetRef(worksheet_id=gid)),
                capabilities=otf.FormulaCapabilitySet(
                    tuple(capability for capability in _CAPABILITIES if capability is not otf.GRID_RECALCULATE or details.recalculation_scopes),
                    details,
                ),
                observed_revision=self._revision(result, payload),
            )
            return _result(binding)
        except _ProtocolFailure:
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid worksheet response")
        except _ProviderFailure as exc:
            return _rejected(exc.code, str(exc))
        except ConnectorError as exc:
            return self._transport_error(exc, "worksheet binding")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid worksheet response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet worksheet binding failed")

    def read_grid(self, request: otf.GridFormulaReadRequest) -> otf.FormulaExtensionResult[otf.GridFormulaObservation]:
        try:
            details = self._binding_details(request.target)
            rectangle = self._validated_range(request.cell_range, request.limits, details.max_cells_per_operation)
            payload = self._call(self._formula_argv("read", request.target, rectangle) + ("--output", "json"), operation="formula.read", timeout=self._request_timeout(request.limits), limits=request.limits)
            observation = self._parse_formula_observation(payload["result"], request.target, rectangle, request.limits)
            receipt = otf.FormulaReceiptDetails.for_grid_read(
                target=request.target.grid.value,
                selector=request.cell_range,
                capability=otf.GRID_READ.to_reference(),
                dialect=otf.MAYBE_SHEET_A1,
                observation_sha256=otf.formula_observation_hash(observation),
                observed_count=len(observation.formulas),
                revision_after=observation.observed_revision,
            )
            return _result(observation, (receipt,))
        except _LimitFailure as exc:
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet worksheet binding is required")
        except _ProviderFailure as exc:
            return _rejected(exc.code, str(exc))
        except _ProtocolFailure:
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid formula response")
        except ConnectorError as exc:
            return self._transport_error(exc, "formula read")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid formula response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula read failed")

    def read_grid_values(self, request: otf.GridFormulaValueReadRequest) -> otf.FormulaExtensionResult[otf.GridFormulaValueObservation]:
        try:
            details = self._binding_details(request.target)
            rectangle = self._validated_range(request.cell_range, request.limits, details.max_cells_per_operation)
            payload = self._call(
                self._worksheet_argv(request.target, rectangle),
                operation="excel-worksheet.read",
                timeout=self._request_timeout(request.limits),
                limits=request.limits,
            )
            observation = self._parse_value_observation(payload["result"], request.target, rectangle, request.limits)
            receipt = otf.FormulaReceiptDetails.for_grid_values_read(
                target=request.target.grid.value,
                selector=request.cell_range,
                capability=otf.GRID_VALUES_READ.to_reference(),
                dialect=otf.MAYBE_SHEET_A1,
                observation_sha256=None,
                value_observation_sha256=otf.formula_observation_hash(observation),
                observed_count=len(observation.values),
                revision_after=observation.observed_revision,
                calculation_state=observation.calculation_state.value,
                calculation_trigger=observation.calculation_trigger.value,
                dependency_scope=observation.dependency_scope,
            )
            return _result(observation, (receipt,))
        except _LimitFailure as exc:
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet worksheet binding is required")
        except _ProviderFailure as exc:
            return _rejected(exc.code, str(exc))
        except _ProtocolFailure:
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid value response")
        except ConnectorError as exc:
            return self._transport_error(exc, "formula value read")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid value response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula value read failed")

    def set_grid(self, request: otf.GridFormulaSetRequest) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        context: tuple[str, str, str] | None = None
        dispatched = False
        try:
            details = self._binding_details(request.target)
            rectangle = self._validated_range(request.cell_range, request.limits, details.max_cells_per_operation)
            if request.expression.dialect != otf.MAYBE_SHEET_A1:
                return _rejected(otf.FormulaErrorCode.INVALID_FORMULA, "MaybeSheet formula dialect is invalid")
            expression_limit = self._expression_limit(request.limits)
            if request.expression.byte_count > expression_limit:
                raise _LimitFailure("formula expression exceeds the configured byte limit", expression_limit)
            target_hash = _hash_payload({"uri": request.target.grid.value, "gid": request.target.worksheet.worksheet_id})
            selector_hash = _hash_payload({"capability": otf.GRID_SET.to_reference()})
            payload_hash = _hash_payload({"range": request.cell_range, "expression_sha256": request.expression.sha256, "expected_revision": request.expected_revision})
            context = (target_hash, selector_hash, payload_hash)
            if request.idempotency_key is not None:
                with self._lock:
                    decision = self._ledger.begin(
                        connector_id="maybe_sheet",
                        capability=otf.GRID_SET.to_reference(),
                        target_hash=target_hash,
                        selector_hash=selector_hash,
                        idempotency_key=request.idempotency_key,
                        payload_hash=payload_hash,
                    )
                if decision.disposition is otf.FormulaIdempotencyDisposition.CONFLICT:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula idempotency key conflicts with a prior request")
                if decision.disposition is otf.FormulaIdempotencyDisposition.IN_FLIGHT:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula idempotency key is already in flight")
                if decision.disposition is otf.FormulaIdempotencyDisposition.UNKNOWN:
                    return _unknown("formula mutation remains uncertain")
                if decision.disposition is otf.FormulaIdempotencyDisposition.REPLAY:
                    with self._lock:
                        cached = self._completed.get(decision.operation_hash or "")
                    return cached if cached is not None else _unknown("formula mutation replay result is unavailable")

            argv = list(self._formula_argv("set", request.target, rectangle))
            argv.extend(("--expression", request.expression.text, "--language", "excel"))
            if request.idempotency_key is not None:
                argv.extend(("--idempotency-key", request.idempotency_key))
            argv.append("--verify")
            if request.expected_revision is not None:
                argv.extend(("--expected-revision", request.expected_revision))
            argv.extend(("--output", "json"))
            dispatched = True
            self._call(tuple(argv), operation="formula.set", timeout=self._request_timeout(request.limits), limits=request.limits)
            readback = self.read_grid(otf.GridFormulaReadRequest(request.target, request.cell_range, request.limits))
            if readback.outcome is not otf.FormulaOutcome.SUCCEEDED or readback.value is None:
                self._mark_unknown(request, context)
                return _unknown("formula commit state could not be determined")
            expected = self._expected_formula_map(rectangle, request.expression)
            observed = {cell.address: cell.expression.text for cell in readback.value.formulas}
            if observed != expected:
                self._mark_unknown(request, context)
                return _failed(
                    otf.FormulaErrorCode.READBACK_MISMATCH,
                    "formula text readback did not match the requested mutation",
                    commit=otf.FormulaCommitState.COMMITTED,
                    verification=otf.FormulaVerificationState.FAILED,
                )
            mutation = otf.FormulaMutation("grid", rectangle.cell_count, readback.value, request.expected_revision, readback.value.observed_revision)
            receipt = otf.FormulaReceiptDetails.for_grid_set(
                target=request.target.grid.value,
                selector=request.cell_range,
                capability=otf.GRID_SET.to_reference(),
                dialect=request.expression.dialect,
                expression_sha256=request.expression.sha256,
                observation_sha256=otf.formula_observation_hash(readback.value),
                affected_count=rectangle.cell_count,
                revision_before=request.expected_revision,
                revision_after=readback.value.observed_revision,
                mutation_atomicity=otf.MutationAtomicity.ATOMIC.value,
                revision_enforcement=otf.RevisionEnforcement.CHECKED.value,
                verification="formula_text_readback",
            )
            result = otf.FormulaExtensionResult(
                mutation,
                otf.FormulaOutcome.SUCCEEDED,
                otf.FormulaCommitState.COMMITTED,
                otf.FormulaVerificationState.PASSED,
                (receipt,),
            )
            if request.idempotency_key is not None and context is not None:
                operation_hash = _hash_payload(mutation.to_wire())
                with self._lock:
                    self._completed[operation_hash] = result
                    self._ledger.succeed(
                        connector_id="maybe_sheet",
                        target_hash=context[0],
                        selector_hash=context[1],
                        idempotency_key=request.idempotency_key,
                        payload_hash=context[2],
                        operation_hash=operation_hash,
                    )
            return result
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet worksheet binding is required")
        except _LimitFailure as exc:
            self._finish_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula commit state could not be determined")
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _ProtocolFailure:
            self._finish_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula commit state could not be determined")
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid mutation response")
        except _ProviderFailure:
            self._finish_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula commit state could not be determined")
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet rejected the formula mutation")
        except ConnectorError as exc:
            before_dispatch = exc.code is ConnectorErrorCode.TIMEOUT and exc.safe_details.get("before_dispatch") is True
            self._finish_ledger(request, context, dispatched=dispatched and not before_dispatch)
            if dispatched and not before_dispatch:
                return _unknown("formula commit state could not be determined")
            return self._transport_error(exc, "formula mutation")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            self._finish_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula commit state could not be determined")
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid mutation response")
        except Exception:
            self._finish_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula commit state could not be determined")
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula mutation failed")

    def recalculate_grid(self, request: otf.GridFormulaRecalculateRequest) -> otf.FormulaExtensionResult[otf.RecalculationObservation]:
        context: tuple[str, str, str] | None = None
        dispatched = False
        try:
            details = self._binding_details(request.target)
            if request.scope.value not in details.recalculation_scopes:
                return _rejected(otf.FormulaErrorCode.UNSUPPORTED_CAPABILITY, "MaybeSheet does not support the requested recalculation scope")
            if request.scope.value == "range":
                if request.cell_range is None:
                    return _rejected(otf.FormulaErrorCode.INVALID_TARGET, "range recalculation requires a bounded cell range")
                rectangle = self._validated_range(request.cell_range, request.limits, details.max_cells_per_operation)
            else:
                if request.cell_range is not None:
                    return _rejected(otf.FormulaErrorCode.INVALID_TARGET, "non-range recalculation must not include a cell range")
                rectangle = None
            target_hash = _hash_payload({"uri": request.target.grid.value, "gid": request.target.worksheet.worksheet_id})
            selector_hash = _hash_payload({"capability": otf.GRID_RECALCULATE.to_reference()})
            payload_hash = _hash_payload(
                {
                    "scope": request.scope.value,
                    "range": request.cell_range,
                    "expected_revision": request.expected_revision,
                }
            )
            context = (target_hash, selector_hash, payload_hash)
            if request.idempotency_key is not None:
                with self._lock:
                    decision = self._ledger.begin(
                        connector_id="maybe_sheet",
                        capability=otf.GRID_RECALCULATE.to_reference(),
                        target_hash=target_hash,
                        selector_hash=selector_hash,
                        idempotency_key=request.idempotency_key,
                        payload_hash=payload_hash,
                    )
                if decision.disposition in {
                    otf.FormulaIdempotencyDisposition.CONFLICT,
                    otf.FormulaIdempotencyDisposition.IN_FLIGHT,
                }:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula recalculation idempotency key conflicts with a prior request")
                if decision.disposition is otf.FormulaIdempotencyDisposition.UNKNOWN:
                    return _unknown("formula recalculation remains uncertain")
                if decision.disposition is otf.FormulaIdempotencyDisposition.REPLAY:
                    with self._lock:
                        cached = self._completed.get(decision.operation_hash or "")
                    return cached if cached is not None else _unknown("formula recalculation replay result is unavailable")
            argv = list(self._formula_argv("recalculate", request.target, rectangle))
            argv.append("--verify")
            if request.expected_revision is not None:
                argv.extend(("--expected-revision", request.expected_revision))
            argv.extend(("--output", "json"))
            dispatched = True
            payload = self._call(
                tuple(argv),
                operation="formula.recalculate",
                timeout=self._request_timeout(request.limits),
                limits=request.limits,
            )
            result = payload["result"]
            requested_scope = result.get("requested_scope", request.scope.value)
            effective_scope = result.get("effective_scope", requested_scope)
            value_observation = None
            raw_values = result.get("value_observation")
            if raw_values is None and "values" in result:
                raw_values = result
            if isinstance(raw_values, Mapping):
                if raw_values.get("kind") == "formula.grid.values.observation":
                    value_observation = otf.GridFormulaValueObservation.from_wire(raw_values)
                else:
                    value_observation = self._parse_value_observation(raw_values, request.target, otf.A1Rectangle.parse(request.cell_range or "A1"), None)
            observation = otf.RecalculationObservation(
                target_kind="grid",
                requested_scope=requested_scope,
                effective_scope=effective_scope,
                revision_before=self._optional_revision(result.get("revision_before")),
                revision_after=self._optional_revision(result.get("revision_after")),
                provider_status=self._safe_provider_text(result.get("provider_status", "completed")),
                calculation_state=otf.CalculationState(result.get("calculation_state", "unknown")),
                verification="passed" if value_observation is not None else "unavailable",
                value_observation=value_observation,
            )
            result = otf.FormulaExtensionResult(
                value=observation,
                outcome=otf.FormulaOutcome.SUCCEEDED,
                commit=otf.FormulaCommitState.NOT_APPLICABLE,
                verification=(
                    otf.FormulaVerificationState.PASSED
                    if observation.verification == "passed"
                    else otf.FormulaVerificationState.UNAVAILABLE
                ),
                receipts=(),
            )
            if request.idempotency_key is not None and context is not None:
                operation_hash = _hash_payload(observation.to_wire())
                with self._lock:
                    self._completed[operation_hash] = result
                    self._ledger.succeed(
                        connector_id="maybe_sheet",
                        target_hash=context[0],
                        selector_hash=context[1],
                        idempotency_key=request.idempotency_key,
                        payload_hash=context[2],
                        operation_hash=operation_hash,
                    )
            return result
        except _ProtocolFailure:
            self._finish_recalculation_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula recalculation state could not be determined")
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid recalculation response")
        except _LimitFailure as exc:
            self._finish_recalculation_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula recalculation state could not be determined")
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet worksheet binding is required")
        except _ProviderFailure as exc:
            self._finish_recalculation_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula recalculation state could not be determined")
            return _rejected(exc.code, str(exc))
        except ConnectorError as exc:
            before_dispatch = exc.code is ConnectorErrorCode.TIMEOUT and exc.safe_details.get("before_dispatch") is True
            self._finish_recalculation_ledger(request, context, dispatched=dispatched and not before_dispatch)
            if dispatched and not before_dispatch:
                return _unknown("formula recalculation state could not be determined")
            return self._transport_error(exc, "formula recalculation")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            self._finish_recalculation_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula recalculation state could not be determined")
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid recalculation response")
        except Exception:
            self._finish_recalculation_ledger(request, context, dispatched=dispatched)
            if dispatched:
                return _unknown("formula recalculation state could not be determined")
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula recalculation failed")

    def _call(
        self,
        argv: tuple[str, ...],
        *,
        operation: str,
        timeout: float | int | None = None,
        limits: otf.FormulaResourceLimits | None = None,
    ) -> Mapping[str, Any]:
        try:
            if self._connector is not None:
                payload = self._connector._run_process(argv, credentials=self._credentials, stdin=None, timeout=self._timeout if timeout is None else timeout)
            else:
                payload = self._process.run(argv, credentials=self._credentials, stdin=None, timeout=self._timeout if timeout is None else timeout)  # type: ignore[union-attr]
        except ConnectorError:
            raise
        except Exception:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "MaybeSheet process operation failed", {}) from None
        if not isinstance(payload, Mapping) or set(payload) not in (_ENVELOPE_KEYS, _ERROR_ENVELOPE_KEYS):
            raise _ProtocolFailure
        if payload["contract_version"] != "1.0" or payload["operation"] != operation:
            raise _ProtocolFailure
        if not isinstance(payload["target"], Mapping) or not isinstance(payload["warnings"], list) or not isinstance(payload["verification"], Mapping):
            raise _ProtocolFailure
        if payload["request_id"] is not None and not isinstance(payload["request_id"], str):
            raise _ProtocolFailure
        if payload["ok"] is False:
            error = payload.get("error")
            if not isinstance(error, Mapping) or not isinstance(error.get("code"), str) or not error["code"].strip():
                raise _ProtocolFailure
            raise _ProviderFailure(*self._provider_error(error))
        if payload["ok"] is not True or "error" in payload or not isinstance(payload["result"], Mapping):
            raise _ProtocolFailure
        requested = limits.max_response_bytes if limits is not None else None
        if requested is not None and (isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0):
            raise _ProtocolFailure
        limit = _MAX_RESPONSE_BYTES if requested is None else min(_MAX_RESPONSE_BYTES, requested)
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > limit:
            raise _LimitFailure("MaybeSheet response exceeded the configured byte limit", limit)
        return payload

    def _formula_argv(self, verb: str, target: otf.BoundGridFormulaTarget, rectangle: otf.A1Rectangle | None) -> tuple[str, ...]:
        argv = ["mbs", "formula", verb, "--target", _mbs_target(target.grid), "--gid", target.worksheet.worksheet_id or ""]
        if rectangle is not None:
            argv.extend(("--range", rectangle.start_address if rectangle.start_address == rectangle.end_address else f"{rectangle.start_address}:{rectangle.end_address}"))
        return tuple(argv)

    def _worksheet_argv(self, target: otf.BoundGridFormulaTarget, rectangle: otf.A1Rectangle) -> tuple[str, ...]:
        return (
            "mbs", "excel-worksheet", "read", "--uri", _mbs_target(target.grid), "--gid", target.worksheet.worksheet_id or "",
            "--range", rectangle.start_address if rectangle.start_address == rectangle.end_address else f"{rectangle.start_address}:{rectangle.end_address}",
            "--value-render-option", "UNFORMATTED_VALUE", "--output", "json",
        )

    def _parse_formula_observation(self, result: Mapping[str, Any], target: otf.BoundGridFormulaTarget, rectangle: otf.A1Rectangle, limits: otf.FormulaResourceLimits | None) -> otf.GridFormulaObservation:
        matrix = self._matrix(result, ("formulas", "formula_values", "formula_matrix"), rectangle)
        metadata = self._metadata_matrix(result.get("cell_metadata", result.get("metadata")), rectangle)
        formulas: list[otf.FormulaCell] = []
        expression_bytes = 0
        for row_offset, row in enumerate(matrix):
            for column_offset, value in enumerate(row):
                metadata_cell = metadata[row_offset][column_offset] if metadata is not None and row_offset < len(metadata) and column_offset < len(metadata[row_offset]) else None
                text = self._formula_text(value, metadata_cell)
                if text is None:
                    continue
                expression_bytes += len(text.encode())
                if expression_bytes > self._expression_limit(limits):
                    raise _LimitFailure("formula response exceeded the configured expression byte limit", self._expression_limit(limits))
                formulas.append(otf.FormulaCell(_address(rectangle.start_column + column_offset, rectangle.start_row + row_offset), otf.FormulaExpression(text, otf.MAYBE_SHEET_A1)))
        revision = self._revision(result, {"target": target.grid.value, "gid": target.worksheet.worksheet_id, "formulas": [cell.to_wire() for cell in formulas]})
        requested_range = rectangle.start_address if rectangle.start_address == rectangle.end_address else f"{rectangle.start_address}:{rectangle.end_address}"
        return otf.GridFormulaObservation(target.worksheet.worksheet_id or "", requested_range, tuple(formulas), revision)

    def _parse_value_observation(self, result: Mapping[str, Any], target: otf.BoundGridFormulaTarget, rectangle: otf.A1Rectangle, limits: otf.FormulaResourceLimits | None) -> otf.GridFormulaValueObservation:
        values = result.get("values")
        if not isinstance(values, list):
            raise _ProtocolFailure
        matrix = self._checked_matrix(values, rectangle)
        metadata = self._metadata_matrix(result.get("cell_metadata", result.get("metadata")), rectangle)
        formula_cells = result.get("formula_cells")
        formula_addresses: set[str] | None = None
        if formula_cells is not None:
            if not isinstance(formula_cells, list):
                raise _ProtocolFailure
            formula_addresses = set()
            for item in formula_cells:
                if not isinstance(item, str):
                    raise _ProtocolFailure
                try:
                    cell = otf.A1Rectangle.parse(item)
                except (TypeError, ValueError):
                    raise _ProtocolFailure from None
                if (
                    cell.cell_count != 1
                    or cell.worksheet_name is not None
                    or not (
                        rectangle.start_column <= cell.start_column <= rectangle.end_column
                        and rectangle.start_row <= cell.start_row <= rectangle.end_row
                    )
                ):
                    raise _ProtocolFailure
                address = _address(cell.start_column, cell.start_row)
                if address in formula_addresses:
                    raise _ProtocolFailure
                formula_addresses.add(address)
        parsed: list[otf.FormulaValueCell] = []
        for row_offset, row in enumerate(matrix):
            for column_offset, raw in enumerate(row):
                address = _address(rectangle.start_column + column_offset, rectangle.start_row + row_offset)
                metadata_cell = metadata[row_offset][column_offset] if metadata is not None and row_offset < len(metadata) and column_offset < len(metadata[row_offset]) else None
                if formula_addresses is not None:
                    is_formula = address in formula_addresses
                else:
                    is_formula = self._is_formula_metadata(metadata_cell)
                if not is_formula:
                    continue
                parsed.append(otf.FormulaValueCell(address, self._value(raw)))
        if formula_addresses is not None:
            returned_addresses = {cell.address for cell in parsed}
            if returned_addresses != formula_addresses:
                raise _ProtocolFailure
        state = result.get("calculation_state", "unknown")
        if not isinstance(state, str):
            raise _ProtocolFailure
        revision = self._revision(result, {"target": target.grid.value, "gid": target.worksheet.worksheet_id, "values": [cell.to_wire() for cell in parsed]})
        requested_range = rectangle.start_address if rectangle.start_address == rectangle.end_address else f"{rectangle.start_address}:{rectangle.end_address}"
        return otf.GridFormulaValueObservation(
            target.worksheet.worksheet_id or "", requested_range, tuple(parsed), otf.CalculationState(state), otf.CalculationTrigger.PROVIDER_READ, "provider_dynamic", revision
        )

    def _matrix(self, result: Mapping[str, Any], keys: tuple[str, ...], rectangle: otf.A1Rectangle) -> list[list[Any]]:
        for key in keys:
            if key in result:
                return self._checked_matrix(result[key], rectangle)
        raise _ProtocolFailure

    def _checked_matrix(self, matrix: object, rectangle: otf.A1Rectangle) -> list[list[Any]]:
        if not isinstance(matrix, list) or len(matrix) > rectangle.height:
            raise _ProtocolFailure
        checked: list[list[Any]] = []
        for row in matrix:
            if not isinstance(row, list) or len(row) > rectangle.width:
                raise _ProtocolFailure
            checked.append(row)
        return checked

    def _metadata_matrix(self, metadata: object, rectangle: otf.A1Rectangle) -> list[list[Any]] | None:
        if metadata is None:
            return None
        return self._checked_matrix(metadata, rectangle)

    def _formula_text(self, value: object, metadata: object) -> str | None:
        if isinstance(metadata, Mapping) and isinstance(metadata.get("formula"), str):
            return metadata["formula"]
        if isinstance(value, Mapping) and isinstance(value.get("formula"), str):
            return value["formula"] if metadata is None or self._is_formula_metadata(metadata) else None
        if not self._is_formula_metadata(metadata):
            if metadata is None and isinstance(value, str) and value:
                return value
            return None
        if not isinstance(value, str) or not value:
            raise _ProtocolFailure
        return value

    def _is_formula_metadata(self, metadata: object) -> bool:
        if not isinstance(metadata, Mapping):
            return False
        return metadata.get("kind") in {"formula", "FORMULA"} or metadata.get("type") in {"formula", "FORMULA"} or metadata.get("is_formula") is True or isinstance(metadata.get("formula"), str)

    def _value(self, raw: object) -> otf.FormulaValue:
        if isinstance(raw, Mapping):
            error = raw.get("error")
            if isinstance(error, Mapping) and isinstance(error.get("code"), str) and error["code"]:
                return otf.FormulaValue.provider_error(otf.FormulaErrorValue(error["code"]))
            if set(raw) == {"error_code"} and isinstance(raw["error_code"], str) and raw["error_code"]:
                return otf.FormulaValue.provider_error(otf.FormulaErrorValue(raw["error_code"]))
        try:
            return otf.FormulaValue.from_python(raw)
        except (TypeError, ValueError):
            raise _ProtocolFailure from None

    def _validated_range(
        self,
        selector: str,
        limits: otf.FormulaResourceLimits | None,
        binding_limit: int | None = None,
    ) -> otf.A1Rectangle:
        rectangle = otf.A1Rectangle.parse(selector)
        limit = _MAX_CELLS if binding_limit is None else min(_MAX_CELLS, binding_limit)
        if limits is not None and limits.max_cells is not None:
            if isinstance(limits.max_cells, bool) or not isinstance(limits.max_cells, int) or limits.max_cells <= 0:
                raise _ProtocolFailure
            limit = min(limit, limits.max_cells)
        if rectangle.cell_count > limit:
            raise _LimitFailure("formula range exceeds the configured cell limit", limit)
        return rectangle

    def _expression_limit(self, limits: otf.FormulaResourceLimits | None) -> int:
        requested = limits.max_expression_bytes if limits is not None else None
        if requested is not None and (isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0):
            raise _ProtocolFailure
        return _MAX_EXPRESSION_BYTES if requested is None else min(_MAX_EXPRESSION_BYTES, requested)

    def _binding_details(self, target: otf.BoundGridFormulaTarget) -> otf.FormulaCapabilityDetails:
        with self._lock:
            cached = self._bindings.get((target.grid.value, target.worksheet.worksheet_id or ""))
        if cached is None:
            raise _BindingFailure
        return cached[1]

    def _capability_details(self, result: Mapping[str, Any]) -> otf.FormulaCapabilityDetails:
        raw_scopes = result.get("recalculation_scopes", ())
        if not isinstance(raw_scopes, list) or not all(isinstance(item, str) for item in raw_scopes):
            raise _ProtocolFailure
        scopes = tuple(item for item in ("range", "worksheet", "workbook") if item in raw_scopes)
        raw_states = result.get("calculation_states", ["provider_current", "unknown"])
        if not isinstance(raw_states, list):
            raise _ProtocolFailure
        states = tuple(otf.CalculationState(item) for item in raw_states)
        atomicity = self._enum(result.get("mutation_atomicity", "unknown"), otf.MutationAtomicity)
        revision = self._enum(result.get("revision_enforcement", "unavailable"), otf.RevisionEnforcement)
        idem = otf.IdempotencyStrength.PROVIDER if result.get("idempotency") in {True, "true", "provider", "confirmed", "supported"} else otf.IdempotencyStrength.HOST_LEDGER
        return otf.FormulaCapabilityDetails("grid", (otf.MAYBE_SHEET_A1,), _MAX_CELLS, _MAX_EXPRESSION_BYTES, scopes, states, atomicity, revision, idem)

    def _enum(self, value: object, enum_type: type[Any]) -> Any:
        if not isinstance(value, str):
            raise _ProtocolFailure
        try:
            return enum_type(value)
        except ValueError:
            return enum_type.UNKNOWN

    def _revision(self, result: Mapping[str, Any], fallback: object) -> str:
        revision = result.get("revision")
        if isinstance(revision, str) and _HASH_RE.fullmatch(revision):
            return revision
        return _hash_payload(fallback)

    def _optional_revision(self, value: object) -> str | None:
        if value is None:
            return None
        return value if isinstance(value, str) and _HASH_RE.fullmatch(value) else _hash_payload(value)

    def _safe_provider_text(self, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise _ProtocolFailure
        return value.strip()

    def _expected_formula_map(self, rectangle: otf.A1Rectangle, expression: otf.FormulaExpression) -> dict[str, str]:
        return {
            _address(column, row): self._translate_formula(expression.text, column - rectangle.start_column, row - rectangle.start_row)
            for row in range(rectangle.start_row, rectangle.end_row + 1)
            for column in range(rectangle.start_column, rectangle.end_column + 1)
        }

    def _translate_formula(self, expression: str, column_delta: int, row_delta: int) -> str:
        output: list[str] = []
        position = 0
        square_bracket_depth = 0
        while position < len(expression):
            if expression[position] in {'"', "'"}:
                quote = expression[position]
                end = position + 1
                while end < len(expression):
                    if expression[end] == quote:
                        end += 1
                        break
                    end += 1
                output.append(expression[position:end])
                position = end
                continue
            if expression[position] == "[":
                square_bracket_depth += 1
                output.append(expression[position])
                position += 1
                continue
            if expression[position] == "]":
                square_bracket_depth = max(0, square_bracket_depth - 1)
                output.append(expression[position])
                position += 1
                continue
            if square_bracket_depth:
                output.append(expression[position])
                position += 1
                continue
            match = _CELL_REFERENCE.match(expression, position)
            if match is None:
                output.append(expression[position])
                position += 1
                continue
            end = match.end()
            previous = expression[position - 1] if position else ""
            following = expression[end] if end < len(expression) else ""
            if following in {"!", "("} or (previous and (previous.isalnum() or previous == "_")):
                output.append(expression[position:end])
                position = end
                continue
            raw_column, raw_row = match.group("column"), match.group("row")
            absolute_column, absolute_row = raw_column.startswith("$"), raw_row.startswith("$")
            column_text, row_text = raw_column.removeprefix("$"), raw_row.removeprefix("$")
            column = 0
            for character in column_text.upper():
                column = column * 26 + ord(character) - ord("A") + 1
            row = int(row_text)
            if not absolute_column:
                column += column_delta
            if not absolute_row:
                row += row_delta
            if column <= 0 or row <= 0:
                raise _ProtocolFailure
            output.append(("$" if absolute_column else "") + _address(column, 1).rstrip("1") + ("$" if absolute_row else "") + str(row))
            position = end
        return "".join(output)

    def _provider_error(self, error: Mapping[str, Any]) -> tuple[otf.FormulaErrorCode, str]:
        raw_code = error.get("code")
        if not isinstance(raw_code, str):
            raise _ProtocolFailure
        code = re.sub(r"[-\s]+", "_", raw_code.strip().casefold())
        mapping = {
            "stale_revision": otf.FormulaErrorCode.STALE_REVISION,
            "revision_mismatch": otf.FormulaErrorCode.STALE_REVISION,
            "invalid_formula": otf.FormulaErrorCode.INVALID_FORMULA,
            "formula_invalid": otf.FormulaErrorCode.INVALID_FORMULA,
            "syntax_error": otf.FormulaErrorCode.INVALID_FORMULA,
            "resource_limit": otf.FormulaErrorCode.RESOURCE_LIMIT,
            "resource_limit_exceeded": otf.FormulaErrorCode.RESOURCE_LIMIT,
            "limit_exceeded": otf.FormulaErrorCode.RESOURCE_LIMIT,
            "protocol_error": otf.FormulaErrorCode.PROTOCOL_FAILURE,
            "protocol_invalid": otf.FormulaErrorCode.PROTOCOL_FAILURE,
            "protocol_failure": otf.FormulaErrorCode.PROTOCOL_FAILURE,
            "provider_rejected": otf.FormulaErrorCode.EXECUTION_FAILED,
            "rejected": otf.FormulaErrorCode.EXECUTION_FAILED,
            "execution_failed": otf.FormulaErrorCode.EXECUTION_FAILED,
        }
        mapped = mapping.get(code, otf.FormulaErrorCode.EXECUTION_FAILED)
        return mapped, f"MaybeSheet provider rejected the {mapped.value.replace('_', ' ')} operation"

    def _request_timeout(self, limits: otf.FormulaResourceLimits | None) -> float | int:
        if limits is None or limits.timeout_seconds is None:
            return self._timeout
        return limits.timeout_seconds

    def _mark_unknown(self, request: otf.GridFormulaSetRequest, context: tuple[str, str, str] | None) -> None:
        if request.idempotency_key is not None and context is not None:
            with self._lock:
                self._ledger.mark_unknown(connector_id="maybe_sheet", target_hash=context[0], selector_hash=context[1], idempotency_key=request.idempotency_key, payload_hash=context[2])

    def _finish_ledger(self, request: otf.GridFormulaSetRequest, context: tuple[str, str, str] | None, *, dispatched: bool) -> None:
        if request.idempotency_key is None or context is None:
            return
        with self._lock:
            if dispatched:
                self._ledger.mark_unknown(connector_id="maybe_sheet", target_hash=context[0], selector_hash=context[1], idempotency_key=request.idempotency_key, payload_hash=context[2])
            else:
                self._ledger.fail_known(connector_id="maybe_sheet", target_hash=context[0], selector_hash=context[1], idempotency_key=request.idempotency_key, payload_hash=context[2])

    def _finish_recalculation_ledger(
        self,
        request: otf.GridFormulaRecalculateRequest,
        context: tuple[str, str, str] | None,
        *,
        dispatched: bool,
    ) -> None:
        if request.idempotency_key is None or context is None:
            return
        with self._lock:
            if dispatched:
                self._ledger.mark_unknown(
                    connector_id="maybe_sheet",
                    target_hash=context[0],
                    selector_hash=context[1],
                    idempotency_key=request.idempotency_key,
                    payload_hash=context[2],
                )
            else:
                self._ledger.fail_known(
                    connector_id="maybe_sheet",
                    target_hash=context[0],
                    selector_hash=context[1],
                    idempotency_key=request.idempotency_key,
                    payload_hash=context[2],
                )

    def _transport_error(self, exc: ConnectorError, operation: str) -> otf.FormulaExtensionResult[Any]:
        mapping = {
            ConnectorErrorCode.TIMEOUT: otf.FormulaErrorCode.TIMEOUT,
            ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED: otf.FormulaErrorCode.RESOURCE_LIMIT,
            ConnectorErrorCode.PROTOCOL_INVALID: otf.FormulaErrorCode.PROTOCOL_FAILURE,
            ConnectorErrorCode.PROTOCOL_VERSION_UNSUPPORTED: otf.FormulaErrorCode.PROTOCOL_FAILURE,
        }
        return _rejected(mapping.get(exc.code, otf.FormulaErrorCode.EXECUTION_FAILED), f"MaybeSheet {operation} failed")


__all__ = ["MaybeSheetGridFormulaExtension"]
