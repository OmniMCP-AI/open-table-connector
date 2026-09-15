"""Smoke-test workspace wheels as independently removable distributions."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

from open_table_connector.contract import PACKAGE_NAMESPACE

_PUBLIC_IMPORTS = {
    "open-table-connector-contract": f"{PACKAGE_NAMESPACE}.contract",
    "open-table-connector-sdk": f"{PACKAGE_NAMESPACE}.sdk",
    "open-table-connector-formulas": f"{PACKAGE_NAMESPACE}.formulas",
    "open-table-connector-spreadsheets": f"{PACKAGE_NAMESPACE}.spreadsheets",
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
            "open-table-connector-sdk",
            "open-table-connector-formulas",
            "open-table-connector-spreadsheets",
            "open-table-connector-process",
            selected,
        }
        paths = [
            str(wheel) for wheel in wheels if _wheel_distribution(wheel) in allowed_distributions
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


def _installed_local_artifact_check(wheels: tuple[Path, ...]) -> str | None:
    """Use a fresh environment, without editable paths or remote provider wheels."""
    required = {
        "open-table-connector-contract",
        "open-table-connector-timeseries",
        "open-table-connector-formulas",
        "open-table-connector-spreadsheets",
        "open-table-connector-sdk",
        "open-table-connector-local-files",
    }
    selected = {
        _wheel_distribution(wheel): wheel
        for wheel in wheels
        if _wheel_distribution(wheel) in required
    }
    missing = required - set(selected)
    if missing:
        return "clean local artifact install: missing wheels " + ", ".join(sorted(missing))
    code = dedent("""
        import importlib.util
        import io
        import json
        import sys
        from pathlib import Path
        from PIL import Image
        from open_table_connector.local_files import LocalFilesConnector
        from open_table_connector.sdk import Client, ConnectorRegistry, OperationResult
        from open_table_connector.spreadsheets import ImageSpec

        for module in ('google_sheets', 'maybe_sheet', 'feishu_bitable', 'postgres', 'sqlite'):
            assert importlib.util.find_spec('open_table_connector.' + module) is None, module
        destination = Path(sys.argv[1]) / 'installed-artifact.xlsx'
        image_bytes = io.BytesIO()
        Image.new('RGB', (4, 3), 'blue').save(image_bytes, format='PNG')
        with Client(registry=ConnectorRegistry([LocalFilesConnector()])) as client:
            book = client.workbook.create(destination.as_uri())
            sheet = book.worksheet.create('Report')
            sheet.range('A1:B1').write([['literal', '']])
            sheet.image(ImageSpec('image/png', image_bytes.getvalue(), 'A3'), width=40, height=30)
            committed = book.write()
            assert committed.commit.value == 'committed'
            assert committed.verification.value == 'passed'
            assert book.verify().verification.value == 'passed'
            wire = json.loads(json.dumps(committed.to_wire()))
            assert OperationResult.from_wire(wire).to_wire() == wire
            expected = wire['receipts'][0]['details']['expected']
            reopened = client.workbook(destination.as_uri(), profile='literal-artifact/1.0')
            assert reopened.verify(expected=expected).verification.value == 'passed'
            assert reopened.worksheet('Report').range('A1:B1').read().require_value() == [['literal', '']]
        assert not any(name.startswith(('open_table_connector.google_sheets',
                                        'open_table_connector.maybe_sheet')) for name in sys.modules)
    """)
    with TemporaryDirectory(prefix="otc-installed-wheels-") as directory:
        environment = Path(directory) / "venv"
        result = subprocess.run(
            ["uv", "venv", "--python", sys.executable, str(environment)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            return "clean local artifact environment: " + result.stderr.strip()
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        result = subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                *(str(selected[name].resolve()) for name in sorted(selected)),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            return "clean local artifact installation: " + result.stderr.strip()
        result = subprocess.run(
            [str(python), "-I", "-c", code, directory],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            return "clean installed local image roundtrip: " + result.stderr.strip()
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
                if not any(name.startswith("open_table_connector/") for name in archive.namelist()):
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
    artifact_error = _installed_local_artifact_check(wheels)
    if artifact_error:
        errors.append(artifact_error)
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
