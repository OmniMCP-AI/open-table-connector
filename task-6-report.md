# Task 6 Report

Date: 2026-08-31

Scope:
- Restore the credential-free `TableURI` invariant for all schemes.
- Make SDK descriptor activation honor the same default environment credential bindings as the CLI for Google Sheets, Feishu Bitable, and MaybeSheet.
- Classify hosted-sheet `URLError(timeout)` failures as `TIMEOUT` without regressing oversized-response handling.

Changes:
- Added SDK regression coverage proving `Client.from_config(...)` works with an empty config plus default provider environment variables for Google Sheets, Feishu Bitable, and MaybeSheet.
- Moved CLI-style default credential synthesis into the SDK registry path so descriptor-backed clients get the same behavior even when no explicit resolver is supplied.
- Tightened `TableURI` validation so local-style schemes such as `csv://` and `excel://` can no longer smuggle credential-bearing query or fragment parameters.
- Hardened both urllib transports to map `URLError(TimeoutError(...))` to `ConnectorErrorCode.TIMEOUT` while preserving `RESOURCE_LIMIT_EXCEEDED` for oversized responses and the existing secret-safe generic fallback for unexpected transport failures.

Verification:
- `uv run --frozen pytest packages/sdk/tests/test_client.py packages/sdk/tests/test_registry.py packages/contract/tests/test_uri.py packages/google_sheets/tests/test_connector.py packages/feishu_bitable/tests/test_connector.py -q`
- `uv run --frozen pytest packages/sdk/tests/test_client.py packages/sdk/tests/test_registry.py packages/google_sheets/tests packages/feishu_bitable/tests packages/maybe_sheet/tests packages/contract/tests packages/cli/tests/test_registry.py packages/cli/tests/test_configuration.py packages/cli/tests/test_credentials.py packages/cli/tests/test_configured_registry.py packages/cli/tests/test_model.py -q`

Results:
- Focused suite: 44 passed
- Broader provider/contract/CLI suite: 184 passed, 1 skipped
