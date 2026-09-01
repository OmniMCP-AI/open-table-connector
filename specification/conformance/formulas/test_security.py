from __future__ import annotations

import pytest
from open_table_connector.conformance.formulas import (
    FormulaProviderCase,
    assert_formula_security_safe,
    assert_grid_formula_conformance,
)

from specification.conformance.formulas.support import (
    SECURITY_EXPRESSION,
    SECURITY_MARKERS,
    BrokenBehavior,
    field_case_kwargs,
    grid_case_kwargs,
)


def test_case_driven_security_probe_accepts_only_typed_observation_markers() -> None:
    probe = assert_formula_security_safe(FormulaProviderCase(**grid_case_kwargs()))

    assert probe.result.error is None
    assert probe.mutation is not None
    assert probe.mutation.formula_observation.formulas[0].expression == SECURITY_EXPRESSION
    assert probe.warnings == ()
    assert all(marker not in repr(probe.reprs) for marker in SECURITY_MARKERS)


def test_case_driven_security_probe_supports_field_cases() -> None:
    probe = assert_formula_security_safe(FormulaProviderCase(**field_case_kwargs()))

    assert probe.mutation is not None
    assert probe.mutation.formula_observation.expression.text == SECURITY_EXPRESSION.text


@pytest.mark.parametrize("channel", ["error", "warning", "log", "repr", "ledger", "operation_id"])
def test_security_probe_rejects_marker_leaks_outside_typed_observations(channel: str) -> None:
    case = FormulaProviderCase(
        **grid_case_kwargs(broken=BrokenBehavior(security_leak_channel=channel))
    )

    with pytest.raises(AssertionError):
        assert_formula_security_safe(case)


def test_grid_formula_conformance_rejects_receipt_marker_leak() -> None:
    broken_case = FormulaProviderCase(**grid_case_kwargs(broken=BrokenBehavior(receipt_leak=True)))

    with pytest.raises(AssertionError, match="receipt|expression|marker"):
        assert_grid_formula_conformance(broken_case)
