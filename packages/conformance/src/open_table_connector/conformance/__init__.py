"""Reusable Connector conformance helpers."""

from .assertions import (
    assert_arrow_polars_equal,
    assert_read_connector_conformance,
    assert_receipt_safe,
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
    "assert_framework_import_free",
    "assert_read_connector_conformance",
    "assert_receipt_safe",
    "assert_managed_lifecycle",
    "assert_temporal_semantics",
    "ManagedLifecycleCase",
    "ManagedLifecycleResult",
    "run_read_suite",
    "TemporalSemanticCase",
    "load_temporal_cases",
]
