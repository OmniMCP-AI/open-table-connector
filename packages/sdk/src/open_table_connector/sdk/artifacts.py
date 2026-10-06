"""Lazy artifact export/view facade over optional physical adapters."""

from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import unquote, urlsplit

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
        path = Path(unquote(urlsplit(request.source.uri).path))
        try:
            evidence = adapter.render(path, request)
            value = ViewValue(tuple(evidence.get("outputs", ())), request.source.uri, evidence.get("source_hash", ""), evidence.get("renderer", {}))
            return OperationResult(value, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.PASSED, ())
        except RuntimeError as exc:
            return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, str(exc))
        except Exception:
            return _failure(ErrorCode.EXECUTION_FAILED, "artifact view failed")

    def watch(self, request):
        from pathlib import Path
        from tempfile import gettempdir

        from open_table_connector.artifacts import WatchValue

        from .preview_sessions import PreviewSessionStore

        store = PreviewSessionStore(Path(gettempdir()) / "open-table-connector-preview")
        if request.action == "start":
            if request.source is None:
                return _failure(ErrorCode.INVALID_TARGET, "watch start requires a source")
            record = store.create({"state": "stopped", "source_uri": request.source.uri, "editability": "preview_copy_only", "persistence": "discard"})
            value = WatchValue(record["session_id"], record["state"], None, None, None)
            return OperationResult(value, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.UNAVAILABLE, ())
        if not request.session_id:
            return _failure(ErrorCode.INVALID_TARGET, "watch action requires a session id")
        try:
            record = store.load(request.session_id)
        except KeyError:
            return _failure(ErrorCode.TARGET_NOT_FOUND, "preview session was not found")
        if request.action == "stop":
            record = store.update(request.session_id, {"state": "stopped"})
        value = WatchValue(record["session_id"], record["state"], record.get("url"), record.get("source_hash"), record.get("snapshot_hash"))
        return OperationResult(value, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.UNAVAILABLE, ())


__all__ = ["ArtifactAccess"]
