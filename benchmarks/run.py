"""Small benchmark runner that records raw samples and its environment."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median

import polars as pl
import pyarrow as pa

from .datasets import temporal_table


@dataclass(frozen=True)
class BenchmarkEnvironment:
    python: str
    pyarrow: str
    polars: str
    platform: str
    cpu: str
    commit: str
    dirty: bool


@dataclass(frozen=True)
class BenchmarkResult:
    schema_version: str
    suite: str
    phase: str
    rows: int
    unique_timestamps: int
    repetitions: int
    warmups: int
    environment: BenchmarkEnvironment
    samples_ns: tuple[int, ...]
    peak_bytes: tuple[int, ...]
    median_ns: int
    minimum_ns: int


def _environment() -> BenchmarkEnvironment:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", True
    return BenchmarkEnvironment(
        python=platform.python_version(),
        pyarrow=pa.__version__,
        polars=pl.__version__,
        platform=platform.platform(),
        cpu=platform.processor() or platform.machine(),
        commit=commit,
        dirty=dirty,
    )


def run_benchmark(
    suite: str,
    *,
    phase: str = "before",
    repetitions: int = 3,
    rows: int = 10_000,
    unique_timestamps: int = 1_000,
    warmups: int = 1,
) -> BenchmarkResult:
    if repetitions < 1 or warmups < 0:
        raise ValueError("repetitions must be positive and warmups cannot be negative")
    table = temporal_table(rows, unique_timestamps)
    frame = pl.from_arrow(table)

    def workload() -> None:
        frame.group_by("entity").agg(pl.col("value").mean()).sort("entity")

    for _ in range(warmups):
        workload()
    samples: list[int] = []
    peaks: list[int] = []
    for _ in range(repetitions):
        tracemalloc.start()
        start = time.perf_counter_ns()
        workload()
        elapsed = time.perf_counter_ns() - start
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        samples.append(elapsed)
        peaks.append(peak)
    return BenchmarkResult(
        schema_version="1.0",
        suite=suite,
        phase=phase,
        rows=rows,
        unique_timestamps=unique_timestamps,
        repetitions=repetitions,
        warmups=warmups,
        environment=_environment(),
        samples_ns=tuple(samples),
        peak_bytes=tuple(peaks),
        median_ns=int(median(samples)),
        minimum_ns=min(samples),
    )


def write_result(path: Path, result: BenchmarkResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="temporal-fixed")
    parser.add_argument("--phase", default="before")
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--rows", type=int, default=10_000)
    args = parser.parse_args()
    output = Path("benchmarks/results") / f"{args.suite}-{args.phase}-{args.rows}.json"
    write_result(
        output,
        run_benchmark(
            args.suite,
            phase=args.phase,
            repetitions=args.repetitions,
            rows=args.rows,
        ),
    )
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
