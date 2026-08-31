from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
CHECKER = ROOT / "scripts/check_package_metadata.py"


def _checker_module() -> ModuleType:
    assert CHECKER.is_file(), "workspace package metadata checker is missing"
    spec = importlib.util.spec_from_file_location("check_package_metadata", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_package_metadata_is_complete() -> None:
    checker = _checker_module()

    assert checker.check_package_metadata(ROOT) == []


def test_hosted_packages_declare_imported_dependencies() -> None:
    checker = _checker_module()

    for package in ("google_sheets", "feishu_bitable"):
        metadata = checker.package_metadata(
            ROOT / f"packages/{package}/pyproject.toml"
        )
        assert set(metadata.dependencies) >= {
            "open-table-connector-contract",
            "polars",
            "pyarrow",
        }
