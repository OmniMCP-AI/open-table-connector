# Formula Extension Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the provider-neutral Formula domain, closed wire contracts, SDK formula facade, extension routing, evidence normalization, and reusable conformance harness without enabling any provider capability prematurely.

**Architecture:** `open_table_connector.formulas` is a framework-neutral deep module that owns immutable formula targets, operations, observations, capabilities, receipts, errors, and the provider extension protocol. Provider extensions return a closed `FormulaExtensionResult[T]`; `open_table_connector.sdk.formula` is the only layer that converts that result into the SDK's `OperationResult[T]`, binds views to a `Client`, and routes grid targets by URI or field targets by their opened `Table`. Static plugin descriptors continue using their existing capability tuple, so discovery needs no open-ended options field.

**Tech Stack:** Python 3.11–3.14, frozen/slotted dataclasses, typing protocols and overloads, JSON Schema 2020-12, jsonschema 4.x, pytest 9, Ruff, mypy, and the existing uv workspace.

**Spec:** `docs/superpowers/specs/2026-09-01-mode-aware-formula-extension-design.md`

## Global Constraints

- Formula support is an optional extension over existing `base-mode` and `sheet-mode`; do not add a third `TableMode` or formula methods to the universal `TableConnector` protocol.
- Keep formula expressions provider-native and opaque. Core validates dialect identity, size, and presence but never parses, rewrites, translates, or evaluates formula text.
- Only `FormulaExpression` passed through a Formula view may activate a formula. Ordinary Table writes retain their current value-only behavior.
- Formula text and calculated values may appear only in typed `OperationResult.value` objects. Never place them in receipts, errors, warnings, logs, operation IDs, idempotency records, or exception chaining.
- Every grid selector is a closed A1 rectangle. Reject open columns, open rows, disjoint selections, reversed rectangles, and selectors larger than effective limits before provider I/O.
- Every mutation performs an independent formula-text readback. There is no `verify=False` path.
- Calculated-value observations always say `dependency_scope="provider_dynamic"`; they never claim dependency lineage or reproducibility.
- Static descriptor capabilities remain authoritative and I/O-free. Effective capabilities returned by target binding may be a subset, never a superset.
- Do not advertise any real provider Formula capability in this plan. The grid and field provider plans enable identities only after their focused conformance gates pass.
- Work test-first. Each task ends with focused tests, `git diff --check`, and a Conventional Commit.

---

## File Map

### New Formula domain package

- `packages/formulas/pyproject.toml`
- `packages/formulas/README.md`
- `packages/formulas/src/open_table_connector/formulas/__init__.py`
- `packages/formulas/src/open_table_connector/formulas/capabilities.py`
- `packages/formulas/src/open_table_connector/formulas/errors.py`
- `packages/formulas/src/open_table_connector/formulas/model.py`
- `packages/formulas/src/open_table_connector/formulas/ranges.py`
- `packages/formulas/src/open_table_connector/formulas/observations.py`
- `packages/formulas/src/open_table_connector/formulas/operations.py`
- `packages/formulas/src/open_table_connector/formulas/protocols.py`
- `packages/formulas/src/open_table_connector/formulas/receipts.py`
- `packages/formulas/src/open_table_connector/formulas/wire.py`
- `packages/formulas/src/open_table_connector/formulas/py.typed`
- `packages/formulas/tests/test_capabilities.py`
- `packages/formulas/tests/test_model.py`
- `packages/formulas/tests/test_ranges.py`
- `packages/formulas/tests/test_observations.py`
- `packages/formulas/tests/test_operations.py`
- `packages/formulas/tests/test_receipts.py`
- `packages/formulas/tests/test_wire.py`

### SDK integration

- `packages/sdk/src/open_table_connector/sdk/formula.py`
- `packages/sdk/tests/test_formula.py`
- Modify `packages/sdk/src/open_table_connector/sdk/client.py`
- Modify `packages/sdk/src/open_table_connector/sdk/connector.py`
- Modify `packages/sdk/src/open_table_connector/sdk/result.py`
- Modify `packages/sdk/src/open_table_connector/sdk/__init__.py`
- Modify `packages/sdk/tests/conftest.py`
- Modify `packages/sdk/pyproject.toml`

### Reusable conformance and specification

- `packages/conformance/src/open_table_connector/conformance/formulas.py`
- `packages/conformance/tests/test_formula_framework.py`
- Modify `packages/conformance/src/open_table_connector/conformance/__init__.py`
- Modify `packages/conformance/pyproject.toml`
- `specification/schemas/formula-operation-v1.schema.json`
- `specification/schemas/formula-observation-v1.schema.json`
- `specification/schemas/formula-capability-details-v1.schema.json`
- `specification/schemas/formula-receipt-details-v1.schema.json`
- `specification/fixtures/formulas/v1/cases.json`
- `specification/fixtures/formulas/v1/grid-copy-fill.json`
- `specification/fixtures/formulas/v1/grid-sparse-observation.json`
- `specification/fixtures/formulas/v1/field-observation.json`
- `specification/fixtures/formulas/v1/value-observations.json`
- `specification/fixtures/formulas/v1/manifest.sha256`
- `specification/conformance/formulas/__init__.py`
- `specification/conformance/formulas/conftest.py`
- `specification/conformance/formulas/support.py`
- `specification/conformance/formulas/test_contract.py`
- `specification/conformance/formulas/test_security.py`

### Workspace metadata and documentation

- Modify `pyproject.toml`
- Modify `uv.lock`
- Modify `scripts/check_package_boundaries.py`
- Modify `scripts/check_package_metadata.py`
- Modify `README.md`

---

### Task 1: Publish the Formula package, capability identities, targets, and A1 bounds

**Files:**
- Create the package files listed under “New Formula domain package” through `ranges.py`.
- Create `packages/formulas/tests/test_capabilities.py`, `test_model.py`, and `test_ranges.py`.
- Modify `pyproject.toml`, `uv.lock`, `scripts/check_package_boundaries.py`, and `scripts/check_package_metadata.py`.

**Interfaces:**
- Produces `FormulaExpression`, `FormulaResourceLimits`, `WorksheetRef`, `FieldRef`, `GridFormulaTarget`, `FieldFormulaTarget[TTable]`, `BoundGridFormulaTarget`, `BoundFieldFormulaTarget`, `A1Rectangle`, `GridRecalculationScope`, and `FieldRecalculationScope`.
- Produces exactly eight `CapabilityIdentity` values: `formula.grid.read/1.0`, `formula.grid.set/1.0`, `formula.grid.values.read/1.0`, `formula.grid.recalculate/1.0`, `formula.field.read/1.0`, `formula.field.set/1.0`, `formula.field.values.read/1.0`, and `formula.field.recalculate/1.0`.
- Consumes only `open-table-connector-contract`; no SDK or provider dependency is allowed.

- [ ] **Step 1: Write failing capability, target, expression, and range tests**

Use a generic field target so the domain package does not import the SDK at runtime:

~~~python
def test_targets_are_kind_safe_and_closed() -> None:
    grid = GridFormulaTarget(
        grid="gsheets://book-1",
        worksheet=WorksheetRef(name="Model"),
    )
    field = FieldFormulaTarget(
        table=object(),
        field=FieldRef(field_id="fld-margin"),
    )
    assert grid.grid.value == "gsheets://book-1"
    assert field.field.field_id == "fld-margin"
    with pytest.raises(ValueError, match="exactly one"):
        WorksheetRef(name="Model", worksheet_id="17")


@pytest.mark.parametrize("selector", ["A:A", "2:2", "A2:A", "B4:A1", "A1,B2"])
def test_a1_range_rejects_unbounded_reversed_or_disjoint_selectors(selector: str) -> None:
    with pytest.raises(ValueError):
        A1Rectangle.parse(selector)


def test_formula_expression_preserves_native_text_exactly() -> None:
    expression = FormulaExpression("='Base Data'!$A2+EXT.FETCH(\"https://x.test\")", "maybe-sheet-a1")
    assert expression.text == "='Base Data'!$A2+EXT.FETCH(\"https://x.test\")"
    assert expression.sha256.startswith("sha256:")
~~~

- [ ] **Step 2: Run the focused tests and verify red**

~~~bash
uv run python -m pytest packages/formulas/tests/test_capabilities.py packages/formulas/tests/test_model.py packages/formulas/tests/test_ranges.py -q
~~~

Expected: collection fails because `open_table_connector.formulas` does not exist.

- [ ] **Step 3: Add package metadata and exact capability constants**

Add `packages/formulas` to `[tool.uv.workspace].members`. The distribution is `open-table-connector-formulas`, version `0.1.0`, depends on `open-table-connector-contract>=0.1,<0.2` and `jsonschema>=4.23,<5`, and exposes only `open_table_connector.formulas*`.

In `capabilities.py`, define constants with `CapabilityIdentity`, an ordered `ALL_CAPABILITIES` tuple, and these dialect strings:

~~~python
GOOGLE_SHEETS_A1 = "google-sheets-a1"
MAYBE_SHEET_A1 = "maybe-sheet-a1"
EXCEL_A1 = "excel-a1"
MAYBE_BASE = "maybe-base"
FEISHU_BITABLE = "feishu-bitable"
FORMULA_DIALECTS = (
    GOOGLE_SHEETS_A1,
    MAYBE_SHEET_A1,
    EXCEL_A1,
    MAYBE_BASE,
    FEISHU_BITABLE,
)
~~~

Insert `open-table-connector-formulas` at dependency level 1 in `scripts/check_package_boundaries.py`; providers and SDK remain level 2, conformance remains level 3. Extend package metadata tests so every package importing Formula declares the workspace dependency.

- [ ] **Step 4: Implement immutable targets and bounded A1 parsing**

Use frozen, slotted dataclasses. `WorksheetRef` and `FieldRef` each require exactly one of name or stable ID. `FormulaExpression` requires exact untrimmed text whose `text.strip()` is non-empty, a dialect in `FORMULA_DIALECTS`, valid UTF-8, and at most 1 MiB at construction; effective provider limits may reject a smaller bound later. Its `repr` must redact `text` and show only dialect, byte count, and SHA-256.

`A1Rectangle.parse()` accepts optional `$` markers and optional quoted worksheet prefixes only when the caller separately proves the prefix matches the bound worksheet. Normalize cell coordinates to uppercase, retain absolute markers, and expose `height`, `width`, and `cell_count`. Reject a worksheet prefix in the selector after binding; the provider adapter receives only the rectangle and the separately bound worksheet ID.

~~~python
@dataclass(frozen=True, slots=True)
class FormulaResourceLimits:
    max_cells: int | None = None
    max_records: int | None = None
    max_response_bytes: int | None = None
    timeout_seconds: float | None = None


class GridRecalculationScope(StrEnum):
    RANGE = "range"
    WORKSHEET = "worksheet"
    WORKBOOK = "workbook"


class FieldRecalculationScope(StrEnum):
    FIELD = "field"
    TABLE = "table"
~~~

- [ ] **Step 5: Run, build, and commit**

~~~bash
uv lock
uv run --frozen python -m pytest packages/formulas/tests/test_capabilities.py packages/formulas/tests/test_model.py packages/formulas/tests/test_ranges.py -q
uv build --package open-table-connector-formulas
git diff --check
git add pyproject.toml uv.lock scripts/check_package_boundaries.py scripts/check_package_metadata.py packages/formulas
git commit -m "feat: define formula extension domain"
~~~

### Task 2: Add observations, capability details, values, and closed wire codecs

**Files:**
- Create `packages/formulas/src/open_table_connector/formulas/observations.py` and `wire.py`.
- Modify `packages/formulas/src/open_table_connector/formulas/__init__.py`.
- Create `packages/formulas/tests/test_observations.py` and `test_wire.py`.

**Interfaces:**
- Produces `FormulaCapabilityDetails`, `FormulaCapabilitySet`, `FormulaCell`, `GridFormulaObservation`, `FieldFormulaObservation`, `FormulaValue`, `FormulaErrorValue`, `FormulaValueCell`, `FormulaRecordValue`, `GridFormulaValueObservation`, `FieldFormulaValueObservation`, `FormulaMutation`, and `RecalculationObservation`.
- Every public record provides `to_wire()` and an exact-key `from_wire()` implementation.

- [ ] **Step 1: Write failing observation and recursive-value tests**

~~~python
def test_grid_formula_observation_is_sparse_and_round_trips() -> None:
    observation = GridFormulaObservation(
        worksheet_id="17",
        requested_range="A1:B2",
        formulas=(FormulaCell("A1", FormulaExpression("=B1+1", "google-sheets-a1")),),
        observed_revision="sha256:" + "a" * 64,
    )
    assert GridFormulaObservation.from_wire(observation.to_wire()) == observation
    assert [cell.address for cell in observation.formulas] == ["A1"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_formula_values_reject_non_json_or_non_finite_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        FormulaValue.from_python(value)
~~~

Also test provider-error values as data, stable record IDs, non-empty revisions, `provider_dynamic`, duplicate cell/record rejection, capability subset validation, mutation count consistency, and recalculation scope consistency.

- [ ] **Step 2: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/formulas/tests/test_observations.py packages/formulas/tests/test_wire.py -q
~~~

Expected: imports for observations and codecs fail.

- [ ] **Step 3: Implement the exact closed enums and records**

Use these enum values:

~~~python
class CalculationState(StrEnum):
    PROVIDER_CURRENT = "provider_current"
    CACHED = "cached"
    UNKNOWN = "unknown"

class CalculationTrigger(StrEnum):
    EXPLICIT_RECALCULATION = "explicit_recalculation"
    MUTATION = "mutation"
    PROVIDER_READ = "provider_read"
    STORED_CACHE = "stored_cache"

class MutationAtomicity(StrEnum):
    ATOMIC = "atomic"
    PARTIAL_REPORTED = "partial_reported"
    UNKNOWN = "unknown"

class RevisionEnforcement(StrEnum):
    ATOMIC = "atomic"
    CHECKED = "checked"
    UNAVAILABLE = "unavailable"

class IdempotencyStrength(StrEnum):
    PROVIDER = "provider"
    HOST_LEDGER = "host_ledger"
    RECONCILED = "reconciled"
~~~

Represent formula values with tagged immutable nodes rather than an unconstrained `Any`: `null`, `boolean`, `integer`, `number`, `string`, `sequence`, `mapping`, `logical`, and `provider_error`. A logical value carries `logical_type` and canonical string or finite numeric representation. A provider error carries a stable provider error code and no raw diagnostic.

`FormulaCapabilitySet` contains capability references plus one `FormulaCapabilityDetails`; reject duplicate capabilities, a target-kind mismatch, dialects outside `FORMULA_DIALECTS`, and a recalculation identity with no supported scopes.

- [ ] **Step 4: Add exact-key codecs and recursive rejection tests**

`from_wire()` rejects extra or missing keys at every level. `wire.py` dispatches tagged unions and exposes `formula_operation_from_wire()`, `formula_observation_from_wire()`, and `formula_observation_hash()`. Canonical hashes are `sha256:` plus lowercase SHA-256 of UTF-8 JSON with sorted keys, compact separators, and `allow_nan=False`.

- [ ] **Step 5: Run and commit**

~~~bash
uv run --frozen python -m pytest packages/formulas/tests/test_observations.py packages/formulas/tests/test_wire.py -q
uv run --frozen ruff check packages/formulas
git diff --check
git add packages/formulas
git commit -m "feat: add formula observations and wire codecs"
~~~

### Task 3: Define provider operations, extension results, errors, receipts, and idempotency utility

**Files:**
- Create `packages/formulas/src/open_table_connector/formulas/errors.py`, `operations.py`, `protocols.py`, and `receipts.py`.
- Modify `packages/formulas/src/open_table_connector/formulas/__init__.py`.
- Create `packages/formulas/tests/test_operations.py` and `test_receipts.py`.

**Interfaces:**
- Produces typed bind/read/set/value-read/recalculate request records for grid and field targets.
- Produces `FormulaExtensionResult[T]`, `FormulaExtensionErrorInfo`, `FormulaReceiptDetails`, `GridFormulaConnectorExtension`, `FieldFormulaConnectorExtension`, `FormulaConnectorExtension`, `CompositeFormulaConnectorExtension`, and `FormulaIdempotencyLedger`.
- Provider packages consume these interfaces and do not import SDK result types.

- [ ] **Step 1: Write failing extension-result and safety tests**

Test all legal result-state rows from the spec and reject illegal combinations. Test same-key/same-payload replay, same-key/different-payload conflict, and an unknown entry that cannot be blindly redispatched. Test that receipt payloads reject `expression`, `formula`, `value`, `values`, `credential`, `token`, URLs copied from expressions, and exception objects.

~~~python
def test_formula_receipt_contains_hashes_not_formula_text() -> None:
    details = FormulaReceiptDetails.for_grid_set(
        target=BOUND_GRID,
        selector="A1:B2",
        capability="formula.grid.set/1.0",
        dialect="google-sheets-a1",
        expression_sha256="sha256:" + "a" * 64,
        observation_sha256="sha256:" + "b" * 64,
        affected_count=4,
        revision_before="sha256:" + "c" * 64,
        revision_after="sha256:" + "d" * 64,
        mutation_atomicity="atomic",
        revision_enforcement="checked",
        verification="formula_text_readback",
    )
    payload = details.to_wire()
    assert "expression" not in json.dumps(payload).casefold()
    assert payload["copy_fill_policy"] == "top_left"
~~~

- [ ] **Step 2: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/formulas/tests/test_operations.py packages/formulas/tests/test_receipts.py -q
~~~

- [ ] **Step 3: Implement the closed provider result algebra**

Use formula-local state enums whose wire values exactly match the SDK (`succeeded`, `planned`, `rejected`, `failed`, `partial`, `unknown`; commit and verification values likewise). `FormulaErrorCode` contains exactly the Formula subset in the design, including `invalid_formula`.

~~~python
T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class FormulaExtensionResult(Generic[T]):
    value: T | None
    outcome: FormulaOutcome
    commit: FormulaCommitState
    verification: FormulaVerificationState
    receipts: tuple[FormulaReceiptDetails, ...]
    error: FormulaExtensionErrorInfo | None = None

@runtime_checkable
class GridFormulaConnectorExtension(Protocol):
    def bind_grid(self, request: GridFormulaBindRequest) -> FormulaExtensionResult[GridFormulaBinding]: ...
    def read_grid(self, request: GridFormulaReadRequest) -> FormulaExtensionResult[GridFormulaObservation]: ...
    def set_grid(self, request: GridFormulaSetRequest) -> FormulaExtensionResult[FormulaMutation]: ...
    def read_grid_values(self, request: GridFormulaValueReadRequest) -> FormulaExtensionResult[GridFormulaValueObservation]: ...
    def recalculate_grid(self, request: GridFormulaRecalculateRequest) -> FormulaExtensionResult[RecalculationObservation]: ...

@runtime_checkable
class FieldFormulaConnectorExtension(Protocol):
    def bind_field(self, request: FieldFormulaBindRequest) -> FormulaExtensionResult[FieldFormulaBinding]: ...
    def read_field(self, request: FieldFormulaReadRequest) -> FormulaExtensionResult[FieldFormulaObservation]: ...
    def set_field(self, request: FieldFormulaSetRequest) -> FormulaExtensionResult[FormulaMutation]: ...
    def read_field_values(self, request: FieldFormulaValueReadRequest) -> FormulaExtensionResult[FieldFormulaValueObservation]: ...
    def recalculate_field(self, request: FieldFormulaRecalculateRequest) -> FormulaExtensionResult[RecalculationObservation]: ...

@runtime_checkable
class FormulaConnectorExtension(
    GridFormulaConnectorExtension,
    FieldFormulaConnectorExtension,
    Protocol,
): ...
~~~

`CompositeFormulaConnectorExtension(grid=..., field=...)` implements the combined protocol by forwarding to optional target-kind delegates and returning a typed `UNSUPPORTED_CAPABILITY` result when a delegate is absent. This lets a provider add grid and field implementations independently without fake methods. Each set result must include a `FormulaMutation` whose observation was obtained by a separate provider read. The protocol has no `verify` parameter.

- [ ] **Step 4: Implement receipt hashing and the bounded host ledger**

`FormulaReceiptDetails` has the exact safe fields listed by the spec, uses schema version `otc.formula-receipt-details/v1`, and validates that calculated-value receipts include calculation state, trigger, and `provider_dynamic`. Set receipts require expression and readback hashes and forbid a calculated-value verification claim.

`FormulaIdempotencyLedger` is a bounded in-memory utility for adapters that declare `host_ledger` or `reconciled`. Key entries by `(connector_id, target_hash, selector_hash, idempotency_key)`, store only operation/payload hashes plus terminal state, evict completed entries in insertion order above a constructor limit, never evict `in_flight` or `unknown`, and expose `begin()`, `succeed()`, `fail_known()`, and `mark_unknown()`. The ledger never stores raw expressions or values.

- [ ] **Step 5: Run and commit**

~~~bash
uv run --frozen python -m pytest packages/formulas/tests/test_operations.py packages/formulas/tests/test_receipts.py -q
uv run --frozen ruff check packages/formulas
git diff --check
git add packages/formulas
git commit -m "feat: define formula provider protocol"
~~~

### Task 4: Publish closed JSON Schemas and vendored Formula fixtures

**Files:**
- Create the four `specification/schemas/formula-*.schema.json` files.
- Create all `specification/fixtures/formulas/v1/*` files.
- Extend `packages/formulas/tests/test_wire.py`.
- Create `specification/conformance/formulas/test_contract.py`.

**Interfaces:**
- The schemas are the language-neutral contract for operation, observation, effective capability details, and Receipt details.
- Fixtures are implementation-independent expected documents; tests must never generate expected copy-fill results with code under test.

- [ ] **Step 1: Add failing schema-validation tests**

Load each fixture with `json.loads`, validate it with Draft 2020-12, decode it with the Python codec, and re-encode byte-equivalent canonical JSON. Mutate every object by adding `"unexpected": true` and assert rejection. Test unknown schema versions, target kinds, calculation states, scopes, dialects, provider-error variants, and receipt fields containing raw formulas or values.

- [ ] **Step 2: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/formulas/tests/test_wire.py specification/conformance/formulas/test_contract.py -q
~~~

- [ ] **Step 3: Write the four closed schemas**

Use `additionalProperties: false` at every object. `formula-operation-v1` uses tagged `grid` and `field` unions and bounded selector strings. `formula-observation-v1` uses tagged formula-text, grid-value, field-value, mutation, and recalculation branches. `$defs.formulaValue` is recursive and rejects non-finite JSON numbers. Receipt schema accepts hashes but contains no property named `expression`, `formula`, `value`, or `values`.

- [ ] **Step 4: Vendor the initial golden corpus and checksum manifest**

`grid-copy-fill.json` contains explicit expected formula maps for relative, absolute, mixed, quoted-sheet, cross-sheet, external-reference, and provider-function cases per dialect. Include the approved Maybe cross-mode case whose text references a base-mode worksheet and whose value evidence says `dependency_scope=provider_dynamic`. `manifest.sha256` uses lexical filename order and `<lowercase-sha256><two spaces><filename>` lines.

- [ ] **Step 5: Run and commit**

~~~bash
uv run --frozen python -m pytest packages/formulas/tests/test_wire.py specification/conformance/formulas/test_contract.py -q
git diff --check
git add specification/schemas/formula-*.schema.json specification/fixtures/formulas specification/conformance/formulas/test_contract.py packages/formulas/tests/test_wire.py
git commit -m "spec: publish formula extension schemas"
~~~

### Task 5: Add `Client.formulas()` and bound grid/field views

**Files:**
- Create `packages/sdk/src/open_table_connector/sdk/formula.py` and `packages/sdk/tests/test_formula.py`.
- Modify `packages/sdk/src/open_table_connector/sdk/client.py`, `connector.py`, `result.py`, `__init__.py`, `packages/sdk/tests/conftest.py`, and `packages/sdk/pyproject.toml`.

**Interfaces:**
- Produces overloaded `Client.formulas(GridFormulaTarget)` and `Client.formulas(FieldFormulaTarget[Table])`.
- Produces `GridFormulaView` and `FieldFormulaView` with the exact methods in the design.
- Consumes `FormulaConnectorExtension`; returns SDK `OperationResult` and raises `OTCError` through existing `_deliver()` semantics.

- [ ] **Step 1: Extend the fake connector and write failing facade tests**

Add a `FakeFormulaExtension` to `packages/sdk/tests/conftest.py` implementing all ten protocol methods with deterministic observations and receipts. Add `formula_extension_for(self)` to `FakeSdkConnector` and its legacy test adapter. Test:

- correct grid/field overload result types;
- URI routing for grids and owning-connector routing for fields;
- sheet/base mode rejection before mutation;
- foreign Table rejection before connector I/O;
- view use after client close;
- unsupported method rejection from effective capabilities before provider I/O;
- dialect and scope rejection;
- exact extension-result to `OperationResult` state conversion;
- receipt envelope construction with no raw expression/value leakage; and
- `INVALID_FORMULA` round-trip in `ErrorCode`.

~~~python
def test_client_binds_grid_and_field_formula_views(fake_connector) -> None:
    client = otc.Client(registry=otc.ConnectorRegistry([fake_connector]))
    grid = client.formulas(
        otc.GridFormulaTarget("fake://warehouse/model", otc.WorksheetRef(name="Model"))
    ).require_value()
    table = client.open("fake://warehouse/orders").require_value()
    field = client.formulas(
        otc.FieldFormulaTarget(table, otc.FieldRef(name="gross_margin"))
    ).require_value()
    assert isinstance(grid, otc.GridFormulaView)
    assert isinstance(field, otc.FieldFormulaView)
~~~

- [ ] **Step 2: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/sdk/tests/test_formula.py packages/sdk/tests/test_result.py packages/sdk/tests/test_registry.py -q
~~~

- [ ] **Step 3: Add extension forwarding to the legacy bridge**

Do not widen `TableConnector`. Add this optional forwarding method only to `LegacyConnectorAdapterBridge`:

~~~python
def formula_extension_for(self) -> FormulaConnectorExtension:
    factory = getattr(self._adapter, "formula_extension_for", None)
    if not callable(factory):
        raise AttributeError("legacy adapter does not expose the formula extension")
    extension = factory()
    if not isinstance(extension, FormulaConnectorExtension):
        raise TypeError("legacy adapter formula extension is invalid")
    return extension
~~~

The SDK helper uses `getattr(connector, "formula_extension_for", None)` and maps a missing extension to `UNSUPPORTED_CAPABILITY` without calling any Table operation.

- [ ] **Step 4: Implement view binding, affinity, preflight, and result normalization**

Add a `_formula_owner_token` to `Client`. Grid targets route through `registry.connector_for(target.grid.value)`. Field targets require a real owned `Table`, use its existing `TableBinding`, and require `BASE_MODE`. A bound view stores the client, owner token, extension, binding, effective capabilities, and observed revision.

`_formula_result()` maps formula-local enum values by value into SDK enums, maps `FormulaErrorCode` by value into `ErrorCode`, constructs an SDK `Receipt(kind="formula", ...)` for each Formula detail object, and calls `_deliver()`. It rejects malformed extension results as `PROTOCOL_FAILURE` without echoing their value.

Each view validates capability, dialect, bounds, revision arguments, and recalc scope before invoking the extension. The view passes its last observed revision only when the caller supplies it as `expected_revision`; it never silently creates optimistic concurrency.

- [ ] **Step 5: Export the approved public surface and run compatibility tests**

Re-export targets and values from `open_table_connector.formulas` through `open_table_connector.sdk` for the `import open_table_connector.sdk as otc` style. Do not export provider request records or the idempotency ledger from SDK.

~~~bash
uv run --frozen python -m pytest packages/sdk/tests/test_formula.py packages/sdk/tests -q
uv run --frozen mypy packages/formulas/src packages/sdk/src
uv run --frozen ruff check packages/formulas packages/sdk
git diff --check
git add packages/sdk packages/formulas/src/open_table_connector/formulas/__init__.py
git commit -m "feat: add SDK formula facade"
~~~

### Task 6: Add reusable Formula conformance assertions and security probes

**Files:**
- Create `packages/conformance/src/open_table_connector/conformance/formulas.py` and `packages/conformance/tests/test_formula_framework.py`.
- Create `specification/conformance/formulas/conftest.py`, `support.py`, and `test_security.py`.
- Modify `packages/conformance/src/open_table_connector/conformance/__init__.py` and `packages/conformance/pyproject.toml`.

**Interfaces:**
- Produces `FormulaProviderCase`, `load_formula_cases()`, `assert_grid_formula_conformance()`, `assert_field_formula_conformance()`, `assert_formula_receipt_safe()`, and capability-selected pytest parametrization helpers.
- Provider plans add cases without copying the invariant assertions.

- [ ] **Step 1: Write failing framework tests with a conforming and deliberately broken fake**

The broken fakes must catch: exact-text broadcast instead of copy-fill, formulas inferred from leading `=`, value results without dependency scope, field conversion, raw-expression receipt leakage, stale revisions accepted contrary to declared enforcement, same-key/different-payload reuse, and advertised methods returning unsupported.

- [ ] **Step 2: Run tests and verify red**

~~~bash
uv run --frozen python -m pytest packages/conformance/tests/test_formula_framework.py specification/conformance/formulas/test_security.py -q
~~~

- [ ] **Step 3: Implement capability-selected reusable assertions**

`FormulaProviderCase` contains provider ID, target kind, dialect, static capabilities, an extension factory, target factories, and optional configured-live evidence. The assertion functions run only the identities statically advertised and fail if effective details add an identity. Mutation checks always do an additional read through a newly created extension instance where the provider supports independent sessions.

Security probes submit expressions containing a URL, token-like text, quoted credential, and workbook path; recursively scan receipts, errors, warnings, `repr`, logs captured by pytest, ledger snapshots, and operation IDs. Only the typed observation may contain the marker.

- [ ] **Step 4: Run and commit**

~~~bash
uv run --frozen python -m pytest packages/conformance/tests/test_formula_framework.py specification/conformance/formulas -q
uv run --frozen ruff check packages/conformance specification/conformance/formulas
git diff --check
git add packages/conformance specification/conformance/formulas
git commit -m "test: add formula extension conformance"
~~~

### Task 7: Document the disabled core surface and verify package integrity

**Files:**
- Modify `packages/formulas/README.md`, `packages/sdk/README.md`, `packages/conformance/README.md`, and root `README.md`.
- Modify universal package/discovery tests only for the new package and still-disabled Formula identities.

**Interfaces:**
- Documents the public facade, provider-native dialect rule, explicit formula-activation boundary, mode-specific target kinds, and the fact that provider identities are enabled by the two dependent plans.

- [ ] **Step 1: Add documentation examples and negative discovery assertions**

Show one grid and one field binding example. State that no provider capability is available until its provider plan is installed and tested. Add a universal discovery test asserting existing descriptors have no Formula identities at this checkpoint.

- [ ] **Step 2: Run the core verification gate**

~~~bash
uv lock --check
uv run --frozen python -m pytest packages/formulas/tests packages/sdk/tests/test_formula.py packages/conformance/tests/test_formula_framework.py specification/conformance/formulas -q
uv run --frozen python -m pytest specification/conformance/universal/test_package_boundaries.py specification/conformance/universal/test_package_metadata.py specification/conformance/universal/test_discovery.py -q
uv run --frozen mypy packages/formulas/src packages/sdk/src packages/conformance/src
uv run --frozen ruff check .
uv build --package open-table-connector-formulas
uv build --package open-table-connector-sdk
git diff --check
~~~

- [ ] **Step 3: Review the public and safety surface**

Run:

~~~bash
rg -n "verify=False|eval\(|exec\(|formula.*(log|warning)|details=.*(expression|formula|values?)" packages/formulas packages/sdk packages/conformance specification/conformance/formulas
~~~

Expected: no bypass, evaluator, or raw-evidence leak. Review every SDK export and confirm provider request types remain internal.

- [ ] **Step 4: Commit**

~~~bash
git add README.md packages/formulas/README.md packages/sdk/README.md packages/conformance/README.md specification/conformance/universal
git commit -m "docs: describe formula extension core"
~~~

---

## Core Completion Gate

This plan is complete only when the Formula package, schemas, SDK facade, and fake-provider conformance pass while every real provider still advertises no Formula capability. Then execute the grid-provider plan followed by the field-provider plan; those plans may run in either order after this gate, but each enables capabilities only at its final advertisement task.
