"""Smoke-test workspace wheels as independently removable distributions."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

_PUBLIC_IMPORTS = {
    "open-table-connector-contract": "open_table_connector.contract",
    "open-table-connector-timeseries": "open_table_connector.timeseries",
    "open-table-connector-local-files": "open_table_connector.local_files",
    "open-table-connector-sqlite": "open_table_connector.sqlite",
    "open-table-connector-postgres": "open_table_connector.postgres",
    "open-table-connector-google-sheets": "open_table_connector.google_sheets",
    "open-table-connector-feishu-bitable": "open_table_connector.feishu_bitable",
    "open-table-connector-maybe-sheet": "open_table_connector.maybe_sheet",
    "open-table-connector-conformance": "open_table_connector.conformance",
    "open-table-connector-process": "open_table_connector.process",
    "open-table-connector-dbt": "open_table_connector.dbt",
    "open-table-connector": "open_table_connector.cli",
}
_PROVIDER_MODULES = (
    "open_table_connector.local_files",
    "open_table_connector.sqlite",
    "open_table_connector.postgres",
    "open_table_connector.google_sheets",
    "open_table_connector.feishu_bitable",
    "open_table_connector.maybe_sheet",
)
_DISTRIBUTION_MODULES = {
    "open-table-connector-local-files": "open_table_connector.local_files",
    "open-table-connector-sqlite": "open_table_connector.sqlite",
    "open-table-connector-postgres": "open_table_connector.postgres",
    "open-table-connector-google-sheets": "open_table_connector.google_sheets",
    "open-table-connector-feishu-bitable": "open_table_connector.feishu_bitable",
    "open-table-connector-maybe-sheet": "open_table_connector.maybe_sheet",
}


def _wheel_distribution(wheel: Path) -> str:
    return wheel.name.split("-", 1)[0].replace("_", "-")


def _wheel_import_check(wheel: Path, module: str) -> str | None:
    code = "import sys; sys.path.insert(0, sys.argv[1]); __import__(sys.argv[2])"
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(wheel), module],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return f"{wheel.name}: importing {module} failed: {result.stderr.strip()}"
    return None


def _uninstall_check(wheels: tuple[Path, ...], removed: str) -> str | None:
    remaining = [str(path) for path in wheels if _wheel_distribution(path) != removed]
    blocked = {_DISTRIBUTION_MODULES[removed]} if removed in _DISTRIBUTION_MODULES else set()
    code = (
        "import builtins,sys; "
        "sys.path[:0]=sys.argv[1:]; "
        f"blocked={blocked!r}; "
        "real=builtins.__import__; "
        "builtins.__import__=lambda n,*a,**k: (_ for _ in ()).throw(ModuleNotFoundError(name=n)) "
        "if any(n==x or n.startswith(x+'.') for x in blocked) else real(n,*a,**k); "
        "[__import__(m) for m in ("
        "'open_table_connector.contract','open_table_connector.timeseries',"
        "'open_table_connector.cli','open_table_connector.process')]"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, *remaining],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return f"after removing {removed}: core import failed: {result.stderr.strip()}"
    return None


def check_independence(root: Path, dist: Path, *, build: bool = False) -> list[str]:
    if build:
        subprocess.run(
            ["uv", "build", "--all-packages", "--out-dir", str(dist)],
            cwd=root,
            check=True,
        )
    wheels = tuple(sorted(dist.glob("*.whl")))
    if not wheels:
        return [f"{dist}: no wheels found"]
    by_distribution = {_wheel_distribution(wheel): wheel for wheel in wheels}
    errors: list[str] = []
    for distribution, module in _PUBLIC_IMPORTS.items():
        wheel = by_distribution.get(distribution)
        if wheel is None:
            errors.append(f"missing wheel for {distribution}")
            continue
        try:
            with zipfile.ZipFile(wheel) as archive:
                if not any(
                    name.startswith("open_table_connector/")
                    for name in archive.namelist()
                ):
                    errors.append(f"{wheel.name}: no open_table_connector package payload")
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"{wheel.name}: unreadable wheel ({exc})")
            continue
        error = _wheel_import_check(wheel, module)
        if error:
            errors.append(error)
    for distribution in sorted(by_distribution):
        if distribution in _PUBLIC_IMPORTS and distribution != "open-table-connector":
            error = _uninstall_check(wheels, distribution)
            if error:
                errors.append(error)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("dist", nargs="?", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    errors = check_independence(root, args.dist or root / "dist", build=args.build)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
