"""Build workspace wheels and verify their package payloads."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path


def build_all_wheels(root: Path, dist: Path | None = None) -> tuple[Path, ...]:
    output = dist or (root / "dist")
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["uv", "build", "--all-packages", "--out-dir", str(output)],
        cwd=root,
        check=True,
    )
    return tuple(sorted(output.glob("*.whl")))


def smoke_wheels(dist: Path) -> list[str]:
    errors: list[str] = []
    for wheel in sorted(dist.glob("*.whl")):
        try:
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
                if not any(name.startswith("open_table_connector/") for name in names):
                    errors.append(f"{wheel.name}: no open_table_connector package payload")
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"{wheel.name}: unreadable wheel ({exc})")
    if not list(dist.glob("*.whl")):
        errors.append(f"{dist}: no wheels found")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("dist", nargs="?", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dist = args.dist or root / "dist"
    if args.build:
        build_all_wheels(root, dist)
    errors = smoke_wheels(dist)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
