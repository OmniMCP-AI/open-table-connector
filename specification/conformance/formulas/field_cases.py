"""Shared, provider-neutral field Formula cases and recovery scenarios."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import open_table_connector.formulas as otf
from open_table_connector.conformance.formulas import FormulaProviderCase
from open_table_connector.contract import CapabilityIdentity, TableURI

from .support import FakeTable, FieldCaseData, make_field_target

FIELD_PROVIDER_IDS = ("maybe_sheet", "feishu_bitable")

EXPECTED_FIELD_CAPABILITIES = {
    "maybe_sheet": {
        "formula.field.read/1.0",
        "formula.field.set/1.0",
        "formula.field.values.read/1.0",
        "formula.field.recalculate/1.0",
    },
    "feishu_bitable": {
        "formula.field.read/1.0",
        "formula.field.set/1.0",
        "formula.field.values.read/1.0",
    },
}

_FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "formulas" / "v1"
_FIELD_FIXTURES = {"field-observation.json", "value-observations.json"}

FIELD_NATIVE_EXPRESSIONS = {
    "maybe_sheet": (
        "IF(price > cost, price - cost, 0)",
        "ROUND(revenue - cost, 2)",
    ),
    "feishu_bitable": (
        "IF(price > cost, price - cost, 0)",
        "ROUND(revenue - cost, 2)",
    ),
}

_FIELD_METADATA = {
    "maybe_sheet": {
        "field_id": "fld-gross-margin",
        "field_name": "gross_margin",
        "type": "formula",
        "result_type": "number",
        "property": {
            "formula_expression": "IF(price > cost, price - cost, 0)",
            "format": "currency",
            "precision": 2,
        },
        "unrelated_properties": {"required": False, "description": "Gross margin"},
    },
    "feishu_bitable": {
        "field_id": "fld-gross-margin",
        "field_name": "gross_margin",
        "type": 20,
        "result_type": "number",
        "property": {
            "formula_expression": "IF(price > cost, price - cost, 0)",
            "format": "currency",
            "precision": 2,
        },
        "unrelated_properties": {"required": False, "description": "Gross margin"},
    },
}


def load_field_fixture(name: str) -> dict[str, Any]:
    """Load one of the contract-owned field observation documents."""

    filename = name if name.endswith(".json") else "field-observation.json"
    if filename not in _FIELD_FIXTURES:
        raise KeyError(f"unknown field fixture: {name}")
    return json.loads((_FIXTURE_ROOT / filename).read_text(encoding="utf-8"))


def field_fixture_metadata(provider_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return complete before/after metadata snapshots for isolation probes."""

    if provider_id not in FIELD_PROVIDER_IDS:
        raise KeyError(f"unknown field provider: {provider_id}")
    before = deepcopy(_FIELD_METADATA[provider_id])
    after = deepcopy(before)
    after["property"]["formula_expression"] = "ROUND(revenue - cost, 2)"
    after["provider_revision"] = "sha256:" + "b" * 64
    after["provider_evidence"] = {"status": "verified", "changed": ("formula_expression",)}
    return before, after


def field_case_data_for_provider(provider_id: str) -> FieldCaseData:
    """Decode the shared value fixture into a provider-specific typed case."""

    if provider_id not in FIELD_PROVIDER_IDS:
        raise KeyError(f"unknown field provider: {provider_id}")
    value = otf.formula_observation_from_wire(load_field_fixture("value-observations.json"))
    if not isinstance(value, otf.FieldFormulaValueObservation):
        raise TypeError("field value fixture must decode to FieldFormulaValueObservation")
    dialect = otf.MAYBE_BASE if provider_id == "maybe_sheet" else otf.FEISHU_BITABLE
    table_uri = TableURI(f"{provider_id}://workspace/orders")
    expected_values = otf.FieldFormulaValueObservation(
        table_uri=table_uri,
        field_id="fld-gross-margin",
        field_name="gross_margin",
        values=value.values,
        calculation_state=value.calculation_state,
        calculation_trigger=value.calculation_trigger,
        dependency_scope=value.dependency_scope,
        observed_revision="sha256:" + "c" * 64,
    )
    expected_after_set = otf.FieldFormulaObservation(
        table_uri=table_uri,
        field_id="fld-gross-margin",
        field_name="gross_margin",
        expression=otf.FormulaExpression("ROUND(revenue - cost, 2)", dialect),
        result_type="number",
        observed_revision="sha256:" + "b" * 64,
    )
    return FieldCaseData(
        set_expression=otf.FormulaExpression("ROUND(revenue - cost, 2)", dialect),
        conflicting_expression=otf.FormulaExpression("ROUND(revenue - tax, 2)", dialect),
        expected_after_set=expected_after_set,
        expected_values=expected_values,
        recalculation_scope=otf.FieldRecalculationScope.FIELD,
        expected_recalculation=None,
    )


def make_field_provider_case(
    provider_id: str,
    extension_factory: Callable[[], object],
    *,
    static_capabilities: tuple[CapabilityIdentity, ...],
    field_target_factory: Callable[[], otf.FieldFormulaTarget[FakeTable]] = make_field_target,
    supports_independent_sessions: bool = True,
) -> FormulaProviderCase:
    """Build the provider case that later adapter tasks will register."""

    return FormulaProviderCase(
        provider_id=provider_id,
        target_kind="field",
        dialect=otf.MAYBE_BASE if provider_id == "maybe_sheet" else otf.FEISHU_BITABLE,
        static_capabilities=static_capabilities,
        extension_factory=extension_factory,
        field_target_factory=field_target_factory,
        field_case=field_case_data_for_provider(provider_id),
        supports_independent_sessions=supports_independent_sessions,
        security_markers=("https://secret.example/formula", "tok_formula"),
        security_expression=otf.FormulaExpression(
            'IF(url = "https://secret.example/formula", "tok_formula", 0)',
            otf.MAYBE_BASE if provider_id == "maybe_sheet" else otf.FEISHU_BITABLE,
        ),
        security_probe_values=("https://secret.example/formula", "tok_formula"),
    )


def load_field_provider_cases() -> tuple[FormulaProviderCase, ...]:
    """Return no registered adapters until the Maybe and Feishu tasks land."""

    return ()


@dataclass(frozen=True, slots=True)
class FieldFailureScenario:
    name: str
    error_code: otf.FormulaErrorCode
    outcome: otf.FormulaOutcome
    commit: otf.FormulaCommitState
    verification: otf.FormulaVerificationState
    safe_message: str
    raw_expression: str
    retry: bool = False


_RAW_FIELD_EXPRESSION = 'IF(url = "https://secret.example/formula", "tok_formula", 0)'

FIELD_FAILURE_SCENARIOS = (
    FieldFailureScenario(
        "timeout_before_dispatch",
        otf.FormulaErrorCode.TIMEOUT,
        otf.FormulaOutcome.REJECTED,
        otf.FormulaCommitState.NOT_STARTED,
        otf.FormulaVerificationState.SKIPPED,
        "formula provider request timed out before dispatch",
        _RAW_FIELD_EXPRESSION,
    ),
    FieldFailureScenario(
        "provider_rejection",
        otf.FormulaErrorCode.INVALID_FORMULA,
        otf.FormulaOutcome.REJECTED,
        otf.FormulaCommitState.NOT_STARTED,
        otf.FormulaVerificationState.SKIPPED,
        "formula provider rejected the expression",
        _RAW_FIELD_EXPRESSION,
    ),
    FieldFailureScenario(
        "readback_mismatch",
        otf.FormulaErrorCode.READBACK_MISMATCH,
        otf.FormulaOutcome.FAILED,
        otf.FormulaCommitState.COMMITTED,
        otf.FormulaVerificationState.FAILED,
        "formula text readback did not match the requested mutation",
        _RAW_FIELD_EXPRESSION,
    ),
    FieldFailureScenario(
        "lost_acknowledgement",
        otf.FormulaErrorCode.UNCERTAIN_MUTATION,
        otf.FormulaOutcome.UNKNOWN,
        otf.FormulaCommitState.UNKNOWN,
        otf.FormulaVerificationState.UNAVAILABLE,
        "formula mutation acknowledgement was lost",
        _RAW_FIELD_EXPRESSION,
    ),
    FieldFailureScenario(
        "unknown_commit",
        otf.FormulaErrorCode.UNCERTAIN_MUTATION,
        otf.FormulaOutcome.UNKNOWN,
        otf.FormulaCommitState.UNKNOWN,
        otf.FormulaVerificationState.UNAVAILABLE,
        "formula commit state could not be determined",
        _RAW_FIELD_EXPRESSION,
    ),
)


def simulate_field_failure(scenario: FieldFailureScenario) -> otf.FormulaExtensionResult[Any]:
    """Return a safe typed result represented by a field recovery scenario."""

    if not isinstance(scenario, FieldFailureScenario):
        raise TypeError("scenario must be a FieldFailureScenario")
    return otf.FormulaExtensionResult(
        value=None,
        outcome=scenario.outcome,
        commit=scenario.commit,
        verification=scenario.verification,
        receipts=(),
        error=otf.FormulaExtensionErrorInfo(
            code=scenario.error_code,
            message=scenario.safe_message,
            safe_details={"target_kind": "field", "status": scenario.commit.value},
        ),
    )


__all__ = [
    "EXPECTED_FIELD_CAPABILITIES",
    "FIELD_FAILURE_SCENARIOS",
    "FIELD_NATIVE_EXPRESSIONS",
    "FIELD_PROVIDER_IDS",
    "FieldFailureScenario",
    "field_case_data_for_provider",
    "field_fixture_metadata",
    "load_field_fixture",
    "load_field_provider_cases",
    "make_field_provider_case",
    "simulate_field_failure",
]
