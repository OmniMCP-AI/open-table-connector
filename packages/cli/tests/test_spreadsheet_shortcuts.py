from __future__ import annotations

import json
from argparse import Namespace

import pytest
from open_table_connector.cli.spreadsheet_shortcuts import compile_shortcut
from open_table_connector.contract import OperationRequest


def _args(action: str, **overrides):
    values = {
        "action": action,
        "uri": "file:///tmp/report.xlsx",
        "sheet": "Report",
        "range": "A1:B2",
        "bold": None,
        "italic": None,
        "no_bold": False,
        "no_italic": False,
        "pattern": None,
        "values_file": None,
        "values": None,
        "worksheet_action": None,
        "name": None,
        "expected_revision": None,
    }
    values.update(overrides)
    return Namespace(**values)


@pytest.mark.parametrize(
    ("action", "changes"),
    [("style", {"bold": True}), ("format", {"pattern": "#,##0.00"}), ("write", {"values": [[None, False], [0, "00123"]]} )],
)
def test_shortcut_equals_generic_operation(tmp_path, action, changes):
    if action == "write":
        path = tmp_path / "values.json"
        path.write_text(json.dumps(changes["values"]))
        args = _args(action, values_file=str(path))
    else:
        args = _args(action, **changes)
    request = compile_shortcut(args)
    assert isinstance(request, OperationRequest)
    assert request.namespace == "spreadsheet"
    assert request.target.sheet == "Report"


def test_omitted_bold_differs_from_no_bold():
    omitted = compile_shortcut(_args("style"))
    disabled = compile_shortcut(_args("style", no_bold=True))
    assert "bold" not in omitted.arguments
    assert disabled.arguments["bold"] is False


def test_values_stay_literal_and_typed(tmp_path):
    path = tmp_path / "values.json"
    path.write_text(json.dumps([[None, False, 0, "", "00123", "=SUM(A1:A2)"]]))
    request = compile_shortcut(_args("write", range="A1:F1", values_file=str(path)))
    assert [list(row) for row in request.arguments["values"]] == [[None, False, 0, "", "00123", "=SUM(A1:A2)"]]


def test_conflicting_boolean_flags_reject():
    with pytest.raises(ValueError, match="conflicting"):
        compile_shortcut(_args("style", bold=True, no_bold=True))


def test_ragged_or_wrong_size_range_rejects_before_dispatch(tmp_path):
    path = tmp_path / "values.json"
    path.write_text("[[1], [2]]")
    with pytest.raises(ValueError, match="dimensions"):
        compile_shortcut(_args("write", values_file=str(path)))


def test_worksheet_delete_keeps_reference_guard():
    request = compile_shortcut(_args("worksheet", worksheet_action="delete"))
    assert request.operation_id == "worksheet.delete"
    assert request.target.sheet == "Report"
