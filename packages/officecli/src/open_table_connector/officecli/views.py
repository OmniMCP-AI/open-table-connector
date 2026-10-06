from __future__ import annotations

from pathlib import Path

from .document import OfficeCliAdapter


def render_view(snapshot_path: Path, request):
    if not snapshot_path.exists():
        raise RuntimeError("renderer snapshot is unavailable")
    return OfficeCliAdapter().render(snapshot_path, request)


__all__ = ["render_view"]
