# Grid Formula Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement conforming sheet-mode formula read/set for Google Sheets, Maybe Sheet, and direct Excel; add calculated-value reads for Google and Maybe; add explicit recalculation for Maybe; and enable only the capabilities proven by each provider suite.

**Architecture:** Each provider owns a `FormulaConnectorExtension` adapter over its existing authenticated transport. Google uses native grid data and `RepeatCellRequest`; Maybe uses the canonical `mbs` process commands; Excel uses openpyxl formula cells plus locked, durable, atomic file replacement. All adapters return the Formula package's closed results and receipts, while the SDK bridge remains provider-agnostic.

**Tech Stack:** Python 3.11–3.14, existing Google HTTP transport, existing Maybe process transport, openpyxl 3.1 formula translator, POSIX file locking already used by local-files, PyArrow/Polars only for existing Table paths, pytest recording fakes, and the Formula conformance corpus.

**Spec:** `docs/superpowers/specs/2026-09-01-mode-aware-formula-extension-design.md`

**Prerequisite:** Complete `docs/superpowers/plans/2026-09-01-formula-extension-core.md` and keep its core verification gate green.

## Global Constraints

- This plan implements only grid targets. Do not create, read, update, or advertise field-formula capabilities here.
- Google, Maybe, and Excel must implement the same top-left copy-fill contract. Exact-text broadcast across a rectangle is a conformance failure.
- Google automatic calculation is not an explicit recalculation capability. Excel recalculation metadata is not execution evidence. Neither provider advertises grid recalculate.
- Excel Formula support applies only to an existing direct `.xlsx` workbook addressed by the `excel` provider. Managed temporal Excel remains formula-rejecting and unchanged.
- A Maybe sheet-mode expression may reference a base-mode worksheet. Preserve that native text exactly and record only `dependency_scope=provider_dynamic`.
- Provider capabilities stay unadvertised until Task 5, after all offline recording, preservation, safety, and conformance tests pass.
- Ordinary Google Table writes continue using `valueInputOption=RAW`; ordinary Excel Table writes continue forcing formula-prefixed strings to text.
- Set always performs a new formula-text read through the provider transport or a separately reopened workbook. A set acknowledgement is not verification.
- Resource limits apply to the provider request and are rechecked after parsing. Provider over-return is an operation failure, not silent truncation for formula maps.
- Work test-first. Each task ends with focused tests, `git diff --check`, and a Conventional Commit.

---

## File Map

### Shared grid-provider conformance

- `specification/conformance/formulas/grid_cases.py`
- `specification/conformance/formulas/test_grid_providers.py`
- `specification/conformance/formulas/test_grid_copy_fill.py`
- `specification/conformance/formulas/test_grid_recovery.py`
- Modify `specification/conformance/formulas/conftest.py`
- Modify `specification/conformance/formulas/support.py`

### Google Sheets

- `packages/google_sheets/src/open_table_connector/google_sheets/formula.py`
- `packages/google_sheets/tests/test_formula.py`
- Modify `packages/google_sheets/src/open_table_connector/google_sheets/connector.py`
- Modify `packages/google_sheets/src/open_table_connector/google_sheets/cli_adapter.py`
- Modify `packages/google_sheets/src/open_table_connector/google_sheets/__init__.py`
- Modify `packages/google_sheets/src/open_table_connector/google_sheets/manifest.json`
- Modify `packages/google_sheets/tests/test_connector.py`
- Modify `packages/google_sheets/tests/test_cli_adapter.py`
- Modify `packages/google_sheets/pyproject.toml`

### Maybe Sheet grid mode

- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py`
- `packages/maybe_sheet/tests/test_grid_formula.py`
- Modify `packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py`
- Modify `packages/maybe_sheet/src/open_table_connector/maybe_sheet/cli_adapter.py`
- Modify `packages/maybe_sheet/src/open_table_connector/maybe_sheet/identity.py`
- Modify `packages/maybe_sheet/src/open_table_connector/maybe_sheet/__init__.py`
- Modify `packages/maybe_sheet/tests/test_connector.py`
- Modify `packages/maybe_sheet/tests/test_cli_adapter.py`
- Modify `packages/maybe_sheet/pyproject.toml`

### Direct Excel grid mode

- `packages/local_files/src/open_table_connector/local_files/excel_formula.py`
- `packages/local_files/tests/test_excel_formula.py`
- Modify `packages/local_files/src/open_table_connector/local_files/excel_connector.py`
- Modify `packages/local_files/src/open_table_connector/local_files/cli_adapter.py`
- Modify `packages/local_files/src/open_table_connector/local_files/__init__.py`
- Modify `packages/local_files/tests/excel_fixtures.py`
- Modify `packages/local_files/tests/test_excel_writer.py`
- Modify `packages/local_files/tests/test_temporal_excel.py`
- Modify `packages/local_files/pyproject.toml`

### Discovery, metadata, and docs

- Modify `specification/conformance/universal/cases.py`
- Modify `specification/conformance/universal/test_discovery.py`
- Modify `specification/conformance/universal/test_package_metadata.py`
- Modify `packages/google_sheets/README.md`
- Modify `packages/maybe_sheet/README.md`
- Modify `packages/local_files/README.md`
- Modify root `README.md`
- Modify `uv.lock`

---

### Task 1: Add capability-selected grid fixtures and failure simulations

**Files:**
- Create the shared grid-provider conformance files.
- Modify Formula fixture files only to add provider-specific expected documents; do not alter the core semantics.

**Interfaces:**
- Produces recording transports/processes and workbook factories used by all three provider suites.
- Consumes `FormulaProviderCase`, `load_formula_cases()`, and `assert_grid_formula_conformance()` from the core plan.

- [ ] **Step 1: Write the recording fixtures and failing provider-case tests**

Create fixtures for:

- single-cell read/set;
- 2×3 relative, absolute, and mixed copy-fill;
- quoted/cross-worksheet reference;
- accepted provider function and external reference;
- sparse formula/value/blank/provider-error read;
- value observations with state and trigger;
- stale revision;
- same-key replay and conflict;
- timeout before dispatch, provider rejection, partial response, lost acknowledgement, readback mismatch, and unknown commit; and
- raw-expression markers in all evidence/error paths.

The expected expanded formulas are literal JSON fixture data. No fixture helper may import openpyxl's translator or provider adapter code to calculate expected values.

- [ ] **Step 2: Add failing matrix assertions**

~~~python
EXPECTED_GRID_CAPABILITIES = {
    "google_sheets": {
        "formula.grid.read/1.0",
        "formula.grid.set/1.0",
        "formula.grid.values.read/1.0",
    },
    "maybe_sheet": {
        "formula.grid.read/1.0",
        "formula.grid.set/1.0",
        "formula.grid.values.read/1.0",
        "formula.grid.recalculate/1.0",
    },
    "excel": {
        "formula.grid.read/1.0",
        "formula.grid.set/1.0",
    },
}
~~~

At this task the test must fail because provider cases do not yet exist. Do not change static provider advertisements.

- [ ] **Step 3: Run and verify red**

~~~bash
uv run --frozen python -m pytest specification/conformance/formulas/test_grid_providers.py specification/conformance/formulas/test_grid_copy_fill.py specification/conformance/formulas/test_grid_recovery.py -q
~~~

Expected: missing provider Formula extensions/cases.

- [ ] **Step 4: Commit the red conformance harness**

~~~bash
git add specification/conformance/formulas specification/fixtures/formulas
git commit -m "test: define grid formula provider matrix"
~~~

### Task 2: Implement Google Sheets grid Formula support behind disabled identities

**Files:**
- Create `packages/google_sheets/src/open_table_connector/google_sheets/formula.py` and `packages/google_sheets/tests/test_formula.py`.
- Modify Google connector/adapter/init/package metadata files, but do not modify capability tuples or manifest JSON yet.

**Interfaces:**
- Produces `GoogleSheetsFormulaExtension` and `GoogleSheetsCliAdapter.formula_extension_for()`.
- Consumes the existing `SheetsTransport`, access token, API endpoint, timeout, and `FormulaConnectorExtension` models.

- [ ] **Step 1: Write failing metadata binding and native-grid read tests**

Record exact calls. Binding issues:

~~~text
GET /v4/spreadsheets/{spreadsheetId}?fields=sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))
~~~

It requires exactly one name/ID match and binds numeric `sheetId`, title, spreadsheet ID, `google-sheets-a1`, effective capabilities, and a metadata hash revision.

Formula/value read issues one bounded grid-data request with the bound title and rectangle. Its field mask contains `userEnteredValue.formulaValue`, `effectiveValue`, and `effectiveFormat.numberFormat`; it does not use rendered strings to identify formulas. Test a literal `"=not-a-formula"` in `userEnteredValue.stringValue` and assert it is absent from `GridFormulaObservation.formulas`.

- [ ] **Step 2: Run focused tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py -q
~~~

- [ ] **Step 3: Implement bind, formula read, and calculated-value normalization**

Use conservative effective limits: 10,000 cells, 50,000 expression bytes, 8 MiB response, connector timeout. Details declare `mutation_atomicity=atomic`, `revision_enforcement=checked`, `idempotency_strength=reconciled`, no recalc scopes, and calculation state `provider_current`.

Normalize Google effective values by their single native branch (`numberValue`, `stringValue`, `boolValue`, or `errorValue`). Reject multiple branches, non-finite numbers, missing error type, and response coordinates beyond the requested rectangle as `PROTOCOL_FAILURE`. Date/time number formats produce a logical value with the native format type/pattern and finite serial.

- [ ] **Step 4: Write failing RepeatCell set/readback/reconciliation tests**

Set must send exactly:

~~~python
{
    "requests": [{
        "repeatCell": {
            "range": {
                "sheetId": 17,
                "startRowIndex": 1,
                "endRowIndex": 3,
                "startColumnIndex": 4,
                "endColumnIndex": 6,
            },
            "cell": {"userEnteredValue": {"formulaValue": "=B2+$C$1"}},
            "fields": "userEnteredValue.formulaValue",
        }
    }],
    "includeSpreadsheetInResponse": True,
    "responseRanges": ["Model!E2:F3"],
    "responseIncludeGridData": True,
}
~~~

to `POST /v4/spreadsheets/{spreadsheetId}:batchUpdate`. Assert the ordinary Table writer still sends `valueInputOption=RAW`. Treat the response grid as the provider-normalized expected copy-fill map, then require a new grid-data GET and compare every affected formula to that map. The shared golden corpus independently proves that Google's returned expansion obeys OTC copy-fill semantics. For a lost acknowledgement, perform one fresh GET; reconcile only when the top-left expression and complete affected formula population prove the requested fill, otherwise return `unknown` with no retry POST.

- [ ] **Step 5: Implement set with checked revisions and safe idempotency**

Before dispatch, compare a caller-supplied revision with a fresh bounded formula observation. Bind the idempotency key to the target, rectangle, dialect, expression hash, and expected-revision hash in `FormulaIdempotencyLedger`. Map a provider 400 syntax rejection to `INVALID_FORMULA` using only status/reason codes; never keep Google diagnostics that may echo text.

Set receipts include expression and readback hashes, affected cell count, `copy_fill_policy=top_left`, revision before/after, and `verification=formula_text_readback`. They do not include effective values or claim calculated-value verification.

- [ ] **Step 6: Add adapter forwarding, run focused tests, and commit**

`GoogleSheetsCliAdapter.formula_extension_for()` returns `CompositeFormulaConnectorExtension(grid=GoogleSheetsFormulaExtension(...), field=None)` over its already configured connector; it must not reacquire credentials from environment variables.

~~~bash
uv lock
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py packages/google_sheets/tests/test_connector.py packages/google_sheets/tests/test_cli_adapter.py -q
uv run --frozen ruff check packages/google_sheets
git diff --check
git add packages/google_sheets uv.lock
git commit -m "feat: implement Google grid formulas"
~~~

### Task 3: Implement Maybe Sheet grid Formula support behind disabled identities

**Files:**
- Create `packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py` and `packages/maybe_sheet/tests/test_grid_formula.py`.
- Modify Maybe connector/adapter/init/package metadata, but do not enable static Formula identities yet.

**Interfaces:**
- Produces `MaybeSheetGridFormulaExtension` and a generic `MaybeSheetCliAdapter.formula_extension_for()` that can later compose a field adapter.
- Consumes the existing `ProcessClient`, scoped credentials, timeout, and `_mbs_target()` helper.

- [ ] **Step 1: Write failing command-recording tests**

The adapter uses canonical JSON-output commands with credentials passed only through `ProcessClient.run(credentials=...)`:

~~~text
mbs worksheet list --uri <target> --output json
mbs formula read --target <target> --gid <gid> --range <A1> --output json
mbs formula set --target <target> --gid <gid> --range <A1> --expression <text> --language excel --idempotency-key <key> --verify --output json
mbs excel-worksheet read --uri <target> --gid <gid> --range <A1> --value-render-option UNFORMATTED_VALUE --output json
mbs formula recalculate --target <target> --gid <gid> [--range <A1>] --verify --output json
~~~

Append `--expected-revision` only when supplied. For worksheet and workbook scopes omit `--range` and preserve the effective scope reported by the result. Test exact argv, no token in argv/stdin/result repr, configured timeout, and strict result-envelope keys.

- [ ] **Step 2: Run focused tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py -q
~~~

- [ ] **Step 3: Implement worksheet binding and formula/value reads**

Bind an exact worksheet name or gid from `worksheet list`, preferring stable gid identity and preserving title only as display metadata. Reject missing/ambiguous matches and non-sheet targets. Effective details use `maybe-sheet-a1`, 10,000 cells, 64 KiB expression text, provider-reported recalculation scopes intersected with `range|worksheet|workbook`, provider-reported atomicity/revision enforcement, and provider idempotency when the command contract confirms the supplied key.

Parse formula reads from the formula-rendered matrix and native cell metadata in the result envelope; never infer from ordinary Table reads. Parse calculated values separately with `calculation_state`, `provider_read`, and `provider_dynamic`.

- [ ] **Step 4: Implement set, independent readback, and explicit recalc**

Always invoke canonical set with `--verify`, then invoke a separate canonical read command and compare the complete formula map. Treat the set response's own verification as provider evidence, not OTC readback. Recalculate returns requested/effective scope, provider status, revision before/after, and any separately returned value evidence; an acknowledgement without values is succeeded with verification unavailable.

Delete `calculate_formulas()` and `read_formula_values()` from `MaybeSheetConnector` once their typed replacements pass. Do not keep aliases.

- [ ] **Step 5: Prove cross-mode references remain opaque**

Use the vendored case:

~~~python
FormulaExpression("='R_Revenue Base'!$C2*0.8", "maybe-sheet-a1")
~~~

Set it in sheet-mode, verify exact native expanded text, and read values. Assert there is no Base target bind/read command, no dependency receipt, and value evidence contains only `dependency_scope=provider_dynamic`.

- [ ] **Step 6: Compose the adapter, run focused tests, and commit**

`MaybeSheetCliAdapter.formula_extension_for()` returns a composite whose grid delegate is `MaybeSheetGridFormulaExtension`. Write it so a later `field_formula_extension` attribute is discovered without changing this forwarding method; absent delegates return typed unsupported results.

~~~bash
uv lock
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_cli_adapter.py -q
uv run --frozen ruff check packages/maybe_sheet
git diff --check
git add packages/maybe_sheet uv.lock
git commit -m "feat: implement Maybe grid formulas"
~~~

### Task 4: Implement direct Excel grid Formula support behind disabled identities

**Files:**
- Create `packages/local_files/src/open_table_connector/local_files/excel_formula.py` and `packages/local_files/tests/test_excel_formula.py`.
- Modify Excel connector/adapter/init/package metadata and Excel fixture/safety tests, but do not enable static Formula identities yet.

**Interfaces:**
- Produces `ExcelFormulaExtension` for existing direct `.xlsx` targets.
- Consumes `ExcelConnector.resolve()`, `source_revision()`, openpyxl, and the Formula package models.

- [ ] **Step 1: Write failing native-cell read and preservation tests**

Build a workbook with formulas, formula-looking strings, constants, blanks, styles, comments, data validation, defined names, an external link, hidden sheets, worksheet order, print settings, and workbook properties. Formula read opens independent bytes with `data_only=False`, returns only cells with `cell.data_type == "f"`, and preserves exact expression text.

Test direct `excel://...#sheet=Model` binding by worksheet name. A `WorksheetRef` must agree with a URI fragment when both exist. Reject `.xls`, `.xlsm`, CSV renamed to `.xlsx`, managed Excel schemes, missing/ambiguous sheets, and symlink targets before mutation.

- [ ] **Step 2: Run focused tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/local_files/tests/test_excel_formula.py -q
~~~

- [ ] **Step 3: Implement read, copy-fill translation, and locked atomic publication**

For each destination address use:

~~~python
Translator(expression.text, origin=rectangle.top_left).translate_formula(destination)
~~~

The top-left cell receives the original text. Effective details use `excel-a1`, 100,000 cells, 8,192 expression bytes, no calculation states/scopes, `mutation_atomicity=atomic`, `revision_enforcement=atomic`, and `idempotency_strength=host_ledger`.

Under an exclusive target-specific `fcntl.flock`:

1. reject symlink/non-regular targets;
2. hash current bytes and enforce `expected_revision`;
3. apply/replay the bounded idempotency entry;
4. load editable workbook bytes with `data_only=False`, `read_only=False`, and `keep_links=True`;
5. change only destination cell formula values;
6. set `workbook.calculation.fullCalcOnLoad=True`, `forceFullCalc=True`, and `calcMode="auto"` without claiming execution;
7. save to `tempfile.mkstemp()` in the target directory;
8. fsync the staged file, atomically `os.replace()` the target, and fsync the directory; and
9. reopen the published path independently and verify every formula cell.

Clean the staging file on every pre-replace failure. A failure after replace returns committed/readback-failed or unknown according to what can be observed; never retry the write blindly.

- [ ] **Step 4: Prove complete preservation and safety boundaries**

Compare all unrelated workbook objects before/after and fail on any unsupported preservation loss. Re-run `test_excel_writer_round_trips_formula_prefixed_headers_and_values_as_text` and the managed temporal formula rejection tests. Assert no calculated-value or recalc method performs I/O and no such capability appears in effective details.

- [ ] **Step 5: Add adapter forwarding, run focused tests, and commit**

`ExcelCliAdapter.formula_extension_for()` returns `CompositeFormulaConnectorExtension(grid=ExcelFormulaExtension(self.connector), field=None)`; CSV, Markdown, and general local-files adapters expose no Formula extension.

~~~bash
uv lock
uv run --frozen python -m pytest packages/local_files/tests/test_excel_formula.py packages/local_files/tests/test_excel_writer.py packages/local_files/tests/test_temporal_excel.py packages/local_files/tests/test_cli_plugin.py -q
uv run --frozen ruff check packages/local_files
git diff --check
git add packages/local_files uv.lock
git commit -m "feat: implement direct Excel grid formulas"
~~~

### Task 5: Enable grid capabilities only after the shared gate passes

**Files:**
- Modify provider identities/manifests/adapters and universal discovery/metadata cases listed in the file map.
- Complete `specification/conformance/formulas/test_grid_providers.py` cases.

**Interfaces:**
- Google statically advertises grid read/set/value-read.
- Maybe statically advertises grid read/set/value-read/recalculate and both Base/Sheet modes.
- Excel statically advertises grid read/set only.

- [ ] **Step 1: Run provider cases while identities are still disabled**

Instantiate each extension directly and run its complete applicable suite:

~~~bash
uv run --frozen python -m pytest packages/google_sheets/tests/test_formula.py packages/maybe_sheet/tests/test_grid_formula.py packages/local_files/tests/test_excel_formula.py specification/conformance/formulas/test_grid_copy_fill.py specification/conformance/formulas/test_grid_recovery.py -q
~~~

Expected: implementations pass; the matrix test still fails only because static identities are absent.

- [ ] **Step 2: Add exact static capability identities and dependencies**

Append capabilities in stable order after existing Table identities. Add `open-table-connector-formulas>=0.1,<0.2` as a workspace dependency to all three packages. Update Google and Excel `CapabilityManifest`; update Maybe identity constants and CLI adapter modes to `(TableMode.BASE, TableMode.SHEET)`. Do not add field identities.

Update `manifest.json` for Google and only the Excel/Maybe discovery fixtures that exist; available capabilities must match runtime tuples exactly. Update universal expected metadata and capability bindings so each advertised identity has an invocable offline case.

- [ ] **Step 3: Run discovery and capability-selected conformance**

~~~bash
uv lock
uv run --frozen python -m pytest specification/conformance/formulas/test_grid_providers.py specification/conformance/formulas/test_grid_copy_fill.py specification/conformance/formulas/test_grid_recovery.py specification/conformance/formulas/test_security.py -q
uv run --frozen python -m pytest specification/conformance/universal/test_discovery.py specification/conformance/universal/test_package_metadata.py specification/conformance/universal/test_package_boundaries.py -q
~~~

Expected: every advertised grid identity invokes a passing offline case; unsupported identities are absent rather than failing at runtime.

- [ ] **Step 4: Commit capability enablement**

~~~bash
git add packages/google_sheets packages/maybe_sheet packages/local_files specification/conformance uv.lock
git commit -m "feat: advertise conforming grid formulas"
~~~

### Task 6: Run cross-provider regression, document semantics, and record evidence

**Files:**
- Modify provider and root READMEs.
- Add configured-live evidence records only when an actual configured run is available; recording tests are not live evidence.

**Interfaces:**
- Documents exact provider matrix, dialects, copy-fill behavior, Maybe cross-mode references, and Excel limitations.

- [ ] **Step 1: Add provider examples and explicit limitations**

Show a bounded read and set for each provider. State that Google and Maybe values have provider-dynamic dependencies, Excel exposes no Formula value read/recalc, and ordinary writes do not activate formulas.

- [ ] **Step 2: Run the full grid verification gate**

~~~bash
uv lock --check
uv run --frozen python -m pytest packages/formulas/tests packages/sdk/tests/test_formula.py packages/google_sheets/tests packages/maybe_sheet/tests packages/local_files/tests specification/conformance/formulas specification/conformance/universal -q
uv run --frozen mypy packages/formulas/src packages/sdk/src packages/google_sheets/src packages/maybe_sheet/src packages/local_files/src
uv run --frozen ruff check .
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen python scripts/check_package_metadata.py
git diff --check
~~~

- [ ] **Step 3: Review dangerous semantic regressions**

~~~bash
rg -n "valueInputOption=" packages/google_sheets
rg -n "data_type = \"f\"|formula.*recalculate|formula.*values" packages/local_files packages/maybe_sheet
~~~

Manually confirm Formula activation appears only in provider Formula adapters, Google ordinary writes still use RAW, Excel ordinary writer still forces strings, and temporal Excel still rejects governed formulas.

- [ ] **Step 4: Commit documentation**

~~~bash
git add README.md packages/google_sheets/README.md packages/maybe_sheet/README.md packages/local_files/README.md
git commit -m "docs: describe grid formula providers"
~~~

---

## Grid Completion Gate

This plan is complete when all three providers pass the common copy-fill/readback suite, only Google and Maybe expose calculated-value reads, only Maybe exposes explicit grid recalculation, ordinary write safety remains green, and static discovery matches the exact grid capability matrix. Proceed to the field-provider plan next.
