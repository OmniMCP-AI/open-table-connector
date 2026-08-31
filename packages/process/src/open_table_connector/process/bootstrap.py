"""Closed, deployment-owned bootstrap for the ``otc-process`` executable."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path

from open_table_connector.contract import (
    PROVIDER_CSV,
    PROVIDER_EXCEL,
    PROVIDER_JSON,
    PROVIDER_JSONL,
    PROVIDER_MAYBE_SHEET,
    PROVIDER_POSTGRES,
    PROVIDER_SQLITE,
    SCHEME_MANAGED_CSV,
    SCHEME_MANAGED_XLSX,
    SCHEME_MAYBE,
    SCHEME_XLSX,
    TableURI,
)
from open_table_connector.timeseries import (
    TemporalExecutionRequest,
    TemporalExecutionResult,
    TemporalTableDescriptor,
    descriptor_from_wire,
)

from .credentials import CredentialResolver
from .plugins import discover_process_binding
from .registry import ConnectorProcessRegistry
from .timeseries import TemporalProcessHandler, temporal_registration

_COMMON_FIELDS = {"schema_version", "provider", "descriptor", "target", "managed"}
_PROVIDER_FIELDS = {
    PROVIDER_CSV: set(),
    PROVIDER_JSON: set(),
    PROVIDER_JSONL: set(),
    PROVIDER_EXCEL: {"worksheet"},
    PROVIDER_SQLITE: {"physical_table"},
    PROVIDER_POSTGRES: {"physical_table"},
    PROVIDER_MAYBE_SHEET: {"maybe_sheet_binary"},
}
_TARGET_SCHEMES = {
    PROVIDER_CSV: {PROVIDER_CSV, SCHEME_MANAGED_CSV},
    PROVIDER_JSON: {PROVIDER_JSON},
    PROVIDER_JSONL: {PROVIDER_JSONL},
    PROVIDER_EXCEL: {PROVIDER_EXCEL, SCHEME_XLSX, SCHEME_MANAGED_XLSX},
    PROVIDER_SQLITE: {PROVIDER_SQLITE},
    PROVIDER_POSTGRES: {PROVIDER_POSTGRES},
    PROVIDER_MAYBE_SHEET: {SCHEME_MAYBE},
}


class _BoundExecutor:
    def __init__(self, target: TableURI, executor) -> None:
        self._target = target
        self._executor = executor

    def execute(self, request: TemporalExecutionRequest) -> TemporalExecutionResult:
        if request.target != self._target:
            raise ValueError("process request target does not match the bootstrapped target")
        return self._executor.execute(request)


def build_process_runtime(
    config_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
) -> tuple[ConnectorProcessRegistry, CredentialResolver]:
    """Build one explicit provider binding from a closed, non-secret JSON file."""

    document = _load_config(Path(config_path))
    provider = document.get("provider")
    if provider not in _PROVIDER_FIELDS:
        raise ValueError("process provider is unsupported")
    expected = _COMMON_FIELDS | _PROVIDER_FIELDS[provider]
    if set(document) != expected:
        raise ValueError("process bootstrap configuration is not closed")
    if document.get("schema_version") != "otc.process-bootstrap/v1":
        raise ValueError("process bootstrap schema version is unsupported")
    if not isinstance(document.get("managed"), bool):
        raise ValueError("process managed flag must be boolean")
    descriptor_document = document.get("descriptor")
    if not isinstance(descriptor_document, Mapping):
        raise ValueError("process temporal descriptor must be an object")
    descriptor = descriptor_from_wire(descriptor_document)
    target = TableURI(str(document.get("target")))
    if target.scheme not in _TARGET_SCHEMES[provider]:
        raise ValueError("process target scheme does not match provider")

    root = Path(artifact_root).absolute()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    executor, store = _provider_binding(provider, document, target, descriptor, root)
    handler = TemporalProcessHandler(
        executor=_BoundExecutor(target, executor),
        store=store,
    )
    registry = ConnectorProcessRegistry((temporal_registration(provider, handler),))
    return registry, CredentialResolver()


def _provider_binding(
    provider: str,
    document: Mapping[str, object],
    target: TableURI,
    descriptor: TemporalTableDescriptor,
    root: Path,
):
    return discover_process_binding(
        provider=provider,
        document=document,
        target=target,
        descriptor=descriptor,
        root=root,
    )


def _required_text(document: Mapping[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"process {field} must be a non-empty string")
    return value


def _load_config(path: Path) -> dict[str, object]:
    with _open_config(path) as stream:
        document = json.load(stream, object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(document, dict):
        raise ValueError("process bootstrap config must be an object")
    return document


def _open_config(path: Path):
    if not path.is_absolute():
        raise ValueError("OTC_PROCESS_CONFIG must be an absolute path")
    before = path.lstat() if not hasattr(os, "O_NOFOLLOW") else None
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("process bootstrap config must be a regular non-symlink file")
        if metadata.st_size > 1_048_576:
            raise ValueError("process bootstrap config exceeds one MiB")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise ValueError("process bootstrap config ownership is not trusted")
        if stat.S_IMODE(metadata.st_mode) & 0o022:
            raise ValueError("process bootstrap config is group/world writable")
        if before is not None and (before.st_dev, before.st_ino) != (
            metadata.st_dev,
            metadata.st_ino,
        ):
            raise ValueError("process bootstrap config changed during open")
        return os.fdopen(fd, "r", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate process bootstrap key: {key}")
        result[key] = value
    return result


__all__ = ["build_process_runtime"]
