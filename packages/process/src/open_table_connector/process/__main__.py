"""Binary stdio entry point for the local connector supervisor."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from .bootstrap import build_process_runtime
from .server import run_server


def main() -> int:
    root = Path(os.environ.get("OTC_ARTIFACT_ROOT", ".otc-process-artifacts"))
    config = os.environ.get("OTC_PROCESS_CONFIG")
    if config is None:
        sys.stderr.write("OTC_PROCESS_CONFIG is required\n")
        return 2
    try:
        registry, resolver = build_process_runtime(config, root)
    except (OSError, TypeError, ValueError):
        sys.stderr.write("OTC process bootstrap configuration is invalid\n")
        return 2
    return run_server(
        sys.stdin.buffer,
        sys.stdout.buffer,
        sys.stderr,
        artifact_root=root,
        registry=registry,
        credential_resolver=resolver,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["main"]
