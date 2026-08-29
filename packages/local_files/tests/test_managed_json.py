from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_table_connector.local_files import JsonManagedTemporalStore
from open_table_connector.timeseries import (
    AbortDisposition,
    ManagedAbortRequest,
    ManagedReadbackRequest,
    ResourceBounds,
)

from packages.timeseries.tests.fixtures import descriptor

from .test_temporal_json import commit, stage, uri, write_direct


@pytest.mark.parametrize("format_name", ("json", "jsonl"))
def test_managed_json_lifecycle_is_deterministic_invisible_and_idempotent(
    tmp_path: Path,
    format_name: str,
) -> None:
    artifact_root = tmp_path / "artifacts"
    path = tmp_path / f"ticks.{format_name}"
    write_direct(path, format_name)
    target = uri(format_name, path)
    store = JsonManagedTemporalStore(format_name, artifact_root, descriptor())
    staged = stage(store, artifact_root, target)
    layout = path.with_name(path.name + ".otc")
    assert staged.visible is False
    assert not (layout / "current.json").exists()

    committed = commit(store, staged)
    assert commit(store, staged, operation_id="commit-retry") == committed
    snapshot = layout / committed.snapshot_reference
    text = snapshot.read_text(encoding="utf-8")
    if format_name == "json":
        assert text.startswith("[{") and text.endswith("}]")
        assert "\n" not in text
    else:
        assert text.endswith("\n")
        assert all(line.startswith("{") for line in text.splitlines())

    readback = store.readback(
        ManagedReadbackRequest(
            "readback-1",
            target,
            committed.snapshot_id,
            committed.snapshot_reference,
            ResourceBounds(100, 10_000_000, 1000),
        )
    )
    assert readback.table is not None
    assert readback.receipt.observed_rows == 7
    aborted = store.abort(ManagedAbortRequest("abort-1", target, staged.stage_id))
    assert aborted.disposition is AbortDisposition.ALREADY_COMMITTED


@pytest.mark.parametrize("format_name", ("json", "jsonl"))
def test_pointer_crash_recovery_reuses_shared_snapshot_primitive(
    tmp_path: Path,
    format_name: str,
) -> None:
    artifact_root = tmp_path / "artifacts"
    path = tmp_path / f"ticks.{format_name}"
    write_direct(path, format_name)
    target = uri(format_name, path)

    def fail(event):
        if event == "after_pointer_replace":
            raise RuntimeError("crash")

    crashing = JsonManagedTemporalStore(
        format_name,
        artifact_root,
        descriptor(),
        fault_injector=fail,
    )
    staged = stage(crashing, artifact_root, target)
    with pytest.raises(RuntimeError, match="crash"):
        commit(crashing, staged)
    pointer = json.loads((path.with_name(path.name + ".otc") / "current.json").read_text())

    recovered = JsonManagedTemporalStore(format_name, artifact_root, descriptor())
    receipt = commit(recovered, staged, operation_id="reconciled")
    assert receipt.snapshot_reference == pointer["snapshot_reference"]


def test_json_managed_namespace_rejects_symlinks(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    path = tmp_path / "ticks.json"
    write_direct(path, "json")
    layout = path.with_name(path.name + ".otc")
    outside = tmp_path / "outside"
    outside.mkdir()
    layout.symlink_to(outside, target_is_directory=True)
    store = JsonManagedTemporalStore("json", artifact_root, descriptor())
    with pytest.raises(PermissionError, match="symlink"):
        stage(store, artifact_root, uri("json", path))
