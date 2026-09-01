# Mode-Aware OTC Formula Extension

**Status:** approved architectural design; implementation has not started.

**Scope:** Google Sheets sheet-mode, Maybe Sheet sheet-mode, local Excel
sheet-mode, Maybe Sheet base-mode, and Feishu Bitable base-mode.

## Decision

Open Table Connector adds one optional, typed Formula Extension with two
different target domains:

- grid formulas address cells and bounded A1 ranges in sheet-mode; and
- field formulas address existing computed fields in base-mode.

The two domains share lifecycle, result, Receipt, revision, idempotency, and
capability conventions. They do not share selectors or expression languages.
A worksheet formula is not modeled as a Table column, and a computed field is
not modeled as a cell range.

Formula expressions are provider-native and opaque to OTC core. Every
expression declares a provider-native dialect, and Connectors preserve the
expression rather than translating it into a portable language. Formula
dependencies may cross worksheets and, where the provider permits it, may
cross Table Modes. In particular, Maybe sheet-mode formulas may reference
base-mode worksheets.

Formula persistence and formula calculation are separate claims. All five
provider/mode combinations in scope implement formula-text read and set. Only
a Connector with independent calculated-value or explicit-recalculation
evidence advertises those additional capabilities. Local Excel v1 persists
and reads formula text but does not claim in-process calculation or fresh
calculated values.

Ordinary Table writes remain formula-safe. A string beginning with `=` never
becomes a formula merely because it crosses a Table or DataFrame write path.
Formula execution is possible only through an explicit `FormulaExpression`
passed to the Formula Extension.

## Context

OTC currently treats formulas as outside Table core. The Python SDK design
reserves coordinate-level formulas for an optional sheet-grid extension, and
the current Maybe Connector exposes fail-closed `formula.calculate` and
`formula.readback` placeholders rather than a usable contract.

The providers do not have one physical formula model:

- Google Sheets, Maybe sheet-mode, and Excel store formulas at grid cells.
- Maybe base-mode and Feishu Bitable store a formula as field metadata and
  calculate one value per record.
- Google and Feishu normally calculate as part of provider behavior but do
  not expose the same explicit recalculation operation as Maybe.
- Excel files can persist formula text and cached results, but the current
  openpyxl-based local Connector has no calculation engine.

A single `Table.formula(...)` method would erase those differences. A generic
provider-operation escape hatch would preserve the differences but lose
typing, capability discovery, and conformance. The selected design uses one
mode-aware extension factory with separate typed views.

## Goals

1. Provide explicit, typed formula-text read and mutation operations for all
   five provider/mode combinations in scope.
2. Preserve the distinction between grid formulas and field formulas.
3. Standardize copy-fill behavior for a formula written to a rectangular
   grid range.
4. Keep provider-native expression dialects intact, including Maybe
   sheet-mode references to base-mode worksheets.
5. Negotiate formula persistence, calculated-value reads, and explicit
   recalculation independently.
6. Verify every formula mutation with an independent formula-text readback.
7. Report calculation freshness and dependency limits honestly.
8. Keep formulas, calculated values, credentials, and external references out
   of safe errors, logs, operation identifiers, and Receipt details.
9. Preserve ordinary Table write safety and current managed-temporal Excel
   formula rejection.
10. Add a provider-independent conformance suite with vendored golden
    expectations.

## Non-goals

- A portable formula language or expression translator.
- Cross-provider formula equivalence.
- An OTC formula parser, optimizer, or calculation engine.
- Complete formula dependency lineage or dependency snapshotting.
- Reproducible calculated values across volatile functions or changing
  provider data.
- Creating a formula field, converting a normal field into a formula field,
  or changing a formula field's result type.
- Clearing formulas, freezing formulas to values, or restoring prior
  formulas in v1.
- Formula validation, compilation, linting, error repair, or authoring UI.
- Batch mutation of multiple disjoint ranges or fields in one operation.
- Calculating local Excel workbooks in-process.
- Enabling formulas in managed temporal Excel snapshots.
- Treating formula text as DataFrame metadata.
- Adding an untyped provider-options mapping.

## Domain Vocabulary

### Formula target

A Formula target is one member of a closed union:

```python
FormulaTarget = GridFormulaTarget | FieldFormulaTarget
```

`GridFormulaTarget` identifies one physical workbook or grid plus exactly one
worksheet. The worksheet is selected by a stable provider ID when one exists;
a name is accepted only when binding resolves it to exactly one stable
worksheet identity.

`FieldFormulaTarget` identifies one opened base-mode `Table` plus exactly one
existing formula field. A caller may bind by field name or stable field ID,
but the bound view and every mutation Receipt record the resolved stable field
ID. Name lookup must be exact and unambiguous.

`WorksheetRef` and `FieldRef` are closed one-of selectors. Each carries exactly
one of `stable_id` or `name`; supplying both or neither is invalid. A grid
target contains a normalized credential-free `TableURI`. A field target
contains an SDK `Table` owned by the calling Client, and that Table must be
base-mode.

### Formula expression

`FormulaExpression` contains provider-native text and a required dialect:

```python
@dataclass(frozen=True, slots=True)
class FormulaExpression:
    text: str
    dialect: FormulaDialect
```

Initial dialect identities are:

```text
google-sheets-a1
maybe-sheet-a1
excel-a1
maybe-base
feishu-bitable
```

Dialect identities are stable strings, not aliases for Connector IDs. A
Connector may evolve its implementation without changing the dialect when the
accepted expression contract is unchanged. A breaking language change
requires a new dialect identity or versioned dialect details.

Grid dialects may require a leading `=`. Base-mode dialects follow their
provider's field-expression grammar and need not use `=`. The bound target
determines the permitted dialect set. A mismatch is rejected before mutation.

OTC does not restrict external workbook references, URLs, data-fetching
functions, volatile functions, or provider-specific functions. Calling
`set()` with a `FormulaExpression` is explicit authorization to submit that
provider-native formula. Deployments may enforce an independent policy above
OTC, but the v1 Formula contract contains no formula allowlist or hidden
sanitizer.

### Formula text and calculated value

Formula text is the persisted expression owned by a formula cell or formula
field. A calculated value is one provider observation produced from a stored
formula and the provider's current dependency state.

Formula-text read and verification do not prove that a formula calculated.
Calculated-value reads do not prove dependency completeness or future
reproducibility.

### Dependency scope

All calculated-value observations in v1 declare:

```text
dependency_scope = provider_dynamic
```

This means the provider may consult fields, sheet-mode worksheets, base-mode
worksheets, external data, volatile state, or other provider-owned inputs.
OTC records the observation but neither resolves nor snapshots the dependency
closure.

## Architecture

```text
Application / thin CLI
          |
          v
open_table_connector.sdk.formula
          |
          +--> GridFormulaView  --> provider grid-formula adapter
          |
          `--> FieldFormulaView --> provider field-formula adapter
                           |
                           v
              OperationResult + formula Receipt details
```

The implementation is divided into deep modules:

- `open_table_connector.formulas` owns immutable targets, expressions,
  observations, mutations, capability details, Receipt details, wire codecs,
  and Connector extension protocols.
- `open_table_connector.sdk.formula` owns `Client.formulas(...)`, bound public
  views, Connector dispatch, Client-affinity enforcement, and result
  normalization.
- Each provider package owns its formula adapter and physical translation.
- `specification/schemas/` owns closed formula wire schemas.
- `specification/conformance/formulas/` owns provider-independent golden
  conformance cases.

Table core is unchanged. The Formula Extension receives only the authorized
Client/Table context, resolved provider route, credential lease, limits, and
typed Formula target needed for its operation.

## Public Python Interface

### Binding

The overloaded factory binds a target and returns the matching view:

```python
grid_result = client.formulas(
    GridFormulaTarget(
        grid="gsheets://spreadsheet-id",
        worksheet=WorksheetRef(name="Model"),
    )
)
grid = grid_result.require_value()

field_result = client.formulas(
    FieldFormulaTarget(
        table=orders,
        field=FieldRef(name="gross_margin"),
    )
)
field = field_result.require_value()
```

Conceptually:

```python
@overload
def formulas(
    self, target: GridFormulaTarget
) -> OperationResult[GridFormulaView]: ...

@overload
def formulas(
    self, target: FieldFormulaTarget
) -> OperationResult[FieldFormulaView]: ...
```

Binding performs the minimum physical inspection needed to:

- select one Connector;
- confirm Table Mode;
- resolve a worksheet name or field name to stable identity;
- prove that a field already is a formula field;
- obtain effective formula capabilities and details; and
- capture an observed revision when the provider exposes one.

A view is bound to its creating Client. Use through a closed or different
Client fails with `CLIENT_CLOSED` or `CLIENT_AFFINITY_MISMATCH` before
provider I/O.

### Grid view

```python
class GridFormulaView:
    target: BoundGridFormulaTarget
    capabilities: FormulaCapabilitySet
    observed_revision: str | None

    def read(
        self,
        cell_range: str,
        *,
        limits: FormulaResourceLimits | None = None,
    ) -> OperationResult[GridFormulaObservation]: ...

    def set(
        self,
        cell_range: str,
        expression: FormulaExpression,
        *,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
        limits: FormulaResourceLimits | None = None,
    ) -> OperationResult[FormulaMutation]: ...

    def read_values(
        self,
        cell_range: str,
        *,
        limits: FormulaResourceLimits | None = None,
    ) -> OperationResult[GridFormulaValueObservation]: ...

    def recalculate(
        self,
        *,
        scope: GridRecalculationScope,
        cell_range: str | None = None,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
    ) -> OperationResult[RecalculationObservation]: ...
```

Grid ranges are closed, bounded A1 rectangles. Open-ended ranges such as
`A:A`, `2:2`, or `A2:A` are rejected. A single cell is represented as a
one-cell rectangle. V1 does not accept a list of disjoint ranges.

### Field view

```python
class FieldFormulaView:
    target: BoundFieldFormulaTarget
    capabilities: FormulaCapabilitySet
    observed_revision: str | None

    def read(self) -> OperationResult[FieldFormulaObservation]: ...

    def set(
        self,
        expression: FormulaExpression,
        *,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
    ) -> OperationResult[FormulaMutation]: ...

    def read_values(
        self,
        *,
        limits: FormulaResourceLimits | None = None,
    ) -> OperationResult[FieldFormulaValueObservation]: ...

    def recalculate(
        self,
        *,
        scope: FieldRecalculationScope,
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
    ) -> OperationResult[RecalculationObservation]: ...
```

`FieldFormulaView.set()` updates formula metadata on the existing formula
field only. A missing field is `TARGET_NOT_FOUND`. A normal field is
`INVALID_TARGET`. The operation never creates a field, changes its field type,
or silently replaces stored record values with a computed field.

### Observations

Formula-text reads return typed observations rather than DataFrames.

```python
@dataclass(frozen=True, slots=True)
class FormulaCell:
    address: str
    expression: FormulaExpression

@dataclass(frozen=True, slots=True)
class GridFormulaObservation:
    worksheet_id: str
    requested_range: str
    formulas: tuple[FormulaCell, ...]
    observed_revision: str

@dataclass(frozen=True, slots=True)
class FieldFormulaObservation:
    table_uri: TableURI
    field_id: str
    field_name: str
    expression: FormulaExpression
    result_type: str | None
    observed_revision: str
```

A grid observation is sparse and contains only cells the provider identifies
as formulas. Formula detection uses native cell type or metadata. OTC never
classifies an ordinary string as a formula merely because it begins with `=`.
An empty `formulas` tuple is a successful observation that found no formulas
in the requested range.

Calculated-value observations are also mode-specific:

- `GridFormulaValueObservation` is a coordinate/value sequence for formula
  cells in the requested range.
- `FieldFormulaValueObservation` contains stable record ID plus calculated
  field value for every returned record, under explicit row and byte bounds.

Each calculated cell or record may contain either a value or a provider
formula-error observation such as division by zero. A formula error is data,
not an OTC operation failure, when the provider successfully observed it.

`FormulaValue` is a closed JSON-compatible value union: null, boolean,
integer, finite float, string, sequence of Formula values, or string-keyed
mapping of Formula values. Provider date/time values include their native
logical-type descriptor and use canonical ISO text or a documented numeric
serial representation. Non-finite numbers and unsupported provider objects
are rejected as `PROTOCOL_FAILURE`; they are never silently stringified by the
Formula Extension.

Every calculated-value observation records:

```text
calculation_state: provider_current | cached | unknown
calculation_trigger: explicit_recalculation | mutation | provider_read | stored_cache
dependency_scope: provider_dynamic
observed_revision: non-empty revision or observation identity
```

`provider_current` means only that the provider represents the value as
current for the stored formula at observation time. It does not prove that
OTC captured every dependency. `cached` means a stored result was returned
without a freshness proof. `unknown` is an honest provider observation with
no stronger calculation claim.

### Mutation result

```python
@dataclass(frozen=True, slots=True)
class FormulaMutation:
    target_kind: Literal["grid", "field"]
    affected_count: int
    formula_observation: GridFormulaObservation | FieldFormulaObservation
    revision_before: str | None
    revision_after: str
```

`affected_count` is the number of formula cells persisted for grid set and
one for field set. A successful mutation always carries its independent
formula-text readback observation.

`FormulaResourceLimits` contains optional positive `max_cells`, `max_records`,
`max_response_bytes`, and `timeout_seconds`. Grid operations use
`max_cells`; field value reads use `max_records`; every operation uses byte and
time bounds. Connector-specific hard limits may be lower and are disclosed in
effective capability details.

## Capabilities

Capabilities are independent and versioned:

```text
formula.grid.read/1.0
formula.grid.set/1.0
formula.grid.values.read/1.0
formula.grid.recalculate/1.0

formula.field.read/1.0
formula.field.set/1.0
formula.field.values.read/1.0
formula.field.recalculate/1.0
```

Static discovery lists capability identities. Target binding returns typed
effective details:

```python
@dataclass(frozen=True, slots=True)
class FormulaCapabilityDetails:
    target_kind: Literal["grid", "field"]
    dialects: tuple[str, ...]
    max_cells_per_operation: int | None
    max_expression_bytes: int
    recalculation_scopes: tuple[str, ...]
    calculation_states: tuple[CalculationState, ...]
    mutation_atomicity: Literal["atomic", "partial_reported", "unknown"]
    revision_enforcement: Literal["atomic", "checked", "unavailable"]
    idempotency_strength: Literal["provider", "host_ledger", "reconciled"]
```

Boolean provider feature flags are insufficient. A Connector that supports
formula reads but cannot verify set, for example, advertises read only.

`formula.grid.set/1.0` includes the copy-fill contract below. A Connector
cannot advertise a weaker exact-text broadcast under the same identity.

## Grid Copy-Fill Semantics

Writing one expression to a rectangular range uses copy-fill semantics:

1. The expression is anchored at the range's top-left cell.
2. The top-left cell receives the provider-normalized form of the input.
3. Relative row and column references adjust for each destination cell.
4. Absolute references remain fixed.
5. Mixed references adjust only their relative component.
6. Quoted worksheet names, cross-worksheet references, provider functions,
   structured references, and external references retain provider semantics.

OTC core does not parse or translate the expression. Each provider adapter
owns its dialect-specific native fill operation or translator and must pass
the shared golden copy-fill corpus.

Set accepts one expression and one range. It does not accept an explicit
two-dimensional formula matrix in v1. Callers that need unrelated formulas
perform separate idempotent operations.

## Formula Read Semantics

Formula reads are nonmutating and bounded.

Grid read returns the native formula text of each formula cell in the exact
requested range. Literal cells, blanks, and cached calculated values are not
returned as formulas.

Field read returns the native formula metadata of one existing formula field.
The provider's formula result type may be reported when it is stable metadata;
OTC never infers it from sampled calculated values.

Formula reads record one observed revision or deterministic observation
identity. A provider that cannot expose a revision hashes the complete native
formula observation plus stable target identity; that hash proves what OTC
observed, not a provider-wide snapshot.

## Formula Set Semantics

Every set operation follows this sequence:

1. Resolve and bind the stable worksheet or field identity.
2. Confirm effective capability, target kind, dialect, range and expression
   bounds, revision policy, and idempotency binding.
3. Dispatch exactly one typed provider mutation.
4. Perform a fresh formula-text read through a physically independent request
   or reopened local workbook.
5. Compare the complete observed formula map or field expression with the
   adapter's expected provider-native result.
6. Return `OperationResult[FormulaMutation]`.

Readback is mandatory in v1; there is no `verify=False` option. Set verifies
formula persistence only. Automatic calculation during the provider mutation
does not upgrade the set Receipt into calculated-value evidence.

The adapter's expected grid expansion is produced by a dialect-specific
translator independently tested against vendored golden results. Runtime
verification compares all affected cells, not only the top-left cell or cell
count.

Setting a formula explicitly overwrites existing content in the target cell
or range. This destructive scope is visible in the typed selector and bound
into idempotency. Field set changes only formula metadata on the selected
existing formula field.

## Revision and Idempotency

An observed revision captured during binding is available on the view.
Mutation `expected_revision` is optional. When omitted and the bound view has
an observed revision, that revision becomes the mutation expectation. A
caller may explicitly pass the same current revision; a conflicting explicit
value is rejected locally.

Revision enforcement strength is provider-specific and disclosed in
capability details:

- `atomic`: the provider or local publication primitive enforces the expected
  revision with the mutation;
- `checked`: OTC checks before and after but cannot eliminate every race; or
- `unavailable`: expected-revision mutation is unsupported.

OTC never labels a checked comparison atomic.

Every mutation accepts an idempotency key. It binds at least:

```text
principal or tenant
operation and capability version
Connector and canonical physical target
stable worksheet or field identity
exact A1 range when grid-targeted
dialect and expression hash
expected revision
```

The same key and same binding joins or replays one logical effect. The same
key with any changed bound input is `IDEMPOTENCY_CONFLICT`. If a provider has
no native idempotency key, the SDK host ledger and fresh formula readback are
used for replay and reconciliation. Lost acknowledgement never causes a blind
repeat.

## Calculated-Value Read Semantics

Calculated-value reads are available only under `formula.*.values.read/1.0`.
They observe stored formulas and calculated values as one revision-bound
operation when the provider permits it. If two provider calls are necessary,
the adapter must prove the target revision did not change between them or
fail with `SNAPSHOT_UNAVAILABLE`.

Grid value reads return values only for cells observed to be formulas in the
requested range. Field value reads return stable record IDs and the selected
computed-field value. Resource limits bound grid cells, records, response
bytes, and elapsed time.

The result and Receipt disclose calculation state and trigger. They never
claim dependency lineage, repeatability, or cross-provider equivalence.

Local Excel v1 does not advertise calculated-value read. Ordinary Excel Table
reads may continue returning workbook-cached values, but those values are not
Formula Extension evidence.

## Explicit Recalculation

Explicit recalculation is a separate mutation capability. Initial scopes are:

```text
grid: range | worksheet | workbook
field: field | table
```

Effective capability details list the exact supported subset. A view rejects
an unsupported scope before provider I/O.

Recalculation returns `RecalculationObservation` with the requested and
effective scope, revision before and after, provider status, and calculation
state. When the provider can perform a revision-stable value readback, that
observation is attached and verification is `passed`. A provider acknowledgement
without value evidence may succeed only with verification `unavailable`; it
does not fabricate values.

Automatic provider calculation on set or read is not an explicit
recalculation capability. Google Sheets and Feishu Bitable therefore do not
advertise `formula.*.recalculate/1.0` in v1. Local Excel setting workbook
recalculation metadata also does not prove execution and does not advertise
the capability.

## Operation Results and Receipt Evidence

All Formula operations use the SDK's existing `OperationResult[T]` envelope.
Formula mutation states follow the standard invariants:

| Condition | Outcome | Commit | Verification |
| --- | --- | --- | --- |
| Invalid target, dialect, bounds, or stale preflight | `rejected` | `not_started` | `skipped` |
| Formula text read successfully | `succeeded` | `not_applicable` | `passed` |
| Formula persisted and exact readback matched | `succeeded` | `committed` | `passed` |
| Provider rejected formula before effect | `failed` | `not_committed` | `skipped` |
| Formula persisted but readback mismatched | `failed` | `committed` | `failed` |
| Known subset of a range changed | `partial` | `partial` | `failed` |
| Mutation acknowledgement and readback both unavailable | `unknown` | `unknown` | `unavailable` |

Formula Receipts use the ordinary SDK `Receipt` envelope with a versioned,
closed Formula details payload. Details include:

- Formula Receipt details version;
- target kind and Table Mode;
- safe canonical target;
- stable worksheet or field identity;
- exact bounded selector;
- capability and dialect;
- expression SHA-256 when a mutation supplied an expression;
- observed formula-map or field-expression SHA-256;
- calculated-value observation SHA-256 when applicable;
- affected or observed count;
- copy-fill policy for grid set;
- calculation state and trigger;
- `dependency_scope=provider_dynamic` for calculated values;
- revision before and after when known;
- mutation atomicity, revision enforcement, and verification facts; and
- safe provider receipt reference when available.

Raw formula expressions and calculated values appear only in the typed
`OperationResult.value`. They never appear in Receipt details, safe errors,
warnings, logs, tracing attributes, operation IDs, idempotency records, or
exception chaining. Operation and idempotency identities use hashes.

## Error Model

Formula operations reuse existing SDK errors:

```text
INVALID_TARGET
UNSUPPORTED_MODE
UNSUPPORTED_CAPABILITY
TARGET_NOT_FOUND
STALE_REVISION
IDEMPOTENCY_CONFLICT
RESOURCE_LIMIT
TIMEOUT
CANCELLED
SNAPSHOT_UNAVAILABLE
EXECUTION_FAILED
PARTIAL_EFFECT
UNCERTAIN_MUTATION
READBACK_MISMATCH
PROTOCOL_FAILURE
CLIENT_CLOSED
CLIENT_AFFINITY_MISMATCH
```

The SDK adds `INVALID_FORMULA` for dialect mismatch, empty/oversized formula
text, or normalized provider syntax rejection. Provider formula-error values
such as division by zero remain observations rather than `INVALID_FORMULA`
when the formula was accepted and evaluated.

Safe error details may contain a target kind, safe URI, worksheet or field ID,
range, dialect, limit, provider status code, revision hash, and affected
count. They must not contain raw expression text, calculated values, provider
diagnostics that echo formula text, credentials, or exception objects.

## Provider Capability Matrix

| Provider and mode | Target | Formula read | Formula set | Value read | Explicit recalc |
| --- | --- | ---: | ---: | ---: | ---: |
| Google Sheets sheet-mode | A1 cell/range | yes | yes | yes | no |
| Maybe Sheet sheet-mode | A1 cell/range | yes | yes | yes | yes |
| Local Excel sheet-mode | A1 cell/range | yes | yes | no | no |
| Maybe Sheet base-mode | stable formula field | yes | yes | yes | yes |
| Feishu Bitable base-mode | stable formula field | yes | yes | yes | no |

The matrix is the v1 implementation target. A deployment still reports only
the capabilities proven by its configured provider version and credentials.

## Google Sheets Mapping

Google binds the credential-free spreadsheet ID and stable numeric `sheetId`.
Names are resolved through spreadsheet metadata before formula operations.

Formula read uses native cell data and selects
`userEnteredValue.formulaValue`; it does not infer formulas from rendered
strings. Calculated-value read selects `effectiveValue` from the same bounded
grid observation when possible. The resulting state is `provider_current`
with trigger `provider_read` or `mutation`, but dependency scope remains
`provider_dynamic`.

Grid set uses a Sheets API `RepeatCellRequest` or an equivalent native request
whose documented behavior copies one formula across a `GridRange` while
adjusting relative references. It does not use the ordinary OTC Table write
path. A fresh grid-data request verifies every affected cell's native formula
text.

Google automatic calculation does not become an explicit recalculation API.
The Connector advertises:

```text
formula.grid.read/1.0
formula.grid.set/1.0
formula.grid.values.read/1.0
```

The existing Google Table writer remains `valueInputOption=RAW`. Only the
Formula adapter may submit formula-typed user-entered values.

## Maybe Sheet Sheet-Mode Mapping

Maybe binds a canonical workbook URI plus stable worksheet `gid` when
available. An exactly resolved worksheet name is preserved as display
metadata, not primary identity.

The adapter uses the `mbs` sheet-mode formula read/set seams and formula-rendered
worksheet reads. Range set must implement the common top-left copy-fill
contract and return enough state for an independent formula-text readback.

Provider-native `maybe-sheet-a1` expressions pass through unchanged. This
includes expressions that refer to base-mode worksheets. OTC does not resolve
the referenced base worksheet, convert its field model into cells, or attach
dependency Receipts. Calculated-value evidence records
`dependency_scope=provider_dynamic`.

Maybe advertises all four grid capabilities when the configured `mbs` and
backend versions pass conformance. Effective recalculation details list only
the scopes the backend actually supports, such as range, worksheet, or
workbook.

## Local Excel Mapping

Excel formula support applies to direct `.xlsx` workbooks through the local
Excel Connector. It does not apply to managed temporal Excel storage.

Read opens the workbook with `data_only=False` and detects formulas from the
native formula cell type. Set opens the existing workbook in editable mode,
changes only the selected formula cells, and uses the openpyxl A1 formula
translator for copy-fill. It must preserve unrelated cells, formulas,
worksheets, worksheet identities, styles, names, links, and workbook
properties supported by the direct Connector.

Publication uses a target-specific lock, a staged workbook in the target
directory, durable flush where supported, and atomic replacement. The
filesystem content identity is the revision. Set reopens the published file
with `data_only=False` and verifies every affected formula.

The adapter may mark the workbook for recalculation when next opened by a
calculation-capable application. That metadata is not evidence that formula
execution occurred. The adapter must not invent or retain a known-stale cached
result for a changed formula.

Excel advertises:

```text
formula.grid.read/1.0
formula.grid.set/1.0
```

It does not advertise calculated-value read or explicit recalculation in v1.
The ordinary Excel writer continues forcing formula-prefixed user strings to
text. The managed temporal Excel reader continues rejecting formulas in its
governed worksheet.

## Maybe Sheet Base-Mode Mapping

Maybe base-mode binds a stable logical table identity and resolves an exact
field name to stable field ID. Binding confirms through field metadata that
the field already is a formula field.

Field formula read/set use the `mbs` base formula metadata operations. Set
updates only the expression on the bound field and performs a fresh metadata
readback. It does not create, convert, rename, or change the result type of the
field.

Calculated-value read uses stable record IDs plus the computed field value.
Explicit recalculation uses only provider-supported field or table scope and
returns the provider's formula-execution evidence. Maybe advertises all four
field capabilities after configured conformance passes.

## Feishu Bitable Mapping

Feishu binds the Bitable app token, table ID, and stable field ID. Name binding
lists field metadata and requires exactly one match. Binding confirms that the
field is a Feishu formula field before returning a view.

Formula read uses the Bitable field metadata endpoint. Formula set uses the
field update endpoint to change only the provider formula property while
preserving field identity, name, type, and unrelated properties. A fresh field
metadata request verifies the stored expression.

Calculated-value read uses the existing paginated record endpoint and returns
stable Feishu record IDs plus the computed field value under row, byte, and
time limits. Feishu provider calculation is observable through record values
but is not exposed as explicit recalculation.

Feishu advertises:

```text
formula.field.read/1.0
formula.field.set/1.0
formula.field.values.read/1.0
```

A Feishu deployment whose API version, tenant policy, or credentials cannot
read and update the formula property must omit the affected capability rather
than falling back to record writes or field conversion.

## Wire Contracts

The implementation adds closed, versioned schemas:

```text
specification/schemas/formula-operation-v1.schema.json
specification/schemas/formula-observation-v1.schema.json
specification/schemas/formula-capability-details-v1.schema.json
specification/schemas/formula-receipt-details-v1.schema.json
```

The schemas use tagged unions for grid and field targets. Unknown keys,
unknown target kinds, unsupported versions, malformed A1 ranges, invalid
calculation states, and formula Receipts containing raw expression/value
fields are rejected.

Formula wire models use JSON-compatible scalar/value encodings with explicit
provider-error variants. Large calculated field results cross internal
Connector boundaries through bounded Arrow carriers where appropriate, but
the public Formula observation and Receipt semantics remain identical.

The existing capability manifest schema remains valid for static capability
identities. Effective Formula details use the new Formula capability-details
schema rather than weakening the manifest into an arbitrary options object.

## Discovery and Routing

Provider descriptors statically declare supported Formula identities and
target modes without performing I/O. The lazy provider factory supplies a
Formula Connector extension protocol in addition to the ordinary Table
Connector protocol.

Routing is target-kind aware:

- grid targets require sheet-mode and a grid-capable provider route;
- field targets require an opened base-mode Table and its owning Connector;
- no Connector fallback may change target mode or physical engine; and
- a Maybe sheet-mode target never falls back to Maybe base-mode merely because
  its expression references a base-mode worksheet.

The current Maybe CLI adapter's base-only Table surface does not prevent the
same provider plugin from exposing a separately typed sheet-grid Formula
extension. Discovery must describe both extension target modes truthfully.

## Formula Safety Boundary

Formula activation is intentionally narrow:

- `Table.insert`, materialization, imports, and ordinary Connector writes
  continue treating caller strings as values.
- Google ordinary writes continue using `RAW`.
- Local Excel ordinary writes continue forcing strings to text cells.
- Maybe and Feishu ordinary record writes do not interpret formula-like
  strings as field definitions.
- Only `FormulaExpression` submitted through `GridFormulaView.set()` or
  `FieldFormulaView.set()` can mutate formula definitions.

This boundary prevents accidental formula injection while permitting the
explicit provider-native external and cross-mode references approved for v1.

## Conformance

Formula conformance is capability-selected. A Connector is tested only for
the identities it advertises, and no Connector may advertise a capability
before passing its applicable suite.

### Contract tests

- Target, expression, capability-detail, observation, mutation, and Receipt
  round trips.
- Closed-schema rejection for extra/missing keys and unknown versions.
- Grid/field selector and Table Mode mismatch rejection before provider I/O.
- Dialect mismatch, blank expressions, oversized expressions, open-ended
  ranges, reversed ranges, and excessive cell counts.
- Client affinity and closed-client behavior.

### Grid golden corpus

- Single-cell formula persistence.
- Rectangular copy-fill with relative, absolute, and mixed A1 references.
- Quoted worksheet names and cross-worksheet references.
- Provider-specific functions and accepted external references.
- Literal strings beginning with `=` remaining non-formulas outside the
  Formula Extension.
- Sparse reads containing formulas, values, blanks, and provider formula
  errors.
- Maybe sheet-mode formulas referencing a base-mode worksheet with exact text
  preservation and `dependency_scope=provider_dynamic`.

Expected expanded formulas are vendored per dialect. Tests never compute
expected output with the implementation under test.

### Field golden corpus

- Exact name-to-stable-ID binding.
- Formula metadata read and result-type preservation.
- Updating an existing formula field without changing ID, name, type, or
  unrelated properties.
- Rejection of missing, ambiguous, and normal fields before mutation.
- Calculated-value observations keyed by stable record ID.
- Provider-native field references and functions.

### Mutation and recovery tests

- Formula-text readback success and mismatch.
- Stale revision under each declared enforcement strength.
- Same-key/same-payload replay and same-key/different-payload conflict.
- Timeout before dispatch, confirmed failure, partial effect, lost
  acknowledgement, reconciliation, and unknown commit.
- No blind retry after an uncertain mutation.
- Resource bounds applied at the provider request and rechecked locally.

### Security and evidence tests

- Formula text containing URLs, token-like strings, workbook paths, and quoted
  credentials never appears in errors, warnings, logs, operation IDs,
  idempotency entries, or Receipt details.
- Raw formula and calculated values appear only in the typed operation value.
- Receipt hashes change when formula text, selector, target, or values change.
- Calculated-value Receipts always declare calculation state, trigger, and
  `dependency_scope=provider_dynamic`.
- A formula set Receipt never claims calculated-value verification.

### Provider tests

- Recording tests assert exact Google request type, GridRange, native formula
  field, bounded readback, and unchanged ordinary `RAW` writes.
- Recording tests assert exact `mbs` sheet/base formula commands, credential
  locality, result-envelope parsing, and recalculation scopes.
- Excel tests reopen independent workbook instances, compare formula text, and
  prove preservation of unrelated values, formulas, styles, names, links,
  worksheet order, and workbook structure after atomic replacement.
- Feishu tests assert field metadata lookup/update/readback, stable IDs,
  formula-property isolation, paginated value reads, and provider-code
  normalization.
- Configured-live tests prove each advertised provider capability. Recorded
  stubs alone cannot upgrade a capability to configured-live evidence.

## Migration

1. Add the Formula domain package, SDK facade, error code, and closed schemas
   without changing current Connector advertisements.
2. Add Formula extension discovery and target-kind routing.
3. Implement provider adapters behind unadvertised capabilities.
4. Add the shared golden conformance corpus and provider recording fixtures.
5. Enable capability advertisement provider by provider only after the
   applicable suite passes.
6. Replace the Maybe Connector's fail-closed `calculate_formulas()` and
   `read_formula_values()` placeholders with the typed extension. Do not keep
   them as permanent public aliases.
7. Refresh capability manifests, provider evidence, compatibility hashes, and
   discovery assertions.

The migration does not change ordinary Table read/write semantics, current
managed temporal protocols, or the default Excel/Google formula-injection
defenses.

## Acceptance Criteria

The design is implemented when all of the following are true:

1. `Client.formulas(...)` returns a typed grid or field view and rejects
   cross-mode/selector mistakes before mutation.
2. Formula text read and independently verified set pass for Google Sheets,
   Maybe sheet-mode, direct Excel, Maybe base-mode, and Feishu Bitable.
3. Grid set implements the same golden copy-fill semantics on Google, Maybe,
   and Excel.
4. Maybe sheet-mode preserves provider-native references to base-mode
   worksheets without claiming dependency lineage.
5. Field set updates only an existing formula field and never creates or
   converts fields.
6. Google and Maybe sheet-mode, Maybe base-mode, and Feishu return honest
   calculated-value observations; Excel makes no fresh-value claim.
7. Only Maybe advertises the explicit recalculation scopes proven by its
   configured provider paths.
8. Formula mutations always perform fresh formula-text readback and preserve
   committed/partial/unknown state accurately.
9. Formula Receipt details contain hashes and safe target facts but no raw
   expressions or calculated values.
10. Ordinary Table writes cannot activate formulas, and managed temporal Excel
    continues rejecting formula-bearing governed worksheets.
11. All closed schemas, universal Formula conformance tests, provider
    recording tests, configured-live evidence checks, and package-boundary
    tests pass.

## References

- OTC Python SDK architecture:
  `docs/superpowers/specs/2026-08-31-python-sdk-design.md`
- Universal Connector conformance:
  `docs/superpowers/specs/2026-08-28-universal-connector-conformance-design.md`
- Google Sheets
  [ValueInputOption](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueInputOption)
  and
  [ValueRenderOption](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueRenderOption)
- Google Sheets
  [spreadsheets.values.update](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/update)
- Feishu Bitable
  [list fields](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-field/list)
  and
  [update field](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-field/update)
- Maybe Sheet CLI formula and worksheet contracts in the sibling
  `maybeai-sheet-cli` repository.
