"""Universal connector conformance registry and deterministic fixtures."""

from .cases import ConnectorCase, all_cases, case, cases_with
from .fixtures import RecordingProcessClient, RecordingSheetsTransport

__all__ = [
    "ConnectorCase",
    "RecordingProcessClient",
    "RecordingSheetsTransport",
    "all_cases",
    "case",
    "cases_with",
]
