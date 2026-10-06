"""Lazy artifact export/view facade over optional physical adapters."""

from __future__ import annotations

import csv
import hashlib
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from open_table_connector.contract import SCHEME_FILE

from .result import CommitState, ErrorCode, ErrorInfo, OperationResult, Outcome, VerificationState


def _failure(code, message):
    return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(code, message))


class ArtifactAccess:
    def __init__(self, client):
        self._client = client

    def _adapter(self):
        try:
            from open_table_connector.officecli import artifact_adapter

            return artifact_adapter()
        except (ImportError, ModuleNotFoundError):
            return None

    def _preview_store(self):
        from .preview_sessions import PreviewSessionStore

        return PreviewSessionStore(Path(tempfile.gettempdir()) / "open-table-connector-preview")

    def _snapshot(self, source, directory):
        parsed = urlsplit(source.uri)
        if parsed.scheme != SCHEME_FILE or parsed.netloc not in {"", "localhost"} or not parsed.path.startswith("/"):
            raise RuntimeError("artifact preview requires a local committed file; remote export is not qualified")
        path = Path(unquote(parsed.path))
        if path.suffix.lower() not in {".docx", ".pptx", ".xlsx"}:
            raise RuntimeError("artifact preview format is not qualified")
        data = path.read_bytes()
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        directory.mkdir(parents=True, exist_ok=True)
        snapshot = directory / ("snapshot" + path.suffix.lower())
        snapshot.write_bytes(data)
        return path, snapshot, digest

    def export(self, request):
        try:
            from open_table_connector.artifacts import ArtifactValue
        except (ImportError, ModuleNotFoundError):
            return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "artifact contracts are not installed")
        destination = Path(unquote(urlsplit(request.destination_uri).path))
        suffix = destination.suffix.casefold()
        if suffix == ".xlsx":
            return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "XLSX export requires the Excelize rich writer")
        adapter = self._adapter()
        if adapter is None:
            return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "OfficeCLI adapter is unavailable")
        source = Path(unquote(urlsplit(request.source_uri).path))
        if destination.exists():
            return _failure(ErrorCode.DESTINATION_EXISTS, "artifact destination already exists")
        try:
            if source.suffix.casefold() == ".csv":
                with source.open(newline="", encoding="utf-8") as stream:
                    rows = [row for row in csv.reader(stream)]
            else:
                return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "source format is not qualified")
            evidence = adapter.create_table(destination, rows, request.spec)
            value = ArtifactValue(evidence["uri"], evidence["media_type"], evidence["content_hash"], evidence["engine"], tuple(evidence.get("coverage", ())))
            return OperationResult(value, Outcome.SUCCEEDED, CommitState.COMMITTED, VerificationState.PASSED, ())
        except FileExistsError:
            return _failure(ErrorCode.DESTINATION_EXISTS, "artifact destination already exists")
        except Exception:
            return _failure(ErrorCode.EXECUTION_FAILED, "artifact export failed")

    def view(self, request):
        try:
            from open_table_connector.artifacts import ViewValue
        except (ImportError, ModuleNotFoundError):
            return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "artifact contracts are not installed")
        adapter = self._adapter()
        if adapter is None:
            return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "OfficeCLI adapter is unavailable")
        try:
            with tempfile.TemporaryDirectory(prefix="otc-preview-") as directory:
                source, snapshot, digest = self._snapshot(request.source, Path(directory))
                evidence = adapter.render(snapshot, request)
                if "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                    return _failure(ErrorCode.SNAPSHOT_UNAVAILABLE, "source changed during rendering")
            value = ViewValue(tuple(evidence.get("outputs", ())), request.source.uri, digest, evidence.get("renderer", {}))
            return OperationResult(value, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.PASSED, ())
        except RuntimeError as exc:
            return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, str(exc))
        except FileExistsError:
            return _failure(ErrorCode.DESTINATION_EXISTS, "view destination already exists")
        except Exception:
            return _failure(ErrorCode.EXECUTION_FAILED, "artifact view failed")

    def watch(self, request):
        from open_table_connector.artifacts import WatchValue
        from open_table_connector.contract import TargetSelector

        store = self._preview_store()
        if request.action == "start":
            if request.source is None:
                return _failure(ErrorCode.INVALID_TARGET, "watch start requires a source")
            if request.read_only_required:
                return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "watch runtime cannot enforce a read-only preview")
            adapter = self._adapter()
            if adapter is None or not hasattr(adapter, "start_watch"):
                return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "watch runtime is unavailable")
            record = store.create({"state": "stopped", "source_uri": request.source.uri, "editability": "preview_copy_only", "persistence": "discard"})
        elif not request.session_id:
            return _failure(ErrorCode.INVALID_TARGET, "watch action requires a session id")
        else:
            try:
                record = store.load(request.session_id)
            except (KeyError, ValueError):
                return _failure(ErrorCode.TARGET_NOT_FOUND, "preview session was not found")
        session_id = record["session_id"]
        if request.action in {"start", "refresh"}:
            adapter = self._adapter()
            if adapter is None or not hasattr(adapter, "start_watch"):
                return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "watch runtime is unavailable")
            if request.action == "refresh":
                store.stop(session_id)
            try:
                source, snapshot, digest = self._snapshot(TargetSelector(record["source_uri"]), store.directory / session_id)
                store.update(session_id, {"snapshot_path": str(snapshot)})
                process, url = adapter.start_watch(snapshot)
                store.attach(session_id, process)
                parsed = urlsplit(url)
                if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"} or parsed.username or parsed.password:
                    raise RuntimeError("watch requires a loopback-only URL")
                if "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                    raise RuntimeError("source changed during watch startup")
                record = store.update(session_id, {"url": url, "source_hash": digest, "snapshot_hash": digest})
            except Exception as exc:
                store.stop(session_id)
                return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, str(exc))
        elif request.action == "stop":
            record = store.stop(session_id)
        else:
            state = store.runtime_state(session_id)
            record = store.update(session_id, {"state": state, "url": record.get("url") if state == "running" else None})
        value = WatchValue(record["session_id"], record["state"], record.get("url"), record.get("source_hash"), record.get("snapshot_hash"))
        verified = VerificationState.PASSED if record["state"] in {"running", "stopped"} else VerificationState.UNAVAILABLE
        return OperationResult(value, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, verified, ())


__all__ = ["ArtifactAccess"]
