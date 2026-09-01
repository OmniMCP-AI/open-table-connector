from __future__ import annotations

from copy import deepcopy

import pytest
from open_table_connector.conformance.formulas import (
    FormulaProviderCase,
    assert_formula_security_safe,
)
from open_table_connector.formulas import FormulaErrorCode

from .field_cases import (
    FIELD_FAILURE_SCENARIOS,
    assert_field_metadata_isolated,
    field_fixture_metadata,
    simulate_field_failure,
)
from .support import BrokenBehavior, field_case_kwargs


def test_field_metadata_fixture_allows_only_expression_and_evidence_changes() -> None:
    for provider_id in ("maybe_sheet", "feishu_bitable"):
        before, after = field_fixture_metadata(provider_id)
        assert before["field_id"] == after["field_id"]
        assert before["field_name"] == after["field_name"]
        assert before["type"] == after["type"]
        assert before["result_type"] == after["result_type"]
        assert before["property"]["format"] == after["property"]["format"]
        assert before["property"]["formula_expression"] != after["property"]["formula_expression"]
        assert_field_metadata_isolated(before, after)


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
@pytest.mark.parametrize(
    "path",
    [
        ("field_id",),
        ("field_name",),
        ("type",),
        ("result_type",),
        ("property", "format"),
        ("property", "precision"),
        ("unrelated_properties", "description"),
    ],
)
def test_field_metadata_fixture_rejects_unrelated_mutation(
    provider_id: str,
    path: tuple[str, ...],
) -> None:
    before, after = field_fixture_metadata(provider_id)
    broken = deepcopy(after)
    current = broken
    for segment in path[:-1]:
        current = current[segment]
    current[path[-1]] = "changed"

    with pytest.raises(AssertionError, match="disallowed field metadata mutation"):
        assert_field_metadata_isolated(before, broken)


@pytest.mark.parametrize(
    "channel",
    ["result_repr", "error", "error_details", "warning", "log", "repr", "operation_id", "ledger"],
)
def test_field_security_probe_rejects_marker_leaks_in_every_safe_surface(channel: str) -> None:
    case = FormulaProviderCase(
        **field_case_kwargs(broken=BrokenBehavior(security_leak_channel=channel))
    )

    with pytest.raises(AssertionError):
        assert_formula_security_safe(case)


def test_field_security_probe_rejects_marker_leaks_in_receipts() -> None:
    case = FormulaProviderCase(
        **field_case_kwargs(broken=BrokenBehavior(receipt_leak=True))
    )

    with pytest.raises(AssertionError, match="receipt|marker|expression"):
        assert_formula_security_safe(case)
