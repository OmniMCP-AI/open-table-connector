from __future__ import annotations

import os
from pathlib import Path

import pyarrow as pa
import pytest

from open_table_connector.process import ArtifactStore
from open_table_connector.timeseries import ResourceBounds, TemporalExtensionError


def table() -> pa.Table:
    return pa.table({"symbol": ["AAPL", "MSFT"], "price": [100.0, 200.0]})


def bounds(**changes) -> ResourceBounds:
    values = {"max_rows": 10, "max_bytes": 1_000_000, "max_duration_ms": 1000}
    values.update(changes)
    return ResourceBounds(**values)


def test_artifacts_are_atomic_content_addressed_arrow_streams(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    reference = store.put_arrow(table())

    assert reference.relative_path == f"sha256/{reference.sha256[7:]}.arrow"
    assert (tmp_path / reference.relative_path).stat().st_mode & 0o077 == 0
    assert store.get_arrow(reference, bounds()).equals(table())


def test_artifact_reads_detect_tampering_bounds_symlinks_and_permissions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ArtifactStore(tmp_path)
    reference = store.put_arrow(table())
    path = tmp_path / reference.relative_path

    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(TemporalExtensionError, match="artifact"):
        store.get_arrow(reference, bounds())

    reference = store.put_arrow(table())
    with pytest.raises(TemporalExtensionError, match="max_bytes"):
        store.get_arrow(reference, bounds(max_bytes=8))
    with pytest.raises(TemporalExtensionError, match="max_rows"):
        store.get_arrow(reference, bounds(max_rows=1))

    metadata = (tmp_path / reference.relative_path).stat()
    monkeypatch.setattr(
        "open_table_connector.process.artifacts.os.getuid",
        lambda: metadata.st_uid + 1,
    )
    with pytest.raises(PermissionError, match="ownership"):
        store.get_arrow(reference, bounds())
    monkeypatch.undo()

    path = tmp_path / reference.relative_path
    path.chmod(0o644)
    with pytest.raises(PermissionError, match="permissions"):
        store.get_arrow(reference, bounds())

    target = tmp_path / "target.arrow"
    target.write_bytes(b"target")
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(PermissionError, match="symlink"):
        store.get_arrow(reference, bounds())


def test_expired_artifacts_are_cleaned_without_following_symlinks(tmp_path: Path) -> None:
    now = [1000.0]
    store = ArtifactStore(tmp_path, ttl_seconds=10, clock=lambda: now[0])
    reference = store.put_arrow(table())
    path = tmp_path / reference.relative_path
    os.utime(path, (980, 980))

    assert store.cleanup_expired() == 1
    assert not path.exists()
