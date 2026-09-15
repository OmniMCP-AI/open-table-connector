"""Recorded mbs 0.28.4 / contract 1.0 transport behavior."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from open_table_connector.contract import CapabilityIdentity, ConnectorError, ConnectorErrorCode
from open_table_connector.maybe_sheet.connector import MaybeSheetConnector
from open_table_connector.spreadsheets import SpreadsheetTarget
from open_table_connector.spreadsheets._operations import Change


def env(op, result):
    return dict(
        contract_version="1.0",
        ok=True,
        operation=op,
        target={},
        warnings=[],
        request_id="r",
        result=result,
        verification={"status": "unavailable"},
        trace=None,
    )


class Recording:
    def __init__(self, fail=None):
        self.calls = []
        self.mutations = []
        self.sheets = [
            {"gid": "1", "name": "Report", "data_engine": "sheet"},
            {"gid": "2", "name": "Base", "data_engine": "base"},
        ]
        self.fail = fail

    def run(self, argv, **kwargs):
        argv = (argv[0], *argv[3:]) if argv[1:3] == ("--contract-version", "1.0") else argv
        self.calls.append(argv)
        op = ".".join(argv[1:3])
        if op == "worksheet.list":
            return env(op, {"worksheets": deepcopy(self.sheets)})
        if op == "range.read":
            return env(op, {"values": [[None, None]], "formulas": [["", ""]]})
        self.mutations.append(argv)
        if len(self.mutations) == self.fail:
            raise ConnectorError(ConnectorErrorCode.TIMEOUT, "timed out", {})
        result = {}
        if op == "worksheet.create":
            result = {"gid": "3", "name": argv[argv.index("--name") + 1], "data_engine": "sheet"}
            self.sheets.append(result)
        if "--values" in argv:
            result["values"] = json.loads(Path(argv[argv.index("--values") + 1]).read_text())
        return env(op, result)


def change(op, sheet="Report", **args):
    return Change(op, CapabilityIdentity("spreadsheet.test", "1.0"), sheet, args)


def provider(process):
    p = MaybeSheetConnector(process).spreadsheet_provider()
    return p, p.bind(SpreadsheetTarget("https://www.maybe.ai/docs/spreadsheets/d/doc"))


def test_reject_atomic_batch_without_dispatch():
    process = Recording()
    p, b = provider(process)
    with pytest.raises(ConnectorError):
        p.commit(
            b,
            [
                change("range.write", address="A1", values=[["x"]]),
                change("range.style", address="A1", bold=True),
            ],
            allow_partial=False,
            expected_revision=None,
            idempotency_key=None,
        )
    assert not process.mutations


def test_preflight_mixed_base_and_bad_sheet_rejects_before_mutations():
    process = Recording()
    p, b = provider(process)
    for name in ("Base", "missing"):
        with pytest.raises(ConnectorError):
            p.preflight(b, [change("range.write", name, address="A1", values=[["x"]])])
    assert not process.mutations


@pytest.mark.parametrize("fail", [1, 2, 3])
def test_partial_retains_created_id_and_unknown_dispatch(fail):
    process = Recording(fail)
    p, b = provider(process)
    changes = [
        change("worksheet.create", "New"),
        change("range.write", "New", address="A1", values=[["=literal"]]),
        change("range.clear", "New", address="A2"),
    ]
    result = p.commit(b, changes, allow_partial=True, expected_revision=None, idempotency_key=None)
    assert result["commit"] == "unknown"
    assert result["value"]["unknown_operation"] == changes[fail - 1].operation_id
    assert len(result["receipts"]) == fail - 1
    if fail > 1:
        assert result["value"]["created_ids"]["New"] == "3"
    assert len(process.mutations) == fail


def test_literal_range_and_stale_binding():
    process = Recording()
    p, b = provider(process)
    result = p.commit(
        b,
        [change("range.write", address="A1:B1", values=[["=literal", None]])],
        allow_partial=True,
        expected_revision=None,
        idempotency_key=None,
    )
    assert result["receipts"][0]["result"]["values"] == [["=literal", None]]
    process.sheets[0]["gid"] = "99"
    with pytest.raises(ConnectorError):
        p.preflight(b, [change("range.clear", address="A1")])


def test_pending_observation_is_explicitly_rejected():
    p, b = provider(Recording())
    with pytest.raises(ConnectorError):
        p.observe(
            b,
            dict(
                operation="range.read",
                target_key="Report",
                address="A1",
                changes=(change("range.clear", address="A1"),),
            ),
        )


@pytest.mark.parametrize(
    "operation,arguments,expected",
    [
        ("worksheet.create", {}, ("worksheet", "create")),
        ("worksheet.rename", {"name": "Renamed"}, ("worksheet", "rename")),
        ("worksheet.delete", {}, ("worksheet", "delete")),
        ("worksheet.move", {"index": 1}, ("worksheet", "move")),
        ("range.clear", {"address": "A1"}, ("range", "clear")),
        ("range.style", {"address": "A1", "bold": True, "fill": "#FFFFFF"}, ("style", "format")),
        ("range.format", {"address": "A1", "kind": "text"}, ("style", "format")),
        ("range.merge", {"address": "A1:B1"}, ("range", "merge")),
        ("range.unmerge", {"address": "A1:B1"}, ("range", "unmerge")),
        ("row.height", {"row": 1, "height_points": 24}, ("style", "rows-height")),
        ("column.width", {"column": "A", "width_pixels": 150}, ("column", "width")),
        ("formula.set", {"address": "A1", "expression": "=1+2"}, ("formula", "set")),
        (
            "image.insert",
            {"anchor": "A1", "mime_type": "image/png", "content": b"png"},
            ("image", "insert"),
        ),
        ("image.delete", {"picture_id": "image1"}, ("image", "delete")),
    ],
)
def test_recorded_command_surfaces(operation, arguments, expected):
    process = Recording()
    p, b = provider(process)
    result = p.commit(
        b,
        [change(operation, "New" if operation == "worksheet.create" else "Report", **arguments)],
        allow_partial=True,
        expected_revision=None,
        idempotency_key=None,
    )
    assert result["commit"] == "committed"
    assert process.mutations[-1][1:3] == expected


def test_create_is_buffered_and_retains_workbook_id():
    class CreateRecording(Recording):
        def run(self, argv, **kwargs):
            if "workbook" in argv and "create" in argv:
                self.calls.append(argv)
                return {
                    "success": True,
                    "endpoint": "/api/v1/excel/create",
                    "result": {"success": True, "spreadsheet_id": "created-doc"},
                    "target": {},
                }
            return super().run(argv, **kwargs)

    process = CreateRecording()
    p, b = provider(process)
    b["new"] = True
    assert process.calls == []
    p.preflight(b, [])
    assert process.calls == []
    result = p.commit(b, [], allow_partial=False, expected_revision=None, idempotency_key=None)
    assert result["commit"] == "committed"
    assert result["value"]["created_ids"]["workbook"] == "created-doc"
    assert b["uri"] == "https://www.maybe.ai/docs/spreadsheets/d/created-doc"


def test_stable_sort_requires_partial_and_preserves_ties_blanks_header():
    class SortRecording(Recording):
        def run(self, argv, **kwargs):
            if "range" in argv and "read" in argv:
                return env(
                    "range.read",
                    {
                        "formulas": [["", ""] for _ in range(5)],
                        "value_types": [["string", "string"] for _ in range(4)]
                        + [["blank", "string"]],
                        "values": [
                            ["k", "v"],
                            ["b", "one"],
                            ["a", "two"],
                            ["a", "three"],
                            [None, "four"],
                        ],
                    },
                )
            return super().run(argv, **kwargs)

    process = SortRecording()
    p, b = provider(process)
    c = change("range.sort", address="A1:B5", key_column=1, header=True)
    with pytest.raises(ConnectorError):
        p.commit(b, [c], allow_partial=False, expected_revision=None, idempotency_key=None)
    assert not process.mutations
    result = p.commit(b, [c], allow_partial=True, expected_revision=None, idempotency_key=None)
    assert result["receipts"][0]["result"]["values"] == [
        ["k", "v"],
        ["a", "two"],
        ["a", "three"],
        ["b", "one"],
        [None, "four"],
    ]


def test_actual_contract_null_verification_and_style_context():
    class Actual(Recording):
        def run(self, argv, **kwargs):
            if "style" in argv:
                return dict(
                    success=True,
                    endpoint="/api/v1/excel/batch_set_cell_style",
                    result={"success": True},
                    target={},
                    context={"source_command": "style.format"},
                )
            payload = super().run(argv, **kwargs)
            payload["verification"] = None
            return payload

    p, b = provider(Actual())
    assert (
        p.commit(
            b,
            [change("range.style", address="A1", bold=True)],
            allow_partial=True,
            expected_revision=None,
            idempotency_key=None,
        )["commit"]
        == "committed"
    )


@pytest.mark.parametrize("value", [1, 1.5, True, ""])
def test_reject_known_raw_type_loss_before_dispatch(value):
    process = Recording()
    p, b = provider(process)
    with pytest.raises(ConnectorError):
        p.commit(
            b,
            [change("range.write", address="A1", values=[[value]])],
            allow_partial=True,
            expected_revision=None,
            idempotency_key=None,
        )
    assert process.mutations == []


def test_live_disposable_sheet_contract():
    """Opt-in remote gate; owns and marks its disposable workbook deleted."""
    import base64
    import os
    import shutil
    import struct
    import uuid
    import zlib

    from open_table_connector.maybe_sheet.process import SubprocessProcessClient
    from open_table_connector.maybe_sheet.spreadsheet import MaybeSpreadsheetProvider

    if os.environ.get("OTC_TEST_MBS_ENABLED") != "1" or not os.environ.get("MAYBEAI_API_TOKEN"):
        pytest.skip("OTC_TEST_MBS_ENABLED=1 and MAYBEAI_API_TOKEN are required")
    process = SubprocessProcessClient(binary=shutil.which("mbs"))
    credentials = {"access_token": os.environ["MAYBEAI_API_TOKEN"]}
    p = MaybeSpreadsheetProvider(MaybeSheetConnector(process), credentials)
    b = p.bind(SpreadsheetTarget("https://www.maybe.ai/docs/spreadsheets/d/otc-disposable-" + uuid.uuid4().hex))
    b["new"] = True

    def commit(op, name="Report", **arguments):
        result = p.commit(
            b,
            [change(op, name, **arguments)],
            allow_partial=True,
            expected_revision=None,
            idempotency_key=None,
        )
        print("live", op, result["commit"], flush=True)
        assert result["commit"] == "committed", (op, result["value"])
        return result

    created = p.commit(b, [], allow_partial=False, expected_revision=None, idempotency_key=None)
    assert created["commit"] == "committed", created
    uri = "https://www.maybe.ai/docs/spreadsheets/d/" + created["value"]["created_ids"]["workbook"]
    try:
        commit("worksheet.create")
        commit(
            "range.write",
            address="A1:B4",
            values=[["Key", "Value"], ["b", "one"], ["a", "two"], ["a", "three"]],
        )
        commit("range.style", address="A1:B1", bold=True)
        commit("range.sort", address="A1:B4", key_column=1, header=True)
        observed = p.observe(
            b, {"operation": "range.read", "target_key": "Report", "address": "A1:B4"}
        )["value"]
        assert observed["values"] == [["Key", "Value"], ["a", "two"], ["a", "three"], ["b", "one"]]
        commit("formula.set", address="C2", expression="=1+2")
        observed = p.observe(
            b, {"operation": "range.read", "target_key": "Report", "address": "C2:C2"}
        )["value"]
        assert observed["formulas"] == [["=1+2"]]
        commit("row.height", row=1, height_points=24)
        commit("column.width", column="A", width_pixels=150)
        commit("range.merge", address="D1:E1")
        commit("range.unmerge", address="D1:E1")
        commit("range.clear", address="A4")

        def chunk(kind, data):
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            )

        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\0\xff\0" * 2))
            + chunk(b"IEND", b"")
        )
        commit("image.insert", anchor="G1", mime_type="image/png", content=png)
        pictures = p.observe(b, {"operation": "image.list", "target_key": "Report"})["value"][
            "pictures"
        ]
        picture_id = pictures[0]["id"]
        observed = p.observe(
            b, {"operation": "image.read", "target_key": "Report", "picture_id": picture_id}
        )["value"]
        assert base64.b64encode(png).decode() in json.dumps(observed)
        commit("image.delete", picture_id=picture_id)
        commit("worksheet.create", "Other")
        result = p.commit(
            b,
            [change("worksheet.rename", "Other", name="Renamed")],
            allow_partial=True,
            expected_revision=None,
            idempotency_key=None,
        )
        assert result["commit"] == "committed"
        commit("worksheet.move", "Renamed", index=0)
        commit("worksheet.delete", "Renamed")
        process.run(
            (
                "mbs",
                "--contract-version",
                "1.0",
                "worksheet",
                "create",
                "--uri",
                uri,
                "--name",
                "BaseSibling",
                "--engine",
                "base",
                "--output",
                "json",
            ),
            credentials=credentials,
        )
        b = p.bind(SpreadsheetTarget(b["uri"]))
        with pytest.raises(ConnectorError):
            p.preflight(b, [change("range.clear", "BaseSibling", address="A1")])
        commit("range.write", address="F2", values=[["=literal"]])
        sheets = p.observe(b, {"operation": "worksheet.list"})["value"]["worksheets"]
        assert next(s for s in sheets if s["name"] == "BaseSibling")["engine"] == "base"
    except Exception as exc:
        pytest.fail(f"Live contract failed: {type(exc).__name__}: {exc}", pytrace=False)
    finally:
        try:
            process.run(
                (
                    "mbs",
                    "--contract-version",
                    "1.0",
                    "workbook",
                    "delete",
                    "--uri",
                    uri,
                    "--yes",
                    "--output",
                    "json",
                ),
                credentials=credentials,
            )
        except ConnectorError:
            pytest.fail("Live disposable workbook cleanup failed", pytrace=False)


def test_dimension_configuration_expands_before_atomic_boundary_check():
    process = Recording()
    p, b = provider(process)
    c = change("worksheet.config", row_heights={1: 24}, column_widths_pixels={"A": 150})
    with pytest.raises(ConnectorError):
        p.commit(b, [c], allow_partial=False, expected_revision=None, idempotency_key=None)
    assert not process.mutations
    r = p.commit(b, [c], allow_partial=True, expected_revision=None, idempotency_key=None)
    assert r["commit"] == "committed"
    assert len(process.mutations) == 2
    assert process.mutations[0][process.mutations[0].index("--height") + 1] == "32px"
    with pytest.raises(ConnectorError):
        p.preflight(b, [change("worksheet.config", column_widths={"A": 20})])


def test_actual_recorded_creation_url_retains_gid():
    recordings = json.loads(
        (Path(__file__).parent / "fixtures" / "spreadsheet-mbs-0.28.4.json").read_text()
    )

    class Actual:
        def run(self, argv, **kwargs):
            return deepcopy(
                recordings["worksheet.create" if "create" in argv else "worksheet.list"]
            )

    p = MaybeSheetConnector(Actual()).spreadsheet_provider()
    b = p.bind(SpreadsheetTarget("https://www.maybe.ai/docs/spreadsheets/d/fixture-document"))
    r = p.commit(
        b,
        [change("worksheet.create", "New")],
        allow_partial=False,
        expected_revision=None,
        idempotency_key=None,
    )
    assert r["commit"] == "committed"
    assert r["value"]["created_ids"]["New"] == "1"


@pytest.mark.parametrize("missing", ["formulas", "value_types"])
def test_sort_missing_cell_evidence_never_writes(missing):
    class Incomplete(Recording):
        def run(self, argv, **kwargs):
            if "range" in argv and "read" in argv:
                result = {
                    "values": [["b"], ["a"]],
                    "formulas": [[""], [""]],
                    "value_types": [["string"], ["string"]],
                }
                result.pop(missing)
                return env("range.read", result)
            return super().run(argv, **kwargs)

    process = Incomplete()
    p, b = provider(process)
    result = p.commit(
        b,
        [change("range.sort", address="A1:A2")],
        allow_partial=True,
        expected_revision=None,
        idempotency_key=None,
    )
    assert result["commit"] == "not_committed"
    assert process.mutations == []


def test_merge_rejects_formula_with_empty_display_before_write():
    class FormulaInterior(Recording):
        def run(self, argv, **kwargs):
            if "range" in argv and "read" in argv:
                return env("range.read", {"values": [["top", ""]], "formulas": [["", '=""']]})
            return super().run(argv, **kwargs)

    process = FormulaInterior()
    p, b = provider(process)
    r = p.commit(
        b,
        [change("range.merge", address="A1:B1")],
        allow_partial=True,
        expected_revision=None,
        idempotency_key=None,
    )
    assert r["commit"] == "not_committed"
    assert process.mutations == []


def test_live_typed_raw_range_contract(tmp_path):
    """Deployment gate for the upstream fix, independent of OTC's rejection guard."""
    import os
    import shutil
    import uuid

    from open_table_connector.maybe_sheet.process import SubprocessProcessClient
    from open_table_connector.maybe_sheet.spreadsheet import MaybeSpreadsheetProvider

    if os.environ.get("OTC_TEST_MBS_TYPED_RAW_ENABLED") != "1" or not os.environ.get(
        "MAYBEAI_API_TOKEN"
    ):
        pytest.skip("typed RAW deployment gate is opt-in")
    process = SubprocessProcessClient(binary=shutil.which("mbs"))
    provider = MaybeSpreadsheetProvider(
        MaybeSheetConnector(process), {"access_token": os.environ["MAYBEAI_API_TOKEN"]}
    )
    bound = provider.bind(SpreadsheetTarget("https://www.maybe.ai/docs/spreadsheets/d/otc-typed-" + uuid.uuid4().hex))
    bound["new"] = True
    created = provider.commit(
        bound, [], allow_partial=False, expected_revision=None, idempotency_key=None
    )
    uri = "https://www.maybe.ai/docs/spreadsheets/d/" + created["value"]["created_ids"]["workbook"]
    (tmp_path / "owned-workbook.json").write_text(json.dumps({"uri": uri}))
    try:
        provider.commit(
            bound,
            [change("worksheet.create", "Report")],
            allow_partial=True,
            expected_revision=None,
            idempotency_key=None,
        )
        values = tmp_path / "values.json"
        values.write_text(json.dumps([[2, 2.5, True, False, "", None, "001", "=1+2"]]))
        provider._call(
            (
                "mbs",
                "range",
                "write",
                "--uri",
                uri,
                "--worksheet-name",
                "Report",
                "--range",
                "A1:H1",
                "--values",
                str(values),
            ),
            "range.write",
        )
        observed = provider.observe(
            bound, {"operation": "range.read", "target_key": "Report", "address": "A1:H1"}
        )["value"]
        assert observed["value_types"] == [
            ["number", "number", "boolean", "boolean", "string", "blank", "string", "string"]
        ]
        assert observed["values"][0][4:] == ["", "", "001", "=1+2"]
        assert observed["formulas"] == [[""] * 8]
    except Exception as exc:
        pytest.fail(f"Typed RAW deployment gate failed: {type(exc).__name__}", pytrace=False)
    finally:
        try:
            process.run(
                (
                    "mbs",
                    "workbook",
                    "delete",
                    "--uri",
                    uri,
                    "--mode",
                    "mark",
                    "--yes",
                    "--output",
                    "json",
                ),
                credentials={"access_token": os.environ["MAYBEAI_API_TOKEN"]},
            )
        except Exception:
            pytest.fail(f"Typed RAW disposable workbook cleanup failed: {uri}", pytrace=False)
