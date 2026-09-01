# Field Formula Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement conforming base-mode formula-field read/set/value-read for Maybe Sheet and Feishu Bitable, add Maybe explicit recalculation, and enable only the capabilities proven by each provider suite.

**Architecture:** Field formulas bind through an SDK-owned base-mode `Table`, then resolve one exact provider field to a stable ID and prove it is already a formula field. Maybe uses canonical `mbs` metadata/formula/record commands. Feishu uses field metadata list/update plus the existing paginated record transport. Neither adapter writes calculated record values or converts a normal field.

**Tech Stack:** Python 3.11–3.14, existing Maybe process transport, existing Feishu HTTP transport, frozen Formula domain records, pytest recording fakes, and the Formula conformance corpus.

**Spec:** `docs/superpowers/specs/2026-09-01-mode-aware-formula-extension-design.md`

**Prerequisites:** Complete `docs/superpowers/plans/2026-09-01-formula-extension-core.md` and `docs/superpowers/plans/2026-09-01-grid-formula-providers.md`. The grid plan installs the generic Maybe extension composition seam used here.

## Global Constraints

- This plan implements only field targets. Do not change grid semantics or capability identities.
- A field view binds only an existing base-mode `Table` owned by the calling `Client` and one exact existing provider formula field.
- Field set changes only formula expression metadata. It never creates a field, converts a normal field, renames a field, changes the provider type/result type, or writes calculated record values.
- Missing fields are `TARGET_NOT_FOUND`; ambiguous names and non-formula fields are `INVALID_TARGET`. Reject them before any mutation request.
- Formula metadata readback is mandatory after set and must come from a fresh provider call.
- Maybe is the only field provider with an explicit recalculation capability in v1. Feishu provider calculation observed through record reads is not explicit recalc.
- Every value observation is keyed by stable provider record ID and says `dependency_scope=provider_dynamic`.
- Static identities remain unchanged until Task 4. Capability advertisement follows successful offline conformance; configured-live evidence is recorded separately.
- Ordinary Maybe/Feishu record writes remain value-only and must never interpret formula-like strings as field definitions.
- Formula expressions and calculated values may appear only in typed result values, never in safe evidence or errors.
- Work test-first. Each task ends with focused tests, `git diff --check`, and a Conventional Commit.

---

## File Map

### Shared field-provider conformance

- `specification/conformance/formulas/field_cases.py`
- `specification/conformance/formulas/test_field_providers.py`
- `specification/conformance/formulas/test_field_mutation.py`
- `specification/conformance/formulas/test_field_values.py`
- Modify `specification/conformance/formulas/conftest.py`
- Modify `specification/conformance/formulas/support.py`
- Modify `specification/fixtures/formulas/v1/field-observation.json`
- Modify `specification/fixtures/formulas/v1/value-observations.json`
- Modify `specification/fixtures/formulas/v1/manifest.sha256`

### Maybe Sheet base mode

- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/field_formula.py`
- `packages/maybe_sheet/tests/test_field_formula.py`
- Modify `packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py`
- Modify `packages/maybe_sheet/src/open_table_connector/maybe_sheet/__init__.py`
- Modify `packages/maybe_sheet/src/open_table_connector/maybe_sheet/identity.py`
- Modify `packages/maybe_sheet/tests/test_cli_adapter.py`
- Modify `packages/maybe_sheet/tests/test_connector.py`

### Feishu Bitable base mode

- `packages/feishu_bitable/src/open_table_connector/feishu_bitable/formula.py`
- `packages/feishu_bitable/tests/test_formula.py`
- Modify `packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py`
- Modify `packages/feishu_bitable/src/open_table_connector/feishu_bitable/cli_adapter.py`
- Modify `packages/feishu_bitable/src/open_table_connector/feishu_bitable/identity.py`
- Modify `packages/feishu_bitable/src/open_table_connector/feishu_bitable/__init__.py`
- Modify `packages/feishu_bitable/src/open_table_connector/feishu_bitable/manifest.json`
- Modify `packages/feishu_bitable/tests/test_connector.py`
- Modify `packages/feishu_bitable/tests/test_cli_adapter.py`
- Modify `packages/feishu_bitable/pyproject.toml`

### Discovery, metadata, and docs

- Modify `specification/conformance/universal/cases.py`
- Modify `specification/conformance/universal/test_discovery.py`
- Modify `specification/conformance/universal/test_package_metadata.py`
- Modify `packages/maybe_sheet/README.md`
- Modify `packages/feishu_bitable/README.md`
- Modify root `README.md`
- Modify `uv.lock`

---

### Task 1: Add capability-selected field fixtures and mutation isolation probes

**Files:**
- Create the shared field-provider conformance files.
- Extend only the field/value fixture documents and checksum manifest.

**Interfaces:**
- Produces recording Maybe processes and Feishu transports with metadata, records, pagination, revisions, timeouts, and failure injection.
- Consumes `FormulaProviderCase`, `load_formula_cases()`, and `assert_field_formula_conformance()` from the core plan.

- [ ] **Step 1: Write the field golden cases**

Include:

- exact name-to-stable-ID and ID-to-name binding;
- missing, ambiguous, and non-formula fields;
- native field expressions/functions;
- result-type and unrelated-property preservation;
- stable record IDs with null, boolean, integer, finite float, string, logical date/time, nested value, and provider formula-error values;
- multiple record pages under row/byte/time bounds;
- stale revision;
- same-key replay and conflict;
- provider rejection, timeout before dispatch, lost acknowledgement, readback mismatch, and unknown commit; and
- formula markers that must not leak into receipts/errors/logs/ledger state.

The mutation fixture has a complete before/after metadata document. The only allowed difference is the formula-expression property and provider revision/evidence fields.

- [ ] **Step 2: Add the failing capability matrix**

~~~python
EXPECTED_FIELD_CAPABILITIES = {
    "maybe_sheet": {
        "formula.field.read/1.0",
        "formula.field.set/1.0",
        "formula.field.values.read/1.0",
        "formula.field.recalculate/1.0",
    },
    "feishu_bitable": {
        "formula.field.read/1.0",
        "formula.field.set/1.0",
        "formula.field.values.read/1.0",
    },
}
~~~

Assert no field-create/convert or Feishu recalc capability exists. At this task the tests fail because extensions/cases are not implemented.

- [ ] **Step 3: Run and verify red**

~~~bash
uv run --frozen python -m pytest specification/conformance/formulas/test_field_providers.py specification/conformance/formulas/test_field_mutation.py specification/conformance/formulas/test_field_values.py -q
~~~

- [ ] **Step 4: Commit the red field harness**

~~~bash
git add specification/conformance/formulas specification/fixtures/formulas
git commit -m "test: define field formula provider matrix"
~~~

### Task 2: Implement Maybe Sheet base-mode Formula support behind disabled identities

**Files:**
- Create `packages/maybe_sheet/src/open_table_connector/maybe_sheet/field_formula.py` and `packages/maybe_sheet/tests/test_field_formula.py`.
- Modify Maybe connector/init tests, but do not enable field identities yet.

**Interfaces:**
- Produces `MaybeSheetFieldFormulaExtension` and installs it as `MaybeSheetConnector.field_formula_extension` for the composite forwarding seam created by the grid plan.
- Consumes the existing configured `ProcessClient`, credentials, timeout, `_mbs_target()`, and Formula protocol requests.

- [ ] **Step 1: Write failing binding and exact-command tests**

Use canonical JSON-output commands with credentials only in `ProcessClient.run(credentials=...)`:

~~~text
mbs formula read --target <base-target> (--field <name> | --field-id <id>) --output json
mbs formula set --target <base-target> --field-id <id> --expression <text> --language base --idempotency-key <key> --verify --output json
mbs base-table read --uri <workbook-uri> --table-id <id> --limit <n> --offset <n> --output json
mbs formula recalculate --target <base-target> --field-id <id> --verify --output json
~~~

Append `--expected-revision` only when supplied. Continue paged `base-table read` until provider exhaustion or a bound is reached. Assert target resolution extracts the stable Base table ID from formula metadata; it does not treat a worksheet name as the primary table identity.

- [ ] **Step 2: Run focused tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_field_formula.py -q
~~~

- [ ] **Step 3: Implement exact formula-field binding and metadata read**

Binding passes the SDK `FieldFormulaBindRequest` table URI/mode/revision and selector to canonical formula read. Require:

- response target is base-mode;
- stable table ID and field ID are present;
- name selection has exactly one result;
- provider field kind is formula;
- expression, name, ID, result type, and revision are non-empty/valid; and
- effective capabilities are a subset of the Maybe descriptor.

Effective details use `maybe-base`, 64 KiB expression bytes, provider-reported field/table recalc scopes intersected with `field|table`, provider-reported atomicity/revision enforcement, and provider idempotency when the command proves the supplied key.

- [ ] **Step 4: Write and implement mutation-isolation tests**

Before set, store a normalized metadata snapshot with formula text replaced by its hash. Invoke canonical set using stable IDs and always `--verify`. Then issue a separate canonical formula read and compare:

~~~python
assert after.field_id == before.field_id
assert after.field_name == before.field_name
assert after.provider_type == before.provider_type
assert after.result_type == before.result_type
assert after.unrelated_properties == before.unrelated_properties
assert after.expression == requested_expression
~~~

If any non-expression metadata changed, return committed/readback-failed. Never issue a field create/update/type-conversion or record-write command as recovery. Set `affected_count=1` and bind idempotency to table ID, field ID, expression hash, dialect, and expected revision.

- [ ] **Step 5: Implement stable-record value reads and explicit recalculation**

Parse every record using the provider's stable record ID and only the bound formula field value. Enforce `max_records`, response bytes, and elapsed time on every page and cumulatively. Use `calculation_state` supplied by the provider or `unknown`; never upgrade an unproven value to `provider_current`. Trigger is `provider_read`; dependency scope is fixed to `provider_dynamic`.

Recalculate supports only scopes returned at bind. Field scope sends `--field-id`; table scope omits it only when provider capability details include table scope. Acknowledgement without separate values returns verification unavailable. If value evidence is returned through a new read, mark trigger `explicit_recalculation`.

- [ ] **Step 6: Run focused tests and commit**

Remove the old untyped `calculate_formulas()` and `read_formula_values()` methods if the grid plan did not already remove them. Verify the composite adapter now satisfies both grid and field protocol methods.

~~~bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_field_formula.py packages/maybe_sheet/tests/test_grid_formula.py packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_cli_adapter.py -q
uv run --frozen ruff check packages/maybe_sheet
git diff --check
git add packages/maybe_sheet
git commit -m "feat: implement Maybe field formulas"
~~~

### Task 3: Implement Feishu Bitable Formula support behind disabled identities

**Files:**
- Create `packages/feishu_bitable/src/open_table_connector/feishu_bitable/formula.py` and `packages/feishu_bitable/tests/test_formula.py`.
- Modify Feishu connector/adapter/init/package metadata, but do not enable static identities yet.

**Interfaces:**
- Produces `FeishuBitableFormulaExtension` and `FeishuBitableCliAdapter.formula_extension_for()`.
- Consumes the existing configured `FeishuTransport`, tenant token, endpoint, timeout, `ResolvedFeishuBitable`, and record normalization.

- [ ] **Step 1: Write failing paginated field-metadata binding tests**

Binding lists fields through:

~~~text
GET /apps/{app_token}/tables/{table_id}/fields?page_size=100[&page_token=...]
~~~

Require `code == 0`, follow `has_more`, and resolve exactly one field by name or ID. Define `FEISHU_FORMULA_FIELD_TYPE = 20`; reject every other type before mutation. Require `property.formula_expression` to be a string and preserve the complete field document for later isolation checks.

Test duplicate names, missing IDs, wrong type, malformed properties, page loops, response over-return, timeouts, and non-zero provider codes. Safe details may contain provider code/table ID/field ID but not formula text or tenant token.

- [ ] **Step 2: Run focused tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/feishu_bitable/tests/test_formula.py -q
~~~

- [ ] **Step 3: Implement bind/read and effective capability details**

Bind app token and table ID from the Table URI, but never put the app token in `repr` or Formula receipt details; use the existing safe Table URI policy. Bind stable field ID/name, `feishu-bitable`, result-type descriptor from field properties, and a canonical metadata hash revision.

Use conservative effective limits: 50,000 records, 64 KiB expression bytes, 8 MiB response, connector timeout, `mutation_atomicity=atomic`, `revision_enforcement=checked`, `idempotency_strength=reconciled`, supported calculation state `provider_current|unknown`, and no recalc scopes.

- [ ] **Step 4: Write failing isolated-update and readback tests**

Set updates:

~~~text
PUT /apps/{app_token}/tables/{table_id}/fields/{field_id}
~~~

with a body constructed only from allowed Feishu update fields:

~~~python
{
    "field_name": before["field_name"],
    "type": FEISHU_FORMULA_FIELD_TYPE,
    "property": {
        **before["property"],
        "formula_expression": expression.text,
    },
}
~~~

Do not send server-owned IDs/revisions. After acknowledgement, list field metadata again through a new GET, require the exact expression, and assert ID, name, type, result formatting, and every unrelated property are unchanged. Test a formula syntax 4xx/non-zero provider code mapping to `INVALID_FORMULA` without retaining provider text.

- [ ] **Step 5: Implement checked revisions, reconciliation, and value reads**

When `expected_revision` is supplied, perform a fresh metadata read before PUT and reject stale revisions. Use `FormulaIdempotencyLedger` because Feishu update has no provider idempotency key. On lost acknowledgement, do one fresh metadata read; succeed as reconciled only if the complete isolated after-state matches, otherwise return unknown and do not resend PUT.

Read calculated values through the existing records endpoint, selecting only the bound field when the API supports projection:

~~~text
GET /apps/{app_token}/tables/{table_id}/records?page_size=500[&page_token=...]
~~~

Return `FormulaRecordValue(record_id, value)` in provider order. Reject a missing/duplicate record ID, page loop, non-finite number, unknown provider object, or cumulative limit breach. Use state `provider_current` only when the API response identifies the field value as current; otherwise `unknown`, with trigger `provider_read` and `provider_dynamic`.

- [ ] **Step 6: Add adapter forwarding, run focused tests, and commit**

`FeishuBitableCliAdapter.formula_extension_for()` returns an extension over the already configured connector. It must not create a second credential source or serialize the tenant token into requests/results.

~~~bash
uv lock
uv run --frozen python -m pytest packages/feishu_bitable/tests/test_formula.py packages/feishu_bitable/tests/test_connector.py packages/feishu_bitable/tests/test_cli_adapter.py -q
uv run --frozen ruff check packages/feishu_bitable
git diff --check
git add packages/feishu_bitable uv.lock
git commit -m "feat: implement Feishu field formulas"
~~~

### Task 4: Enable field capabilities only after the shared gate passes

**Files:**
- Modify Maybe/Feishu capability constants, manifests, adapters, universal discovery/metadata cases, and field provider cases.

**Interfaces:**
- Maybe adds field read/set/value-read/recalculate to its already enabled grid identities.
- Feishu adds field read/set/value-read and no recalc.

- [ ] **Step 1: Run provider cases while identities are disabled**

~~~bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_field_formula.py packages/feishu_bitable/tests/test_formula.py specification/conformance/formulas/test_field_mutation.py specification/conformance/formulas/test_field_values.py -q
~~~

Expected: implementations pass; only the static matrix test remains red.

- [ ] **Step 2: Append exact static identities and metadata**

Append field capabilities after existing grid identities in stable order. Add `open-table-connector-formulas>=0.1,<0.2` workspace dependency to Feishu; Maybe already has it from the grid plan. Update Feishu `CapabilityManifest`, CLI descriptor, and `manifest.json`. Update Maybe identity/descriptor tuples without removing sheet mode or grid identities.

Extend universal expected metadata and capability bindings. Every advertised Formula identity must have an offline invoker; do not count a method returning unsupported as coverage.

- [ ] **Step 3: Run capability-selected field conformance and discovery**

~~~bash
uv lock
uv run --frozen python -m pytest specification/conformance/formulas/test_field_providers.py specification/conformance/formulas/test_field_mutation.py specification/conformance/formulas/test_field_values.py specification/conformance/formulas/test_security.py -q
uv run --frozen python -m pytest specification/conformance/universal/test_discovery.py specification/conformance/universal/test_package_metadata.py specification/conformance/universal/test_package_boundaries.py -q
~~~

Expected: exact matrix match, no Feishu recalc, no field-create/convert identity, and no capability/effective-detail superset mismatch.

- [ ] **Step 4: Commit capability enablement**

~~~bash
git add packages/maybe_sheet packages/feishu_bitable specification/conformance uv.lock
git commit -m "feat: advertise conforming field formulas"
~~~

### Task 5: Run the complete Formula regression and document customized column formulas

**Files:**
- Modify Maybe, Feishu, and root READMEs.
- Add configured-live evidence only for actually executed provider versions/tenants.

**Interfaces:**
- Documents that Maybe base-mode and Feishu Bitable formulas are customized computed columns with provider-native languages, distinct from sheet cell formulas.

- [ ] **Step 1: Add user-facing examples and migration notes**

Show:

~~~python
table = client.open("maybe://document/R_orders").require_value()
margin = client.formulas(
    FieldFormulaTarget(table, FieldRef(name="gross_margin"))
).require_value()
margin.set(FormulaExpression("revenue - cost", "maybe-base"))
~~~

Add the corresponding Feishu example. State explicitly that callers must create/convert a formula field with provider-native administration outside this v1 API before binding it. Explain stable record IDs, provider-dynamic dependencies, and Maybe-only explicit recalc.

- [ ] **Step 2: Run the complete Formula verification gate**

~~~bash
uv lock --check
uv run --frozen python -m pytest packages/formulas/tests packages/sdk/tests packages/google_sheets/tests packages/maybe_sheet/tests packages/local_files/tests packages/feishu_bitable/tests packages/conformance/tests specification/conformance/formulas specification/conformance/universal -q
uv run --frozen mypy packages/formulas/src packages/sdk/src packages/google_sheets/src packages/maybe_sheet/src packages/local_files/src packages/feishu_bitable/src packages/conformance/src
uv run --frozen ruff check .
uv run --frozen python scripts/check_package_boundaries.py
uv run --frozen python scripts/check_package_metadata.py
git diff --check
~~~

- [ ] **Step 3: Run safety scans and review the complete Formula diff**

~~~bash
rg -n "field.*(create|convert)|record.*(update|write).*formula|verify=False|formula_expression.*(details|error|warning|log)" packages/maybe_sheet packages/feishu_bitable packages/formulas packages/sdk
git diff --stat HEAD~5..HEAD
~~~

Confirm no Formula set path invokes field creation/conversion or calculated-record writes, no raw expression enters safe evidence, all set paths perform fresh metadata readback, and ordinary record writes are unchanged.

- [ ] **Step 4: Commit documentation**

~~~bash
git add README.md packages/maybe_sheet/README.md packages/feishu_bitable/README.md
git commit -m "docs: describe field formula providers"
~~~

---

## Field Completion Gate

This plan is complete when Maybe and Feishu bind only existing formula fields by stable identity, formula set changes only the expression with independent metadata readback, calculated values retain stable record IDs and honest freshness, only Maybe advertises explicit recalculation, and the full five-provider Formula matrix passes without weakening ordinary Table write safety.
