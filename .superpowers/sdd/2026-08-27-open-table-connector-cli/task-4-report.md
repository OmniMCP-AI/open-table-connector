# Task 4 implementation report

Status: complete

Changed files:

- `packages/cli/src/open_connectors/cli/adapters.py`
- `packages/cli/src/open_connectors/cli/registry.py`
- `packages/cli/tests/test_registry.py`

Commits:

- `433dab9 feat: add otc connector registry`

Tests and results:

- `uv run python -m pytest packages/cli/tests/test_registry.py -q` — 5 passed
- `uv run python -m pytest packages/cli/tests -q` — 18 passed
- `uv run python -m pytest packages/google_sheets/tests packages/feishu_bitable/tests packages/maybesheet/tests -q` — 15 passed
- `uv run python -m compileall -q packages/cli/src/open_connectors/cli` — passed
- `git diff --check` — passed

Concerns:

- The task brief's exact command `uv run pytest ...` could not spawn `pytest` in this environment; the equivalent `uv run python -m pytest ...` command was used successfully.
- Local inspection/write receipts use the existing neutral contract with a stable local marker; local file contents and credentials are not included in diagnostics.

Deviations:

- Added two deterministic registry adapter tests beyond the three brief examples to cover injected Google transport translation, CLI-token precedence, and unsupported HTTPS host rejection.

## Review-fix round

Status: complete

Changes:

- Fixed Google Sheets and Feishu Bitable inspection adapters to retain `options` while constructing their credentialed provider connectors.
- Removed unsupported `sheet.read` and `sheet.inspect` capabilities from MaybeSheet. The Task 4 `maybe://DOCUMENT/TARGET` grammar dispatches base-table reads/inspection only, so unsupported sheet capability requests now fail in the registry before process I/O.
- Added regression coverage for both injected inspection transports and MaybeSheet capability rejection/process-call absence.

Commit:

- `b45ce3c fix: correct task 4 adapter capabilities`

Tests and results:

- Red regression run: `uv run python -m pytest packages/cli/tests/test_registry.py -q` — 5 passed, 3 failed with the two `UnboundLocalError` inspection failures and the false-positive MaybeSheet capability assertion.
- Green focused run: `uv run python -m pytest packages/cli/tests/test_registry.py -q` — 8 passed
- `uv run python -m pytest packages/cli/tests -q` — 21 passed
- `uv run python -m pytest packages/google_sheets/tests packages/feishu_bitable/tests packages/maybesheet/tests -q` — 15 passed
- `git diff --check` — passed

Concerns:

- MaybeSheet sheet-mode capabilities remain intentionally unavailable because the specified CLI grammar provides only base-table dispatch; no process call is made for rejected sheet capability requests.
