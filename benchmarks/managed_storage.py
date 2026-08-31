"""Placeholder workload namespace for managed-storage measurements."""

from .run import run_benchmark


def run(rows: int = 10_000, repetitions: int = 3):
    return run_benchmark("managed-storage", rows=rows, repetitions=repetitions)
