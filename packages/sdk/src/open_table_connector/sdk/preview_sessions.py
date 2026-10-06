"""User-scoped disposable preview session records."""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
from pathlib import Path


_OWNED = {}


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

    def attach(self, session_id, process):
        token = secrets.token_hex(16)
        _OWNED[(str(self.directory.resolve()), session_id)] = (token, process)
        return self.update(session_id, {"owner_token": token, "pid": process.pid, "state": "running"})

    def _owned(self, record):
        owned = _OWNED.get((str(self.directory.resolve()), record["session_id"]))
        return owned[1] if owned and owned[0] == record.get("owner_token") else None

    def runtime_state(self, session_id):
        record = self.load(session_id)
        if record["state"] == "stopped":
            return "stopped"
        process = self._owned(record)
        if process is None:
            return "orphaned"
        return "running" if process.poll() is None else "crashed"

    def stop(self, session_id):
        record = self.load(session_id)
        process = self._owned(record)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        _OWNED.pop((str(self.directory.resolve()), session_id), None)
        snapshot = record.get("snapshot_path")
        if snapshot:
            path = Path(snapshot)
            # Persisted metadata cannot authorize deletion outside our session directory.
            root = self.directory.resolve() / session_id
            if path.resolve().parent == root:
                shutil.rmtree(root, ignore_errors=True)
        return self.update(session_id, {"state": "stopped", "url": None})

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
