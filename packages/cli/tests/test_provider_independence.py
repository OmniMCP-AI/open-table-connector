from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from open_table_connector.cli.plugins import _descriptor_entries
from open_table_connector.cli.registry import build_default_registry

from scripts.check_canonical_literals import check_canonical_literals

ROOT = Path(__file__).resolve().parents[3]
URL_POLICY_CHECKER = ROOT / "scripts/check_url_literals.py"


def test_cli_discovers_provider_owned_descriptors_without_activation() -> None:
    registry = build_default_registry(env={})
    names = {descriptor.name for descriptor in registry.list()}
    assert {"local_files", "google_sheets", "feishu_bitable", "maybe_sheet"} <= names


def test_cli_entrypoints_are_provider_owned() -> None:
    entries = {entry.name: entry.value for entry in _descriptor_entries()}
    assert entries["google_sheets"].startswith("open_table_connector.google_sheets.")
    assert entries["feishu_bitable"].startswith("open_table_connector.feishu_bitable.")
    assert entries["maybe_sheet"].startswith("open_table_connector.maybe_sheet.")
    assert entries["local_files"].startswith("open_table_connector.local_files.")


def test_production_python_reuses_canonical_provider_and_route_constants() -> None:
    assert check_canonical_literals(ROOT) == []


def test_url_literal_checker_rejects_csv_in_any_composite_scheme_position(
    tmp_path: Path,
) -> None:
    direct = "csv" + "://"
    composites = ("foo+csv", "csv+foo", "foo+csv+bar")
    (tmp_path / "README.md").write_text(f"use {direct} for data\n", encoding="utf-8")
    (tmp_path / "composite.md").write_text(
        "".join(f"reject {scheme}://snapshots/orders\n" for scheme in composites),
        encoding="utf-8",
    )
    (tmp_path / "managed.md").write_text(
        "managed+csv://snapshots/orders\nmanaged+xlsx://snapshots/orders\n",
        encoding="utf-8",
    )
    forbidden = ", ".join(f"{scheme}://" for scheme in ("csv", "excel", "xlsx"))
    (tmp_path / "AGENTS.md").write_text(
        "Project URL policy: local tabular/workbook files use canonical file:// URLs; "
        f"do not introduce {forbidden}, or {'maybe' + '://'} public routes. "
        "MaybeSheet uses canonical HTTPS document URLs.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(URL_POLICY_CHECKER), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "README.md:1: forbidden public URL scheme: csv",
        "composite.md:1: forbidden public URL scheme: csv",
        "composite.md:2: forbidden public URL scheme: csv",
        "composite.md:3: forbidden public URL scheme: csv",
    ]


def test_repository_has_no_forbidden_public_url_literals() -> None:
    result = subprocess.run(
        [sys.executable, str(URL_POLICY_CHECKER)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
