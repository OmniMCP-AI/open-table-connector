from __future__ import annotations

from open_table_connector.formulas import FormulaErrorCode

from .grid_cases import GRID_FAILURE_SCENARIOS, simulate_grid_failure


def test_grid_recovery_corpus_covers_known_and_uncertain_mutation_states() -> None:
    actual = {scenario.name: scenario.error_code for scenario in GRID_FAILURE_SCENARIOS}

    assert actual == {
        "timeout_before_dispatch": FormulaErrorCode.TIMEOUT,
        "provider_rejection": FormulaErrorCode.INVALID_FORMULA,
        "partial_response": FormulaErrorCode.PARTIAL_EFFECT,
        "lost_acknowledgement": FormulaErrorCode.UNCERTAIN_MUTATION,
        "readback_mismatch": FormulaErrorCode.READBACK_MISMATCH,
        "unknown_commit": FormulaErrorCode.UNCERTAIN_MUTATION,
    }


def test_grid_recovery_corpus_marks_uncertain_mutations_without_blind_retry() -> None:
    uncertain = {
        scenario.name
        for scenario in GRID_FAILURE_SCENARIOS
        if scenario.error_code is FormulaErrorCode.UNCERTAIN_MUTATION
    }

    assert uncertain == {"lost_acknowledgement", "unknown_commit"}
    assert all(not scenario.retry for scenario in GRID_FAILURE_SCENARIOS)


def test_grid_recovery_simulations_use_typed_outcome_commit_and_verification_states() -> None:
    actual = {
        scenario.name: simulate_grid_failure(scenario)
        for scenario in GRID_FAILURE_SCENARIOS
    }

    assert (actual["timeout_before_dispatch"].outcome.value,
            actual["timeout_before_dispatch"].commit.value,
            actual["timeout_before_dispatch"].verification.value) == (
        "rejected",
        "not_started",
        "skipped",
    )
    assert (actual["provider_rejection"].outcome.value,
            actual["provider_rejection"].commit.value) == ("rejected", "not_started")
    assert (actual["partial_response"].outcome.value,
            actual["partial_response"].commit.value,
            actual["partial_response"].verification.value) == (
        "partial",
        "partial",
        "failed",
    )
    assert (actual["lost_acknowledgement"].outcome.value,
            actual["lost_acknowledgement"].commit.value,
            actual["lost_acknowledgement"].verification.value) == (
        "unknown",
        "unknown",
        "unavailable",
    )
    assert actual["readback_mismatch"].error is not None
    assert actual["readback_mismatch"].error.code is FormulaErrorCode.READBACK_MISMATCH
    assert actual["unknown_commit"].error is not None
    assert actual["unknown_commit"].error.code is FormulaErrorCode.UNCERTAIN_MUTATION


def test_grid_recovery_simulations_redact_raw_expression_markers() -> None:
    for scenario in GRID_FAILURE_SCENARIOS:
        result = simulate_grid_failure(scenario)
        safe_text = repr(result)
        assert scenario.raw_expression not in safe_text
        if result.error is not None:
            assert scenario.raw_expression not in result.error.message
            assert scenario.raw_expression not in repr(result.error.safe_details)


def test_grid_failure_scenarios_expose_provider_safe_diagnostics_only() -> None:
    for scenario in GRID_FAILURE_SCENARIOS:
        result = simulate_grid_failure(scenario)

        assert result.error is not None
        assert result.error.message == scenario.safe_message
        assert set(result.error.safe_details) <= {"status", "target_kind", "revision_hash"}
