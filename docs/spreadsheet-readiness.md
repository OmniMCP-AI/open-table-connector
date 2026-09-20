# Spreadsheet readiness evidence

Status: 2026-09-14. The implemented local artifact and supported workbook operations
pass the recorded regression and distribution gates. **Maybe Sheet's required
typed-value/empty-string baseline remains blocked by the upstream CLI contract.**
This is not a complete spreadsheet catalog release or a FinClaw cutover.

Final source revision: `dea43f785833fc83ad9ac7bf8c5c03b5e37292b7`.
The final tests and rebuilt wheels used the exact source committed there; this
following documentation update changes no implementation. Environment: macOS
26.6.2 arm64, Python 3.11.15, 3.12.13, 3.13.13 and 3.14.4. Baseline
`8e1347bccd6ba2593be3eab1b5ab15763fbfa3d8`: **1,397 passed, 3 skipped**.

## Implemented behavior

- One private provider-neutral session buffers Excel/Maybe changes using the
  existing `bind`, `preflight`, `commit`, `observe` seam. SDK operations adapt
  existing results; providers do not import the SDK for workbook storage.
- Inputs and receipt/error details are frozen. Planned results retain their
  identity after commit. Dry-run retains pending edits; close never saves.
  Concurrent writes, reads or close during a write reject. Write flags require
  real booleans. Partial/unknown effects block retry until known reconciliation
  or rebind. Dirty verification rejects rather than verifying an older snapshot.
- Worksheet generations invalidate old sheet/range/Formula handles after
  delete/recreate or rename. Strict literal sessions reject a second write;
  clean general sessions can return their captured no-op result.
- Local `.xlsx` writes stage, close, independently verify and publish with
  exclusive creation or guarded general replacement. Local Formula writes share
  file coordination and invalidate stale workbook sessions. Existing destinations
  and postcommit artifacts survive failures; optional diagnostic retention has
  separate error evidence.
- The independent verifier checks bounded raw archive/XML and decoded content
  against retained intent. Reopened strict verification needs that expectation.
  Original PNG/JPEG bytes, anchors, dimensions, literal cells and declared
  layout are checked. General edits preserve supported objects and reject unsafe
  unsupported parts and structural reference changes. Existing pivot/cache parts
  reject before editing because cache-preservation parity is not yet proven.
- Maybe uses the actual `mbs 0.28.4`, JSON contract `1.0` commands. It validates
  Sheet engines/gids, preserves Base worksheets, retains known IDs/effects,
  rejects unsupported dirty previews, and requires partial opt-in beyond a
  tested single-command boundary. Reconciliation is observation only.
- CLI batch/standalone mutations use the same SDK session and existing result
  JSON. Closed, bounded command files use existing operation verbs/arguments;
  standalone mutations commit once. Provider discovery has matching dispatch
  evidence. Google retains its prior behavior and is deferred from this work.

Usage, native units and per-operation restrictions are in the
[spreadsheet user guide](user-guide/spreadsheet-operations.md).

## Validation ledger

Commands without an explicit environment prefix use Python 3.14.4 in the shared
worktree. Counts describe the named runs; the four full runs below cover the final source.

| Run | Exact command | Observed result |
| --- | --- | --- |
| Baseline | `uv run --all-packages --frozen python -m pytest -q` | 1,397 passed, 3 skipped, 45.72s |
| Universal conformance after capability binding updates | `uv run --all-packages --frozen python -m pytest specification/conformance/universal -x -q` | 310 passed, 98.87s |
| Session/stale-handle/sealed and local integration | `uv run --all-packages --frozen python -m pytest packages/sdk/tests/test_workbook_session.py packages/spreadsheets/tests/test_session.py packages/local_files/tests/test_spreadsheet_provider.py specification/conformance/spreadsheets/test_operations.py -q` | 43 passed, 1.74s |
| Maybe recorded/provider suite | `uv run --all-packages python -m pytest packages/maybe_sheet/tests -q --tb=short` | 121 passed, 2 skipped, 1.07s |
| Authorized disposable Maybe live contract | `OTC_TEST_MBS_ENABLED=1 uv run --all-packages python -m pytest packages/maybe_sheet/tests/test_spreadsheet.py::test_live_disposable_sheet_contract -q --tb=no` | 1 passed, 62.76s; disposable workbook cleanup succeeded |
| Clean installed-wheel regression | `uv run --all-packages --frozen python scripts/check_package_independence.py` | The initial run exposed empty-string readback loss. After normalization, fresh venv installation, PNG publish, verify, receipt JSON and reopened empty-string readback all passed; `--build` rerun exited 0. |
| Changed-source formatting/static checks | Focused `ruff check` on changed session/SDK/CLI/conformance sources; `git diff --check` | Passed in the focused runs |
| Python 3.11.15 full suite | `UV_PROJECT_ENVIRONMENT=/tmp/otc-spreadsheet-3.11 uv run --python 3.11 --all-packages --frozen python -m pytest -q` | 1,518 passed, 4 skipped, 123.32s |
| Python 3.12.13 full suite | `UV_PROJECT_ENVIRONMENT=/tmp/otc-spreadsheet-3.12 uv run --python 3.12 --all-packages --frozen python -m pytest -q` | 1,518 passed, 4 skipped, 126.65s |
| Python 3.13.13 full suite | `UV_PROJECT_ENVIRONMENT=/tmp/otc-spreadsheet-3.13 uv run --python 3.13 --all-packages --frozen python -m pytest -q` | 1,518 passed, 4 skipped, 126.77s |
| Python 3.14.4 full suite | `UV_PROJECT_ENVIRONMENT=/tmp/otc-spreadsheet-3.14 uv run --python 3.14 --all-packages --frozen python -m pytest -q` | 1,518 passed, 4 skipped, 129.89s |
| Final built distribution/clean install | `uv run --all-packages --frozen python scripts/check_package_independence.py --build` | Passed; 15 wheels built; installed local image, verification, receipt and empty-string roundtrip passed |
| Wheel smoke | `uv run --all-packages --frozen python scripts/smoke_wheels.py --build` | Passed; final provider/session wheel contents also compared byte-for-byte to source |
| Repository Ruff gate | `uv run --frozen ruff check scripts specification/conformance/universal/test_package_boundaries.py` | Passed; all changed Python files also pass Ruff |
| Repository typing | `uv run --frozen mypy scripts` | Passed, 6 source files |
| Metadata, boundaries, canonical literals | `uv run --all-packages --frozen python scripts/check_package_metadata.py`; same prefix for `check_package_boundaries.py` and `check_canonical_literals.py` | All passed |
| Whitespace | `git diff --check` | Passed |

The earlier full implementation run exposed manifest fixture mismatches rather
than a baseline waiver. Universal capability bindings now execute real isolated
XLSX operations; the 310-test rerun passed. Final runs include subsequent
review fixes. An intermediate concurrent Python 3.14 run exceeded an existing
managed-operation test’s one-second deadline (1 failed, 1,512 passed, 4 skipped).
The unchanged focused rerun passed, and both the full standalone rerun and final
four-version run passed without weakening that bound. Each final full run emits
one intentional duplicate-ZIP-member warning from the corruption fixture; opt-in
service tests account for the four skips. Maybe live acceptance was run separately.

## Maybe typed-value gate

## Unified Table financial-layout gate

The unified `Table.layout()` implementation is gated separately from the
existing workbook completion evidence. The installed MaybeSheet CLI is
`0.29.0`; its help exposes worksheet configuration and style write commands,
but this checkout has no authenticated workbook response proving independent
style/config reads, default or inherited style evidence, stable sheet identity,
or reopen persistence. The recorded qualification manifest is
`packages/maybe_sheet/tests/fixtures/layout-protocol.json`.

Until a disposable authenticated probe supplies versioned command mappings and
read/write/reopen responses, OTC must not advertise the new MaybeSheet layout
capabilities. The missing upstream evidence covers `range.style.read`,
`worksheet.config.read`, alignment, borders, complete Excel number/date/
currency/accounting formats, text-layout modes, metadata-only sheet binding,
and persisted physical evidence. This is an explicit external gate; local
contract and Excel implementation work may proceed, but it is not a positive
MaybeSheet acceptance result.

The authorized live probe wrote `[['=literal', ''], ['b', 2]]`. Readback reported
value types `[['string', 'blank'], ['string', 'string']]` and values
`[['=literal', ''], ['b', '2']]`: numeric `2` became text, and readback classified the empty literal
as blank. Installed `mbs 0.28.4 range write --help` exposes no typed-cell or
`USER_ENTERED`/`value_input_option` option to preserve those distinctions.

The adapter therefore rejects numeric, Boolean, date/time and empty-string
writes before mutation (`test_reject_known_raw_type_loss_before_dispatch`). This
is an explicit **required baseline gap**, not unsupported optional catalog work.
The live test establishes the supported literal-string/lifecycle/style/dimension/
merge/sort/Formula/image behavior and Base preservation; it does not remove that
gate. PNG base64 readback was exact. No unsupported conversion fallback is used.

## R1–R16 evidence map

The rows identify implemented checks and tests. A mapped test is evidence, not a
claim of exhaustive testing of every possible XLSX input. Final regression and
distribution gates passed; restrictions remain explicit in the user guide.

| Requirement | Implemented evidence | Acceptance status |
| --- | --- | --- |
| R1 ordered sheets/names | `test_local_general_operation_save_reopen`; independent fixture ordered-sheet checks | Mapped tests and final matrix passed |
| R2 literal cells/empty/Unicode/bounds | `test_literal_layout_images_empty_and_receipt_roundtrip`, `test_empty_literal_coverage`, `test_cells_limit_exact_boundary_and_invalid_manifest` | Mapped tests and rebuilt-wheel empty-string regression passed |
| R3 native styles/layout | `test_style_and_native_layout_tampering`, `test_style_only_intent_is_verified`, literal layout fixture | Mapped tests and final matrix passed |
| R4 merges/no hidden interior values | `test_shared_string_reference_and_hidden_merge_value`; merge/unmerge conformance | Mapped tests and final matrix passed |
| R5 exact PNG/JPEG/media/anchors | `test_independent_image_bytes_anchor_and_limits`, `test_jpeg_bytes_are_not_transcoded` | Mapped tests and rebuilt-wheel gate passed |
| R6 finite parsing/decompression/image limits | `test_all_archive_and_text_limits_exact_boundary`, `test_image_limit_exact_boundaries`, `test_forged_size_with_matching_prefix_crc_cannot_hide_expansion` | Boundary/corruption tests and final matrix passed |
| R7 exclusive publication | `test_competing_creator_cannot_delete_winner`, `test_two_creators_have_exactly_one_winner`, `test_stale_session_and_symlink_fail_without_modification` | Mapped tests and final matrix passed |
| R8 no formulas/calculation properties in literal artifacts | `test_corruption_fails_closed`, `test_ragged_matrix_and_literal_formula_rejected_before_mutation` | Mapped tests and final matrix passed |
| R9 canonical intent/byte hashes and existing receipts | `test_literal_layout_images_empty_and_receipt_roundtrip`, independent image hashes, clean-install result serialization | Mapped tests and final matrix passed |
| R10 ownership/cleanup/truthful postcommit failures | `test_failure_before_publish_keeps_quarantine`, `test_postcommit_cleanup_failure_keeps_destination_and_freezes`, `test_failure_retention_failure_is_reported` | Mapped tests and final matrix passed |
| R11 independently retained intent | `test_independent_fixture`, `test_default_reopen_verifies_explicit_strict_manifest` | Mapped tests and final matrix passed |
| R12 raw structural rejection | `test_duplicate_member_and_orphan_part`, `test_relationship_id_external_and_missing_target`, `test_closed_raw_metadata_and_cell_schema` | Mapped tests and final matrix passed |
| R13 independent decoded comparison | `test_limit_and_expectation_mismatch`, style/layout/media corruption fixtures | Mapped tests and final matrix passed |
| R14 stable bounded error evidence | SDK unknown receipt retention, lifecycle rejection and local failure-retention tests | Mapped tests and final matrix passed |
| R15 clean installation/discovery | 310 universal cases, actual advertised workbook binding invocation, extended clean-venv image smoke | Rebuilt-wheel gate passed |
| R16 legacy Table/Formula/temporal/provider compatibility | Baseline recorded; universal rerun green; final full supported-Python runs coordinated separately | Final compatibility matrix passed |

## Separate delivery gates

| Gate | State |
| --- | --- |
| Shared SDK/session and CLI implementation | Implemented; focused tests pass |
| Local literal artifact R1–R16 | Mapped R1–R16 tests and full/distribution gates passed for supported literal profile |
| General Excel baseline/preservation | Supported operations pass full regressions; unsafe parts and structural edits reject; catalog gaps remain |
| Maybe recorded commands | Passed recorded run for supported commands |
| Maybe authorized live commands | Passed disposable live run for supported subset |
| Maybe required typed/empty-value baseline | **Blocked upstream; provider release gate remains closed** |
| Complete optional catalog CRUD | Unsupported/deferred rows remain in user guide; no completeness claim |
| Distribution and supported-Python matrix | Passed: all four Python versions and rebuilt-wheel/clean-install gates |
| FinClaw integration/cutover | Outside this implementation; not claimed |

## Typed RAW follow-up (2026-09-14)

The CLI already sends native JSON values. Two upstream defects explain the observed
loss: Playground stringifies the value matrix (including null → empty string),
and SheetTable accepts only string values and classifies empty stored strings as
blank during readback. The earlier statement that every empty literal was physically
converted to a blank was stronger than the live evidence justified.

Source fixes are under review in [SheetTable #110](https://github.com/OmniMCP-AI/SheetTable/pull/110)
and [Playground #382](https://github.com/fastestai/fastestai-playground/pull/382).
SheetTable's real HTTP/save/reopen regression preserves numbers, booleans, literal
strings, empty strings and nulls; full Go API/test packages, targeted legacy
conversion/read tests and Go vet pass. The proxy's two isolated payload tests pass;
its complete dispatcher suite is blocked by the checkout's missing `audit` package.
The isolated tests replace only the unrelated audit-header dependency and do not
establish complete service integration.

Deploy storage first, then the proxy. The current deployed service still fails the
new opt-in gate, so OTC's rejection guard stays enabled. Run with `mbs 0.29.0` or a
compatible CLI supporting recoverable `workbook delete --mode mark`:

```sh
OTC_TEST_MBS_TYPED_RAW_ENABLED=1 uv run --all-packages --frozen python -m pytest \
  packages/maybe_sheet/tests/test_spreadsheet.py::test_live_typed_raw_range_contract -q
```

This gate owns a disposable Sheet workbook, writes through the CLI independently
of OTC's guard, checks value types/formulas, and marks the workbook deleted in
cleanup. Enable OTC typed writes only after deployed readback passes. Native
Python date/time serialization remains a separate unsupported input.

## Unified financial layout live gates (2026-09-20)

The shared Excel/MaybeSheet layout contract, independent observation decoder,
Excel physical reader, metadata-only Table facade and CLI read actions are
implemented and covered by offline tests. External acceptance remains closed
until a disposable authenticated MaybeSheet workbook and a real Excel
application/render service are available:

```sh
OTC_TEST_MBS_LAYOUT_ENABLED=1 uv run --all-packages --frozen python -m pytest \
  specification/conformance/spreadsheets/test_layout_live.py -k maybe -q
OTC_TEST_EXCEL_LAYOUT_RENDER_ENABLED=1 uv run --all-packages --frozen python -m pytest \
  specification/conformance/spreadsheets/test_layout_live.py -k excel -q
```

In this checkout both environment gates are disabled, so the live tests are
explicitly skipped and the release status is **not accepted**. No MaybeSheet
style/config read capability is advertised from the recorded `mbs 0.29.1`
help surface; unsupported operations return a capability error. No service
credentials, workbook data or fabricated application-render evidence is stored
in the repository.
