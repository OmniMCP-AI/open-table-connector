from __future__ import annotations

import pytest

from .field_cases import FIELD_PROVIDER_IDS, load_field_fixture
from .grid_cases import GRID_PROVIDER_IDS, load_grid_fixture
from .support import (
    SECURITY_EXPRESSION,
    SECURITY_MARKERS,
    RecordingFeishuTransport,
    RecordingMaybeProcess,
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


@pytest.fixture(params=FIELD_PROVIDER_IDS)
def field_fixture_document(request: pytest.FixtureRequest) -> dict[str, object]:
    return load_field_fixture("field-observation.json")


@pytest.fixture
def recording_sheets_transport() -> type[RecordingSheetsTransport]:
    return RecordingSheetsTransport


@pytest.fixture
def recording_process_client() -> type[RecordingProcessClient]:
    return RecordingProcessClient


@pytest.fixture
def recording_workbook_factory() -> type[RecordingWorkbookFactory]:
    return RecordingWorkbookFactory


@pytest.fixture
def recording_maybe_process() -> type[RecordingMaybeProcess]:
    return RecordingMaybeProcess


@pytest.fixture
def recording_feishu_transport() -> type[RecordingFeishuTransport]:
    return RecordingFeishuTransport
