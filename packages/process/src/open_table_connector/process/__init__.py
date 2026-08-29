"""Versioned local process transport for connector isolation."""

from .artifacts import ArtifactStore
from .credentials import CredentialLease, CredentialResolver
from .envelope import (
    ConnectorProcessEnvelope,
    PORTABLE_PLAN_VERSION,
    PROCESS_PROTOCOL,
    ProcessOperation,
)
from .framing import FrameError, read_frame, write_frame
from .registry import ConnectorProcessRegistry, ConnectorRegistration, ProcessHandler
from .server import (
    BoundedDiagnostics,
    ConnectorProcessServer,
    ProcessError,
    ProcessRequestContext,
    ProcessResult,
    redact_text,
    run_server,
)
from .timeseries import (
    PORTABLE_PROVIDER_CAPABILITIES,
    TemporalProcessHandler,
    temporal_registration,
)

__all__ = [
    "ArtifactStore",
    "BoundedDiagnostics",
    "ConnectorProcessEnvelope",
    "ConnectorProcessRegistry",
    "ConnectorProcessServer",
    "ConnectorRegistration",
    "CredentialLease",
    "CredentialResolver",
    "FrameError",
    "PORTABLE_PLAN_VERSION",
    "PORTABLE_PROVIDER_CAPABILITIES",
    "PROCESS_PROTOCOL",
    "ProcessError",
    "ProcessHandler",
    "ProcessOperation",
    "ProcessRequestContext",
    "ProcessResult",
    "TemporalProcessHandler",
    "read_frame",
    "redact_text",
    "run_server",
    "temporal_registration",
    "write_frame",
]
