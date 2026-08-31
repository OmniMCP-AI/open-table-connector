"""Placeholder workload namespace for bounded CLI measurements."""

from .run import run_benchmark


def run(rows: int = 10_000, repetitions: int = 3):
    return run_benchmark("cli-streaming", rows=rows, repetitions=repetitions)
