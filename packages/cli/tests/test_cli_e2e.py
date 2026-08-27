import json
import os
import subprocess
import sys


def _run_module(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    if env is not None:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "open_connectors.cli", *args],
        capture_output=True,
        text=True,
        env=child_env,
    )


def test_parser_requires_explicit_from_and_to_for_import() -> None:
    result = _run_module("import", "--from", "rows.csv")

    assert result.returncode == 2
    assert "--to" in result.stderr


def test_otc_convert_csv_to_jsonl(tmp_path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id\na\n")

    result = subprocess.run(
        ["otc", "convert", "--from", str(source), "--to", "-", "--to-format", "jsonl"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout.splitlines()[0]) == {"id": "a"}


def test_module_and_alias_help_commands_exit_successfully() -> None:
    for command in (
        [sys.executable, "-m", "open_connectors.cli", "--help"],
        ["otc", "--help"],
        ["open-table-connector", "--help"],
        ["open-connectors", "--help"],
    ):
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, (command, result.stderr)
        assert "usage:" in result.stdout
