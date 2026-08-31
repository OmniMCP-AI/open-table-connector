from __future__ import annotations

from pathlib import Path

from open_table_connector.cli.plugins import _descriptor_entries
from open_table_connector.cli.registry import build_default_registry

from scripts.check_canonical_literals import check_canonical_literals

ROOT = Path(__file__).resolve().parents[3]


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
