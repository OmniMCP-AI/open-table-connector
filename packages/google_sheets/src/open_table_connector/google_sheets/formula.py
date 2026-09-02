"""Google Sheets grid Formula extension.

The ordinary Google table writer deliberately remains value-only.  This module
is the separate, opt-in Formula seam that submits native grid requests and
verifies them with formula text readback.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import open_table_connector.formulas as otf
from open_table_connector.contract import (
    HOST_GOOGLE_DOCS,
    PROVIDER_GOOGLE_SHEETS,
    SCHEME_GSHEETS,
    SCHEME_HTTPS,
    ConnectorError,
    ConnectorErrorCode,
    TableURI,
)

from .connector import GoogleSheetsConnector, SheetsTransport

_FORMULA_CAPABILITIES = (otf.GRID_READ, otf.GRID_SET, otf.GRID_VALUES_READ)
_MAX_CELLS = 10_000
_MAX_EXPRESSION_BYTES = 50_000
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_DEFAULT_LEDGER_LIMIT = 1024
_CELL_REFERENCE = re.compile(r"(?P<column>\$?[A-Za-z]{1,3})(?P<row>\$?[1-9]\d*)")
_SIMPLE_A1_TITLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FORMULA_REJECTION_REASONS = frozenset(
    {
        "invalid_formula",
        "invalidformula",
        "formula_error",
        "formula_parse_error",
        "formula_syntax_error",
    }
)
_GRID_FIELDS = (
    "sheets(properties(sheetId,title),data(startRow,startColumn,"
    "rowData(values(userEnteredValue,effectiveValue,effectiveFormat(numberFormat)))))"
)
_METADATA_FIELDS = "sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))"


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _address(column: int, row: int) -> str:
    letters = ""
    value = column
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return f"{letters}{row}"


def _result(
    value: object,
    receipts: tuple[object, ...] = (),
) -> otf.FormulaExtensionResult[Any]:
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
    details: Mapping[str, Any] | None = None,
    receipts: tuple[object, ...] = (),
) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(
        value=None,
        outcome=otf.FormulaOutcome.FAILED,
        commit=commit,
        verification=verification,
        receipts=receipts,
        error=otf.FormulaExtensionErrorInfo(code, message, details or {}),
    )


def _unknown(
    code: otf.FormulaErrorCode,
    message: str,
    details: Mapping[str, Any] | None = None,
) -> otf.FormulaExtensionResult[Any]:
    return otf.FormulaExtensionResult(
        value=None,
        outcome=otf.FormulaOutcome.UNKNOWN,
        commit=otf.FormulaCommitState.UNKNOWN,
        verification=otf.FormulaVerificationState.UNAVAILABLE,
        receipts=(),
        error=otf.FormulaExtensionErrorInfo(code, message, details or {}),
    )


class GoogleSheetsFormulaExtension(otf.GridFormulaConnectorExtension):
    """Formula adapter over an already configured Google Sheets connector."""

    def __init__(
        self,
        connector: GoogleSheetsConnector | None = None,
        *,
        transport: SheetsTransport | None = None,
        access_token: str | None = None,
        timeout: int = 30,
        api_endpoint: str = "https://sheets.googleapis.com",
    ) -> None:
        self._connector = connector or GoogleSheetsConnector(
            transport=transport,
            access_token=access_token,
            timeout=timeout,
            api_endpoint=api_endpoint,
        )
        self._bindings: dict[tuple[str, str], tuple[str, int | None, int | None]] = {}
        self._ledger = otf.FormulaIdempotencyLedger(limit=_DEFAULT_LEDGER_LIMIT)
        self._completed: dict[str, otf.FormulaExtensionResult[otf.FormulaMutation]] = {}
        self._lock = threading.RLock()

    def bind_grid(self, request: otf.GridFormulaBindRequest) -> otf.FormulaExtensionResult[otf.GridFormulaBinding]:
        try:
            spreadsheet_id = self._spreadsheet_id(request.target.grid)
            if not spreadsheet_id:
                return _rejected(otf.FormulaErrorCode.INVALID_TARGET, "Google Sheets grid target is invalid")
            reference = request.target.worksheet
            target_title = self._worksheet_name(request.target.grid)
            if (
                reference.name is not None
                and target_title is not None
                and reference.name != target_title
            ):
                return _rejected(
                    otf.FormulaErrorCode.TARGET_NOT_FOUND,
                    "Google Sheets worksheet name and URI name do not match",
                )
            properties = self._metadata(spreadsheet_id)
            matches = [
                item
                for item in properties
                if (reference.worksheet_id is None or str(item.get("sheetId")) == reference.worksheet_id)
                and (reference.name is None or item.get("title") == reference.name)
                and (target_title is None or item.get("title") == target_title)
            ]
            if len(matches) != 1:
                return _rejected(
                    otf.FormulaErrorCode.TARGET_NOT_FOUND,
                    "Google Sheets worksheet does not identify exactly one sheet",
                )
            item = matches[0]
            sheet_id = item.get("sheetId")
            title = item.get("title")
            if isinstance(sheet_id, bool) or not isinstance(sheet_id, int) or sheet_id < 0 or not isinstance(title, str) or not title:
                return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets metadata was malformed")
            if target_title is not None and target_title != title:
                return _rejected(
                    otf.FormulaErrorCode.TARGET_NOT_FOUND,
                    "Google Sheets worksheet name and ID do not match",
                )
            grid_properties = item.get("gridProperties")
            row_count = grid_properties.get("rowCount") if isinstance(grid_properties, Mapping) else None
            column_count = grid_properties.get("columnCount") if isinstance(grid_properties, Mapping) else None
            if row_count is not None and (isinstance(row_count, bool) or not isinstance(row_count, int) or row_count < 0):
                return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets metadata was malformed")
            if column_count is not None and (isinstance(column_count, bool) or not isinstance(column_count, int) or column_count < 0):
                return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets metadata was malformed")
            metadata_revision = _hash_payload({"spreadsheet_id": spreadsheet_id, "sheets": properties})
            with self._lock:
                self._bindings[(spreadsheet_id, str(sheet_id))] = (title, row_count, column_count)
            binding = otf.GridFormulaBinding(
                target=otf.BoundGridFormulaTarget(
                    request.target.grid.value,
                    otf.WorksheetRef(worksheet_id=str(sheet_id)),
                ),
                capabilities=otf.FormulaCapabilitySet(
                    _FORMULA_CAPABILITIES,
                    otf.FormulaCapabilityDetails(
                        target_kind="grid",
                        dialects=(otf.GOOGLE_SHEETS_A1,),
                        max_cells_per_operation=_MAX_CELLS,
                        max_expression_bytes=_MAX_EXPRESSION_BYTES,
                        recalculation_scopes=(),
                        calculation_states=(otf.CalculationState.PROVIDER_CURRENT,),
                        mutation_atomicity=otf.MutationAtomicity.ATOMIC,
                        revision_enforcement=otf.RevisionEnforcement.CHECKED,
                        idempotency_strength=otf.IdempotencyStrength.RECONCILED,
                    ),
                ),
                observed_revision=metadata_revision,
            )
            return _result(binding)
        except ConnectorError as exc:
            return self._transport_error(exc, operation="binding")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets metadata was malformed")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "Google Sheets formula binding failed")

    def read_grid(self, request: otf.GridFormulaReadRequest) -> otf.FormulaExtensionResult[otf.GridFormulaObservation]:
        try:
            rectangle = self._validated_range(request.cell_range, request.limits)
            self._check_dimensions(request.target, rectangle)
            response, title = self._grid_request(request.target, rectangle, request.limits)
            observation, _ = self._parse_grid_response(response, request.target, rectangle, title, request.limits)
            receipt = otf.FormulaReceiptDetails.for_grid_read(
                target=request.target.grid.value,
                selector=request.cell_range,
                capability=otf.GRID_READ.to_reference(),
                dialect=otf.GOOGLE_SHEETS_A1,
                observation_sha256=otf.formula_observation_hash(observation),
                observed_count=len(observation.formulas),
                revision_after=observation.observed_revision,
            )
            return _result(observation, (receipt,))
        except _LimitFailure as exc:
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _ProtocolFailure:
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets returned an invalid formula response")
        except ConnectorError as exc:
            return self._transport_error(exc, operation="formula read")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets returned an invalid formula response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "Google Sheets formula read failed")

    def read_grid_values(
        self, request: otf.GridFormulaValueReadRequest
    ) -> otf.FormulaExtensionResult[otf.GridFormulaValueObservation]:
        try:
            rectangle = self._validated_range(request.cell_range, request.limits)
            self._check_dimensions(request.target, rectangle)
            response, title = self._grid_request(request.target, rectangle, request.limits)
            _, cells = self._parse_grid_response(response, request.target, rectangle, title, request.limits)
            values = tuple(
                otf.FormulaValueCell(address, value)
                for address, value in cells
            )
            observation = otf.GridFormulaValueObservation(
                worksheet_id=request.target.worksheet.worksheet_id or "",
                requested_range=request.cell_range,
                values=values,
                calculation_state=otf.CalculationState.PROVIDER_CURRENT,
                calculation_trigger=otf.CalculationTrigger.PROVIDER_READ,
                dependency_scope="provider_dynamic",
                observed_revision=_hash_payload({"target": request.target.grid.value, "range": request.cell_range, "values": [cell.to_wire() for cell in values]}),
            )
            receipt = otf.FormulaReceiptDetails.for_grid_values_read(
                target=request.target.grid.value,
                selector=request.cell_range,
                capability=otf.GRID_VALUES_READ.to_reference(),
                dialect=otf.GOOGLE_SHEETS_A1,
                observation_sha256=otf.formula_observation_hash(
                    otf.GridFormulaObservation(
                        worksheet_id=observation.worksheet_id,
                        requested_range=request.cell_range,
                        formulas=(),
                        observed_revision=observation.observed_revision,
                    )
                ),
                value_observation_sha256=otf.formula_observation_hash(observation),
                observed_count=len(values),
                revision_after=observation.observed_revision,
                calculation_state=observation.calculation_state.value,
                calculation_trigger=observation.calculation_trigger.value,
                dependency_scope=observation.dependency_scope,
            )
            return _result(observation, (receipt,))
        except _LimitFailure as exc:
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _ProtocolFailure:
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets returned an invalid value response")
        except ConnectorError as exc:
            return self._transport_error(exc, operation="formula value read")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets returned an invalid value response")
        except Exception:
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "Google Sheets formula value read failed")

    def set_grid(self, request: otf.GridFormulaSetRequest) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        ledger_context: tuple[str, str, str] | None = None
        post_dispatched = False
        try:
            rectangle = self._validated_range(request.cell_range, request.limits)
            self._check_dimensions(request.target, rectangle)
            if request.expression.dialect != otf.GOOGLE_SHEETS_A1:
                return _rejected(otf.FormulaErrorCode.INVALID_FORMULA, "Google Sheets formula dialect is invalid")
            expression_limit = self._expression_limit(request.limits)
            if request.expression.byte_count > expression_limit:
                raise _LimitFailure("formula expression exceeds the configured byte limit", expression_limit)
            before_result = self.read_grid(
                otf.GridFormulaReadRequest(request.target, request.cell_range, request.limits)
            )
            if before_result.outcome is not otf.FormulaOutcome.SUCCEEDED or before_result.value is None:
                return before_result
            before = before_result.value
            if request.expected_revision is not None and request.expected_revision != before.observed_revision:
                return _rejected(
                    otf.FormulaErrorCode.STALE_REVISION,
                    "formula target revision is stale",
                    {"revision_hash": before.observed_revision},
                )
            target_hash = _hash_payload({"uri": request.target.grid.value, "worksheet_id": request.target.worksheet.worksheet_id})
            selector_hash = _hash_payload({"capability": otf.GRID_SET.to_reference()})
            payload_hash = _hash_payload({"range": request.cell_range, "dialect": request.expression.dialect, "expression_sha256": request.expression.sha256, "expected_revision": request.expected_revision})
            ledger_context = (target_hash, selector_hash, payload_hash)
            decision = None
            if request.idempotency_key is not None:
                with self._lock:
                    decision = self._ledger.begin(
                        connector_id=PROVIDER_GOOGLE_SHEETS,
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
                    return _unknown(otf.FormulaErrorCode.UNCERTAIN_MUTATION, "formula mutation remains uncertain")
                if decision.disposition is otf.FormulaIdempotencyDisposition.REPLAY:
                    if decision.operation_hash is not None:
                        with self._lock:
                            cached = self._completed.get(decision.operation_hash)
                        if cached is not None:
                            return cached
                    return _unknown(
                        otf.FormulaErrorCode.UNCERTAIN_MUTATION,
                        "formula mutation replay result is unavailable",
                    )

            body = {
                "requests": [{
                    "repeatCell": {
                        "range": {
                            "sheetId": int(request.target.worksheet.worksheet_id or 0),
                            "startRowIndex": rectangle.start_row - 1,
                            "endRowIndex": rectangle.end_row,
                            "startColumnIndex": rectangle.start_column - 1,
                            "endColumnIndex": rectangle.end_column,
                        },
                        "cell": {"userEnteredValue": {"formulaValue": request.expression.text}},
                        "fields": "userEnteredValue.formulaValue",
                    }
                }],
                "includeSpreadsheetInResponse": True,
                "responseRanges": [f"{self._a1_title(self._title_for(request.target))}!{request.cell_range}"],
                "responseIncludeGridData": True,
            }
            url = self._url(
                f"/v4/spreadsheets/{quote(self._spreadsheet_id(request.target.grid), safe='')}:batchUpdate"
            )
            try:
                headers = self._connector._headers()
                post_dispatched = True
                response = self._connector._transport.request(
                    "POST", url, headers=headers, body=body, timeout=self._connector._timeout
                )
            except ConnectorError as exc:
                if exc.code is ConnectorErrorCode.TIMEOUT and exc.safe_details.get("before_dispatch") is True:
                    self._fail_ledger(request, target_hash, selector_hash, payload_hash)
                    post_dispatched = False
                    return _rejected(otf.FormulaErrorCode.TIMEOUT, "formula provider request timed out before dispatch")
                if exc.code is ConnectorErrorCode.EXECUTION_FAILED and exc.safe_details.get("status") == 400:
                    self._mark_unknown_ledger(request, target_hash, selector_hash, payload_hash)
                    return self._provider_400_result(exc)
                reconciled = self._reconcile_after_uncertain(
                    request, rectangle, request.expression, before.observed_revision,
                    target_hash, selector_hash, payload_hash,
                )
                return reconciled

            if not isinstance(response, Mapping):
                raise _ProtocolFailure
            self._check_response_size(response, request.limits)
            updated = response.get("updatedSpreadsheet", response)
            if not isinstance(updated, Mapping):
                raise _ProtocolFailure
            expected, _ = self._parse_grid_response(
                updated, request.target, rectangle, self._title_for(request.target), request.limits
            )
            if len(expected.formulas) != rectangle.cell_count:
                self._mark_unknown_ledger(request, target_hash, selector_hash, payload_hash)
                if not expected.formulas:
                    return _failed(otf.FormulaErrorCode.PARTIAL_EFFECT, "formula provider returned a partial mutation response")
                partial_mutation = otf.FormulaMutation(
                    target_kind="grid",
                    affected_count=len(expected.formulas),
                    formula_observation=expected,
                    revision_before=before.observed_revision,
                    revision_after=expected.observed_revision,
                )
                return otf.FormulaExtensionResult(
                    value=partial_mutation,
                    outcome=otf.FormulaOutcome.PARTIAL,
                    commit=otf.FormulaCommitState.PARTIAL,
                    verification=otf.FormulaVerificationState.FAILED,
                    receipts=(),
                    error=otf.FormulaExtensionErrorInfo(
                        otf.FormulaErrorCode.PARTIAL_EFFECT,
                        "formula provider returned a partial mutation response",
                    ),
                )
            if self._formula_map(expected) != self._expected_formula_map(rectangle, request.expression):
                self._mark_unknown_ledger(request, target_hash, selector_hash, payload_hash)
                return _failed(
                    otf.FormulaErrorCode.PROTOCOL_FAILURE,
                    "Google Sheets returned non-conforming copy-fill formulas",
                    commit=otf.FormulaCommitState.COMMITTED,
                    verification=otf.FormulaVerificationState.FAILED,
                )
            readback_result = self.read_grid(otf.GridFormulaReadRequest(request.target, request.cell_range, request.limits))
            if readback_result.outcome is not otf.FormulaOutcome.SUCCEEDED or readback_result.value is None:
                self._mark_unknown_ledger(request, target_hash, selector_hash, payload_hash)
                return _unknown(otf.FormulaErrorCode.UNCERTAIN_MUTATION, "formula commit state could not be determined")
            readback = readback_result.value
            if self._formula_map(readback) != self._formula_map(expected):
                self._mark_unknown_ledger(request, target_hash, selector_hash, payload_hash)
                return _failed(
                    otf.FormulaErrorCode.READBACK_MISMATCH,
                    "formula text readback did not match the requested mutation",
                    commit=otf.FormulaCommitState.COMMITTED,
                    verification=otf.FormulaVerificationState.FAILED,
                )
            mutation = otf.FormulaMutation(
                target_kind="grid",
                affected_count=rectangle.cell_count,
                formula_observation=readback,
                revision_before=before.observed_revision,
                revision_after=readback.observed_revision,
            )
            receipt = otf.FormulaReceiptDetails.for_grid_set(
                target=request.target.grid.value,
                selector=request.cell_range,
                capability=otf.GRID_SET.to_reference(),
                dialect=request.expression.dialect,
                expression_sha256=request.expression.sha256,
                observation_sha256=otf.formula_observation_hash(readback),
                affected_count=rectangle.cell_count,
                revision_before=before.observed_revision,
                revision_after=readback.observed_revision,
                mutation_atomicity=otf.MutationAtomicity.ATOMIC.value,
                revision_enforcement=otf.RevisionEnforcement.CHECKED.value,
                verification="formula_text_readback",
            )
            operation_hash = _hash_payload(mutation.to_wire())
            result = otf.FormulaExtensionResult(
                value=mutation,
                outcome=otf.FormulaOutcome.SUCCEEDED,
                commit=otf.FormulaCommitState.COMMITTED,
                verification=otf.FormulaVerificationState.PASSED,
                receipts=(receipt,),
            )
            if request.idempotency_key is not None:
                with self._lock:
                    # Publish the result while the ledger is still protected.  A
                    # replay can therefore observe either IN_FLIGHT or a complete
                    # cached result, but can never fall through to another POST.
                    self._completed[operation_hash] = result
                    self._ledger.succeed(
                        connector_id=PROVIDER_GOOGLE_SHEETS, target_hash=target_hash, selector_hash=selector_hash,
                        idempotency_key=request.idempotency_key, payload_hash=payload_hash, operation_hash=operation_hash,
                    )
            return result
        except _LimitFailure as exc:
            self._finish_ledger_failure(request, ledger_context, post_dispatched=post_dispatched)
            return _rejected(otf.FormulaErrorCode.RESOURCE_LIMIT, str(exc), {"limit": exc.limit})
        except _ProtocolFailure:
            self._finish_ledger_failure(request, ledger_context, post_dispatched=post_dispatched)
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets returned an invalid mutation response")
        except ConnectorError as exc:
            self._finish_ledger_failure(request, ledger_context, post_dispatched=post_dispatched)
            if exc.code is ConnectorErrorCode.TIMEOUT:
                return _unknown(otf.FormulaErrorCode.UNCERTAIN_MUTATION, "formula commit state could not be determined")
            if exc.code is ConnectorErrorCode.EXECUTION_FAILED and exc.safe_details.get("status") == 400:
                return self._provider_400_result(exc)
            return self._transport_error(exc, operation="formula mutation")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            self._finish_ledger_failure(request, ledger_context, post_dispatched=post_dispatched)
            return _failed(otf.FormulaErrorCode.PROTOCOL_FAILURE, "Google Sheets returned an invalid mutation response")
        except Exception:
            self._finish_ledger_failure(request, ledger_context, post_dispatched=post_dispatched)
            return _failed(otf.FormulaErrorCode.EXECUTION_FAILED, "Google Sheets formula mutation failed")

    def recalculate_grid(self, request: otf.GridFormulaRecalculateRequest) -> otf.FormulaExtensionResult[otf.RecalculationObservation]:
        return _rejected(otf.FormulaErrorCode.UNSUPPORTED_CAPABILITY, "Google Sheets does not expose explicit grid recalculation")

    def _metadata(self, spreadsheet_id: str) -> list[dict[str, Any]]:
        url = self._url(
            f"/v4/spreadsheets/{quote(spreadsheet_id, safe='')}?fields={_METADATA_FIELDS}"
        )
        payload = self._connector._transport.request(
            "GET", url, headers=self._connector._headers(), timeout=self._connector._timeout
        )
        self._check_response_size(payload)
        sheets = payload.get("sheets")
        if not isinstance(sheets, list):
            raise _ProtocolFailure
        properties: list[dict[str, Any]] = []
        for sheet in sheets:
            if not isinstance(sheet, Mapping) or not isinstance(sheet.get("properties"), Mapping):
                raise _ProtocolFailure
            properties.append(dict(sheet["properties"]))
        return properties

    def _grid_request(
        self,
        target: otf.BoundGridFormulaTarget,
        rectangle: otf.A1Rectangle,
        limits: otf.FormulaResourceLimits | None,
    ) -> tuple[Mapping[str, Any], str]:
        title = self._title_for(target)
        url = self._url(
            f"/v4/spreadsheets/{quote(self._spreadsheet_id(target.grid), safe='')}?"
            f"includeGridData=true&ranges={quote(f'{self._a1_title(title)}!{rectangle.start_address}:{rectangle.end_address}', safe='')}&"
            f"fields={_GRID_FIELDS}"
        )
        payload = self._connector._transport.request(
            "GET", url, headers=self._connector._headers(), timeout=self._connector._timeout
        )
        self._check_response_size(payload, limits)
        return payload, title

    def _parse_grid_response(
        self,
        payload: Mapping[str, Any],
        target: otf.BoundGridFormulaTarget,
        rectangle: otf.A1Rectangle,
        title: str,
        limits: otf.FormulaResourceLimits | None = None,
    ) -> tuple[otf.GridFormulaObservation, tuple[tuple[str, otf.FormulaValue], ...]]:
        sheets = payload.get("sheets")
        if not isinstance(sheets, list):
            raise _ProtocolFailure
        matching = [
            sheet for sheet in sheets
            if isinstance(sheet, Mapping)
            and isinstance(sheet.get("properties"), Mapping)
            and str(sheet["properties"].get("sheetId")) == target.worksheet.worksheet_id
            and sheet["properties"].get("title") == title
        ]
        if len(matching) != 1:
            raise _ProtocolFailure
        formulas: list[otf.FormulaCell] = []
        values: list[tuple[str, otf.FormulaValue]] = []
        data = matching[0].get("data", [])
        if not isinstance(data, list):
            raise _ProtocolFailure
        expression_bytes = 0
        expression_limit = self._expression_limit(limits)
        for grid_data in data:
            if not isinstance(grid_data, Mapping):
                raise _ProtocolFailure
            start_row = grid_data.get("startRow", 0)
            start_column = grid_data.get("startColumn", 0)
            row_data = grid_data.get("rowData", [])
            if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in (start_row, start_column)):
                raise _ProtocolFailure
            if not isinstance(row_data, list):
                raise _ProtocolFailure
            for row_offset, row in enumerate(row_data):
                if not isinstance(row, Mapping):
                    raise _ProtocolFailure
                cell_data = row.get("values", [])
                if not isinstance(cell_data, list):
                    raise _ProtocolFailure
                for column_offset, cell in enumerate(cell_data):
                    if not isinstance(cell, Mapping):
                        raise _ProtocolFailure
                    row_number = start_row + row_offset + 1
                    column_number = start_column + column_offset + 1
                    if not (rectangle.start_row <= row_number <= rectangle.end_row and rectangle.start_column <= column_number <= rectangle.end_column):
                        raise _ProtocolFailure
                    address = _address(column_number, row_number)
                    user_value = cell.get("userEnteredValue", {})
                    if not isinstance(user_value, Mapping):
                        raise _ProtocolFailure
                    user_branches = [key for key in ("formulaValue", "numberValue", "stringValue", "boolValue", "errorValue") if key in user_value]
                    if len(user_branches) > 1:
                        raise _ProtocolFailure
                    formula = user_value.get("formulaValue")
                    if formula is not None:
                        if not isinstance(formula, str) or not formula:
                            raise _ProtocolFailure
                        expression_bytes += len(formula.encode("utf-8"))
                        if expression_bytes > expression_limit:
                            raise _LimitFailure("formula response exceeded the configured expression byte limit", expression_limit)
                        formulas.append(otf.FormulaCell(address, otf.FormulaExpression(formula, otf.GOOGLE_SHEETS_A1)))
                    if "effectiveValue" in cell:
                        values.append((address, self._effective_value(cell["effectiveValue"], cell.get("effectiveFormat"))))
                    elif cell:
                        values.append((address, otf.FormulaValue("null")))
        revision = _hash_payload({"target": target.grid.value, "worksheet_id": target.worksheet.worksheet_id, "range": f"{rectangle.start_address}:{rectangle.end_address}", "formulas": [cell.to_wire() for cell in formulas]})
        observation = otf.GridFormulaObservation(
            worksheet_id=target.worksheet.worksheet_id or "",
            requested_range=f"{rectangle.start_address}:{rectangle.end_address}" if rectangle.start_address != rectangle.end_address else rectangle.start_address,
            formulas=tuple(formulas),
            observed_revision=revision,
        )
        return observation, tuple(values)

    def _effective_value(self, raw: object, number_format: object) -> otf.FormulaValue:
        if not isinstance(raw, Mapping):
            raise _ProtocolFailure
        branches = [key for key in ("numberValue", "stringValue", "boolValue", "errorValue") if key in raw]
        if len(branches) > 1:
            raise _ProtocolFailure
        if not branches:
            return otf.FormulaValue("null")
        branch = branches[0]
        value = raw[branch]
        if branch == "numberValue":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise _ProtocolFailure
            format_data = number_format if isinstance(number_format, Mapping) else {}
            format_type = format_data.get("numberFormat", {}).get("type") if isinstance(format_data.get("numberFormat"), Mapping) else None
            pattern = format_data.get("numberFormat", {}).get("pattern") if isinstance(format_data.get("numberFormat"), Mapping) else None
            if format_type in {"DATE", "TIME", "DATE_TIME"}:
                if pattern is not None and not isinstance(pattern, str):
                    raise _ProtocolFailure
                logical_type = f"{format_type}:{pattern or ''}"
                return otf.FormulaValue.logical(logical_type, float(value))
            return otf.FormulaValue("number", float(value))
        if branch == "stringValue":
            if not isinstance(value, str):
                raise _ProtocolFailure
            return otf.FormulaValue("string", value)
        if branch == "boolValue":
            if not isinstance(value, bool):
                raise _ProtocolFailure
            return otf.FormulaValue("boolean", value)
        if not isinstance(value, Mapping) or not isinstance(value.get("type"), str) or not value["type"]:
            raise _ProtocolFailure
        return otf.FormulaValue.provider_error(otf.FormulaErrorValue(value["type"]))

    def _validated_range(self, selector: str, limits: otf.FormulaResourceLimits | None) -> otf.A1Rectangle:
        rectangle = otf.A1Rectangle.parse(selector)
        max_cells = _MAX_CELLS if limits is None or limits.max_cells is None else min(_MAX_CELLS, limits.max_cells)
        if rectangle.cell_count > max_cells:
            raise _LimitFailure("formula range exceeds the configured cell limit", max_cells)
        return rectangle

    def _expression_limit(self, limits: otf.FormulaResourceLimits | None) -> int:
        requested = limits.max_expression_bytes if limits is not None else None
        if requested is not None and (
            isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0
        ):
            raise _ProtocolFailure
        return _MAX_EXPRESSION_BYTES if requested is None else min(_MAX_EXPRESSION_BYTES, requested)

    def _check_dimensions(self, target: otf.BoundGridFormulaTarget, rectangle: otf.A1Rectangle) -> None:
        spreadsheet_id = self._spreadsheet_id(target.grid)
        worksheet_id = target.worksheet.worksheet_id
        if worksheet_id is None:
            raise _ProtocolFailure
        with self._lock:
            dimensions = self._bindings.get((spreadsheet_id, worksheet_id))
        if dimensions is None:
            return
        _, row_count, column_count = dimensions
        if row_count is not None and rectangle.end_row > row_count:
            raise _LimitFailure("formula range exceeds the worksheet row limit", row_count)
        if column_count is not None and rectangle.end_column > column_count:
            raise _LimitFailure("formula range exceeds the worksheet column limit", column_count)

    def _title_for(self, target: otf.BoundGridFormulaTarget) -> str:
        spreadsheet_id = self._spreadsheet_id(target.grid)
        worksheet_id = target.worksheet.worksheet_id
        if worksheet_id is None:
            raise _ProtocolFailure
        with self._lock:
            cached = self._bindings.get((spreadsheet_id, worksheet_id))
        if cached is not None:
            target_title = self._worksheet_name(target.grid)
            if target_title is not None and target_title != cached[0]:
                raise _ProtocolFailure
            return cached[0]
        title = self._worksheet_name(target.grid)
        if title is not None:
            return title
        raise _ProtocolFailure

    def _spreadsheet_id(self, uri: TableURI | str) -> str:
        value = uri.value if isinstance(uri, TableURI) else TableURI(uri).value
        parsed = urlsplit(value)
        if parsed.scheme == SCHEME_GSHEETS:
            return parsed.netloc
        if parsed.scheme == SCHEME_HTTPS and parsed.hostname == HOST_GOOGLE_DOCS:
            parts = parsed.path.split("/")
            try:
                return parts[parts.index("d") + 1]
            except (ValueError, IndexError):
                return ""
        return ""

    def _url(self, path: str) -> str:
        return self._connector._url(path)

    def _formula_map(self, observation: otf.GridFormulaObservation) -> dict[str, str]:
        return {cell.address: cell.expression.text for cell in observation.formulas}

    def _check_response_size(
        self,
        payload: Mapping[str, Any],
        limits: otf.FormulaResourceLimits | None = None,
    ) -> None:
        requested = limits.max_response_bytes if limits is not None else None
        if requested is not None and (isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0):
            raise _ProtocolFailure
        limit = _MAX_RESPONSE_BYTES if requested is None else min(_MAX_RESPONSE_BYTES, requested)
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > limit:
            raise _LimitFailure("Google Sheets response exceeded the configured byte limit", limit)

    def _provider_400_result(self, exc: ConnectorError) -> otf.FormulaExtensionResult[Any]:
        if self._is_formula_rejection(exc):
            return _rejected(
                otf.FormulaErrorCode.INVALID_FORMULA,
                "formula provider rejected the expression",
                {"provider_status_code": 400},
            )
        return self._transport_error(exc, operation="formula mutation")

    def _is_formula_rejection(self, exc: ConnectorError) -> bool:
        if exc.safe_details.get("status") != 400:
            return False
        for key in ("reason", "code"):
            value = exc.safe_details.get(key)
            if isinstance(value, str) and re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") in _FORMULA_REJECTION_REASONS:
                return True
        return False

    def _worksheet_name(self, uri: TableURI | str) -> str | None:
        value = uri.value if isinstance(uri, TableURI) else TableURI(uri).value
        parsed = urlsplit(value)
        if parsed.scheme != SCHEME_GSHEETS:
            return None
        title = unquote(parsed.path.lstrip("/"))
        return title or None

    def _a1_title(self, title: str) -> str:
        if _SIMPLE_A1_TITLE.fullmatch(title) and _CELL_REFERENCE.fullmatch(title) is None:
            return title
        return "'" + title.replace("'", "''") + "'"

    def _transport_error(self, exc: ConnectorError, *, operation: str) -> otf.FormulaExtensionResult[Any]:
        mapping = {
            ConnectorErrorCode.AUTHENTICATION: otf.FormulaErrorCode.EXECUTION_FAILED,
            ConnectorErrorCode.TIMEOUT: otf.FormulaErrorCode.TIMEOUT,
            ConnectorErrorCode.RESOURCE_LIMIT_EXCEEDED: otf.FormulaErrorCode.RESOURCE_LIMIT,
            ConnectorErrorCode.PROTOCOL_INVALID: otf.FormulaErrorCode.PROTOCOL_FAILURE,
            ConnectorErrorCode.PROTOCOL_VERSION_UNSUPPORTED: otf.FormulaErrorCode.PROTOCOL_FAILURE,
        }
        code = mapping.get(exc.code, otf.FormulaErrorCode.EXECUTION_FAILED)
        details: dict[str, Any] = {}
        if isinstance(exc.safe_details.get("status"), int):
            details["provider_status_code"] = exc.safe_details["status"]
        return _rejected(code, f"Google Sheets {operation} failed", details)

    def _reconcile_after_uncertain(
        self,
        request: otf.GridFormulaSetRequest,
        rectangle: otf.A1Rectangle,
        expression: otf.FormulaExpression,
        revision_before: str,
        target_hash: str,
        selector_hash: str,
        payload_hash: str,
    ) -> otf.FormulaExtensionResult[otf.FormulaMutation]:
        readback_result = self.read_grid(otf.GridFormulaReadRequest(request.target, request.cell_range, request.limits))
        expected = self._expected_formula_map(rectangle, expression)
        if readback_result.outcome is otf.FormulaOutcome.SUCCEEDED and readback_result.value is not None and self._formula_map(readback_result.value) == expected:
            mutation = otf.FormulaMutation("grid", rectangle.cell_count, readback_result.value, revision_before, readback_result.value.observed_revision)
            operation_hash = _hash_payload(mutation.to_wire())
            receipt = otf.FormulaReceiptDetails.for_grid_set(
                target=request.target.grid.value, selector=request.cell_range,
                capability=otf.GRID_SET.to_reference(), dialect=expression.dialect,
                expression_sha256=expression.sha256, observation_sha256=otf.formula_observation_hash(readback_result.value),
                affected_count=rectangle.cell_count, revision_before=revision_before, revision_after=readback_result.value.observed_revision,
                mutation_atomicity=otf.MutationAtomicity.ATOMIC.value, revision_enforcement=otf.RevisionEnforcement.CHECKED.value,
                verification="formula_text_readback",
            )
            result = otf.FormulaExtensionResult(mutation, otf.FormulaOutcome.SUCCEEDED, otf.FormulaCommitState.COMMITTED, otf.FormulaVerificationState.PASSED, (receipt,))
            if request.idempotency_key is not None:
                with self._lock:
                    self._ledger.succeed(connector_id=PROVIDER_GOOGLE_SHEETS, target_hash=target_hash, selector_hash=selector_hash, idempotency_key=request.idempotency_key, payload_hash=payload_hash, operation_hash=operation_hash)
                    self._completed[operation_hash] = result
            return result
        self._mark_unknown_ledger(request, target_hash, selector_hash, payload_hash)
        return _unknown(otf.FormulaErrorCode.UNCERTAIN_MUTATION, "formula mutation acknowledgement was lost")

    def _expected_formula_map(self, rectangle: otf.A1Rectangle, expression: otf.FormulaExpression) -> dict[str, str]:
        return {
            _address(column, row): self._translate_formula(
                expression.text,
                column - rectangle.start_column,
                row - rectangle.start_row,
            )
            for row in range(rectangle.start_row, rectangle.end_row + 1)
            for column in range(rectangle.start_column, rectangle.end_column + 1)
        }

    def _translate_formula(self, expression: str, column_delta: int, row_delta: int) -> str:
        output: list[str] = []
        position = 0
        while position < len(expression):
            if expression[position] in {'"', "'"}:
                quote_character = expression[position]
                end = position + 1
                while end < len(expression):
                    if expression[end] == quote_character:
                        end += 1
                        break
                    end += 1
                output.append(expression[position:end])
                position = end
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
            raw_column = match.group("column")
            raw_row = match.group("row")
            absolute_column = raw_column.startswith("$")
            absolute_row = raw_row.startswith("$")
            column_text = raw_column.removeprefix("$")
            row_text = raw_row.removeprefix("$")
            column_number = 0
            for character in column_text.upper():
                column_number = column_number * 26 + ord(character) - ord("A") + 1
            row_number = int(row_text)
            if not absolute_column:
                column_number += column_delta
            if not absolute_row:
                row_number += row_delta
            if column_number <= 0 or row_number <= 0:
                raise _ProtocolFailure
            output.append(
                ("$" if absolute_column else "")
                + _address(column_number, 1).rstrip("1")
                + ("$" if absolute_row else "")
                + str(row_number)
            )
            position = end
        return "".join(output)

    def _fail_ledger(self, request: otf.GridFormulaSetRequest, target_hash: str, selector_hash: str, payload_hash: str) -> None:
        if request.idempotency_key is not None:
            with self._lock:
                self._ledger.fail_known(connector_id=PROVIDER_GOOGLE_SHEETS, target_hash=target_hash, selector_hash=selector_hash, idempotency_key=request.idempotency_key, payload_hash=payload_hash)

    def _mark_unknown_ledger(self, request: otf.GridFormulaSetRequest, target_hash: str, selector_hash: str, payload_hash: str) -> None:
        if request.idempotency_key is not None:
            with self._lock:
                self._ledger.mark_unknown(connector_id=PROVIDER_GOOGLE_SHEETS, target_hash=target_hash, selector_hash=selector_hash, idempotency_key=request.idempotency_key, payload_hash=payload_hash)

    def _finish_ledger_failure(
        self,
        request: otf.GridFormulaSetRequest,
        ledger_context: tuple[str, str, str] | None,
        *,
        post_dispatched: bool,
    ) -> None:
        if request.idempotency_key is None or ledger_context is None:
            return
        if post_dispatched:
            self._mark_unknown_ledger(request, *ledger_context)
        else:
            self._fail_ledger(request, *ledger_context)


class _ProtocolFailure(Exception):
    pass


class _LimitFailure(Exception):
    def __init__(self, message: str, limit: int) -> None:
        super().__init__(message)
        self.limit = limit


__all__ = ["GoogleSheetsFormulaExtension"]
