"""Check relative Markdown links in the manuals and package READMEs."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "README.md",
    ROOT / "docs/user-guide",
    ROOT / "docs/reference",
    ROOT / "packages",
)
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def markdown_files():
    for source in SOURCES:
        if source.is_file():
            yield source
        elif source in {ROOT / "docs/user-guide", ROOT / "docs/reference", ROOT / "packages"}:
            yield from source.rglob("*.md")


def main() -> int:
    errors = []
    for source in sorted(set(markdown_files())):
        for raw in LINK.findall(source.read_text(encoding="utf-8")):
            target = raw.split("#", 1)[0].strip()
            if not target or "://" in target or target.startswith(("mailto:", "codex:")):
                continue
            path = (source.parent / unquote(urlsplit(target).path)).resolve()
            if not path.exists():
                errors.append(f"{source.relative_to(ROOT)}: {raw}")
    for error in errors:
        print(error)
    if not errors:
        print("manual and README links are current")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
