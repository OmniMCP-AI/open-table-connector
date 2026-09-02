"""Formula-field support for existing Feishu Bitable fields."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import OrderedDict
from collections.abc import Mapping
from time import monotonic
from typing import Any
from urllib.parse import quote

import open_table_connector.formulas as otf
from open_table_connector.contract import (
    PROVIDER_FEISHU_BITABLE,
    ConnectorError,
    ConnectorErrorCode,
    ResolveContext,
    TableMode,
    TableURI,
)

from .connector import FeishuBitableConnector, FeishuTransport

FEISHU_FORMULA_FIELD_TYPE = 20
_CAPABILITIES = (otf.FIELD_READ, otf.FIELD_SET, otf.FIELD_VALUES_READ)
_MAX_RECORDS = 50_000
_MAX_EXPRESSION_BYTES = 64 * 1024
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_LEDGER_LIMIT = 1024
_PAGE_SIZE = 100
_RECORD_PAGE_SIZE = 500


class _ProtocolFailure(Exception):
    pass


class _BindingFailure(Exception):
    def __init__(self, message: str, code: otf.FormulaErrorCode = otf.FormulaErrorCode.TARGET_NOT_FOUND) -> None:
        super().__init__(message)
        self.code = code


class _ProviderFailure(Exception):
    def __init__(self, code: otf.FormulaErrorCode, status_code: int | str | None = None) -> None:
        super().__init__(code.value)
        self.code = code
        self.status_code = status_code


class _LimitFailure(Exception):
    def __init__(self, message: str, limit: int) -> None:
        super().__init__(message)
        self.limit = limit


def _hash_payload(value: object) -> str:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _ProtocolFailure from exc
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _success(value: Any, receipts: tuple[object, ...] = ()) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(value, otf.FormulaOutcome.SUCCEEDED, otf.FormulaCommitState.NOT_APPLICABLE, otf.FormulaVerificationState.PASSED, receipts)


def _rejected(code: otf.FormulaErrorCode, message: str, details: Mapping[str, Any] | None = None) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(None, otf.FormulaOutcome.REJECTED, otf.FormulaCommitState.NOT_STARTED, otf.FormulaVerificationState.SKIPPED, (), otf.FormulaExtensionErrorInfo(code, message, details or {}))


def _failed(code: otf.FormulaErrorCode, message: str, *, commit: otf.FormulaCommitState = otf.FormulaCommitState.NOT_COMMITTED, verification: otf.FormulaVerificationState = otf.FormulaVerificationState.SKIPPED) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(None, otf.FormulaOutcome.FAILED, commit, verification, (), otf.FormulaExtensionErrorInfo(code, message, {}))


def _unknown(message: str = "formula commit state could not be determined") -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(None, otf.FormulaOutcome.UNKNOWN, otf.FormulaCommitState.UNKNOWN, otf.FormulaVerificationState.UNAVAILABLE, (), otf.FormulaExtensionErrorInfo(otf.FormulaErrorCode.UNCERTAIN_MUTATION, message, {}))


class FeishuBitableFormulaExtension(otf.FieldFormulaConnectorExtension):
    """Formula operations over existing Feishu Bitable formula fields."""

    def __init__(
        self,
        connector_or_transport: FeishuBitableConnector | FeishuTransport,
        *,
        tenant_access_token: str | None = None,
        timeout: int | float = 30,
        api_endpoint: str = "https://open.feishu.cn/open-apis/bitable/v1",
    ) -> None:
        if isinstance(connector_or_transport, FeishuBitableConnector):
            self._connector = connector_or_transport
        else:
            self._connector = FeishuBitableConnector(connector_or_transport, tenant_access_token=tenant_access_token, timeout=int(timeout), api_endpoint=api_endpoint)
        self._bindings: dict[tuple[int, str], tuple[str, dict[str, Any], otf.FormulaCapabilityDetails, str]] = {}
        self._ledger = otf.FormulaIdempotencyLedger(limit=_LEDGER_LIMIT)
        self._completed: OrderedDict[str, otf.FormulaExtensionResult[Any]] = OrderedDict()

    def __repr__(self) -> str:
        return "FeishuBitableFormulaExtension(connector_id='feishu_bitable')"

    def bind_field(self, request: otf.FieldFormulaBindRequest[Any]) -> otf.FormulaExtensionResult[otf.FieldFormulaBinding[Any]]:
        try:
            uri = self._table_uri(request.target.table)
            resource = self._resource(uri)
            if self._table_mode(request.target.table) is not TableMode.BASE:
                return _rejected(otf.FormulaErrorCode.UNSUPPORTED_MODE, "Feishu Bitable field formulas require a base-mode Table")
            fields = self._list_fields(resource.app_token, resource.table_id)
            field = self._select_field(fields, request.target.field)
            self._validate_formula_field(field)
            field_id = self._field_id(field)
            details = self._details()
            revision = self._revision(field)
            bound = otf.FieldFormulaBinding(
                otf.BoundFieldFormulaTarget(request.target.table, otf.FieldRef(field_id=field_id)),
                otf.FormulaCapabilitySet(_CAPABILITIES, details),
                revision,
            )
            self._bindings[(id(request.target.table), field_id)] = (resource.table_id, copy.deepcopy(field), details, revision)
            return _success(bound)
        except _ProviderFailure as exc:
            return _rejected(exc.code, "Feishu Bitable rejected the formula field binding")
        except _BindingFailure as exc:
            return _rejected(exc.code, str(exc) or "Feishu Bitable formula field was not found")
        except ConnectorError as exc:
            return self._transport_error(exc)
        except (_ProtocolFailure, TypeError, ValueError, KeyError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Feishu Bitable returned an invalid formula field response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "Feishu Bitable formula field binding failed")

    def read_field(self, request: otf.FieldFormulaReadRequest[Any]) -> otf.FormulaExtensionResult[otf.FieldFormulaObservation]:
        try:
            table_id, before, _details, _revision = self._binding(request.target)
            uri = self._table_uri(request.target.table)
            resource = self._resource(uri)
            field = self._select_field(self._list_fields(resource.app_token, table_id), request.target.field)
            self._validate_formula_field(field)
            if self._field_id(field) != request.target.field.field_id:
                raise _ProtocolFailure
            observation = self._observation(uri, field)
            receipt = otf.FormulaReceiptDetails(
                target_kind="field", table_mode="base", target=self._safe_uri(uri, resource.table_id), selector=observation.field_id,
                capability=otf.FIELD_READ.to_reference(), dialect=otf.FEISHU_BITABLE,
                observation_sha256=otf.formula_observation_hash(observation), observed_count=1, revision_after=observation.observed_revision,
            )
            return _success(observation, (receipt,))
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "Feishu Bitable formula field binding is required")
        except _ProviderFailure as exc:
            return _rejected(exc.code, "Feishu Bitable rejected the formula field read")
        except ConnectorError as exc:
            return self._transport_error(exc)
        except (_ProtocolFailure, TypeError, ValueError, KeyError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Feishu Bitable returned an invalid formula field response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "Feishu Bitable formula field read failed")

    def set_field(self, request: otf.FieldFormulaSetRequest[Any]) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        context: tuple[str, str, str] | None = None
        dispatched = False
        try:
            table_id, before, details, bound_revision = self._binding(request.target)
            if request.expression.dialect != otf.FEISHU_BITABLE:
                return _rejected(otf.FormulaErrorCode.INVALID_FORMULA, "Feishu Bitable field formulas require the feishu-bitable dialect")
            if request.expression.byte_count > details.max_expression_bytes:
                raise _LimitFailure("formula expression exceeds the configured byte limit", details.max_expression_bytes)
            uri = self._table_uri(request.target.table)
            resource = self._resource(uri)
            expected_revision = request.expected_revision or bound_revision
            target_hash = _hash_payload({"table_id": table_id, "field_id": request.target.field.field_id})
            selector_hash = _hash_payload({"field_id": request.target.field.field_id})
            payload_hash = _hash_payload({"table_id": table_id, "field_id": request.target.field.field_id, "expression_sha256": request.expression.sha256, "dialect": request.expression.dialect, "expected_revision": expected_revision})
            context = (target_hash, selector_hash, payload_hash)
            if request.idempotency_key is not None:
                decision = self._ledger.begin(connector_id=PROVIDER_FEISHU_BITABLE, capability=otf.FIELD_SET.to_reference(), target_hash=target_hash, selector_hash=selector_hash, idempotency_key=request.idempotency_key, payload_hash=payload_hash)
                if decision.disposition is otf.FormulaIdempotencyDisposition.CONFLICT:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula field idempotency key conflicts with a prior request")
                if decision.disposition is otf.FormulaIdempotencyDisposition.IN_FLIGHT:
                    return _rejected(otf.FormulaErrorCode.IDEMPOTENCY_CONFLICT, "formula field idempotency key is already in flight")
                if decision.disposition is otf.FormulaIdempotencyDisposition.UNKNOWN:
                    return _unknown()
                if decision.disposition is otf.FormulaIdempotencyDisposition.REPLAY:
                    cached = self._completed.get(decision.operation_hash or "")
                    return cached if cached is not None else _unknown("formula field replay result is unavailable")
            fresh_before = self._fresh_field(resource.app_token, table_id, request.target.field.field_id or "")
            if self._revision(fresh_before) != expected_revision:
                self._finish_ledger(request, context)
                return _rejected(otf.FormulaErrorCode.STALE_REVISION, "formula field revision is stale", {"revision_hash": self._revision(fresh_before)})
            body = self._update_body(fresh_before, request.expression.text)
            dispatched = True
            reconciled_after: dict[str, Any] | None = None
            try:
                self._request("PUT", self._field_url(resource.app_token, table_id, request.target.field.field_id or ""), body)
            except ConnectorError:
                reconciled_after = self._reconcile(resource.app_token, table_id, request.target.field.field_id or "", fresh_before, request.expression.text)
                if reconciled_after is None:
                    self._finish_ledger(request, context, unknown=True)
                    return _unknown()
            fresh_after = reconciled_after or self._fresh_field(resource.app_token, table_id, request.target.field.field_id or "")
            if not self._isolated(fresh_before, fresh_after) or self._expression(fresh_after) != request.expression.text:
                self._finish_ledger(request, context, unknown=True)
                return _failed(otf.FormulaErrorCode.READBACK_MISMATCH, "formula field metadata readback did not match the isolated mutation", commit=otf.FormulaCommitState.COMMITTED, verification=otf.FormulaVerificationState.FAILED)
            observation = self._observation(uri, fresh_after)
            mutation = otf.FormulaMutation("field", 1, observation, expected_revision, self._revision(fresh_after))
            receipt = otf.FormulaReceiptDetails.for_field_set(target=self._safe_uri(uri, table_id), selector=observation.field_id, capability=otf.FIELD_SET.to_reference(), dialect=request.expression.dialect, expression_sha256=request.expression.sha256, observation_sha256=otf.formula_observation_hash(observation), affected_count=1, revision_before=expected_revision, revision_after=mutation.revision_after, mutation_atomicity=details.mutation_atomicity.value, revision_enforcement=details.revision_enforcement.value, verification="formula_text_readback")
            final = otf.FormulaExtensionResult(mutation, otf.FormulaOutcome.SUCCEEDED, otf.FormulaCommitState.COMMITTED, otf.FormulaVerificationState.PASSED, (receipt,))
            self._succeed_ledger(request, context, final, mutation)
            return final
        except _LimitFailure as exc:
            self._finish_ledger(request, context, unknown=dispatched)
            return _unknown() if dispatched else _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _ProviderFailure as exc:
            self._finish_ledger(request, context)
            return _rejected(exc.code, "Feishu Bitable rejected the formula field mutation")
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "Feishu Bitable formula field binding is required")
        except ConnectorError as exc:
            self._finish_ledger(request, context, unknown=dispatched)
            return _unknown() if dispatched else self._transport_error(exc)
        except (_ProtocolFailure, TypeError, ValueError, KeyError):
            self._finish_ledger(request, context, unknown=dispatched)
            return _unknown() if dispatched else _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Feishu Bitable returned an invalid formula field mutation response")
        except Exception:
            self._finish_ledger(request, context, unknown=dispatched)
            return _unknown() if dispatched else _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "Feishu Bitable formula field mutation failed")

    def read_field_values(self, request: otf.FieldFormulaValueReadRequest[Any]) -> otf.FormulaExtensionResult[otf.FieldFormulaValueObservation]:
        try:
            table_id, before, _details, _revision = self._binding(request.target)
            uri = self._table_uri(request.target.table)
            resource = self._resource(uri)
            limits = request.limits
            max_records = _MAX_RECORDS if limits is None or limits.max_records is None else min(limits.max_records, _MAX_RECORDS)
            max_bytes = _MAX_RESPONSE_BYTES if limits is None or limits.max_response_bytes is None else min(limits.max_response_bytes, _MAX_RESPONSE_BYTES)
            timeout = self._connector._timeout if limits is None or limits.timeout_seconds is None else limits.timeout_seconds
            values: list[otf.FormulaRecordValue] = []
            seen: set[str] = set()
            seen_tokens: set[str] = set()
            token: str | None = None
            response_bytes = 0
            started = monotonic()
            states: list[otf.CalculationState] = []
            while True:
                if token is not None:
                    if token in seen_tokens:
                        raise _ProtocolFailure
                    seen_tokens.add(token)
                query = f"page_size={_RECORD_PAGE_SIZE}"
                if token:
                    query += "&page_token=" + quote(token, safe="")
                payload = self._request("GET", self._records_url(resource.app_token, table_id, query), None, timeout=timeout)
                response_bytes += len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                if response_bytes > max_bytes:
                    raise _LimitFailure("formula field values exceeded the configured response byte limit", max_bytes)
                if (monotonic() - started) > timeout:
                    raise _LimitFailure("formula field values exceeded the configured timeout", int(timeout * 1000))
                data = payload.get("data")
                if not isinstance(data, Mapping):
                    raise _ProtocolFailure
                items = data.get("items", [])
                if not isinstance(items, list) or len(items) > _RECORD_PAGE_SIZE:
                    raise _ProtocolFailure
                states.append(self._calculation_state(data))
                for item in items:
                    if not isinstance(item, Mapping):
                        raise _ProtocolFailure
                    record_id = item.get("record_id")
                    if not isinstance(record_id, str) or not record_id or record_id in seen:
                        raise _ProtocolFailure
                    fields = item.get("fields")
                    if not isinstance(fields, Mapping):
                        raise _ProtocolFailure
                    field_id = request.target.field.field_id or ""
                    field_name = before.get("field_name")
                    if field_id in fields:
                        raw_value = fields[field_id]
                    elif isinstance(field_name, str) and field_name in fields:
                        raw_value = fields[field_name]
                    else:
                        raise _ProtocolFailure
                    values.append(otf.FormulaRecordValue(record_id, self._formula_value(raw_value)))
                    seen.add(record_id)
                    if len(values) > max_records:
                        raise _LimitFailure("formula field values exceeded the configured record limit", max_records)
                has_more = data.get("has_more", False)
                if not isinstance(has_more, bool):
                    raise _ProtocolFailure
                if not has_more:
                    break
                token = data.get("page_token")
                if not isinstance(token, str) or not token:
                    raise _ProtocolFailure
            if not states:
                states = [otf.CalculationState.UNKNOWN]
            state = otf.CalculationState.UNKNOWN if len(set(states)) != 1 else states[0]
            revision = _hash_payload({"table_id": table_id, "field_id": request.target.field.field_id, "records": [item.to_wire() for item in values]})
            observation = otf.FieldFormulaValueObservation(uri, request.target.field.field_id or "", str(before.get("field_name")), tuple(values), state, otf.CalculationTrigger.PROVIDER_READ, "provider_dynamic", revision)
            receipt = otf.FormulaReceiptDetails.for_field_values_read(target=self._safe_uri(uri, table_id), selector=observation.field_id, capability=otf.FIELD_VALUES_READ.to_reference(), dialect=otf.FEISHU_BITABLE, observation_sha256=_hash_payload({"field_id": observation.field_id, "revision": revision}), value_observation_sha256=otf.formula_observation_hash(observation), observed_count=len(values), revision_after=revision, calculation_state=state.value, calculation_trigger=observation.calculation_trigger.value, dependency_scope=observation.dependency_scope)
            return _success(observation, (receipt,))
        except _LimitFailure as exc:
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _BindingFailure:
            return _rejected(otf.FormulaErrorCode.TARGET_NOT_FOUND, "Feishu Bitable formula field binding is required")
        except _ProviderFailure as exc:
            return _rejected(exc.code, "Feishu Bitable rejected the formula field value read")
        except ConnectorError as exc:
            return self._transport_error(exc)
        except (_ProtocolFailure, TypeError, ValueError, KeyError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Feishu Bitable returned an invalid formula field value response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "Feishu Bitable formula field value read failed")

    def recalculate_field(self, request: otf.FieldFormulaRecalculateRequest[Any]) -> otf.FormulaExtensionResult[otf.RecalculationObservation]:
        del request
        return _rejected(otf.FormulaErrorCode.UNSUPPORTED_CAPABILITY, "Feishu Bitable does not expose explicit formula recalculation")

    def _table_uri(self, table: Any) -> TableURI:
        binding = getattr(table, "_binding", None)
        uri = getattr(binding, "uri", None)
        if not isinstance(uri, TableURI):
            try:
                uri = TableURI(uri)
            except (TypeError, ValueError) as exc:
                raise _BindingFailure("Feishu Bitable field formulas require an SDK-owned Table") from exc
        return uri

    def _table_mode(self, table: Any) -> TableMode:
        mode = getattr(getattr(table, "_binding", None), "mode", None)
        try:
            return mode if isinstance(mode, TableMode) else TableMode(str(mode).replace("-mode", ""))
        except ValueError as exc:
            raise _BindingFailure("Feishu Bitable Table mode is invalid") from exc

    def _resource(self, uri: TableURI):
        try:
            resolved = self._connector.resolve(uri, ResolveContext())
        except ConnectorError:
            raise
        return resolved.resource

    def _binding(self, target: otf.BoundFieldFormulaTarget[Any]):
        item = self._bindings.get((id(target.table), target.field.field_id or ""))
        if item is None:
            raise _BindingFailure("Feishu Bitable formula field binding is required")
        return item

    def _list_fields(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        fields: list[dict[str, Any]] = []
        token: str | None = None
        seen: set[str] = set()
        while True:
            if token is not None:
                if token in seen:
                    raise _ProtocolFailure
                seen.add(token)
            query = f"page_size={_PAGE_SIZE}"
            if token:
                query += "&page_token=" + quote(token, safe="")
            payload = self._request("GET", self._fields_url(app_token, table_id, query), None)
            data = payload.get("data")
            if not isinstance(data, Mapping):
                raise _ProtocolFailure
            items = data.get("items", [])
            if not isinstance(items, list) or len(items) > _PAGE_SIZE:
                raise _ProtocolFailure
            for field in items:
                if not isinstance(field, Mapping):
                    raise _ProtocolFailure
                fields.append(dict(field))
            has_more = data.get("has_more", False)
            if not isinstance(has_more, bool):
                raise _ProtocolFailure
            if not has_more:
                return fields
            token = data.get("page_token")
            if not isinstance(token, str) or not token:
                raise _ProtocolFailure

    @staticmethod
    def _select_field(fields: list[dict[str, Any]], selector: otf.FieldRef) -> dict[str, Any]:
        matches = [field for field in fields if (selector.field_id is not None and field.get("field_id") == selector.field_id) or (selector.name is not None and field.get("field_name") == selector.name)]
        if not matches:
            raise _BindingFailure("Feishu Bitable formula field was not found")
        if len(matches) != 1:
            raise _BindingFailure("Feishu Bitable formula field selector is ambiguous", otf.FormulaErrorCode.INVALID_TARGET)
        return matches[0]

    @staticmethod
    def _validate_formula_field(field: Mapping[str, Any]) -> None:
        if field.get("type") != FEISHU_FORMULA_FIELD_TYPE:
            raise _BindingFailure("Feishu Bitable target is not a formula field", otf.FormulaErrorCode.INVALID_TARGET)
        if not isinstance(field.get("field_id"), str) or not field["field_id"] or not isinstance(field.get("field_name"), str) or not field["field_name"]:
            raise _ProtocolFailure
        prop = field.get("property")
        if not isinstance(prop, Mapping) or not isinstance(prop.get("formula_expression"), str) or not prop["formula_expression"].strip():
            raise _ProtocolFailure

    @staticmethod
    def _field_id(field: Mapping[str, Any]) -> str:
        value = field.get("field_id")
        if not isinstance(value, str) or not value:
            raise _ProtocolFailure
        return value

    @staticmethod
    def _expression(field: Mapping[str, Any]) -> str:
        prop = field.get("property")
        if not isinstance(prop, Mapping) or not isinstance(prop.get("formula_expression"), str):
            raise _ProtocolFailure
        return prop["formula_expression"]

    @classmethod
    def _revision(cls, field: Mapping[str, Any]) -> str:
        return _hash_payload(field)

    @staticmethod
    def _details() -> otf.FormulaCapabilityDetails:
        return otf.FormulaCapabilityDetails("field", (otf.FEISHU_BITABLE,), None, _MAX_EXPRESSION_BYTES, (), (otf.CalculationState.PROVIDER_CURRENT, otf.CalculationState.UNKNOWN), otf.MutationAtomicity.ATOMIC, otf.RevisionEnforcement.CHECKED, otf.IdempotencyStrength.RECONCILED)

    def _fresh_field(self, app_token: str, table_id: str, field_id: str) -> dict[str, Any]:
        fields = self._list_fields(app_token, table_id)
        for field in fields:
            if field.get("field_id") == field_id:
                self._validate_formula_field(field)
                return field
        raise _BindingFailure("Feishu Bitable formula field was not found")

    @staticmethod
    def _update_body(field: Mapping[str, Any], expression: str) -> dict[str, Any]:
        prop = field.get("property")
        if not isinstance(prop, Mapping):
            raise _ProtocolFailure
        updated = copy.deepcopy(dict(prop))
        updated["formula_expression"] = expression
        return {"field_name": field["field_name"], "type": FEISHU_FORMULA_FIELD_TYPE, "property": updated}

    @classmethod
    def _isolated(cls, before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
        def normalized(field: Mapping[str, Any]) -> dict[str, Any]:
            value = copy.deepcopy(dict(field))
            prop = value.get("property")
            if isinstance(prop, Mapping):
                property_value = dict(prop)
                property_value.pop("formula_expression", None)
                value["property"] = property_value
            value.pop("provider_revision", None)
            value.pop("provider_evidence", None)
            return value

        return normalized(before) == normalized(after)

    def _reconcile(self, app_token: str, table_id: str, field_id: str, before: Mapping[str, Any], expression: str) -> dict[str, Any] | None:
        try:
            after = self._fresh_field(app_token, table_id, field_id)
        except Exception:
            return None
        return after if self._isolated(before, after) and self._expression(after) == expression else None

    def _request(self, method: str, url: str, body: Mapping[str, Any] | None, *, timeout: int | float | None = None) -> Mapping[str, Any]:
        payload = self._connector._transport.request(method, self._connector._url(url), headers=self._connector._headers(), body=body, timeout=self._connector._timeout if timeout is None else timeout)
        if not isinstance(payload, Mapping):
            raise _ProtocolFailure
        code = payload.get("code", _MISSING)
        if isinstance(code, bool) or not isinstance(code, int):
            raise _ProtocolFailure
        if code != 0:
            if method == "PUT" and isinstance(code, int) and 400 <= code < 500:
                raise _ProviderFailure(otf.FormulaErrorCode.INVALID_FORMULA, code)
            raise _ProviderFailure(otf.FormulaErrorCode.EXECUTION_FAILED, code)
        return payload

    @staticmethod
    def _formula_value(raw: object) -> otf.FormulaValue:
        if isinstance(raw, Mapping):
            if "error" in raw:
                error = raw.get("error")
                if not isinstance(error, Mapping):
                    raise _ProtocolFailure
                return otf.FormulaValue.provider_error(otf.FormulaErrorValue(otf.FormulaErrorCode.INVALID_FORMULA.value))
            if "type" in raw:
                if raw.get("type") in {"error", "formula_error"}:
                    return otf.FormulaValue.provider_error(otf.FormulaErrorValue(otf.FormulaErrorCode.INVALID_FORMULA.value))
                raise _ProtocolFailure
            if "kind" in raw:
                try:
                    return otf.FormulaValue.from_wire(raw)
                except (TypeError, ValueError, KeyError):
                    raise _ProtocolFailure from None
        try:
            return otf.FormulaValue.from_python(raw)
        except (TypeError, ValueError):
            raise _ProtocolFailure from None

    def _finish_ledger(self, request: otf.FieldFormulaSetRequest[Any], context: tuple[str, str, str] | None, *, unknown: bool = False) -> None:
        if request.idempotency_key is None or context is None:
            return
        kwargs = {"connector_id": PROVIDER_FEISHU_BITABLE, "target_hash": context[0], "selector_hash": context[1], "idempotency_key": request.idempotency_key, "payload_hash": context[2]}
        if unknown:
            self._ledger.mark_unknown(**kwargs)
        else:
            self._ledger.fail_known(**kwargs)

    def _succeed_ledger(self, request: otf.FieldFormulaSetRequest[Any], context: tuple[str, str, str] | None, result: otf.FormulaExtensionResult[Any], mutation: otf.FormulaMutation) -> None:
        if request.idempotency_key is None or context is None:
            return
        operation_hash = _hash_payload(mutation.to_wire())
        self._completed[operation_hash] = result
        self._completed.move_to_end(operation_hash)
        while len(self._completed) > _LEDGER_LIMIT:
            self._completed.popitem(last=False)
        self._ledger.succeed(connector_id=PROVIDER_FEISHU_BITABLE, target_hash=context[0], selector_hash=context[1], idempotency_key=request.idempotency_key, payload_hash=context[2], operation_hash=operation_hash)

    def _observation(self, uri: TableURI, field: Mapping[str, Any]) -> otf.FieldFormulaObservation:
        prop = field["property"]
        result_type = prop.get("result_type") or prop.get("formatter") or field.get("result_type")
        return otf.FieldFormulaObservation(uri, field["field_id"], field["field_name"], otf.FormulaExpression(self._expression(field), otf.FEISHU_BITABLE), result_type if isinstance(result_type, str) and result_type else None, self._revision(field))

    @staticmethod
    def _calculation_state(data: Mapping[str, Any]) -> otf.CalculationState:
        state = data.get("formula_calculation_state", data.get("calculation_state"))
        if state in {"current", "provider_current", True}:
            return otf.CalculationState.PROVIDER_CURRENT
        if state in {None, "unknown", False}:
            return otf.CalculationState.UNKNOWN
        raise _ProtocolFailure

    @staticmethod
    def _transport_error(exc: ConnectorError) -> otf.FormulaExtensionResult[Any]:
        mapping = {ConnectorErrorCode.AUTHENTICATION: otf.FormulaErrorCode.EXECUTION_FAILED, ConnectorErrorCode.TIMEOUT: otf.FormulaErrorCode.TIMEOUT, ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED: otf.FormulaErrorCode.RESOURCE_LIMIT, ConnectorErrorCode.INVALID_URI: otf.FormulaErrorCode.INVALID_TARGET}
        return _rejected(mapping.get(exc.code, otf.FormulaErrorCode.EXECUTION_FAILED), "Feishu Bitable formula provider request failed")

    @staticmethod
    def _safe_uri(uri: TableURI, table_id: str) -> str:
        del uri
        return f"feishu://redacted/{quote(table_id, safe='')}"

    @staticmethod
    def _fields_url(app_token: str, table_id: str, query: str) -> str:
        return f"/apps/{quote(app_token, safe='')}/tables/{quote(table_id, safe='')}/fields?{query}"

    @staticmethod
    def _field_url(app_token: str, table_id: str, field_id: str) -> str:
        return f"/apps/{quote(app_token, safe='')}/tables/{quote(table_id, safe='')}/fields/{quote(field_id, safe='')}"

    @staticmethod
    def _records_url(app_token: str, table_id: str, query: str) -> str:
        return f"/apps/{quote(app_token, safe='')}/tables/{quote(table_id, safe='')}/records?{query}"


_MISSING = object()

FeishuBitableFieldFormulaExtension = FeishuBitableFormulaExtension

__all__ = [
    "FEISHU_FORMULA_FIELD_TYPE",
    "FeishuBitableFieldFormulaExtension",
    "FeishuBitableFormulaExtension",
]
