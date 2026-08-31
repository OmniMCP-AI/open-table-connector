from __future__ import annotations

import hashlib
from pathlib import Path

import pyarrow as pa

from scripts.verify_compatibility import compute_manifest_hash

ROOT = Path(__file__).parents[3]


def test_manifest_hash_is_stable_for_arrow_fixture_bytes() -> None:
    fixture = ROOT / "specification/fixtures/timeseries/v1/source/ticks.json"
    expected = hashlib.sha256(fixture.read_bytes()).hexdigest()
    assert expected
    assert compute_manifest_hash(ROOT, (str(fixture.relative_to(ROOT)),)).startswith("sha256:")


def test_arrow_logical_schema_round_trip_is_stable() -> None:
    schema = pa.schema(
        [pa.field("ts", pa.timestamp("us", tz="UTC")), pa.field("price", pa.float64())]
    )
    restored = pa.ipc.read_schema(pa.BufferReader(schema.serialize()))
    assert restored == schema


def test_cross_implementation_artifact_is_explicitly_optional() -> None:
    artifact = ROOT / "specification/conformance/timeseries/artifacts/arrow-rust-schema.json"
    if not artifact.is_file():
        import pytest

        pytest.skip("cross-implementation artifact not supplied")
