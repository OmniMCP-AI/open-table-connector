"""Public contract-v1 symbols for framework-neutral Connectors."""

from .capabilities import CapabilityManifest, TableMode
from .coordinates import (
    BaseConvention,
    BaseCoordinate,
    SheetConvention,
    SheetCoordinate,
    TableCoordinate,
)
from .identity import CapabilityIdentity, ConnectorIdentity
from .errors import ConnectorError, ConnectorErrorCode
from .inspect import InspectRequest, TableInspection, TableInspector
from .read import (
    ArrowReadResult,
    ArrowTableReader,
    PolarsReadResult,
    PolarsTableReader,
    TableReadRequest,
)
from .receipts import NeutralReceipt
from .resolve import (
    ResolvedTable,
    ResolveContext,
    ResourceLimits,
    URIResolver,
)
from .scalars import Scalar
from .uri import TableURI
from .execution import ExecutionRequest, ExecutionResult, PreparedOperation, StepExecutor
from .storage import TableWriteRequest, TableWriteResult, TableWriter, TransactionalStore

__all__ = [
    "BaseConvention",
    "BaseCoordinate",
    "CapabilityIdentity",
    "CapabilityManifest",
    "ConnectorError",
    "ConnectorErrorCode",
    "ConnectorIdentity",
    "InspectRequest",
    "NeutralReceipt",
    "ArrowReadResult",
    "ArrowTableReader",
    "PolarsReadResult",
    "PolarsTableReader",
    "ResolvedTable",
    "ResolveContext",
    "ResourceLimits",
    "Scalar",
    "SheetConvention",
    "SheetCoordinate",
    "TableCoordinate",
    "TableMode",
    "TableInspection",
    "TableInspector",
    "TableReadRequest",
    "URIResolver",
    "TableURI",
    "ExecutionRequest",
    "ExecutionResult",
    "PreparedOperation",
    "StepExecutor",
    "TableWriteRequest",
    "TableWriteResult",
    "TableWriter",
    "TransactionalStore",
]
