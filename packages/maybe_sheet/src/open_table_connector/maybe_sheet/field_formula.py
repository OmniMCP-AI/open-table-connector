"""Maybe Sheet base-mode formula-field extension."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from collections.abc import Mapping
from time import monotonic
from typing import Any

import open_table_connector.formulas as otf
from open_table_connector.contract import ConnectorError, ConnectorErrorCode, TableMode

from .connector import MaybeSheetConnector, ProcessClient, _mbs_target

_CAPABILITIES = (otf.FIELD_READ, otf.FIELD_SET, otf.FIELD_VALUES_READ, otf.FIELD_RECALCULATE)
_MAX_RECORDS = 50_000
_MAX_EXPRESSION_BYTES = 64 * 1024
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_LEDGER_LIMIT = 1024
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


class _ProtocolFailure(Exception):
    pass


class _BindingFailure(Exception):
    def __init__(self, message: str, code: otf.FormulaErrorCode = otf.FormulaErrorCode.TARGET_NOT_FOUND) -> None:
        super().__init__(message)
        self.code = code


class _ProviderFailure(Exception):
    def __init__(self, code: otf.FormulaErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


class _LimitFailure(Exception):
    def __init__(self, message: str, limit: int) -> None:
        super().__init__(message)
        self.limit = limit


class _SnapshotFailure(Exception):
    pass


def _hash_payload(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _success(value: Any, receipts: tuple[object, ...] = ()) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(
        value=value,
        outcome=otf.FormulaOutcome.SUCCEEDED,
        commit=otf.FormulaCommitState.NOT_APPLICABLE,
        verification=otf.FormulaVerificationState.PASSED,
        receipts=receipts,
    )


def _rejected(
    code: otf.FormulaErrorCode,
    message: str,
    details: Mapping[str, Any] | None = None,
) -> otf.FormulaExtensionResult[Any]:
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


def _unknown(message: str = "formula commit state could not be determined") -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(
        value=None,
        outcome=otf.FormulaOutcome.UNKNOWN,
        commit=otf.FormulaCommitState.UNKNOWN,
        verification=otf.FormulaVerificationState.UNAVAILABLE,
        receipts=(),
        error=otf.FormulaExtensionErrorInfo(otf.FormulaErrorCode.UNCERTAIN_MUTATION, message, {}),
    )


class MaybeSheetFieldFormulaExtension(otf.FieldFormulaConnectorExtension):
    """Formula operations over existing Maybe base-mode formula fields."""

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
        self._bindings: dict[tuple[int, str], tuple[str, dict[str, Any], otf.FormulaCapabilityDetails, str]] = {}
        self._ledger = otf.FormulaIdempotencyLedger(limit=_LEDGER_LIMIT)
        self._completed: OrderedDict[str, otf.FormulaExtensionResult[Any]] = OrderedDict()
        self._lock = threading.RLock()

    def bind_field(
        self,
        request: otf.FieldFormulaBindRequest[Any],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaBinding[Any]]:
        table = request.target.table
        try:
            uri, mode = self._table_info(table)
            if mode is not TableMode.BASE:
                return _rejected(otf.FormulaErrorCode.UNSUPPORTED_MODE, "MaybeSheet field formulas require a base-mode Table")
            selector = request.target.field
            argv = self._formula_read_argv(uri, selector)
            payload = self._call(argv, operation="formula.read")
            result = self._result(payload)
            if self._target_kind(payload, result) not in {"base", "table"}:
                return _rejected(otf.FormulaErrorCode.UNSUPPORTED_MODE, "MaybeSheet formula target is not base mode")
            table_id = self._table_id(result)
            field = self._select_field(result, selector)
            self._validate_formula_field(field)
            field_id = self._field_id(field)
            details = self._capability_details(result)
            revision = self._revision(result, field)
            bound = otf.FieldFormulaBinding(
                target=otf.BoundFieldFormulaTarget(table, otf.FieldRef(field_id=field_id)),
                capabilities=otf.FormulaCapabilitySet(
                    tuple(capability for capability in _CAPABILITIES if capability is not otf.FIELD_RECALCULATE or details.recalculation_scopes),
                    details,
                ),
                observed_revision=revision,
            )
            with self._lock:
                self._bindings[(id(table), field_id)] = (table_id, dict(field), details, revision)
            return _success(bound)
        except _ProviderFailure as exc:
            return _rejected(exc.code, "MaybeSheet rejected the formula field binding")
        except _BindingFailure as exc:
            return _rejected(exc.code, str(exc) or "MaybeSheet formula field was not found")
        except ConnectorError as exc:
            return self._transport_error(exc)
        except _ProtocolFailure:
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid formula field response")
        except (TypeError, ValueError, KeyError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid formula field response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula field binding failed")

    def read_field(
        self,
        request: otf.FieldFormulaReadRequest[Any],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaObservation]:
        try:
            table_id, before, _details, _binding_revision = self._binding(request.target)
            uri, _mode = self._table_info(request.target.table)
            payload = self._call(
                self._formula_read_argv(uri, request.target.field),
                operation="formula.read",
            )
            result = self._result(payload)
            field = self._select_field(result, request.target.field)
            self._validate_formula_field(field)
            if self._table_id(result) != table_id or self._field_id(field) != request.target.field.field_id:
                raise _ProtocolFailure
            observation = self._observation(uri, field, result, fallback=before)
            receipt = otf.FormulaReceiptDetails(
                target_kind="field",
                table_mode="base",
                target=uri.value,
                selector=observation.field_id,
                capability=otf.FIELD_READ.to_reference(),
                dialect=observation.expression.dialect,
                observed_count=1,
                observation_sha256=otf.formula_observation_hash(observation),
                revision_after=observation.observed_revision,
            )
            return _success(observation, (receipt,))
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet formula field binding is required")
        except _ProviderFailure as exc:
            return _rejected(exc.code, "MaybeSheet rejected the formula field read")
        except ConnectorError as exc:
            return self._transport_error(exc)
        except (_ProtocolFailure, TypeError, ValueError, KeyError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid formula field response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula field read failed")

    def set_field(
        self,
        request: otf.FieldFormulaSetRequest[Any],
    ) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        context: tuple[str, str, str] | None = None
        dispatched = False
        try:
            table_id, before, details, binding_revision = self._binding(request.target)
            uri, _mode = self._table_info(request.target.table)
            if request.expression.dialect != otf.MAYBE_BASE:
                return _rejected(otf.FormulaErrorCode.INVALID_FORMULA, "MaybeSheet field formulas require the maybe-base dialect")
            if request.expression.byte_count > self._expression_limit(request, details):
                raise _LimitFailure("formula expression exceeds the configured byte limit", self._expression_limit(request, details))
            fresh_before = self._read_metadata(uri, request.target.field, table_id)
            expected_revision = request.expected_revision or binding_revision
            if fresh_before[2] != expected_revision:
                return _rejected(otf.FormulaErrorCode.STALE_REVISION, "formula field revision is stale", {"revision_hash": fresh_before[2]})
            target_hash = _hash_payload({"table_id": table_id, "field_id": request.target.field.field_id})
            selector_hash = _hash_payload({"field_id": request.target.field.field_id})
            payload_hash = _hash_payload({"table_id": table_id, "field_id": request.target.field.field_id, "expression_sha256": request.expression.sha256, "dialect": request.expression.dialect, "expected_revision": expected_revision})
            context = (target_hash, selector_hash, payload_hash)
            decision = None
            if request.idempotency_key is not None:
                with self._lock:
                    decision = self._ledger.begin(
                        connector_id="maybe_sheet",
                        capability=otf.FIELD_SET.to_reference(),
                        target_hash=target_hash,
                        selector_hash=selector_hash,
                        idempotency_key=request.idempotency_key,
                        payload_hash=payload_hash,
                    )
                if decision.disposition is otf.FormulaIdempotencyDisposition.CONFLICT:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula field idempotency key conflicts with a prior request")
                if decision.disposition is otf.FormulaIdempotencyDisposition.IN_FLIGHT:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula field idempotency key is already in flight")
                if decision.disposition is otf.FormulaIdempotencyDisposition.UNKNOWN:
                    return _unknown()
                if decision.disposition is otf.FormulaIdempotencyDisposition.REPLAY:
                    with self._lock:
                        cached = self._completed.get(decision.operation_hash or "")
                    return cached if cached is not None else _unknown("formula field replay result is unavailable")
            argv = [
                "mbs", "formula", "set", "--target", _mbs_target(uri),
                "--field-id", request.target.field.field_id or "",
                "--expression", request.expression.text,
                "--language", "base",
            ]
            if request.idempotency_key is not None:
                argv.extend(("--idempotency-key", request.idempotency_key))
            argv.append("--verify")
            argv.extend(("--expected-revision", expected_revision))
            argv.extend(("--output", "json"))
            dispatched = True
            self._call(tuple(argv), operation="formula.set")
            fresh_after = self._read_metadata(uri, request.target.field, table_id)
            if not self._metadata_isolated(fresh_before[0], fresh_after[0]):
                self._finish_ledger(request, context, True)
                return _failed(otf.FormulaErrorCode.READBACK_MISMATCH, "formula field metadata changed outside the expression", commit=otf.FormulaCommitState.COMMITTED, verification=otf.FormulaVerificationState.FAILED)
            after_field = fresh_after[1]
            if self._expression(after_field) != request.expression.text:
                self._finish_ledger(request, context, True)
                return _failed(otf.FormulaErrorCode.READBACK_MISMATCH, "formula field readback did not match the requested expression", commit=otf.FormulaCommitState.COMMITTED, verification=otf.FormulaVerificationState.FAILED)
            observation = self._observation(uri, after_field, {"revision": fresh_after[2]}, fallback=fresh_before[0], expression=request.expression)
            mutation = otf.FormulaMutation("field", 1, observation, expected_revision, fresh_after[2])
            receipt = otf.FormulaReceiptDetails.for_field_set(
                target=uri.value,
                selector=observation.field_id,
                capability=otf.FIELD_SET.to_reference(),
                dialect=request.expression.dialect,
                expression_sha256=request.expression.sha256,
                observation_sha256=otf.formula_observation_hash(observation),
                affected_count=1,
                revision_before=mutation.revision_before,
                revision_after=mutation.revision_after,
                mutation_atomicity=details.mutation_atomicity.value,
                revision_enforcement=details.revision_enforcement.value,
                verification="formula_text_readback",
            )
            result = otf.FormulaExtensionResult(mutation, otf.FormulaOutcome.SUCCEEDED, otf.FormulaCommitState.COMMITTED, otf.FormulaVerificationState.PASSED, (receipt,))
            if request.idempotency_key is not None and context is not None:
                operation_hash = _hash_payload(mutation.to_wire())
                with self._lock:
                    self._completed[operation_hash] = result
                    self._completed.move_to_end(operation_hash)
                    while len(self._completed) > _LEDGER_LIMIT:
                        self._completed.popitem(last=False)
                    self._ledger.succeed(connector_id="maybe_sheet", target_hash=context[0], selector_hash=context[1], idempotency_key=request.idempotency_key, payload_hash=context[2], operation_hash=operation_hash)
            return result
        except _LimitFailure as exc:
            self._finish_ledger(request, context, dispatched)
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit}) if not dispatched else _unknown()
        except _ProviderFailure as exc:
            self._finish_ledger(request, context, False)
            return _rejected(exc.code, "MaybeSheet rejected the formula field mutation")
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet formula field binding is required")
        except ConnectorError as exc:
            self._finish_ledger(request, context, dispatched)
            before_dispatch = exc.code is ConnectorErrorCode.TIMEOUT and exc.safe_details.get("before_dispatch") is True
            if dispatched and not before_dispatch:
                return _unknown()
            return self._transport_error(exc)
        except (_ProtocolFailure, TypeError, ValueError, KeyError):
            self._finish_ledger(request, context, dispatched)
            return _unknown() if dispatched else _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid formula field mutation response")
        except Exception:
            self._finish_ledger(request, context, dispatched)
            return _unknown() if dispatched else _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula field mutation failed")

    def read_field_values(
        self,
        request: otf.FieldFormulaValueReadRequest[Any],
    ) -> otf.FormulaExtensionResult[otf.FieldFormulaValueObservation]:
        try:
            table_id, before, _details, _binding_revision = self._binding(request.target)
            uri, _mode = self._table_info(request.target.table)
            max_records, max_bytes = self._value_limits(request.limits)
            records: list[otf.FormulaRecordValue] = []
            seen: set[str] = set()
            offset = 0
            pages: list[Mapping[str, Any]] = []
            state: otf.CalculationState | None = None
            snapshot_revision: str | None = None
            response_bytes = 0
            started = monotonic()
            timeout_seconds = self._timeout if request.limits is None or request.limits.timeout_seconds is None else request.limits.timeout_seconds
            while True:
                payload = self._call(
                    (
                        "mbs", "base-table", "read", "--uri", _mbs_target(uri),
                        "--table-id", table_id, "--limit", str(min(500, max_records)),
                        "--offset", str(offset), "--output", "json",
                    ),
                    operation="base-table.read",
                    limits=request.limits,
                )
                result = self._result(payload)
                pages.append(result)
                if self._table_id(result) != table_id:
                    raise _ProtocolFailure
                page_revision = result.get("snapshot_revision", result.get("revision"))
                if not self._is_hash(page_revision):
                    raise _SnapshotFailure
                if snapshot_revision is None:
                    snapshot_revision = page_revision
                elif snapshot_revision != page_revision:
                    raise _SnapshotFailure
                response_bytes += len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode())
                if response_bytes > max_bytes:
                    raise _LimitFailure("formula field values exceeded the configured response byte limit", max_bytes)
                elapsed_ms = (monotonic() - started) * 1000
                if elapsed_ms > timeout_seconds * 1000:
                    raise _LimitFailure("formula field values exceeded the configured timeout", int(timeout_seconds * 1000))
                page_state = self._calculation_state(result.get("calculation_state"))
                if state is None:
                    state = page_state
                elif state is not page_state:
                    raise _ProtocolFailure
                raw_records = result.get("records", result.get("rows"))
                if not isinstance(raw_records, list):
                    raise _ProtocolFailure
                for raw_record in raw_records:
                    if not isinstance(raw_record, Mapping):
                        raise _ProtocolFailure
                    record_id = raw_record.get("record_id", raw_record.get("id"))
                    if not isinstance(record_id, str) or not record_id or record_id in seen:
                        raise _ProtocolFailure
                    value = self._record_value(raw_record, request.target.field.field_id or "")
                    seen.add(record_id)
                    records.append(otf.FormulaRecordValue(record_id, value))
                    if len(records) > max_records:
                        raise _LimitFailure("formula field values exceeded the configured record limit", max_records)
                has_more = result.get("has_more", False)
                if not isinstance(has_more, bool):
                    raise _ProtocolFailure
                if not has_more:
                    break
                next_offset = result.get("next_offset", offset + len(raw_records))
                if isinstance(next_offset, bool) or not isinstance(next_offset, int) or next_offset <= offset:
                    raise _ProtocolFailure
                offset = next_offset
            if snapshot_revision is None:
                raise _SnapshotFailure
            revision = snapshot_revision
            observation = otf.FieldFormulaValueObservation(
                table_uri=uri,
                field_id=request.target.field.field_id or "",
                field_name=self._field_name(before),
                values=tuple(records),
                calculation_state=state or otf.CalculationState.UNKNOWN,
                calculation_trigger=otf.CalculationTrigger.PROVIDER_READ,
                dependency_scope="provider_dynamic",
                observed_revision=revision,
            )
            receipt = otf.FormulaReceiptDetails.for_field_values_read(
                target=uri.value,
                selector=observation.field_id,
                capability=otf.FIELD_VALUES_READ.to_reference(),
                dialect=otf.MAYBE_BASE,
                observation_sha256=_hash_payload({"field_id": observation.field_id, "revision": revision}),
                value_observation_sha256=otf.formula_observation_hash(observation),
                observed_count=len(records),
                revision_after=revision,
                calculation_state=observation.calculation_state.value,
                calculation_trigger=observation.calculation_trigger.value,
                dependency_scope=observation.dependency_scope,
            )
            return _success(observation, (receipt,))
        except _LimitFailure as exc:
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _SnapshotFailure:
            return _rejected(otf.FormulaErrorCode.SNAPSHOT_UNAVAILABLE, "MaybeSheet could not prove a stable formula value snapshot")
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet formula field binding is required")
        except _ProviderFailure as exc:
            return _rejected(exc.code, "MaybeSheet rejected the formula field value read")
        except ConnectorError as exc:
            return self._transport_error(exc)
        except (_ProtocolFailure, TypeError, ValueError, KeyError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid formula field value response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula field value read failed")

    def recalculate_field(
        self,
        request: otf.FieldFormulaRecalculateRequest[Any],
    ) -> otf.FormulaExtensionResult[otf.RecalculationObservation]:
        context: tuple[str, str, str] | None = None
        dispatched = False
        try:
            table_id, before, details, binding_revision = self._binding(request.target)
            if request.scope.value not in details.recalculation_scopes:
                return _rejected(otf.FormulaErrorCode.UNSUPPORTED_CAPABILITY, "MaybeSheet does not support the requested field recalculation scope")
            uri, _mode = self._table_info(request.target.table)
            expected_revision = request.expected_revision or binding_revision
            target_hash = _hash_payload({"table_id": table_id, "field_id": request.target.field.field_id})
            selector_hash = _hash_payload({"scope": request.scope.value})
            payload_hash = _hash_payload({"table_id": table_id, "field_id": request.target.field.field_id, "scope": request.scope.value, "expected_revision": expected_revision})
            context = (target_hash, selector_hash, payload_hash)
            decision = None
            if request.idempotency_key is not None:
                with self._lock:
                    decision = self._ledger.begin(
                        connector_id="maybe_sheet",
                        capability=otf.FIELD_RECALCULATE.to_reference(),
                        target_hash=target_hash,
                        selector_hash=selector_hash,
                        idempotency_key=request.idempotency_key,
                        payload_hash=payload_hash,
                    )
                if decision.disposition is otf.FormulaIdempotencyDisposition.CONFLICT:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula recalculation idempotency key conflicts with a prior request")
                if decision.disposition is otf.FormulaIdempotencyDisposition.IN_FLIGHT:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula recalculation idempotency key is already in flight")
                if decision.disposition is otf.FormulaIdempotencyDisposition.UNKNOWN:
                    return _unknown("formula recalculation remains uncertain")
                if decision.disposition is otf.FormulaIdempotencyDisposition.REPLAY:
                    with self._lock:
                        cached = self._completed.get(decision.operation_hash or "")
                    return cached if cached is not None else _unknown("formula recalculation replay result is unavailable")
            argv = ["mbs", "formula", "recalculate", "--target", _mbs_target(uri)]
            if request.scope is otf.FieldRecalculationScope.FIELD:
                argv.extend(("--field-id", request.target.field.field_id or ""))
            argv.append("--verify")
            argv.extend(("--expected-revision", expected_revision))
            argv.extend(("--output", "json"))
            dispatched = True
            payload = self._call(tuple(argv), operation="formula.recalculate")
            result = self._result(payload)
            state = self._calculation_state(result.get("calculation_state"))
            value_observation = None
            raw_values = result.get("value_observation")
            if raw_values is None and "records" in result:
                value_observation = self._values_from_result(uri, before, result, trigger=otf.CalculationTrigger.EXPLICIT_RECALCULATION)
            elif raw_values is not None:
                if not isinstance(raw_values, Mapping):
                    raise _ProtocolFailure
                value_observation = otf.FieldFormulaValueObservation.from_wire(raw_values)
            if value_observation is not None:
                state = value_observation.calculation_state
            observation = otf.RecalculationObservation(
                target_kind="field",
                requested_scope=request.scope.value,
                effective_scope=str(result.get("effective_scope", request.scope.value)),
                revision_before=expected_revision,
                revision_after=self._optional_revision(result.get("revision", expected_revision)),
                provider_status=self._safe_text(result.get("status", "completed")),
                calculation_state=state,
                verification="passed" if value_observation is not None else "unavailable",
                value_observation=value_observation,
            )
            verification = otf.FormulaVerificationState.PASSED if value_observation is not None else otf.FormulaVerificationState.UNAVAILABLE
            final = otf.FormulaExtensionResult(observation, otf.FormulaOutcome.SUCCEEDED, otf.FormulaCommitState.COMMITTED, verification, ())
            if request.idempotency_key is not None and context is not None:
                operation_hash = _hash_payload(observation.to_wire())
                with self._lock:
                    self._completed[operation_hash] = final
                    self._completed.move_to_end(operation_hash)
                    while len(self._completed) > _LEDGER_LIMIT:
                        self._completed.popitem(last=False)
                    self._ledger.succeed(connector_id="maybe_sheet", target_hash=context[0], selector_hash=context[1], idempotency_key=request.idempotency_key, payload_hash=context[2], operation_hash=operation_hash)
            return final
        except _ProviderFailure as exc:
            self._finish_recalc_ledger(request, context, False)
            return _rejected(exc.code, "MaybeSheet rejected the formula field recalculation")
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "MaybeSheet formula field binding is required")
        except ConnectorError as exc:
            self._finish_recalc_ledger(request, context, dispatched)
            before_dispatch = exc.code is ConnectorErrorCode.TIMEOUT and exc.safe_details.get("before_dispatch") is True
            return _unknown() if dispatched and not before_dispatch else self._transport_error(exc)
        except (_ProtocolFailure, TypeError, ValueError, KeyError):
            self._finish_recalc_ledger(request, context, dispatched)
            return _unknown() if dispatched else _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "MaybeSheet returned an invalid recalculation response")
        except Exception:
            self._finish_recalc_ledger(request, context, dispatched)
            return _unknown() if dispatched else _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "MaybeSheet formula field recalculation failed")

    def _table_info(self, table: Any):
        binding = getattr(table, "_binding", None)
        uri = getattr(binding, "uri", None)
        mode = getattr(binding, "mode", None)
        if uri is None or mode is None:
            raise _BindingFailure("MaybeSheet field formulas require an SDK-owned Table")
        try:
            normalized_mode = mode if isinstance(mode, TableMode) else TableMode(str(mode))
        except ValueError as exc:
            raise _BindingFailure("MaybeSheet Table mode is invalid") from exc
        return uri, normalized_mode

    def _binding(self, target: otf.BoundFieldFormulaTarget[Any]):
        with self._lock:
            item = self._bindings.get((id(target.table), target.field.field_id or ""))
        if item is None:
            raise _BindingFailure
        return item

    def _formula_read_argv(self, uri, selector: otf.FieldRef) -> tuple[str, ...]:
        option, value = ("--field-id", selector.field_id) if selector.field_id is not None else ("--field", selector.name)
        return ("mbs", "formula", "read", "--target", _mbs_target(uri), option, value or "", "--output", "json")

    def _call(self, argv: tuple[str, ...], *, operation: str, limits: otf.FormulaResourceLimits | None = None) -> Mapping[str, Any]:
        timeout = self._timeout if limits is None or limits.timeout_seconds is None else limits.timeout_seconds
        try:
            if self._connector is not None:
                payload = self._connector._run_process(argv, credentials=self._credentials, stdin=None, timeout=timeout)
            else:
                payload = self._process.run(argv, credentials=self._credentials, stdin=None, timeout=timeout)  # type: ignore[union-attr]
        except ConnectorError:
            raise
        except Exception:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "MaybeSheet process operation failed", {}) from None
        if not isinstance(payload, Mapping) or set(payload) not in (_ENVELOPE_KEYS, _ERROR_ENVELOPE_KEYS):
            raise _ProtocolFailure
        if payload.get("contract_version") != "1.0" or payload.get("operation") != operation:
            raise _ProtocolFailure
        if payload.get("ok") is False:
            error = payload.get("error")
            if not isinstance(error, Mapping) or not isinstance(error.get("code"), str):
                raise _ProtocolFailure
            raise _ProviderFailure(self._provider_error(error["code"]))
        if payload.get("ok") is not True or "error" in payload or not isinstance(payload.get("result"), Mapping):
            raise _ProtocolFailure
        limit = _MAX_RESPONSE_BYTES if limits is None or limits.max_response_bytes is None else min(_MAX_RESPONSE_BYTES, limits.max_response_bytes)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise _ProtocolFailure
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()) > limit:
            raise _LimitFailure("MaybeSheet response exceeded the configured byte limit", limit)
        return payload

    @staticmethod
    def _result(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise _ProtocolFailure
        return result

    @staticmethod
    def _target_kind(payload: Mapping[str, Any], result: Mapping[str, Any]) -> str:
        target = payload.get("target")
        kind = target.get("kind") if isinstance(target, Mapping) else result.get("target_kind")
        if not isinstance(kind, str):
            raise _ProtocolFailure
        return kind.casefold()

    @staticmethod
    def _table_id(result: Mapping[str, Any]) -> str:
        value = result.get("table_id", result.get("base_table_id"))
        if not isinstance(value, str) or not value.strip():
            raise _ProtocolFailure
        return value.strip()

    @staticmethod
    def _select_field(result: Mapping[str, Any], selector: otf.FieldRef) -> Mapping[str, Any]:
        raw_fields = result.get("fields")
        if raw_fields is None and isinstance(result.get("field"), Mapping):
            raw_fields = [result["field"]]
        if not isinstance(raw_fields, list):
            raise _ProtocolFailure
        matches = []
        for field in raw_fields:
            if not isinstance(field, Mapping):
                raise _ProtocolFailure
            field_id = field.get("field_id", field.get("id"))
            field_name = field.get("field_name", field.get("name"))
            if (selector.field_id is not None and field_id == selector.field_id) or (selector.name is not None and field_name == selector.name):
                matches.append(field)
        if not matches:
            raise _BindingFailure("MaybeSheet formula field was not found")
        if len(matches) != 1:
            raise _BindingFailure("MaybeSheet formula field selector is ambiguous", otf.FormulaErrorCode.INVALID_TARGET)
        return matches[0]

    @staticmethod
    def _field_id(field: Mapping[str, Any]) -> str:
        value = field.get("field_id", field.get("id"))
        if not isinstance(value, str) or not value.strip():
            raise _ProtocolFailure
        return value.strip()

    @staticmethod
    def _field_name(field: Mapping[str, Any]) -> str:
        value = field.get("field_name", field.get("name"))
        if not isinstance(value, str) or not value.strip():
            raise _ProtocolFailure
        return value.strip()

    @classmethod
    def _validate_formula_field(cls, field: Mapping[str, Any]) -> None:
        kind = field.get("type", field.get("kind"))
        if kind not in {"formula", "FORMULA"} and field.get("is_formula") is not True:
            raise _BindingFailure("MaybeSheet target field is not a formula field", otf.FormulaErrorCode.INVALID_TARGET)
        cls._field_id(field)
        cls._field_name(field)
        cls._expression(field)

    @staticmethod
    def _expression(field: Mapping[str, Any]) -> str:
        prop = field.get("property")
        value = prop.get("formula_expression") if isinstance(prop, Mapping) else field.get("formula_expression")
        if value is None:
            value = field.get("expression")
        if isinstance(value, Mapping):
            value = value.get("text")
        if not isinstance(value, str) or not value.strip():
            raise _ProtocolFailure
        return value.strip()

    @classmethod
    def _observation(cls, uri, field: Mapping[str, Any], result: Mapping[str, Any], *, fallback: Mapping[str, Any], expression: otf.FormulaExpression | None = None) -> otf.FieldFormulaObservation:
        dialect = expression.dialect if expression is not None else otf.MAYBE_BASE
        expr = expression or otf.FormulaExpression(cls._expression(field), dialect)
        prop = field.get("property")
        result_type = field.get("result_type")
        if result_type is None and isinstance(prop, Mapping):
            result_type = prop.get("result_type")
        if not isinstance(result_type, str) or not result_type.strip():
            raise _ProtocolFailure
        return otf.FieldFormulaObservation(uri, cls._field_id(field), cls._field_name(field), expr, result_type.strip(), cls._revision(result, field or fallback))

    @staticmethod
    def _revision(result: Mapping[str, Any], field: Mapping[str, Any]) -> str:
        value = result.get("revision")
        if isinstance(value, str) and value.startswith("sha256:") and len(value) == 71:
            return value
        return _hash_payload(field)

    @staticmethod
    def _optional_revision(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and value.startswith("sha256:") and len(value) == 71:
            return value
        return _hash_payload(value)

    @staticmethod
    def _is_hash(value: object) -> bool:
        return isinstance(value, str) and value.startswith("sha256:") and len(value) == 71

    @classmethod
    def _capability_details(cls, result: Mapping[str, Any]) -> otf.FormulaCapabilityDetails:
        raw_scopes = result.get("recalculation_scopes", ["field", "table"])
        if not isinstance(raw_scopes, list) or not all(isinstance(item, str) for item in raw_scopes):
            raise _ProtocolFailure
        scopes = tuple(scope for scope in ("field", "table") if scope in raw_scopes)
        raw_states = result.get("calculation_states", ["unknown"])
        if not isinstance(raw_states, list):
            raise _ProtocolFailure
        states = tuple(otf.CalculationState(item) for item in raw_states)
        atomicity = cls._enum(result.get("mutation_atomicity", "unknown"), otf.MutationAtomicity)
        revision = cls._enum(result.get("revision_enforcement", "unavailable"), otf.RevisionEnforcement)
        idem = otf.IdempotencyStrength.PROVIDER if result.get("idempotency") in {True, "true", "provider", "confirmed", "supported"} else otf.IdempotencyStrength.HOST_LEDGER
        return otf.FormulaCapabilityDetails("field", (otf.MAYBE_BASE,), None, _MAX_EXPRESSION_BYTES, scopes, states, atomicity, revision, idem)

    @staticmethod
    def _enum(value: object, enum_type: type[Any]) -> Any:
        if not isinstance(value, str):
            raise _ProtocolFailure
        try:
            return enum_type(value)
        except ValueError:
            return enum_type.UNKNOWN

    @staticmethod
    def _metadata_isolated(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
        def normalized(field: Mapping[str, Any]) -> dict[str, Any]:
            value = json.loads(json.dumps(field, sort_keys=True, default=str))
            prop = value.get("property")
            if isinstance(prop, dict):
                prop.pop("formula_expression", None)
            value.pop("formula_expression", None)
            return value
        return normalized(before) == normalized(after)

    def _read_metadata(self, uri, selector: otf.FieldRef, table_id: str):
        payload = self._call(self._formula_read_argv(uri, selector), operation="formula.read")
        result = self._result(payload)
        if self._table_id(result) != table_id:
            raise _ProtocolFailure
        field = self._select_field(result, selector)
        self._validate_formula_field(field)
        return dict(field), dict(field), self._revision(result, field)

    @staticmethod
    def _record_value(record: Mapping[str, Any], field_id: str) -> otf.FormulaValue:
        containers = [record.get("fields"), record.get("values")]
        raw = None
        found = False
        for container in containers:
            if isinstance(container, Mapping) and field_id in container:
                raw, found = container[field_id], True
                break
        if not found and "value" in record:
            raw, found = record["value"], True
        if not found:
            raise _ProtocolFailure
        if isinstance(raw, Mapping) and "kind" in raw:
            return otf.FormulaValue.from_wire(raw)
        if isinstance(raw, Mapping) and isinstance(raw.get("error"), Mapping):
            code = raw["error"].get("code")
            if isinstance(code, str) and code:
                return otf.FormulaValue.provider_error(otf.FormulaErrorValue(code))
        try:
            return otf.FormulaValue.from_python(raw)
        except (TypeError, ValueError):
            raise _ProtocolFailure from None

    @classmethod
    def _values_from_result(cls, uri, field: Mapping[str, Any], result: Mapping[str, Any], *, trigger: otf.CalculationTrigger):
        raw_records = result.get("records")
        if not isinstance(raw_records, list):
            raise _ProtocolFailure
        values = tuple(
            otf.FormulaRecordValue(
                record.get("record_id", record.get("id")),
                cls._record_value(record, cls._field_id(field)),
            )
            for record in raw_records
            if isinstance(record, Mapping)
        )
        return otf.FieldFormulaValueObservation(uri, cls._field_id(field), cls._field_name(field), values, cls._calculation_state(result.get("calculation_state")), trigger, "provider_dynamic", cls._revision(result, field))

    @staticmethod
    def _calculation_state(value: object) -> otf.CalculationState:
        if not isinstance(value, str):
            return otf.CalculationState.UNKNOWN
        try:
            return otf.CalculationState(value)
        except ValueError:
            return otf.CalculationState.UNKNOWN

    @staticmethod
    def _safe_text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise _ProtocolFailure
        return value.strip()

    @staticmethod
    def _provider_error(value: str) -> otf.FormulaErrorCode:
        normalized = value.casefold().replace("-", "_").replace(" ", "_")
        return {
            "stale_revision": otf.FormulaErrorCode.STALE_REVISION,
            "revision_mismatch": otf.FormulaErrorCode.STALE_REVISION,
            "invalid_formula": otf.FormulaErrorCode.INVALID_FORMULA,
            "formula_invalid": otf.FormulaErrorCode.INVALID_FORMULA,
            "syntax_error": otf.FormulaErrorCode.INVALID_FORMULA,
            "resource_limit": otf.FormulaErrorCode.RESOURCE_LIMIT,
            "resource_limit_exceeded": otf.FormulaErrorCode.RESOURCE_LIMIT,
        }.get(normalized, otf.FormulaErrorCode.EXECUTION_FAILED)

    @staticmethod
    def _value_limits(limits: otf.FormulaResourceLimits | None) -> tuple[int, int]:
        max_records = _MAX_RECORDS if limits is None or limits.max_records is None else limits.max_records
        max_bytes = _MAX_RESPONSE_BYTES if limits is None or limits.max_response_bytes is None else min(_MAX_RESPONSE_BYTES, limits.max_response_bytes)
        if isinstance(max_records, bool) or not isinstance(max_records, int) or max_records <= 0:
            raise _ProtocolFailure
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise _ProtocolFailure
        return min(_MAX_RECORDS, max_records), max_bytes

    @staticmethod
    def _expression_limit(request: otf.FieldFormulaSetRequest[Any], details: otf.FormulaCapabilityDetails) -> int:
        return details.max_expression_bytes

    @staticmethod
    def _revision_from_pages(pages: list[Mapping[str, Any]]) -> str:
        return _hash_payload(pages)

    def _finish_ledger(self, request: otf.FieldFormulaSetRequest[Any], context: tuple[str, str, str] | None, dispatched: bool) -> None:
        if request.idempotency_key is None or context is None:
            return
        with self._lock:
            if dispatched:
                self._ledger.mark_unknown(connector_id="maybe_sheet", target_hash=context[0], selector_hash=context[1], idempotency_key=request.idempotency_key, payload_hash=context[2])
            else:
                self._ledger.fail_known(connector_id="maybe_sheet", target_hash=context[0], selector_hash=context[1], idempotency_key=request.idempotency_key, payload_hash=context[2])

    def _finish_recalc_ledger(
        self,
        request: otf.FieldFormulaRecalculateRequest[Any],
        context: tuple[str, str, str] | None,
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

    @staticmethod
    def _transport_error(exc: ConnectorError) -> otf.FormulaExtensionResult[Any]:
        mapping = {
            ConnectorErrorCode.TIMEOUT: otf.FormulaErrorCode.TIMEOUT,
            ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED: otf.FormulaErrorCode.RESOURCE_LIMIT,
            ConnectorErrorCode.PROTOCOL_INVALID: otf.FormulaErrorCode.PROTOCOL_FAILURE,
            ConnectorErrorCode.PROTOCOL_VERSION_UNSUPPORTED: otf.FormulaErrorCode.PROTOCOL_FAILURE,
        }
        return _rejected(mapping.get(exc.code, otf.FormulaErrorCode.EXECUTION_FAILED), "MaybeSheet formula field operation failed")


__all__ = ["MaybeSheetFieldFormulaExtension"]
