from __future__ import annotations

import pytest
from open_table_connector.contract import (
    PROVIDER_CSV,
    PROVIDER_EXCEL,
    PROVIDER_JSON,
    PROVIDER_JSONL,
    PROVIDER_LOCAL_FILES,
    SCHEME_FILE,
    SCHEME_MD,
    SCHEME_XLSX,
    ProviderConfig,
    ProviderFactoryContext,
)
from open_table_connector.local_files.cli_adapter import (
    csv_cli_plugin,
    excel_cli_plugin,
    local_files_cli_plugin,
    markdown_cli_plugin,
)


@pytest.mark.parametrize(
    ("factory", "provider_id", "schemes", "local", "handles_paths"),
    (
        (csv_cli_plugin, PROVIDER_CSV, (PROVIDER_CSV,), True, False),
        (
            excel_cli_plugin,
            PROVIDER_EXCEL,
            (PROVIDER_EXCEL, SCHEME_XLSX),
            True,
            False,
        ),
        (markdown_cli_plugin, SCHEME_MD, (SCHEME_MD,), True, False),
        (
            local_files_cli_plugin,
            PROVIDER_LOCAL_FILES,
            (SCHEME_FILE, PROVIDER_JSON, PROVIDER_JSONL),
            True,
            True,
        ),
    ),
)
def test_local_cli_descriptors_are_provider_owned(
    factory, provider_id, schemes, local, handles_paths
):
    descriptor = factory()
    assert descriptor.identity.connector_id == provider_id
    assert descriptor.schemes == schemes
    assert descriptor.local is local
    assert descriptor.handles_paths is handles_paths
    assert descriptor.factory.__module__.startswith("open_table_connector.local_files")


def test_local_factories_reject_runtime_bindings_before_io() -> None:
    context = ProviderFactoryContext(
        ProviderConfig(PROVIDER_CSV, environment={"unexpected": "HOST_VALUE"}),
        environment={"unexpected": "value"},
    )
    with pytest.raises(ValueError, match="environment"):
        csv_cli_plugin().factory(context)
