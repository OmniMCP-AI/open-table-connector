from __future__ import annotations

import json
from pathlib import Path

from benchmarks.datasets import temporal_table
from benchmarks.run import run_benchmark, write_result


def test_benchmark_result_records_reproducible_environment(tmp_path: Path) -> None:
    result = run_benchmark("temporal-fixed", repetitions=3, rows=10_000)
    path = tmp_path / "result.json"
    write_result(path, result)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == "1.0"
    assert document["environment"]["commit"]
    assert document["environment"]["python"]
    assert document["environment"]["pyarrow"]
    assert document["environment"]["polars"]
    assert len(document["samples_ns"]) == 3


def test_temporal_dataset_shape_is_deterministic() -> None:
    first = temporal_table(20, 4)
    second = temporal_table(20, 4)
    assert first.equals(second)
