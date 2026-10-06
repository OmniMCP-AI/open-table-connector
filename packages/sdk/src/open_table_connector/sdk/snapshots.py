"""Bounded workbook snapshot capture for disposable renderers."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from open_table_connector.contract import SCHEME_FILE, TargetSelector
from open_table_connector.spreadsheets import WorkbookSnapshot

from .result import CommitState, ErrorCode, ErrorInfo, OperationResult, Outcome, VerificationState


def _failure(code: ErrorCode, message: str) -> OperationResult[None]:
    return OperationResult(None, Outcome.REJECTED, CommitState.NOT_STARTED, VerificationState.SKIPPED, (), error=ErrorInfo(code, message))


def capture_workbook_snapshot(client, target: TargetSelector | str, directory) -> OperationResult[WorkbookSnapshot]:
    selector = target if isinstance(target, TargetSelector) else TargetSelector(target)
    parsed = urlsplit(selector.uri)
    data: bytes
    revision = None
    if parsed.scheme == SCHEME_FILE:
        path = Path(unquote(parsed.path))
        try:
            data = path.read_bytes()
        except OSError:
            return _failure(ErrorCode.SNAPSHOT_UNAVAILABLE, "local workbook snapshot is unavailable")
        revision = "sha256:" + hashlib.sha256(data).hexdigest()
        consistency = "revision_bound"
    else:
        try:
            descriptor = client._registry.descriptor_for(selector.uri)
            connector = client._registry.connector_for(selector.uri)
            exporter = getattr(connector, "export_workbook", None)
            if not callable(exporter):
                return _failure(ErrorCode.UNSUPPORTED_CAPABILITY, "provider does not expose a workbook export")
            data = exporter(selector.uri)
            if not isinstance(data, bytes):
                return _failure(ErrorCode.PROTOCOL_FAILURE, "provider export was not bytes")
            revision = getattr(descriptor, "revision", None)
            consistency = "revision_bound" if revision else "revision_unavailable"
        except Exception:
            return _failure(ErrorCode.SNAPSHOT_UNAVAILABLE, "remote workbook snapshot is unavailable")
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    snapshot = WorkbookSnapshot(selector.uri, selector, digest, datetime.now(UTC).isoformat(), revision, consistency)
    return OperationResult(snapshot, Outcome.SUCCEEDED, CommitState.NOT_APPLICABLE, VerificationState.PASSED, ())


__all__ = ["capture_workbook_snapshot"]
