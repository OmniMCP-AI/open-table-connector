"""User-scoped disposable preview session records."""

from __future__ import annotations

import json
import secrets
from pathlib import Path


class PreviewSessionStore:
    def __init__(self, runtime_directory: Path):
        self.directory = Path(runtime_directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        if not session_id.isalnum():
            raise ValueError("invalid preview session id")
        return self.directory / f"{session_id}.json"

    def create(self, record):
        session_id = secrets.token_urlsafe(18).replace("-", "A").replace("_", "B")
        value = {**record, "session_id": session_id}
        self._path(session_id).write_text(json.dumps(value), encoding="utf-8")
        return value

    def load(self, session_id: str):
        path = self._path(session_id)
        if not path.exists():
            raise KeyError("preview session not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def update(self, session_id: str, changes):
        value = {**self.load(session_id), **changes}
        self._path(session_id).write_text(json.dumps(value), encoding="utf-8")
        return value

    def remove(self, session_id: str):
        self._path(session_id).unlink(missing_ok=True)


__all__ = ["PreviewSessionStore"]
