from __future__ import annotations

from pathlib import Path

import pytest

from open_table_connector.contract import TableURI
from open_table_connector.local_files import ExcelTemporalExecutor
from open_table_connector.timeseries import (
    PolarsTemporalExecutor,
    TemporalExecutionRequest,
    TemporalExtensionError,
)

from packages.timeseries.tests.fixtures import MemoryTemporalSource, descriptor

from .excel_fixtures import formula_workbook, value_workbook
from .test_temporal_csv import operations


@pytest.mark.parametrize("plan", operations())
def test_direct_excel_matches_portable_arrow_evaluation(tmp_path: Path, plan) -> None:
    path = value_workbook(tmp_path / "ticks.xlsx")
    target = TableURI(f"xlsx://{path.as_posix()}#sheet=Ticks")
    request = TemporalExecutionRequest(
        target,
        plan,
        None,
        f"excel-{type(plan.operation).__name__}",
        None,
    )

    actual = ExcelTemporalExecutor(descriptor(), worksheet="Ticks").execute(request).table
    expected = PolarsTemporalExecutor(MemoryTemporalSource()).execute(request).table
    assert actual is not None and expected is not None
    assert actual.equals(expected)


def test_direct_excel_rejects_formula_in_governed_worksheet(tmp_path: Path) -> None:
    path = formula_workbook(tmp_path / "formula.xlsx")
    target = TableURI(f"xlsx://{path.as_posix()}#sheet=Ticks")
    request = TemporalExecutionRequest(target, operations()[0], None, "formula", None)

    with pytest.raises(TemporalExtensionError, match="formula"):
        ExcelTemporalExecutor(descriptor(), worksheet="Ticks").execute(request)


def test_excel_advertises_no_formula_calculation_or_evidence() -> None:
    capabilities = ExcelTemporalExecutor.CAPABILITIES
    assert not any("formula" in capability.casefold() for capability in capabilities)
    assert not any("pushdown" in capability.casefold() for capability in capabilities)
