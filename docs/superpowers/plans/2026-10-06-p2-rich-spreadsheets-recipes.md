# P2 Rich Spreadsheets and Recipes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose existing Excelize-backed rich operations for local XLSX and MaybeSheet sheet-mode, with truthful qualification and replayable layout recipes.

**Architecture:** Shared schemas and buffered sessions route to local Excelize or existing MaybeSheet commands. Local rich files have an explicit profile; remote operations retain partial-effects semantics. OfficeCLI never writes either authoritative target.

**Tech Stack:** Existing Python Excelize `0.1.0` locked binding, existing MaybeSheet subprocess protocol, Pillow/OOXML readers for independent observations, SDK results, pytest.

**Spec:** [Sections 7 and 10; A9/A10/A12](../specs/2026-10-06-cli-and-office-artifacts-p0-p2-design.md).

## Global Constraints

All [index constraints/interfaces](2026-10-06-cli-and-office-artifacts-p0-p2.md) apply. Required providers: local XLSX and MaybeSheet sheet-mode. No new engine/server features. Local profile `rich-artifact/1.0`; MaybeSheet stays `general/1.0`; strict/general legacy local behavior unchanged. Preserve stable IDs, native units, explicit formulas and partial/unknown receipts.

## Review Focus

- Python binding method presence does not establish remote exposure or round-trip support: R1/R4.
- Image bytes, dimensions and anchors can change independently: R2/R3 independent observations.
- Multi-command remote failure can occur after object allocation: R3 preserves IDs and blocks retry.
- Base/Sheet mixed workbooks and stale worksheet generations: R3/R5 reject wrong targets and preserve Base.
- Recipes cannot safely translate Excel character widths into remote pixels: R5 rejects incompatible units.

## Task R1: Rich Contracts and Qualification Inventory

**Files:** Create `packages/spreadsheets/src/open_table_connector/spreadsheets/rich.py`, `schemas/rich-objects.json`; update `operation_catalog.py`, `capabilities.py`; create `packages/spreadsheets/tests/test_rich_contract.py`; create `specification/conformance/spreadsheets/rich_cases.py`, `fixtures/rich-qualification.json`; create `docs/spreadsheet-rich-readiness.md`.

**Interfaces:** Produce frozen `RichObjectRequest(operation_id: str, target_key: str, arguments: Mapping[str, object])`, `ObjectObservation(object_id: str, kind: str, fields: Mapping[str, object], coverage: tuple[str, ...], content_hash: str | None)`, and `RichQualification(provider_id: str, operation_id: str, options_schema: Mapping[str, object], status: str, evidence: tuple[str, ...], reason: str | None)`. Status is `qualified` or `blocked`. Existing image operation wire fields are preserved; typed objects normalize to existing `Change` records. Qualified object operations use `<kind>.create/read/list/delete` only where actually supported; existing `image.insert/read/list/delete` names remain unchanged.

- [x] Read installed binding signatures/types and existing MaybeSheet help/protocol with byte-capped output. Record versions and exact API/command mapping for images, charts, shapes, native tables, pivots, comments, validation and conditional formatting. This is read-only discovery; no engines were installed or updated.
- [x] Add `test_unknown_rich_option_rejected`, `test_qualification_does_not_advertise_blocked`, `test_image_contract_preserves_existing_wire`, `test_missing_remote_operation_not_inferred_from_local`, `test_rich_contract_imports_no_provider`.
- [x] Run `pytest packages/spreadsheets/tests/test_rich_contract.py`; initial run failed on the intentionally missing contract.
- [x] Implement schemas with exact typed arguments for admitted existing APIs, named provider-only options and strict validation. Populate an initially blocked qualification manifest and readiness matrix.
- [x] Run the module and D2 schema-example parity tests; all pass with blocked operations undiscoverable as supported. Commit R1 files: `feat: define rich spreadsheet contracts and qualification inventory`.

## Task R2: Local Excelize Image Workflow and Verified Publication

**Files:** Create `packages/local_files/src/open_table_connector/local_files/excelize_workbook.py`, `excelize_objects.py`, `rich_observe.py`; update `spreadsheet_workbook.py` only at explicit profile selection and shared coordination integration; update SDK `workbook.py` and CLI `spreadsheet_commands.py` to allow the new profile without changing defaults; create `packages/local_files/tests/test_excelize_rich_workbook.py`, `test_excelize_rich_images.py`; extend `packages/cli/tests/test_spreadsheet_commands.py`; update qualification/readiness files from R1.

**Interfaces:** `ExcelizeSpreadsheetProvider` implements existing bind/preflight/commit/observe protocol. `observe_rich_xlsx(data: bytes, selectors: Sequence[Mapping[str, object]], limits: object) -> tuple[ObjectObservation, ...]` reads raw archive/XML and existing independent decoders without resaving. `apply_excelize_object(book: object, change: Change) -> Mapping[str, object]` dispatches a closed schema-validated operation set. Initially register image insert/list/read/delete; return IDs based on serialized object relationships with explicit stability scope, not unrelated process counters.

- [x] Add `test_rich_profile_selects_excelize_only`, `test_general_and_literal_profiles_unchanged`, `test_cli_explicit_rich_profile`, `test_png_jpeg_original_bytes_and_anchor`, `test_image_delete_preserves_other_objects`, `test_reopen_matches_retained_intent`; assert exact media bytes/hash, worksheet binding/anchor and declared sizing observations. CLI `--profile rich-artifact/1.0` reaches the existing provider path; omission retains the old default.
- [ ] Add `test_formula_like_text_and_leading_zero_stay_literal`, `test_null_empty_false_zero_preserved`, `test_unsupported_option_has_no_destination_effect`, `test_rich_chart_never_roundtrips_through_general_writer` using an existing supported chart fixture.
- [ ] Add `test_competing_creators_one_winner`, `test_stale_template_rejected`, `test_verification_failure_never_publishes`, `test_cleanup_failure_retains_committed_receipt`; reuse current publication test patterns rather than replacing them.
- [x] Run the two new modules; initial run failed on the missing profile support.
- [x] Implement explicit rich profile selection over the existing Excelize-backed provider and independent serialized image observation; retain legacy tests and no OfficeCLI fallback.
- [x] Run new modules plus existing `test_spreadsheet_provider.py`, `test_spreadsheet_verify.py`, `test_excel_formula.py`; all pass. Commit R2 files: `feat: add verified Excelize rich workbook image operations`.

## Task R3: MaybeSheet Shared Images and Remote Effects

**Files:** Update `packages/maybe_sheet/src/open_table_connector/maybe_sheet/spreadsheet.py` and existing provider catalog registration; create `packages/maybe_sheet/tests/test_rich_images.py`, `tests/fixtures/rich-image-protocol.json`; extend `specification/conformance/spreadsheets/rich_cases.py`; update qualification/readiness matrix.

**Interfaces:** Keep existing image arguments and command compiler; adapt results to R1 observations while preserving raw safe receipt evidence. `image.delete` continues requiring `picture_id`; PNG/JPEG insertion retains 8 MiB and current anchor-only sizing restrictions. No new server command is defined by this plan.

- [x] Add recorded tests `test_sheet_engine_required`, `test_mixed_base_sheet_unchanged`, `test_image_bytes_anchor_and_picture_id`, `test_explicit_size_rejected_before_dispatch`, `test_eight_mib_boundary`.
- [ ] Add `test_multicommand_requires_allow_partial`, `test_timeout_after_insert_retains_id_and_unknown`, `test_unknown_commit_blocks_retry`, `test_cas_idempotency_flags_rejected`; assert exact commit state and dispatched-command count, including zero on preflight rejection.
- [x] Run `pytest packages/maybe_sheet/tests/test_rich_images.py`; initial run failed before the new recorded module existed.
- [x] Reuse the existing command compiler/transport and shared schemas with credential-safe recorded fixtures; no local behavior is inferred for remote support.
- [x] Run the new recorded MaybeSheet module (`5 passed`) and existing suites. Live disposable evidence is unavailable, so A10 remains pending and the readiness matrix records MaybeSheet image operations as blocked. Commit R3 files: `feat: align MaybeSheet rich image observations and capability gates`.

## Task R4: Remaining Existing Object Families and Snapshot Contract

**Files:** Extend local `excelize_objects.py`, `rich_observe.py`; extend MaybeSheet `spreadsheet.py` only for already exposed qualified commands; extend R1 schemas; create `packages/local_files/tests/test_excelize_rich_objects.py`, `packages/maybe_sheet/tests/test_rich_objects.py`, `specification/conformance/spreadsheets/test_rich_objects.py`; create `packages/spreadsheets/src/open_table_connector/spreadsheets/snapshots.py`, `packages/sdk/src/open_table_connector/sdk/snapshots.py`, `packages/sdk/tests/test_workbook_snapshots.py`; update readiness matrix.

**Interfaces:** `WorkbookSnapshot(uri: str, source: TargetSelector, content_hash: str, captured_at: str, provider_revision: str | None, consistency: str)` lives in the spreadsheet extension, not SDK, so providers can return it without reverse imports. `capture_workbook_snapshot(client, target, directory) -> OperationResult[WorkbookSnapshot]` captures a closed local file or existing MaybeSheet export. Consistency is `revision_bound` or `revision_unavailable`; no invented revision. Export absence yields unsupported, never a reconstructed workbook labeled an export.

- [ ] For each family in order (charts, shapes, native tables, pivots, comments, validation, conditional formatting), freeze existing option mapping from R1. Record blocked remote families with concrete absence/rejection evidence; do not guess endpoints.
- [ ] Add parameterized `test_object_create_reopen_observe`, `test_object_options_preflight`, `test_unrelated_parts_preserved`, `test_unknown_type_no_fallback` with a fixture per admitted family. Validate content and references independently, including pivot cache consistency and validation/formula references. For unsupported families assert discoverability is unsupported and dispatch count is zero.
- [ ] Run object modules; new admitted behavior must fail before its mapping. Implement one family's mapping/readback at a time; rerun and commit each accepted family with its updated qualification row. Do not weaken observation checks to admit a family.
- [x] Add `test_snapshot_local_hash_unchanged`, `test_remote_snapshot_without_revision_is_marked`, `test_export_unavailable_not_synthesized`, `test_snapshot_credentials_redacted`, `test_snapshot_source_changes_detected_when_revision_available`.
- [x] Run snapshot tests red; implement `capture_workbook_snapshot` with finite existing limits and provider export semantics, then run green. No engine write or local-to-remote upload is part of capture. Commit snapshot files: `feat: expose verified workbook snapshots for presentation`.
- [ ] Run shared rich conformance plus existing spreadsheet layout/operations suites. Update the matrix with exact versions, fixtures and current qualified/blocked subsets; A9/A10 do not claim unsupported families passed.

## Task R5: Observed Layout Recipe Export and Apply

**Files:** Create `packages/spreadsheets/src/open_table_connector/spreadsheets/recipes.py`, `schemas/recipe.json`; create `packages/sdk/src/open_table_connector/sdk/recipes.py`; create `packages/cli/src/open_table_connector/cli/recipe_commands.py`; update CLI parser/dispatcher; create `packages/spreadsheets/tests/test_recipes.py`, `packages/sdk/tests/test_recipes.py`, `packages/cli/tests/test_recipe_commands.py`; update CLI/agent docs and reference checker.

**Interfaces:** `LayoutRecipe(schema: str, version: str, requirements: tuple[str, ...], operations: tuple[RichObjectRequest, ...])`; `parse_recipe(payload: object) -> LayoutRecipe`. `export_recipe(client, target, selectors: Sequence[Mapping[str, object]], *, allow_incomplete: bool=False) -> OperationResult[LayoutRecipe]`; `apply_recipe(client, target, recipe, options) -> OperationResult[object]`. The envelope is exactly spec section 10, `otc.spreadsheet-recipe/1.0`, version `1.0`. `selectors` names bounded ranges/fields/config/object IDs; objects require existing bindings and do not recreate absent content.

- [x] Add `test_recipe_roundtrip_closed_envelope`, `test_10001_operations_reject`, `test_requirements_recomputed_not_trusted`, `test_unsupported_property_rejects_entire_preflight`, `test_no_values_formulas_assets_in_export`.
- [ ] Add `test_export_uses_fresh_observation`, `test_missing_observation_rejects_by_default`, `test_allow_incomplete_reports_omissions`, `test_character_width_not_converted_to_pixels`, `test_missing_object_binding_rejected`, `test_dry_run_no_mutation`, `test_remote_partial_flag_preserved`.
- [x] Run the three new modules red. Implement parser, observed export and apply through D2 dispatcher/current sessions; retain per-operation identity and provider observation coverage. `allow_partial` never drops unsupported properties.
- [x] Add `otc spreadsheet recipe export` with explicit target/selector input and `otc spreadsheet apply --spec FILE`; use D1 limits/parser. Existing batch envelope and actions remain unchanged.
- [x] Run recipe suites and the CLI reference checker. Commit R5 files: `feat: export and apply capability-gated layout recipes`.

**Handoff:** R2 creates local rich artifacts; R3/R4 preserve remote semantics; R4 supplies O3 snapshot input; R5 supplies MCP recipe execution. Do not advertise complete remote feature parity unless each row is qualified.
