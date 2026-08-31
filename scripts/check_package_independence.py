"""Smoke-test workspace wheels as independently removable distributions."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

from open_table_connector.contract import PACKAGE_NAMESPACE

_PUBLIC_IMPORTS = {
    "open-table-connector-contract": f"{PACKAGE_NAMESPACE}.contract",
    "open-table-connector-timeseries": f"{PACKAGE_NAMESPACE}.timeseries",
    "open-table-connector-local-files": f"{PACKAGE_NAMESPACE}.local_files",
    "open-table-connector-sqlite": f"{PACKAGE_NAMESPACE}.sqlite",
    "open-table-connector-postgres": f"{PACKAGE_NAMESPACE}.postgres",
    "open-table-connector-google-sheets": f"{PACKAGE_NAMESPACE}.google_sheets",
    "open-table-connector-feishu-bitable": f"{PACKAGE_NAMESPACE}.feishu_bitable",
    "open-table-connector-maybe-sheet": f"{PACKAGE_NAMESPACE}.maybe_sheet",
    "open-table-connector-conformance": f"{PACKAGE_NAMESPACE}.conformance",
    "open-table-connector-process": f"{PACKAGE_NAMESPACE}.process",
    "open-table-connector-dbt": f"{PACKAGE_NAMESPACE}.dbt",
    "open-table-connector": f"{PACKAGE_NAMESPACE}.cli",
}
_PROVIDER_MODULES = (
    f"{PACKAGE_NAMESPACE}.local_files",
    f"{PACKAGE_NAMESPACE}.sqlite",
    f"{PACKAGE_NAMESPACE}.postgres",
    f"{PACKAGE_NAMESPACE}.google_sheets",
    f"{PACKAGE_NAMESPACE}.feishu_bitable",
    f"{PACKAGE_NAMESPACE}.maybe_sheet",
)
_DISTRIBUTION_MODULES = {
    "open-table-connector-local-files": "open_table_connector.local_files",
    "open-table-connector-sqlite": "open_table_connector.sqlite",
    "open-table-connector-postgres": "open_table_connector.postgres",
    "open-table-connector-google-sheets": "open_table_connector.google_sheets",
    "open-table-connector-feishu-bitable": "open_table_connector.feishu_bitable",
    "open-table-connector-maybe-sheet": "open_table_connector.maybe_sheet",
}


def _cli_provider_matrix_check(wheels: tuple[Path, ...]) -> list[str]:
    """Verify CLI discovery remains usable with one provider wheel at a time."""

    errors: list[str] = []
    provider_distributions = (
        "open-table-connector-local-files",
        "open-table-connector-google-sheets",
        "open-table-connector-feishu-bitable",
        "open-table-connector-maybe-sheet",
    )
    for selected in provider_distributions:
        selected_module = _DISTRIBUTION_MODULES[selected]
        allowed_distributions = {
            "open-table-connector",
            "open-table-connector-contract",
            "open-table-connector-timeseries",
            selected,
        }
        paths = [
            str(wheel)
            for wheel in wheels
            if _wheel_distribution(wheel) in allowed_distributions
        ]
        blocked = {
            module
            for distribution, module in _DISTRIBUTION_MODULES.items()
            if distribution != selected
        }
        expected_id = selected_module.rsplit(".", 1)[-1]
        code = (
            "import builtins,sys;"
            "sys.path[:0]=sys.argv[1:];"
            f"blocked={blocked!r};"
            "real=builtins.__import__;"
            "builtins.__import__=lambda n,*a,**k: "
            "(_ for _ in ()).throw(ModuleNotFoundError(name=n)) "
            "if any(n==x or n.startswith(x+'.') for x in blocked) else real(n,*a,**k);"
            "from open_table_connector.cli.registry import build_default_registry;"
            "r=build_default_registry(env={});"
            f"assert any(d.identity.connector_id == {expected_id!r} for d in r.list())"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-c", code, *paths],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            errors.append(
                f"CLI with {selected}: provider matrix check failed: {result.stderr.strip()}"
            )
    return errors


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
        f"'{PACKAGE_NAMESPACE}.contract','{PACKAGE_NAMESPACE}.timeseries',"
        f"'{PACKAGE_NAMESPACE}.cli','{PACKAGE_NAMESPACE}.process')]"
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
    errors.extend(_cli_provider_matrix_check(wheels))
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
