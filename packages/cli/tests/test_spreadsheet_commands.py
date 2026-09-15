import json

from open_table_connector.cli.__main__ import main


def test_spreadsheet_batch_dry_run_then_commit_and_read(tmp_path, capsys):
    destination = tmp_path / "report.xlsx"
    commands = tmp_path / "commands.json"
    commands.write_text(
        json.dumps(
            {
                "version": "1.0",
                "changes": [
                    {"operation_id": "worksheet.create", "target_key": "Report", "arguments": {}},
                    {
                        "operation_id": "range.write",
                        "target_key": "Report",
                        "arguments": {"address": "A1", "values": [["value"]]},
                    },
                ],
            }
        )
    )
    argv = [
        "spreadsheet",
        "batch",
        "--uri",
        destination.as_uri(),
        "--create",
        "--commands",
        str(commands),
    ]
    assert main([*argv, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["outcome"] == "planned"
    assert not destination.exists()
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["commit"] == "committed"
    assert (
        main(
            [
                "spreadsheet",
                "read",
                "--uri",
                destination.as_uri(),
                "--sheet",
                "Report",
                "--range",
                "A1",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["value"] == [["value"]]


def test_batch_rejects_unknown_keys_before_creating_file(tmp_path, capsys):
    destination = tmp_path / "report.xlsx"
    commands = tmp_path / "bad.json"
    commands.write_text(json.dumps({"version": "1.0", "changes": [], "ignored": True}))
    assert (
        main(
            [
                "spreadsheet",
                "batch",
                "--uri",
                destination.as_uri(),
                "--create",
                "--commands",
                str(commands),
            ]
        )
        != 0
    )
    assert not destination.exists()


def test_standalone_create_commits_and_verify_uses_retained_intent(tmp_path, capsys):
    destination = tmp_path / "report.xlsx"
    assert (
        main(
            [
                "spreadsheet",
                "operation",
                "--uri",
                destination.as_uri(),
                "--create",
                "--operation",
                "worksheet.create",
                "--sheet",
                "Report",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["commit"] == "committed"
    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps(payload["receipts"][0]["details"]["expected"]))
    assert (
        main(
            [
                "spreadsheet",
                "verify",
                "--uri",
                destination.as_uri(),
                "--profile",
                "literal-artifact/1.0",
                "--expected",
                str(expected),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["verification"] == "passed"
    assert (
        main(
            [
                "spreadsheet",
                "verify",
                "--uri",
                destination.as_uri(),
                "--profile",
                "literal-artifact/1.0",
            ]
        )
        == 5
    )
    assert json.loads(capsys.readouterr().err)["error"]["code"]
