from __future__ import annotations

from dataclasses import fields, is_dataclass

import pytest
from open_table_connector.conformance.formulas import (
    FormulaProviderCase,
    assert_formula_receipt_safe,
    assert_grid_formula_conformance,
)

from specification.conformance.formulas.support import (
    SECURITY_MARKERS,
    BrokenBehavior,
    collect_security_probe,
    grid_case_kwargs,
)


def _assert_probe_is_clean(probe: object, markers: tuple[str, ...]) -> None:
    def walk(value: object, *, allow_formula_value: bool = False) -> None:
        if value is None:
            return
        if hasattr(value, "formula_observation"):
            walk(value.formula_observation, allow_formula_value=True)
            return
        if isinstance(value, str):
            if not allow_formula_value:
                assert all(marker not in value for marker in markers), value
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item, allow_formula_value=allow_formula_value)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item, allow_formula_value=allow_formula_value)
            return
        if is_dataclass(value):
            for field in fields(value):
                next_allow = allow_formula_value or field.name == "mutation"
                walk(getattr(value, field.name), allow_formula_value=next_allow)
            return
        if hasattr(value, "__dict__"):
            for item in value.__dict__.values():
                walk(item, allow_formula_value=allow_formula_value)

    walk(probe)


def test_formula_receipt_safety_accepts_hashed_receipts_only() -> None:
    probe = collect_security_probe()

    assert_formula_receipt_safe(probe.receipts, forbidden_texts=SECURITY_MARKERS)


@pytest.mark.parametrize("channel", ["warning", "log", "repr", "ledger", "operation_id"])
def test_security_probe_rejects_marker_leaks_outside_typed_observations(channel: str) -> None:
    probe = collect_security_probe(leak_channel=channel)

    with pytest.raises(AssertionError):
        _assert_probe_is_clean(probe, SECURITY_MARKERS)


def test_grid_formula_conformance_rejects_receipt_marker_leak() -> None:
    broken_case = FormulaProviderCase(**grid_case_kwargs(broken=BrokenBehavior(receipt_leak=True)))

    with pytest.raises(AssertionError, match="receipt|expression|marker"):
        assert_grid_formula_conformance(broken_case)
