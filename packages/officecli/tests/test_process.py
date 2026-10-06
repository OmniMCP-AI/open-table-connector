from __future__ import annotations

import sys


def test_argv_metacharacters_never_shell():
    from open_table_connector.officecli.process import run_officecli

    result = run_officecli([sys.executable, "-c", "print('ok')"], input_json=None, timeout_seconds=2, max_output_bytes=100)
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"


def test_output_and_deadline_bounded():
    from open_table_connector.officecli.process import run_officecli

    result = run_officecli([sys.executable, "-c", "print('x'*1000)"], input_json=None, timeout_seconds=2, max_output_bytes=100)
    assert result.truncated is True
