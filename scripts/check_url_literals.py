"""Reject retired public URL scheme literals in tracked repository text."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

_FORBIDDEN_SCHEMES = ("csv", "excel", "maybe")
_FORBIDDEN_URL = re.compile(
    rf"(?<![A-Za-z0-9_+])(?P<scheme>{'|'.join(_FORBIDDEN_SCHEMES)})" + r"://",
    re.IGNORECASE,
)
_AGENTS_POLICY = (
    "Project URL policy: local tabular/workbook files use canonical file:// URLs; "
    "do not introduce "
    + ", ".join(f"{scheme}://" for scheme in ("csv", "excel", "xlsx"))
    + f", or {'maybe' + '://'} public routes. "
    "MaybeSheet uses canonical HTTPS document URLs."
)


def _repository_files(root: Path) -> tuple[Path, ...]:
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0:
        return tuple(
            root / item.decode("utf-8")
            for item in tracked.stdout.split(b"\0")
            if item
        )
    return tuple(
        path
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    )


def check_url_literals(root: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(_repository_files(root)):
        if path.suffix == ".lock":
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root)
        for line_number, line in enumerate(lines, start=1):
            if relative == Path("AGENTS.md") and line == _AGENTS_POLICY:
                continue
            for match in _FORBIDDEN_URL.finditer(line):
                errors.append(
                    f"{relative}:{line_number}: forbidden public URL scheme: "
                    f"{match.group('scheme').casefold()}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = check_url_literals(args.root.resolve())
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
