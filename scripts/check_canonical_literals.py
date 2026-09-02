"""Reject repeated provider and route literals outside the canonical names module."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


def _canonical_values(root: Path) -> dict[str, str]:
    names_path = root / "packages/contract/src/open_table_connector/contract/names.py"
    spec = importlib.util.spec_from_file_location("otc_contract_names", names_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {names_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        name: value
        for name, value in vars(module).items()
        if name.startswith(("PROVIDER_", "SCHEME_", "HOST_")) and isinstance(value, str)
    }


def check_canonical_literals(root: Path) -> list[str]:
    canonical = _canonical_values(root)
    values = set(canonical.values())
    names_path = root / "packages/contract/src/open_table_connector/contract/names.py"
    errors: list[str] = []
    for path in sorted((root / "packages").glob("*/src/**/*.py")):
        if path.resolve() == names_path.resolve():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path}:{exc.lineno}: syntax error")
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in values
            ):
                errors.append(f"{path}:{node.lineno}: repeated canonical literal {node.value!r}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = check_canonical_literals(root)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
