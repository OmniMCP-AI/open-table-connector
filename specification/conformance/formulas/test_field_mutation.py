from __future__ import annotations

import pytest

from open_table_connector.formulas import FormulaErrorCode

from .field_cases import (
    FIELD_FAILURE_SCENARIOS,
    field_fixture_metadata,
    simulate_field_failure,
)


def test_field_metadata_fixture_allows_only_expression_and_evidence_changes() -> None:
    for provider_id in ("maybe_sheet", "feishu_bitable"):
        before, after = field_fixture_metadata(provider_id)
        assert before["field_id"] == after["field_id"]
        assert before["field_name"] == after["field_name"]
        assert before["type"] == after["type"]
        assert before["result_type"] == after["result_type"]
        assert before["property"]["format"] == after["property"]["format"]
        assert before["property"]["formula_expression"] != after["property"]["formula_expression"]


def test_field_failure_corpus_covers_rejection_and_uncertain_commit_states() -> None:
    assert {scenario.name: scenario.error_code for scenario in FIELD_FAILURE_SCENARIOS} == {
        "timeout_before_dispatch": FormulaErrorCode.TIMEOUT,
        "provider_rejection": FormulaErrorCode.INVALID_FORMULA,
        "readback_mismatch": FormulaErrorCode.READBACK_MISMATCH,
        "lost_acknowledgement": FormulaErrorCode.UNCERTAIN_MUTATION,
        "unknown_commit": FormulaErrorCode.UNCERTAIN_MUTATION,
    }
    assert all(not scenario.retry for scenario in FIELD_FAILURE_SCENARIOS)


def test_field_failure_probes_keep_provider_expression_out_of_safe_surfaces() -> None:
    for scenario in FIELD_FAILURE_SCENARIOS:
        result = simulate_field_failure(scenario)
        assert scenario.raw_expression not in repr(result)
        assert result.error is not None
        assert scenario.raw_expression not in result.error.message
        assert scenario.raw_expression not in repr(result.error.safe_details)


@pytest.mark.parametrize("provider_id", ("maybe_sheet", "feishu_bitable"))
def test_field_metadata_fixture_rejects_unrelated_mutation(provider_id: str) -> None:
    before, after = field_fixture_metadata(provider_id)
    broken = dict(after)
    broken["result_type"] = "text"
    assert broken["result_type"] != before["result_type"]
