from __future__ import annotations

import open_table_connector.formulas as otf
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


@pytest.mark.parametrize(
    ("case_kwargs", "set_capability", "reject_field_set"),
    [
        (
            {
                "static_capabilities": (otf.GRID_READ,),
                "broken": BrokenBehavior(reject_grid_set=True),
            },
            otf.GRID_SET,
            False,
        ),
        (
            {
                "static_capabilities": (otf.FIELD_READ,),
                "broken": BrokenBehavior(reject_field_set=True),
            },
            otf.FIELD_SET,
            True,
        ),
    ],
)
def test_security_probe_validates_advertised_set_before_calling_set(
    case_kwargs: dict[str, object],
    set_capability: object,
    reject_field_set: bool,
) -> None:
    factory = field_case_kwargs if reject_field_set else grid_case_kwargs
    case = FormulaProviderCase(**factory(**case_kwargs))

    with pytest.raises(ValueError, match=f"advertised {set_capability.to_reference()} capability"):
        assert_formula_security_safe(case)


@pytest.mark.parametrize(
    "channel",
    ["error", "warning", "log", "repr", "ledger", "operation_id", "result_repr", "value_repr"],
)
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
