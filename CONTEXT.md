# Open Table Connector

Open Table Connector normalizes table-shaped data operations across physical media while preserving the meaningful differences between record tables and spreadsheet surfaces.

## Language

**Table**:
An addressable, schema-bearing tabular resource on which the common table operations have defined semantics.
_Avoid_: Relation, worksheet, grid

**Table Mode**:
The semantic model under which a Table is addressed and mutated: base-mode for records and typed fields, or sheet-mode for a header-aware region in a cell grid.
_Avoid_: Engine, backend

**Base-mode Table**:
A Table whose rows are records and whose columns are typed fields, with provider-defined record and field identity.
_Avoid_: Worksheet, sheet

**Sheet-mode Table**:
A bounded, header-aware Table contained within a Sheet-mode Grid.
_Avoid_: Worksheet, arbitrary range, SheetTable, Sheet Table

**Sheet-mode Grid**:
An addressable cell surface whose native coordinates are rows, columns, and ranges. A Sheet-mode Grid is not a Table unless a bounded, header-aware Sheet-mode Table is defined over it.
_Avoid_: Table, relation

**Worksheet**:
A visible spreadsheet presentation surface that contains a Sheet-mode Grid and may contain one or more Sheet-mode Tables.
_Avoid_: Table

**SheetTable**:
The Maybe base-mode package and physical engine for typed record tables. It is a package name, not the name of a sheet-mode table resource.
_Avoid_: Sheet-mode Table, sheet-mode engine

**Excelize Engine**:
The Maybe sheet-mode physical engine for cell grids, sheet-mode Tables, formulas, and workbook behavior.
_Avoid_: base-mode engine, SheetTable

**Table URI**:
A stable, credential-free identifier for one physical Table. Provider-specific resolution and canonicalization do not change its meaning to callers.
_Avoid_: TableRef, TableHandle

**DataFrame**:
An in-memory table value containing data only; source identity and execution evidence remain separate.
_Avoid_: FrameMeta, metadata-bearing frame

**Complete Read**:
A read of one whole bounded Table within configured finite limits. It follows provider pages internally and fails rather than presenting truncated data as complete.
_Avoid_: Implicit page, best-effort full read

**Page Read**:
A read of one bounded provider page that returns opaque continuation state when more data is available.
_Avoid_: Partial complete read

**Table Source**:
Exactly one DataFrame, existing Table, portable SQL query, or explicit sheet-mode range used to populate a newly created Table.
_Avoid_: Create-from-query operation, create-from-range operation

**Receipt**:
Credential-safe evidence of one physical interaction with a Table, including the observed target identity and version when available.
_Avoid_: Run, RunResult, RunState, lineage graph

**Operation Result**:
The normalized outcome of one OTC operation, containing its value, execution state, physical Receipts, continuation state, warnings, and error evidence when applicable.
_Avoid_: TableWriteResult, CopyResult, SqlQueryResult, RunResult

**SQL Source**:
A logical name bound explicitly to a Table or DataFrame for one portable SQL query. SQL text cannot discover physical resources.
_Avoid_: Relation

**OTC SQL Lite**:
The bounded, read-only SQL surface that compiles into an OTC-owned Portable Plan before any execution strategy is selected.
_Avoid_: Provider SQL, SQLGlot AST, general SQL

**Portable Plan**:
A versioned, provider-neutral relational or temporal query meaning produced from OTC SQL Lite and evaluated with identical semantics across supported media.
_Avoid_: SQL text, parser tree, provider execution plan

**Native SQL**:
Provider-dialect SQL executed only through an explicitly selected physical capability, without portable cross-medium semantics or automatic fallback.
_Avoid_: OTC SQL Lite, portable fallback
