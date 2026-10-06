from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from open_table_connector.contract import OperationRequest, TargetSelector


def test_missing_policy_fails_closed(tmp_path):
    from open_table_connector.mcp.policy import load_policy

    with pytest.raises(ValueError, match="policy"):
        load_policy(tmp_path / "missing.json")


def test_symlink_escape_rejected(tmp_path):
    from open_table_connector.mcp.policy import AccessPolicy, authorize

    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "link"
    link.symlink_to(outside, target_is_directory=True)
    request = OperationRequest("spreadsheet", "range.read", "1.0", TargetSelector((link / "book.xlsx").as_uri()), {"address": "A1"})
    with pytest.raises(PermissionError):
        authorize(request, AccessPolicy((root,), (), (), ()))


def test_remote_origin_exact_match():
    from open_table_connector.mcp.policy import AccessPolicy, authorize

    request = OperationRequest("spreadsheet", "range.read", "1.0", TargetSelector("https://www.maybe.ai/docs/spreadsheets/d/doc"), {"address": "A1"})
    authorize(request, AccessPolicy((), (), ("https://www.maybe.ai",), ()))
    with pytest.raises(PermissionError):
        authorize(request, AccessPolicy((), (), ("https://www.maybe.ai.evil",), ()))


def test_credentials_in_payload_rejected():
    from open_table_connector.mcp.policy import AccessPolicy, authorize

    request = OperationRequest("spreadsheet", "range.read", "1.0", TargetSelector("file:///tmp/book.xlsx"), {"token": "secret"})
    with pytest.raises(PermissionError, match="credential"):
        authorize(request, AccessPolicy((Path("/tmp"),), (), (), ()))


def test_nonexistent_output_parent_resolved(tmp_path):
    from open_table_connector.mcp.policy import AccessPolicy, authorize

    destination = tmp_path / "new" / "report.xlsx"
    request = OperationRequest(
        "artifact",
        "export",
        "1.0",
        TargetSelector((tmp_path / "source.xlsx").as_uri()),
        {"destination_uri": destination.as_uri()},
    )
    authorize(request, AccessPolicy((tmp_path,), (), (), ()))


def test_artifact_paths_and_assets_all_authorized(tmp_path):
    from open_table_connector.mcp.policy import AccessPolicy, authorize

    request = OperationRequest(
        "artifact",
        "export",
        "1.0",
        TargetSelector((tmp_path / "source.xlsx").as_uri()),
        {
            "destination_uri": (tmp_path / "out" / "report.docx").as_uri(),
            "assets": [{"path": "images/logo.png"}],
        },
    )
    authorize(request, AccessPolicy((tmp_path,), (), (), ()))

    request = OperationRequest(
        "artifact",
        "export",
        "1.0",
        TargetSelector((tmp_path / "source.xlsx").as_uri()),
        {"destination_uri": (tmp_path / "out.docx").as_uri(), "assets": [{"path": "../logo.png"}]},
    )
    with pytest.raises(PermissionError):
        authorize(request, AccessPolicy((tmp_path,), (), (), ()))


def test_optional_mcp_absent_core_import_succeeds():
    code = (
        "import builtins; "
        "real=builtins.__import__; "
        "builtins.__import__=lambda n,*a,**k: (_ for _ in ()).throw(ModuleNotFoundError(name=n)) "
        "if n == 'open_table_connector.mcp' or n.startswith('open_table_connector.mcp.') else real(n,*a,**k); "
        "from open_table_connector.sdk import Client; print(Client.__name__)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
