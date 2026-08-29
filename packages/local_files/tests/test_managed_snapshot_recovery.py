from __future__ import annotations

import json
from pathlib import Path
from threading import Barrier, Thread

import pytest

from open_table_connector.contract import TableURI
from open_table_connector.local_files import CsvManagedTemporalStore
from open_table_connector.timeseries import TemporalErrorCode, TemporalExtensionError

from packages.timeseries.tests.fixtures import descriptor

from .managed_fixtures import commit_request, managed_uri, stage_request


def test_crash_before_pointer_is_invisible_and_stale_temporary_is_cleaned(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    logical = tmp_path / "ticks"

    def fail(event):
        if event == "before_pointer_replace":
            raise RuntimeError("simulated crash")

    crashing = CsvManagedTemporalStore(artifact_root, descriptor(), fault_injector=fail)
    stage = crashing.stage(stage_request(artifact_root, logical))
    with pytest.raises(RuntimeError, match="simulated crash"):
        crashing.commit(commit_request(stage))

    layout = logical.with_name("ticks.otc")
    assert not (layout / "current.json").exists()
    assert list(layout.glob(".current.json.*.tmp"))

    recovered = CsvManagedTemporalStore(artifact_root, descriptor())
    recovered.recover(stage.logical_target)
    assert not list(layout.glob("*.tmp"))
    assert recovered.commit(commit_request(stage)).snapshot_reference.startswith("snapshots/")


def test_crash_after_pointer_reconciles_from_pointer_without_guessing(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    logical = tmp_path / "ticks"

    def fail(event):
        if event == "after_pointer_replace":
            raise RuntimeError("simulated crash")

    crashing = CsvManagedTemporalStore(artifact_root, descriptor(), fault_injector=fail)
    stage = crashing.stage(stage_request(artifact_root, logical))
    with pytest.raises(RuntimeError, match="simulated crash"):
        crashing.commit(commit_request(stage))
    pointer = json.loads((logical.with_name("ticks.otc") / "current.json").read_text())
    assert pointer["stage_id"] == stage.stage_id

    recovered = CsvManagedTemporalStore(artifact_root, descriptor())
    receipt = recovered.commit(commit_request(stage, operation_id="commit-reconciled"))
    assert receipt.snapshot_id == pointer["snapshot_id"]
    assert receipt.snapshot_reference == pointer["snapshot_reference"]


def test_concurrent_commits_are_serialized_to_one_closed_pointer(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    logical = tmp_path / "ticks"
    store = CsvManagedTemporalStore(artifact_root, descriptor())
    first = store.stage(stage_request(artifact_root, logical))
    second = store.stage(
        stage_request(artifact_root, logical, operation_id="stage-2", idempotency_key="idem-2")
    )
    barrier = Barrier(3)
    outcomes = []

    def commit(stage, operation_id):
        barrier.wait()
        outcomes.append(store.commit(commit_request(stage, operation_id=operation_id)))

    threads = [
        Thread(target=commit, args=(first, "commit-1")),
        Thread(target=commit, args=(second, "commit-2")),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    pointer = json.loads((logical.with_name("ticks.otc") / "current.json").read_text())
    assert len(outcomes) == 2
    assert pointer["snapshot_id"] in {item.snapshot_id for item in outcomes}
    assert set(pointer) == {
        "schema_version",
        "logical_target",
        "stage_id",
        "idempotency_key",
        "descriptor_hash",
        "snapshot_id",
        "snapshot_reference",
        "committed_at",
    }


def test_managed_targets_reject_traversal_and_symlink_namespaces(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    store = CsvManagedTemporalStore(artifact_root, descriptor())
    traversal = TableURI(f"managed+csv://{tmp_path}/safe/../escape")
    request = stage_request(artifact_root, tmp_path / "valid")
    with pytest.raises(TemporalExtensionError) as raised:
        store.stage(
            type(request)(
                request.operation_id,
                request.artifact,
                request.descriptor_hash,
                    traversal,
                    traversal,
                    request.idempotency_key,
                    request.resource_bounds,
                )
        )
    assert raised.value.code is TemporalErrorCode.PROTOCOL_INVALID

    logical = tmp_path / "linked"
    layout = logical.with_name("linked.otc")
    target = tmp_path / "outside"
    target.mkdir()
    layout.symlink_to(target, target_is_directory=True)
    with pytest.raises(PermissionError, match="symlink"):
        store.stage(stage_request(artifact_root, logical, operation_id="stage-link"))
