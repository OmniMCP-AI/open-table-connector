# Open Table Connector

Open Table Connector normalizes table-shaped data operations across physical media while preserving the meaningful differences between record tables and spreadsheet surfaces.

## Language

**Table**:
A schema-bearing physical tabular resource accessed through exactly one Connector, identified by a canonical Table URI, and governed by a Table Mode.
_Avoid_: Materialized Table, TableRef, TableHandle, relation, worksheet, grid

**Materialization**:
An OTC operation that evaluates a Table Source and creates one new Table through exactly one destination Connector. An existing destination is a conflict rather than an implicit update or replacement.
_Avoid_: Create-from-source operation, copy operation, transfer operation

**Connector**:
A pluggable physical-medium implementation that inspects, reads, creates, and mutates Tables. Creation receives an SDK-prepared bounded carrier or certified provider plan, not a public Table Source object.
_Avoid_: SDK, CLI adapter, backend mode

**Table Theme**:
A portable presentation intent supplied when a Table Source is materialized and expressed over semantic table regions rather than physical coordinates. It does not change table data semantics.
_Avoid_: Table Style, grid style, workbook theme

**Table Style**:
The concrete presentation supported or observed on a Table through a versioned capability. It may realize a Table Theme within target-specific property constraints.
_Avoid_: Table Theme, worksheet style, range style

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
A stable, credential-free identifier for one Table. Provider-specific resolution and canonicalization do not change its meaning to callers.
_Avoid_: TableRef, TableHandle

**DataFrame**:
The canonical in-memory table value in Python, represented by `polars.DataFrame` and containing data only; source identity and execution evidence remain separate.
_Avoid_: Logical Table, FrameMeta, metadata-bearing frame

**Complete Read**:
A read of one whole bounded Table within configured finite limits. It follows provider pages internally and fails rather than presenting truncated data as complete.
_Avoid_: Implicit page, best-effort full read

**Page Read**:
A read of one bounded provider page that returns opaque continuation state when more data is available.
_Avoid_: Partial complete read

**Table Source**:
Exactly one DataFrame, Table, Query, or explicit sheet-mode range that supplies rows to an OTC query or Materialization.
_Avoid_: Create-from-query operation, create-from-range operation

**Query**:
An immutable, deferred table-producing computation backed by a Portable Plan and explicit Table Sources. Its evaluated value is a DataFrame.
_Avoid_: Logical Table, SQLGlot AST, LazyFrame

**Receipt**:
Credential-safe evidence of one operation phase. A physical Receipt identifies the exact observed physical resource and scope—Table when applicable, otherwise for example a database execution domain or grid range—and its revision when available; a local execution Receipt records bounded plan evaluation without inventing a physical interaction.
_Avoid_: Run, RunResult, RunState, lineage graph

**Operation Result**:
The normalized outcome of one OTC operation, containing its value, execution state, ordered Receipts, continuation state, warnings, and error evidence when applicable.
_Avoid_: TableWriteResult, CopyResult, SqlQueryResult, RunResult

**Reconciliation**:
A read-only recovery operation that resolves an uncertain physical mutation from its original operation identity and Connector evidence without repeating the mutation blindly.
_Avoid_: Retry, rollback, repair

**Row Insertion**:
A Table mutation that adds new rows without changing or removing existing rows.
_Avoid_: Append, Write

**Row Update**:
A strict keyed Table mutation in which every submitted key matches exactly one existing row and only supplied non-key fields change; it never inserts or deletes rows.
_Avoid_: Upsert, Replace, Write

**Row Deletion**:
A Table mutation that removes rows selected by a required portable predicate while preserving the Table identity and schema.
_Avoid_: Clear, Drop, Delete Table

**Table Drop**:
A physical mutation that removes one Table resource without implicitly removing its parent database, workbook, Sheet-mode Grid, or provider container.
_Avoid_: Row Deletion, Clear, Replace

**SQL Source**:
A logical name bound explicitly to a Table Source for one portable SQL query. SQL text cannot discover physical resources.
_Avoid_: Relation

**OTC SQL Lite**:
The bounded, read-only SQL surface that compiles into an OTC-owned Portable Plan before any execution strategy is selected.
_Avoid_: Provider SQL, SQLGlot AST, general SQL

**Portable Plan**:
A versioned, provider-neutral relational or temporal query meaning produced from OTC SQL Lite and evaluated with identical semantics across supported media.
_Avoid_: SQL text, parser tree, provider execution plan

**Time-Series View**:
A descriptor-bound temporal interpretation of a Table Source. It is an orthogonal semantic overlay rather than a third Table Mode.
_Avoid_: Time-series table mode, separate table resource

**Temporal Descriptor**:
The immutable semantic description of a Time-Series View, including its event-time field, series keys, tags, values, timezone, precision, ordering, and duplicate policy.
_Avoid_: Inferred timestamp schema, provider metadata

**Temporal SQL**:
The constrained OTC SQL Lite profile whose accepted shapes compile exactly into the Portable Plan operations supported by a Time-Series View.
_Avoid_: TimescaleDB passthrough, native temporal SQL

**Native SQL**:
Provider-dialect SQL executed only through an explicitly selected physical capability, without portable cross-medium semantics or automatic fallback.
_Avoid_: OTC SQL Lite, portable fallback
