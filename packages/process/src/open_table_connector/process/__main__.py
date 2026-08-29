"""Binary stdio entry point for the local connector supervisor."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from .server import run_server


def main() -> int:
    root = Path(os.environ.get("OTC_ARTIFACT_ROOT", ".otc-process-artifacts"))
    return run_server(sys.stdin.buffer, sys.stdout.buffer, sys.stderr, artifact_root=root)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["main"]
