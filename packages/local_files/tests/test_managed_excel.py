from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from open_table_connector.contract import TableURI
from open_table_connector.local_files import ExcelManagedTemporalStore, ExcelTemporalExecutor
from open_table_connector.timeseries import (
    ManagedAbortRequest,
    ManagedCommitRequest,
    ManagedReadbackRequest,
    ManagedStageRequest,
    ResourceBounds,
    TemporalExecutionRequest,
    TemporalExtensionError,
    temporal_descriptor_hash,
)

from packages.timeseries.tests.fixtures import descriptor, ticks_table

from .excel_fixtures import formula_workbook, value_workbook
from .managed_fixtures import put_artifact
from .test_temporal_csv import operations


def _uri(scheme: str, path: Path, sheet: str = "Ticks") -> TableURI:
    return TableURI(f"{scheme}://{path.as_posix()}#sheet={sheet}")


def _stage_request(root: Path, source: Path, logical: Path) -> ManagedStageRequest:
    table = ticks_table()
    return ManagedStageRequest(
        "excel-stage",
        put_artifact(root, table),
        temporal_descriptor_hash(descriptor(), table.schema),
        _uri("managed+xlsx", logical),
        _uri("xlsx", source),
        "excel-idem",
        ResourceBounds(100, 10_000_000, 1_000),
    )


def test_managed_excel_publishes_immutable_formula_free_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    source = value_workbook(tmp_path / "source.xlsx")
    logical = tmp_path / "governed-ticks"
    observations: list[bool] = []

    def observe(event: str) -> None:
        pointer = logical.with_name(logical.name + ".otc") / "current.json"
        if event == "before_pointer_replace":
            observations.append(pointer.exists())
        elif event == "after_pointer_replace":
            assert pointer.exists()
        else:
            raise AssertionError(f"unexpected fault event: {event}")

    store = ExcelManagedTemporalStore(
        root,
        descriptor(),
        worksheet="Ticks",
        fault_injector=observe,
    )
    staged = store.stage(_stage_request(root, source, logical))
    committed = store.commit(
        ManagedCommitRequest(
            "excel-commit",
            staged.logical_target,
            staged.stage_id,
            staged.idempotency_key,
            ResourceBounds(100, 10_000_000, 1_000),
        )
    )
    source.unlink()
    readback = store.readback(
        ManagedReadbackRequest(
            "excel-readback",
            staged.logical_target,
            committed.snapshot_id,
            committed.snapshot_reference,
            ResourceBounds(100, 10_000_000, 1_000),
        )
    )

    assert observations == [False]
    assert readback.table is not None and readback.table.equals(ticks_table())
    assert committed.logical_target.value.endswith("#sheet=Ticks")
    snapshot_path = store.resolve_snapshot(staged.logical_target, committed.snapshot_reference)
    workbook = load_workbook(snapshot_path, data_only=False)
    try:
        assert all(cell.data_type != "f" for row in workbook["Ticks"] for cell in row)
    finally:
        workbook.close()

    result = ExcelTemporalExecutor(descriptor(), worksheet="Ticks", managed_store=store).execute(
        TemporalExecutionRequest(
            staged.logical_target,
            operations()[1],
            None,
            "excel-snapshot-query",
            committed.snapshot_reference,
        )
    )
    assert result.table is not None
    aborted = store.abort(ManagedAbortRequest("excel-abort", staged.logical_target, staged.stage_id))
    assert aborted.disposition.value == "already_committed"


def test_managed_excel_rejects_formula_before_creating_namespace(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    source = formula_workbook(tmp_path / "formula.xlsx")
    logical = tmp_path / "governed-ticks"
    store = ExcelManagedTemporalStore(root, descriptor(), worksheet="Ticks")

    with pytest.raises(TemporalExtensionError, match="formula"):
        store.stage(_stage_request(root, source, logical))

    assert not logical.with_name(logical.name + ".otc").exists()
