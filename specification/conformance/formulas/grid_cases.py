"""Shared, provider-neutral grid Formula cases and failure simulations.

Provider cases intentionally remain empty until the provider implementation tasks
register their adapters.  The literal documents in ``fixtures/`` are the shared
contract that those cases will consume.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import open_table_connector.formulas as otf
from open_table_connector.conformance.formulas import FormulaProviderCase
from open_table_connector.contract import CapabilityIdentity

from .support import (
    FakeFormulaExtension,
    FakeFormulaStore,
    GridCaseData,
    make_grid_target,
)

GRID_PROVIDER_IDS = ("google_sheets", "maybe_sheet", "excel")

EXPECTED_GRID_CAPABILITIES = {
    "google_sheets": {
        "formula.grid.read/1.0",
        "formula.grid.set/1.0",
        "formula.grid.values.read/1.0",
    },
    "maybe_sheet": {
        "formula.grid.read/1.0",
        "formula.grid.set/1.0",
        "formula.grid.values.read/1.0",
        "formula.grid.recalculate/1.0",
    },
    "excel": {
        "formula.grid.read/1.0",
        "formula.grid.set/1.0",
    },
}

_FIXTURE_ROOT = (
    Path(__file__).parents[2]
    / "fixtures"
    / "formulas"
    / "v1"
    / "grid-providers"
)

GRID_SECURITY_MARKERS = (
    "https://secret.example/formula",
    "tok_formula",
)


def load_grid_fixture(provider_id: str) -> dict[str, Any]:
    """Load one provider's literal expected grid document."""

    if provider_id not in GRID_PROVIDER_IDS:
        raise KeyError(f"unknown grid provider: {provider_id}")
    path = _FIXTURE_ROOT / f"{provider_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("provider_id") != provider_id:
        raise ValueError(f"invalid grid fixture document: {path.name}")
    return payload


def load_grid_provider_cases() -> tuple[FormulaProviderCase, ...]:
    """Return the offline provider matrix backed by the literal corpus.

    Provider adapters have dedicated recording tests in their package suites.
    These cases exercise the shared capability-selected contract with isolated
    state for each provider/dialect, so the golden documents remain the source
    of expected copy-fill and value observations.
    """

    return tuple(
        _make_registered_case(provider_id)
        for provider_id in GRID_PROVIDER_IDS
    )


def _make_registered_case(provider_id: str) -> FormulaProviderCase:
    fixture = load_grid_fixture(provider_id)
    data = grid_case_data_for_provider(provider_id)
    store = FakeFormulaStore()
    if provider_id == "google_sheets":
        capabilities = (otf.GRID_READ, otf.GRID_SET, otf.GRID_VALUES_READ)
        details = otf.FormulaCapabilityDetails(
            target_kind="grid",
            dialects=(fixture["dialect"],),
            max_cells_per_operation=10_000,
            max_expression_bytes=50_000,
            recalculation_scopes=(),
            calculation_states=(otf.CalculationState.PROVIDER_CURRENT,),
            mutation_atomicity=otf.MutationAtomicity.ATOMIC,
            revision_enforcement=otf.RevisionEnforcement.CHECKED,
            idempotency_strength=otf.IdempotencyStrength.RECONCILED,
        )
    elif provider_id == "maybe_sheet":
        capabilities = (
            otf.GRID_READ,
            otf.GRID_SET,
            otf.GRID_VALUES_READ,
            otf.GRID_RECALCULATE,
        )
        details = otf.FormulaCapabilityDetails(
            target_kind="grid",
            dialects=(fixture["dialect"],),
            max_cells_per_operation=10_000,
            max_expression_bytes=64 * 1024,
            recalculation_scopes=(
                otf.GridRecalculationScope.RANGE.value,
                otf.GridRecalculationScope.WORKSHEET.value,
                otf.GridRecalculationScope.WORKBOOK.value,
            ),
            calculation_states=(otf.CalculationState.PROVIDER_CURRENT,),
            mutation_atomicity=otf.MutationAtomicity.ATOMIC,
            revision_enforcement=otf.RevisionEnforcement.CHECKED,
            idempotency_strength=otf.IdempotencyStrength.PROVIDER,
        )
    else:
        capabilities = (otf.GRID_READ, otf.GRID_SET)
        details = otf.FormulaCapabilityDetails(
            target_kind="grid",
            dialects=(fixture["dialect"],),
            max_cells_per_operation=100_000,
            max_expression_bytes=8_192,
            recalculation_scopes=(),
            calculation_states=(),
            mutation_atomicity=otf.MutationAtomicity.ATOMIC,
            revision_enforcement=otf.RevisionEnforcement.CHECKED,
            idempotency_strength=otf.IdempotencyStrength.RECONCILED,
        )

    return make_grid_provider_case(
        provider_id,
        lambda: FakeFormulaExtension(
            store=store,
            grid_capabilities=capabilities,
            grid_data=data,
            grid_details=details,
        ),
        static_capabilities=capabilities,
    )


def grid_case_data_for_provider(provider_id: str) -> GridCaseData:
    """Decode one provider's literal documents into shared case data."""

    fixture = load_grid_fixture(provider_id)
    dialect = fixture["dialect"]
    copy_fill = fixture["copy_fill"]
    expected_formulas = tuple(
        otf.FormulaCell(
            item["address"],
            otf.FormulaExpression(item["text"], dialect),
        )
        for item in copy_fill["expected"]
    )
    expected_after_set = otf.GridFormulaObservation(
        worksheet_id="ws-model",
        requested_range=fixture["formula_range"],
        formulas=expected_formulas,
        observed_revision="sha256:" + "b" * 64,
    )
    values = otf.formula_observation_from_wire(fixture["value_observation"])
    if not isinstance(values, otf.GridFormulaValueObservation):
        raise TypeError("grid provider value fixture must decode to a grid value observation")
    explicit_values = otf.GridFormulaValueObservation(
        worksheet_id=values.worksheet_id,
        requested_range=values.requested_range,
        values=values.values,
        calculation_state=values.calculation_state,
        calculation_trigger=otf.CalculationTrigger.EXPLICIT_RECALCULATION,
        dependency_scope=values.dependency_scope,
        observed_revision="sha256:" + "c" * 64,
    )
    expected_recalculation = otf.RecalculationObservation(
        target_kind="grid",
        requested_scope=otf.GridRecalculationScope.RANGE.value,
        effective_scope=otf.GridRecalculationScope.RANGE.value,
        revision_before="sha256:" + "b" * 64,
        revision_after="sha256:" + "c" * 64,
        provider_status="completed",
        calculation_state=values.calculation_state,
        verification="passed",
        value_observation=explicit_values,
    )
    return GridCaseData(
        formula_range=fixture["formula_range"],
        literal_range=fixture["literal_range"],
        set_expression=otf.FormulaExpression(copy_fill["source"], dialect),
        conflicting_expression=otf.FormulaExpression("=Z9", dialect),
        expected_after_set=expected_after_set,
        expected_literal_read=otf.GridFormulaObservation(
            worksheet_id="ws-model",
            requested_range=fixture["literal_range"],
            formulas=(),
            observed_revision="sha256:" + "a" * 64,
        ),
        expected_values=values,
        recalculation_scope=otf.GridRecalculationScope.RANGE,
        expected_recalculation=expected_recalculation,
    )


def make_grid_provider_case(
    provider_id: str,
    extension_factory: Callable[[], object],
    *,
    static_capabilities: tuple[CapabilityIdentity, ...],
    grid_target_factory: Callable[[], otf.GridFormulaTarget] = make_grid_target,
    supports_independent_sessions: bool = True,
) -> FormulaProviderCase:
    """Build a provider case from the literal documents and an adapter factory."""

    fixture = load_grid_fixture(provider_id)
    dialect = fixture["dialect"]
    return FormulaProviderCase(
        provider_id=provider_id,
        target_kind="grid",
        dialect=dialect,
        static_capabilities=static_capabilities,
        extension_factory=extension_factory,
        grid_target_factory=grid_target_factory,
        grid_case=grid_case_data_for_provider(provider_id),
        supports_independent_sessions=supports_independent_sessions,
        security_markers=GRID_SECURITY_MARKERS,
        security_expression=otf.FormulaExpression(_RAW_EXPRESSION, dialect),
        security_probe_values=GRID_SECURITY_MARKERS,
    )


@dataclass(frozen=True, slots=True)
class GridFailureScenario:
    """A deterministic mutation failure state for conformance assertions."""

    name: str
    error_code: otf.FormulaErrorCode
    outcome: otf.FormulaOutcome
    commit: otf.FormulaCommitState
    verification: otf.FormulaVerificationState
    safe_message: str
    raw_expression: str
    retry: bool = False


_RAW_EXPRESSION = '=HYPERLINK("https://secret.example/formula", "tok_formula")'

GRID_FAILURE_SCENARIOS = (
    GridFailureScenario(
        name="timeout_before_dispatch",
        error_code=otf.FormulaErrorCode.TIMEOUT,
        outcome=otf.FormulaOutcome.REJECTED,
        commit=otf.FormulaCommitState.NOT_STARTED,
        verification=otf.FormulaVerificationState.SKIPPED,
        safe_message="formula provider request timed out before dispatch",
        raw_expression=_RAW_EXPRESSION,
    ),
    GridFailureScenario(
        name="provider_rejection",
        error_code=otf.FormulaErrorCode.INVALID_FORMULA,
        outcome=otf.FormulaOutcome.REJECTED,
        commit=otf.FormulaCommitState.NOT_STARTED,
        verification=otf.FormulaVerificationState.SKIPPED,
        safe_message="formula provider rejected the expression",
        raw_expression=_RAW_EXPRESSION,
    ),
    GridFailureScenario(
        name="partial_response",
        error_code=otf.FormulaErrorCode.PARTIAL_EFFECT,
        outcome=otf.FormulaOutcome.PARTIAL,
        commit=otf.FormulaCommitState.PARTIAL,
        verification=otf.FormulaVerificationState.FAILED,
        safe_message="formula provider returned a partial mutation response",
        raw_expression=_RAW_EXPRESSION,
    ),
    GridFailureScenario(
        name="lost_acknowledgement",
        error_code=otf.FormulaErrorCode.UNCERTAIN_MUTATION,
        outcome=otf.FormulaOutcome.UNKNOWN,
        commit=otf.FormulaCommitState.UNKNOWN,
        verification=otf.FormulaVerificationState.UNAVAILABLE,
        safe_message="formula mutation acknowledgement was lost",
        raw_expression=_RAW_EXPRESSION,
    ),
    GridFailureScenario(
        name="readback_mismatch",
        error_code=otf.FormulaErrorCode.READBACK_MISMATCH,
        outcome=otf.FormulaOutcome.FAILED,
        commit=otf.FormulaCommitState.COMMITTED,
        verification=otf.FormulaVerificationState.FAILED,
        safe_message="formula text readback did not match the requested mutation",
        raw_expression=_RAW_EXPRESSION,
    ),
    GridFailureScenario(
        name="unknown_commit",
        error_code=otf.FormulaErrorCode.UNCERTAIN_MUTATION,
        outcome=otf.FormulaOutcome.UNKNOWN,
        commit=otf.FormulaCommitState.UNKNOWN,
        verification=otf.FormulaVerificationState.UNAVAILABLE,
        safe_message="formula commit state could not be determined",
        raw_expression=_RAW_EXPRESSION,
    ),
)


def simulate_grid_failure(
    scenario: GridFailureScenario,
) -> otf.FormulaExtensionResult[Any]:
    """Return the typed result represented by a failure scenario."""

    if not isinstance(scenario, GridFailureScenario):
        raise TypeError("scenario must be a GridFailureScenario")

    value: otf.FormulaMutation | None = None
    if scenario.outcome is otf.FormulaOutcome.PARTIAL:
        observation = otf.GridFormulaObservation(
            worksheet_id="ws-model",
            requested_range="A1",
            formulas=(
                otf.FormulaCell(
                    "A1",
                    otf.FormulaExpression(scenario.raw_expression, otf.GOOGLE_SHEETS_A1),
                ),
            ),
            observed_revision="sha256:" + "b" * 64,
        )
        value = otf.FormulaMutation(
            target_kind="grid",
            affected_count=1,
            formula_observation=observation,
            revision_before="sha256:" + "a" * 64,
            revision_after="sha256:" + "b" * 64,
        )

    safe_details: dict[str, Any] = {"target_kind": "grid"}
    if scenario is GRID_FAILURE_SCENARIOS[0]:
        safe_details["status"] = "before_dispatch"
    elif scenario is GRID_FAILURE_SCENARIOS[4]:
        safe_details["status"] = "committed"
    elif scenario is GRID_FAILURE_SCENARIOS[3]:
        safe_details["status"] = "acknowledgement_lost"
    elif scenario is GRID_FAILURE_SCENARIOS[5]:
        safe_details["status"] = "unknown"

    error = otf.FormulaExtensionErrorInfo(
        code=scenario.error_code,
        message=scenario.safe_message,
        safe_details=safe_details,
    )
    return otf.FormulaExtensionResult(
        value=value,
        outcome=scenario.outcome,
        commit=scenario.commit,
        verification=scenario.verification,
        receipts=(),
        error=error,
    )


__all__ = [
    "EXPECTED_GRID_CAPABILITIES",
    "GRID_FAILURE_SCENARIOS",
    "GRID_PROVIDER_IDS",
    "GRID_SECURITY_MARKERS",
    "GridFailureScenario",
    "grid_case_data_for_provider",
    "load_grid_fixture",
    "load_grid_provider_cases",
    "make_grid_provider_case",
    "simulate_grid_failure",
]
