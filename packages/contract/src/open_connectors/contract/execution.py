"""Small neutral processing capability for prepared external operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from .identity import CapabilityIdentity
from .receipts import NeutralReceipt
from .resolve import ResourceLimits
from .uri import TableURI


@dataclass(frozen=True)
class PreparedOperation:
    operation_id: str
    statement: str
    parameters: tuple[Any, ...] = ()
    target: TableURI | None = None
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id.strip():
            raise ValueError("operation_id must be non-empty")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ValueError("statement must be non-empty")
        object.__setattr__(self, "parameters", tuple(self.parameters))


@dataclass(frozen=True)
class ExecutionRequest:
    uri: TableURI
    statement: str
    parameters: tuple[Any, ...] = ()
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)


@dataclass(frozen=True)
class ExecutionResult:
    operation_id: str
    status: str
    affected_rows: int | None
    receipt: NeutralReceipt | None = None
    artifacts: Mapping[str, str] = field(default_factory=dict)


@runtime_checkable
class StepExecutor(Protocol):
    def prepare(self, request: ExecutionRequest) -> PreparedOperation: ...

    def run(self, operation: PreparedOperation) -> ExecutionResult: ...


@dataclass(frozen=True)
class CapabilityReference:
    capability: CapabilityIdentity
    operation: str
