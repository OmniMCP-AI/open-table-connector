"""Entry point for temporal evaluator benchmark workloads."""

from .run import run_benchmark


def run(rows: int = 10_000, repetitions: int = 3):
    return run_benchmark("temporal-fixed", rows=rows, repetitions=repetitions)
