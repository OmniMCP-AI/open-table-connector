from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


MINIMUM_UNIVERSAL_TESTS = 120
UNIVERSAL_DIR = Path(__file__).resolve().parent
COLLECT_COMMAND = (
    sys.executable,
    "-m",
    "pytest",
    str(UNIVERSAL_DIR),
    "--collect-only",
    "-q",
)


def parse_collected_count(output: str) -> int:
    """Parse the collected-test count from pytest's summary line."""
    match = re.search(r"(?m)^\s*(\d+)\s+tests?\s+collected\b", output)
    if match is None:
        raise AssertionError("pytest collection output did not contain a summary count")
    return int(match.group(1))


def test_universal_suite_has_minimum_collected_cases(
    sanitized_subprocess_env: dict[str, str],
) -> None:
    completed = subprocess.run(
        COLLECT_COMMAND,
        check=True,
        capture_output=True,
        text=True,
        env=sanitized_subprocess_env,
    )
    count = parse_collected_count(completed.stdout)
    command = " ".join(COLLECT_COMMAND)
    assert count >= MINIMUM_UNIVERSAL_TESTS, (
        f"command `{command}` collected {count}; "
        f"expected at least {MINIMUM_UNIVERSAL_TESTS}"
    )
