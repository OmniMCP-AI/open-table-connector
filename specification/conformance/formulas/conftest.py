from __future__ import annotations

import pytest

from .grid_cases import GRID_PROVIDER_IDS, load_grid_fixture
from .support import (
    SECURITY_EXPRESSION,
    SECURITY_MARKERS,
    RecordingProcessClient,
    RecordingSheetsTransport,
    RecordingWorkbookFactory,
)


@pytest.fixture
def formula_security_markers() -> tuple[str, ...]:
    return SECURITY_MARKERS


@pytest.fixture
def formula_security_expression() -> object:
    return SECURITY_EXPRESSION


@pytest.fixture(params=GRID_PROVIDER_IDS)
def grid_fixture_document(request: pytest.FixtureRequest) -> dict[str, object]:
    return load_grid_fixture(request.param)


@pytest.fixture
def recording_sheets_transport() -> type[RecordingSheetsTransport]:
    return RecordingSheetsTransport


@pytest.fixture
def recording_process_client() -> type[RecordingProcessClient]:
    return RecordingProcessClient


@pytest.fixture
def recording_workbook_factory() -> type[RecordingWorkbookFactory]:
    return RecordingWorkbookFactory
