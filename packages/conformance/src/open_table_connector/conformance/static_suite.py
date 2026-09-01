"""Static dependency-direction locks for neutral Connector packages."""

from __future__ import annotations

import ast
from pathlib import Path

_FRAMEWORK_PREFIXES = ("finclaw", "open_time_series")


def assert_framework_import_free(root: Path) -> None:
    offenders: list[str] = []
    for path in sorted(Path(root).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.append(node.module)
            if any(name == prefix or name.startswith(prefix + ".") for name in imported for prefix in _FRAMEWORK_PREFIXES):
                offenders.append(str(path))
            if isinstance(node, ast.FunctionDef) and node.name in {"operate", "run_operation"}:
                offenders.append(f"{path}: universal operation function {node.name}")
    assert not offenders, f"framework import or universal operation found: {offenders}"
