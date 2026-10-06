"""Check that the user-facing CLI reference names every parser command."""

from __future__ import annotations

from pathlib import Path


def check_cli_reference(root: Path) -> list[str]:
    from open_table_connector.cli.__main__ import build_parser

    parser = build_parser()
    actions = parser._subparsers._group_actions[0].choices
    reference = root / "docs/user-guide/cli.md"
    if not reference.exists():
        return [f"missing {reference}"]
    text = reference.read_text(encoding="utf-8")
    missing = [f"missing command: {name}" for name in actions if f"`{name}`" not in text and f"| `{name}`" not in text]
    return missing


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = check_cli_reference(root)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["check_cli_reference"]
