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
    token = "token-like-secret"
    result = _run_module("import", "--from", "rows.csv", "--token", token)

    assert result.returncode == 2
    assert len(result.stderr.splitlines()) == 1
    error = json.loads(result.stderr)
    assert error["code"] == "usage"
    assert "--to" in result.stderr
    assert token not in result.stderr


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


def test_read_defaults_to_jsonl_for_module_and_otc(tmp_path) -> None:
    source = tmp_path / "rows.csv"
    source.write_text("id\na\n")

    for command in (
        [sys.executable, "-m", "open_connectors.cli"],
        ["otc"],
    ):
        result = subprocess.run(
            [*command, "read", "--from", str(source)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (command, result.stderr)
        output = [json.loads(line) for line in result.stdout.splitlines()]
        assert output[0] == {"event": "row", "row": {"id": "a"}}
        assert output[1]["event"] == "summary"
        assert output[1]["rows"] == 1


def test_list_accepts_jsonl_output_format_without_endpoints() -> None:
    result = subprocess.run(
        ["otc", "list", "--output-format", "jsonl"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    output = [json.loads(line) for line in result.stdout.splitlines()]
    assert output
    assert all("connector_id" in connector for connector in output)


def test_parser_rejects_auto_output_format() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "open_connectors.cli", "list", "--output-format", "auto"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert len(result.stderr.splitlines()) == 1
    error = json.loads(result.stderr)
    assert error["code"] == "usage"
    assert "--output-format" in result.stderr
    assert "auto" in result.stderr


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
