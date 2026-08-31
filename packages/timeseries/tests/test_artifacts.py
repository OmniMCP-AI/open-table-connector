from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest
from open_table_connector.timeseries import (
    ArrowArtifactReference,
    ResourceBounds,
    TemporalErrorCode,
    TemporalExtensionError,
    read_verified_artifact,
)


def _artifact(root: Path) -> ArrowArtifactReference:
    table = pa.table({"id": ["a", "b"]})
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    data = sink.getvalue().to_pybytes()
    import hashlib

    digest = hashlib.sha256(data).hexdigest()
    path = root / "sha256" / f"{digest}.arrow"
    path.parent.mkdir()
    path.write_bytes(data)
    return ArrowArtifactReference(f"sha256/{digest}.arrow", f"sha256:{digest}", len(data))


def test_verified_artifact_rejects_hash_mismatch(tmp_path: Path) -> None:
    reference = _artifact(tmp_path)
    bad = ArrowArtifactReference(
        reference.relative_path, "sha256:" + "0" * 64, reference.size_bytes
    )
    with pytest.raises(TemporalExtensionError) as raised:
        read_verified_artifact(bad, tmp_path, ResourceBounds(10, 1_000_000, 1_000))
    assert raised.value.code is TemporalErrorCode.SNAPSHOT_UNAVAILABLE


def test_verified_artifact_decodes_and_enforces_bounds(tmp_path: Path) -> None:
    reference = _artifact(tmp_path)
    result = read_verified_artifact(
        reference,
        tmp_path,
        ResourceBounds(2, 1_000_000, 1_000),
    )
    assert result.table.to_pylist() == [{"id": "a"}, {"id": "b"}]
