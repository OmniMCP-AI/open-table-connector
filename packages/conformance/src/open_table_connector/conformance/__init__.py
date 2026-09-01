"""Reusable Connector conformance helpers."""

from .assertions import (
    assert_arrow_polars_equal,
    assert_read_connector_conformance,
    assert_receipt_safe,
)
from .formulas import (
    FieldFormulaCase,
    FormulaProviderCase,
    GridFormulaCase,
    assert_field_formula_conformance,
    assert_formula_receipt_safe,
    assert_grid_formula_conformance,
    field_formula_case_params,
    grid_formula_case_params,
    load_formula_cases,
)
from .read_suite import run_read_suite
from .static_suite import assert_framework_import_free
from .timeseries import (
    ManagedLifecycleCase,
    ManagedLifecycleResult,
    TemporalSemanticCase,
    assert_managed_lifecycle,
    assert_temporal_semantics,
    load_temporal_cases,
)

__all__ = [
    "assert_arrow_polars_equal",
    "assert_field_formula_conformance",
    "assert_formula_receipt_safe",
    "assert_grid_formula_conformance",
    "assert_framework_import_free",
    "assert_read_connector_conformance",
    "assert_receipt_safe",
    "field_formula_case_params",
    "FieldFormulaCase",
    "FormulaProviderCase",
    "grid_formula_case_params",
    "GridFormulaCase",
    "assert_managed_lifecycle",
    "assert_temporal_semantics",
    "ManagedLifecycleCase",
    "ManagedLifecycleResult",
    "load_formula_cases",
    "run_read_suite",
    "TemporalSemanticCase",
    "load_temporal_cases",
]
