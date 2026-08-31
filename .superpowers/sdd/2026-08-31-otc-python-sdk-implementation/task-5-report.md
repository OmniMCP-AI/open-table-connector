# Task 5 Report

Date: 2026-08-31

Scope completed:

- Routed `inspect_endpoint()` through the SDK `Client`/`Table` path whenever the registry is descriptor-backed or otherwise explicitly SDK-enabled.
- Removed the broad `except Exception` suppression around SDK client construction in `read_endpoint()`. Legacy fallback now happens only for explicit OTC compatibility failures (`unsupported_capability` or `protocol_failure`).
- Preserved CLI import compatibility by keeping adapter-backed destination writes on the legacy read/write path, while still allowing SDK-only destinations to use `Client.materialize(...)`.
- Added regression coverage for descriptor-backed SDK delegation and for the narrowed fallback behavior.

Files changed:

- `packages/cli/src/open_table_connector/cli/pipeline.py`
- `packages/cli/tests/test_pipeline.py`

Verification:

- `uv run --frozen pytest packages/cli/tests/test_pipeline.py packages/cli/tests/test_configured_registry.py`
- `PYTHONPATH=/Users/admin/Code/GitHub/open-table-connector/.worktrees/critical-review-remediation uv run --frozen pytest packages/cli/tests`
- `uv run --frozen ruff check packages/cli/src/open_table_connector/cli/pipeline.py packages/cli/tests/test_pipeline.py`

Notes:

- The full CLI suite needs the repo root on `PYTHONPATH` because `packages/cli/tests/test_provider_independence.py` imports `scripts.check_canonical_literals` as a top-level module. That is an existing test invocation constraint, not introduced by this patch.
- I intentionally did not modify SQL, temporal, or provider implementation files in this remediation step.
