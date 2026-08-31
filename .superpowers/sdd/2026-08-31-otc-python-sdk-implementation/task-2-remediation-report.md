Task 2 remediation report
Date: 2026-08-31

Scope
- Fixed SDK `Client.open()` so plain path targets route through `handles_paths` connectors without forcing `TableURI`.
- Fixed `LegacyConnectorAdapterBridge.open_table()` to hydrate a `TableBinding` from legacy `inspect()` plus a bounded `read()` schema probe.
- Fixed descriptor activation so credential leases stay alive through provider factory construction and are disposed immediately after.

Tests added
- `packages/sdk/tests/test_client.py::test_client_open_routes_path_targets_without_forcing_table_uri`
- `packages/sdk/tests/test_client.py::test_client_open_reads_schema_through_a_legacy_adapter`
- `packages/sdk/tests/test_registry.py::test_descriptor_activation_disposes_credential_lease_after_factory_use`

Verification
- `uv run --frozen pytest packages/sdk/tests/test_client.py packages/sdk/tests/test_registry.py packages/contract/tests/test_plugins.py packages/contract/tests/test_protocols.py`
- `uv run --frozen ruff check packages/sdk/src/open_table_connector/sdk/client.py packages/sdk/src/open_table_connector/sdk/connector.py packages/sdk/src/open_table_connector/sdk/registry.py packages/sdk/tests/test_client.py packages/sdk/tests/test_registry.py`
- `uv run --frozen python -m compileall packages/sdk/src/open_table_connector/sdk`

Notes
- `packages/sdk/src/open_table_connector/sdk/client.py` already contains in-flight SQL/temporal work from later tasks, so the remediation commit should stage only the `open()` routing hunk plus `_normalize_open_target()`, not the unrelated additions in that file.
