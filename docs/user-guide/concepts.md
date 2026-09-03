# Concepts

OTC separates physical access, in-memory values, query meaning, and evidence.
That separation keeps provider differences visible without making every caller
depend on provider internals.

| Concept | Meaning |
| --- | --- |
| Connector | Pluggable physical-medium implementation for inspect, read, create, or mutate operations |
| Table | Schema-bearing resource addressed by one credential-free Table URI and one Table Mode |
| DataFrame | In-memory `polars.DataFrame`; it contains data, not source identity or evidence |
| Table Source | A `DataFrame`, `Table`, `Query`, or explicit bounded sheet range |
| Query | Immutable deferred computation that produces a DataFrame |
| Receipt | Credential-safe evidence for one operation phase |
| Operation Result | Value plus outcome, commit state, verification, receipts, warnings, and error evidence |
| Temporal descriptor | Immutable interpretation of a table as a time series |
| Portable plan | Versioned provider-neutral relational or temporal query meaning |

## Table modes

`base-mode` represents records and typed fields. `sheet-mode` represents a
bounded, header-aware table region inside a spreadsheet grid. A worksheet,
arbitrary cell range, or workbook is not itself a `Table`.

## Reads and writes

Complete reads are bounded whole-table reads that fail rather than silently
returning truncated data. Page reads return one bounded page and continuation
state. Materialization is create-only: an existing destination is a conflict,
not an implicit replace. Existing tables change through explicit `insert`,
keyed `update`, predicate-required `delete`, and `drop` operations.

## Temporal interpretation

A `TimeSeriesView` overlays a `Table` with a `TemporalTableDescriptor`. The
descriptor names event time, series keys, tags, values, timezone, precision,
ordering, ingestion time, and duplicate policy. It does not create another
physical table mode.

## Evidence

Receipts identify the physical resource or local execution, requested and
observed bounds, schema/content fingerprints, resource counts, ordering, and
snapshot references where applicable. Credentials are intentionally absent.
The caller can retain receipts as the evidence chain for a result.
