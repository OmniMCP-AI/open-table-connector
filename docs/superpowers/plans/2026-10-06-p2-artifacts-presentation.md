# P2 Artifacts and Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export editable DOCX/PPTX tables through OfficeCLI and present local/MaybeSheet spreadsheet snapshots without giving OfficeCLI ownership of spreadsheet writes.

**Architecture:** Optional neutral artifact contracts feed a lazy SDK facade and optional physical OfficeCLI adapter. Views/watch use disposable snapshots, while rich XLSX export delegates to the R2 Excelize profile.

**Tech Stack:** Python/argparse, existing SDK source collection, OfficeCLI process protocol, installed supported browser for PNG, OOXML/ZIP inspection, pytest. Do not add a custom renderer or legacy converter.

**Spec:** [Sections 4, 8, 9 and 12; A7/A8](../specs/2026-10-06-cli-and-office-artifacts-p0-p2-design.md).

## Global Constraints

All [index constraints/interfaces](2026-10-06-cli-and-office-artifacts-p0-p2.md) apply. Native DOCX/PPTX tables only; legacy DOC/PPT/XLS rejected. OfficeCLI never writes authoritative spreadsheets. Create-only artifact destinations, explicit template copy, canonical URLs, separate semantic/visual evidence and no implicit install/update.

## Review Focus

- Package absent or binary unavailable must not break ordinary table commands: O1/O2.
- Delimited data/Unicode/formula-looking strings must not be reparsed by document convenience syntax: O2.
- A successful OfficeCLI process may contain dropped-property warnings: O2 rejects incomplete writes before publication.
- Screenshot/remote export may be stale or blank: O3 records freshness and validates pixels/selection.
- Reused PID/occupied port/browser edits must not affect unrelated processes or authoritative files: O4.

## Task O1: Optional Contracts, Adapter Protocol and Packaging

**Files:** Create `packages/artifacts/pyproject.toml`, `README.md`, `LICENSE`, `src/open_table_connector/artifacts/{__init__.py,py.typed,model.py,protocols.py,schemas/export.json}` and `tests/test_model.py`; create corresponding `packages/officecli/pyproject.toml`, `README.md`, `LICENSE`, `src/open_table_connector/officecli/{__init__.py,py.typed,plugin.py}`; update root `pyproject.toml`, `uv.lock`, `scripts/check_package_boundaries.py`, `scripts/check_package_metadata.py`, `scripts/check_package_independence.py`, `specification/conformance/universal/test_package_boundaries.py` for the new distributions.

**Interfaces:** Neutral frozen `ExportRequest(source_uri: str, destination_uri: str, engine: str, spec: Mapping[str, object])`, `ViewRequest(source: TargetSelector, mode: str, destination_uri: str | None, selector: Mapping[str, object])`, `WatchRequest(action: str, source: TargetSelector | None, session_id: str | None, read_only_required: bool=False)`. All structured fields validate through closed schemas.

`ArtifactValue` carries actual URI/media type/hash, source schema/snapshot metadata, engine/version, object mappings, display policy and coverage. `ViewValue` carries outputs (URI/media/hash), source/snapshot identity, renderer/browser/font diagnostics and visual coverage. `WatchValue` carries session ID, state, optional URL, source/snapshot hashes, freshness, editability, persistence and owned process identity. Existing `OperationResult` wraps these in SDK; neutral models do not import it.

`ArtifactAdapter` exposes `describe() -> Mapping[str, object]`, `create_table(document_path: Path, rows: Sequence[Sequence[str]], spec: Mapping[str, object]) -> Mapping[str, object]`, `observe_document(document_path: Path, selectors: Sequence[Mapping[str, object]]) -> Mapping[str, object]`, `render(snapshot_path: Path, request: ViewRequest) -> Mapping[str, object]`. Return provider-neutral evidence and raise safe contract errors. Register physical adapters under `open_table_connector.artifact_adapters.v1`; validate duplicate names. No file URI route collision with table providers.

- [x] Add `test_export_spec_closed_and_format_matches`, `test_legacy_extensions_reject`, `test_display_defaults_deterministic`, `test_asset_path_traversal_reject`, `test_optional_artifacts_not_imported_by_core`, `test_duplicate_artifact_adapter_reject`.
- [x] Run model and package-boundary tests red. Missing optional imports are expected only at feature use, never core import.
- [x] Implement models, format-discriminated layout schemas and neutral protocol. DOCX/PPTX display defaults are deterministic and assets stay explicit.
- [x] Add package metadata and boundary rules for artifacts and OfficeCLI; refresh lock and run frozen model/boundary tests green. Commit O1 files: `feat: define optional artifact export and presentation contracts`.

## Task O2: Qualified OfficeCLI Export, Excelize Export Routing and SDK Facade

**Files:** Create `packages/officecli/src/open_table_connector/officecli/{process.py,document.py,observe.py,capabilities.py}`, `tests/test_process.py`, `tests/test_document.py`, `tests/fixtures/protocol/`; create `packages/sdk/src/open_table_connector/sdk/artifacts.py`, `tests/test_artifacts.py`; update SDK `client.py` with lazy `artifacts()`; create `packages/cli/src/open_table_connector/cli/artifact_commands.py`, `tests/test_artifact_export.py`; update CLI parser/dispatcher and docs.

**Interfaces:** `run_officecli(argv: Sequence[str], *, input_json: object | None, timeout_seconds: float, max_output_bytes: int) -> ProcessResult` captures exit/stdout/stderr/truncation without a shell. `ProcessResult` is defined in `process.py`; no caller parses text errors as success. `ArtifactAccess.export(request: ExportRequest) -> OperationResult[ArtifactValue]` uses SDK source collection and adapter evidence. Register export with D2 dispatcher and D1 schemas.

Use finite defaults: 120-second one-shot deadline, 1 MiB combined diagnostic capture, and 16 MiB structured command payload; explicit deployment configuration may lower limits. Kill owned child trees on timeout and report state. Qualify OfficeCLI version `1.0.154` from the researched surface first; inspect actual version/help, capture sanitized fixtures and permit only qualified versions. A missing binary/version mismatch reports unavailable/unsupported. No automatic download/install/update. Qualify the actual `OFFICECLI_SKIP_UPDATE` and `OFFICECLI_NO_AUTO_RESIDENT` behavior before relying on it; block integration if the runtime cannot meet the no-update/no-implicit-writer contract.

- [x] Add process, capability, export routing and core-import tests.
- [x] Add native DOCX/PPTX table creation with deterministic display conversion and independent ZIP/XML evidence.
- [x] Add destination refusal and explicit unsupported XLSX routing behavior.
- [x] Run new modules red, then implement bounded argv process execution and native document creation. OfficeCLI/browser absence remains an explicit capability error.
- [x] Wire SDK/CLI artifact export; XLSX never falls back to OfficeCLI. Commit O2 files: `feat: export native document tables with verified artifact publication`.

## Task O3: Snapshot Views and Independent Presentation Evidence

**Files:** Create `packages/officecli/src/open_table_connector/officecli/views.py`, `tests/test_views.py`; extend SDK `artifacts.py` and CLI `artifact_commands.py`; create `packages/sdk/tests/test_artifact_views.py`, `packages/cli/tests/test_artifact_views.py`; update readiness/docs.

**Interfaces:** `ArtifactAccess.view(request: ViewRequest) -> OperationResult[ViewValue]` obtains `WorkbookSnapshot` through R4 for XLSX/MaybeSheet, or copies a committed DOCX/PPTX file with source hash. Adapter `render` operates only on owned disposable files. Qualify modes per format: html, screenshot, text, outline, stats, issues; separate schema validation descriptor. Selector schema differs by format; reject a PPTX `--page` used as an XLSX range.

- [ ] Add `test_source_hash_unchanged_all_modes`, `test_spreadsheet_render_copy_never_published`, `test_missing_browser_explicit`, `test_invalid_format_selector_rejected`, `test_remote_snapshot_freshness_carried`, `test_missing_remote_export_no_synthetic_snapshot`, `test_credentials_absent_from_renderer_environment`.
- [ ] Add real-runtime `test_png_nonblank_and_correct_selection` using contrasting cell/slide fixtures and pixel bounds, plus `test_html_references_resolve` for packaged/embedded assets. Assert output media/hash, correct number of selected outputs and no original-file mutation. Content hashes verify snapshot identity, not cross-version screenshot identity.
- [x] Run new modules red; implement view adapter and SDK presentation lifecycle. Missing renderers return explicit capability errors.
- [x] Run focused view tests green; actual browser/OfficeCLI evidence is unavailable, so A8 remains open. Commit O3 files: `feat: render bounded artifact snapshots through OfficeCLI`.

## Task O4: Explicit Preview Watch Lifecycle

**Files:** Create `packages/officecli/src/open_table_connector/officecli/watch.py`, `tests/test_watch.py`; create `packages/sdk/src/open_table_connector/sdk/preview_sessions.py`, `tests/test_preview_sessions.py`; extend `artifacts.py`, `artifact_commands.py`; create `packages/cli/tests/test_artifact_watch.py`; update operation schemas/docs/readiness.

**Interfaces:** `PreviewSessionStore(runtime_directory: Path)` persists versioned records; methods `create`, `load`, `update`, `remove` validate owned IDs/paths. `ArtifactAccess.watch(request: WatchRequest) -> OperationResult[WatchValue]` supports `start/status/refresh/stop`. `start_watch(snapshot: Path, *, read_only_required: bool) -> Mapping[str, object]` returns verified loopback URL and process identity. Identity includes PID plus creation identity/token; never trust a stale PID alone.

- [ ] Add `test_occupied_port_selects_another`, `test_nonloopback_bind_rejected`, `test_stale_pid_not_killed`, `test_stop_only_owned_processes`, `test_status_after_crash_has_no_live_url`.
- [ ] Add `test_preview_edits_discarded`, `test_read_only_required_rejects_unproven_mode`, `test_refresh_reexports_and_restarts`, `test_remote_revision_unavailable_reported`, `test_no_background_polling`, `test_stop_not_publish`.
- [x] Run new modules red and implement explicit runtime-directory/session records with owned IDs; no background polling or publish-on-stop.
- [x] Expose parser lifecycle actions and preview-copy/discard semantics. Actual renderer lifecycle remains gated on OfficeCLI/browser availability.
- [x] Run unit/CLI suites green and record unavailable runtime prerequisites. Commit O4 files: `feat: manage explicit disposable artifact preview sessions`.

**Handoff:** Artifact results retain actual media/hash, source identity and verification coverage. Watch process lifecycle is presentation infrastructure, not a P3 persistent mutation service. No current task grants OfficeCLI spreadsheet authoring authority.
