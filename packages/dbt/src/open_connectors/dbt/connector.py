"""Framework-neutral dbt processing Connector.

The Connector owns invocation/artifact bytes. It does not know FinClaw or
Open Time Series plans and never turns a run into a framework dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from open_connectors.contract import ConnectorError, ConnectorErrorCode

from .identity import CONNECTOR_IDENTITY


@dataclass(frozen=True)
class DbtCompileRequest:
    project_dir: Path
    select: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    vars: Mapping[str, Any] = field(default_factory=dict)
    target: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_dir", Path(self.project_dir))
        object.__setattr__(self, "select", tuple(self.select))
        object.__setattr__(self, "exclude", tuple(self.exclude))
        object.__setattr__(self, "vars", dict(self.vars))


@dataclass(frozen=True)
class DbtPreparedOperation:
    invocation_id: str
    argv: tuple[str, ...]
    project_dir: Path
    compiled_artifacts: Mapping[str, bytes]
    manifest_ref: str | None = None
    run_argv: tuple[str, ...] = ()

    @property
    def artifact_hash(self) -> str:
        digest = sha256()
        for name, content in sorted(self.compiled_artifacts.items()):
            digest.update(name.encode("utf-8"))
            digest.update(content)
        return digest.hexdigest()


@dataclass(frozen=True)
class DbtRunResult:
    invocation_id: str
    status: str
    run_results: bytes | None = None
    artifact_refs: Mapping[str, str] = field(default_factory=dict)


class DbtConnector:
    identity = CONNECTOR_IDENTITY

    def __init__(self, runner: Callable[[tuple[str, ...], Path], Mapping[str, Any]] | None = None) -> None:
        self._runner = runner

    def compile(self, request: DbtCompileRequest) -> DbtPreparedOperation:
        invocation_payload = json.dumps(
            {
                "project_dir": str(request.project_dir),
                "select": request.select,
                "exclude": request.exclude,
                "vars": request.vars,
                "target": request.target,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        invocation_id = "dbt_" + sha256(invocation_payload.encode("utf-8")).hexdigest()[:24]
        argv = ("dbt", "compile", "--project-dir", str(request.project_dir))
        if request.select:
            argv += ("--select", *request.select)
        if request.exclude:
            argv += ("--exclude", *request.exclude)
        if request.target:
            argv += ("--target", request.target)
        if request.vars:
            argv += ("--vars", json.dumps(request.vars, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        run_argv = ("dbt", "run", "--project-dir", str(request.project_dir))
        if request.select:
            run_argv += ("--select", *request.select)
        if request.exclude:
            run_argv += ("--exclude", *request.exclude)
        if request.target:
            run_argv += ("--target", request.target)
        if request.vars:
            run_argv += ("--vars", json.dumps(request.vars, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        artifacts: Mapping[str, bytes] = {}
        if self._runner is not None:
            try:
                payload = self._runner(argv, request.project_dir)
                artifacts = {
                    str(name): content if isinstance(content, bytes) else str(content).encode("utf-8")
                    for name, content in dict(payload.get("artifacts", {})).items()
                }
            except Exception as exc:
                raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "dbt compile failed", {"reason": str(exc)}) from None
        else:
            compiled = request.project_dir / "target" / "manifest.json"
            if compiled.is_file():
                artifacts = {"manifest.json": compiled.read_bytes()}
        return DbtPreparedOperation(invocation_id, argv, request.project_dir, artifacts, "manifest.json" if "manifest.json" in artifacts else None, run_argv)

    def run(self, operation: DbtPreparedOperation) -> DbtRunResult:
        if self._runner is None:
            raise ConnectorError(ConnectorErrorCode.UNSUPPORTED_CAPABILITY, "dbt execution runner is not configured", {})
        try:
            argv = operation.run_argv or ("dbt", "run", "--project-dir", str(operation.project_dir))
            payload = self._runner(argv, operation.project_dir)
            run_results = payload.get("run_results")
            return DbtRunResult(operation.invocation_id, str(payload.get("status", "completed")), run_results if isinstance(run_results, bytes) else None, dict(payload.get("artifact_refs", {})))
        except Exception as exc:
            raise ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "dbt run failed", {"reason": str(exc)}) from None

    def cancel(self, operation: DbtPreparedOperation) -> DbtRunResult:
        if self._runner is None:
            raise ConnectorError(ConnectorErrorCode.UNSUPPORTED_CAPABILITY, "dbt cancellation runner is not configured", {})
        try:
            payload = self._runner(("dbt", "cancel", "--invocation-id", operation.invocation_id), operation.project_dir)
            return DbtRunResult(operation.invocation_id, "cancelled", payload.get("run_results"))
        except Exception as exc:
            raise ConnectorError(ConnectorErrorCode.CANCELLED, "dbt cancellation failed", {"reason": str(exc)}) from None

    def read_artifact(self, operation: DbtPreparedOperation, name: str) -> bytes:
        try:
            return operation.compiled_artifacts[name]
        except KeyError:
            raise ConnectorError(ConnectorErrorCode.INVALID_URI, "dbt artifact is unavailable", {"artifact": name}) from None
