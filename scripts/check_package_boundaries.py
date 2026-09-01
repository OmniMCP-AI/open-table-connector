"""Validate workspace package dependency direction."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

_ORDER = {
    "open-table-connector-contract": 0,
    "open-table-connector-timeseries": 1,
    "open-table-connector-formulas": 1,
    "open-table-connector-local-files": 2,
    "open-table-connector-sqlite": 2,
    "open-table-connector-postgres": 2,
    "open-table-connector-google-sheets": 2,
    "open-table-connector-feishu-bitable": 2,
    "open-table-connector-maybe-sheet": 2,
    "open-table-connector-sdk": 2,
    "open-table-connector-conformance": 3,
    "open-table-connector-process": 4,
    "open-table-connector-dbt": 4,
    "open-table-connector": 5,
}


def check_boundaries(root: Path) -> list[str]:
    errors: list[str] = []
    for pyproject in sorted((root / "packages").glob("*/pyproject.toml")):
        document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = document.get("project", {})
        name = str(project.get("name", ""))
        level = _ORDER.get(name)
        if level is None:
            errors.append(f"{pyproject.parent.name}: unknown distribution {name!r}")
            continue
        requirements = list(project.get("dependencies", []))
        for extra_requirements in project.get("optional-dependencies", {}).values():
            requirements.extend(extra_requirements)
        for requirement in requirements:
            dependency = str(requirement).split(" ", 1)[0]
            dependency = dependency.split("<", 1)[0].split(">", 1)[0].split("=", 1)[0]
            if dependency in _ORDER and _ORDER[dependency] > level:
                errors.append(f"{name}: dependency direction points upward to {dependency}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = check_boundaries(root)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
