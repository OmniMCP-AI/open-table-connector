"""Public contract-v1 symbols for framework-neutral Connectors."""

from .bounded_reads import (
    BOUNDED_ARROW_TABLE_READ_CAPABILITY,
    BoundedArrowTableReader,
    BoundedArrowTableReadResult,
    BoundedReadReceipt,
    BoundedTableReadRequest,
    ReadExtent,
)
from .capabilities import CapabilityManifest, TableMode
from .coordinates import (
    BaseConvention,
    BaseCoordinate,
    SheetConvention,
    SheetCoordinate,
    TableCoordinate,
)
from .errors import ConnectorError, ConnectorErrorCode
from .execution import (
    ExecutionRequest,
    ExecutionResult,
    PreparedOperation,
    SqlExecutor,
    StepExecutor,
)
from .identity import CapabilityIdentity, ConnectorIdentity
from .inspect import InspectRequest, TableInspection, TableInspector
from .plugins import PluginDescriptor, PluginFactory
from .read import (
    ArrowReadResult,
    ArrowTableReader,
    PolarsReadResult,
    PolarsTableReader,
    TableReadRequest,
)
from .receipts import NeutralReceipt
from .resolve import (
    ResolveContext,
    ResolvedTable,
    ResourceLimits,
    URIResolver,
)
from .scalars import Scalar
from .storage import TableWriter, TableWriteRequest, TableWriteResult, TransactionalStore
from .uri import TableURI

__all__ = [
    "BaseConvention",
    "BOUNDED_ARROW_TABLE_READ_CAPABILITY",
    "BoundedArrowTableReadResult",
    "BoundedArrowTableReader",
    "BoundedReadReceipt",
    "BoundedTableReadRequest",
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
    "PluginDescriptor",
    "PluginFactory",
    "ResolvedTable",
    "ResolveContext",
    "ResourceLimits",
    "ReadExtent",
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
    "SqlExecutor",
    "TableWriteRequest",
    "TableWriteResult",
    "TableWriter",
    "TransactionalStore",
]
