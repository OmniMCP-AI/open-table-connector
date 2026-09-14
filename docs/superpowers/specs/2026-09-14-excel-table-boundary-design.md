# Excel table boundary

Approved scope: add reusable OTC table I/O for FinClaw Gold Base and rectangular report blocks. Keep business projections, metrics and financial semantic verification in the consumer. Do not add a template engine or a second workbook implementation.

## API and semantics

1. `client.materialize(frame, to="file:///absolute/book.xlsx#sheet=Base")` uses the existing DirectDestination contract. Explicit worksheet is required. A missing file is created; an existing file gets a new worksheet. Existing worksheet names (case insensitive) are rejected, including identical contents. No append/overwrite fallback. Return the existing SDK Table and operation evidence.
2. `range.write_table(frame, header=True, style=None)` and `range.read_table(header=True)` reuse the existing range operations. The caller supplies a bounded rectangle; OTC owns column names, row conversion and shape checking. No extra session or commit occurs. `read_table` preserves the observation result's effects and receipts.
3. Excel tables follow existing RAW lexical semantics: bounded range table values are encoded as strings, with nulls retained under the general profile. Direct materialization writes integers of at most 15 decimal digits as numeric cells (needed for SUMIFS); wider integers, floats and booleans use lexical strings. Readback always uses RAW string columns. Literal-artifact still requires string-only cells. String cells beginning with `=`, `+`, `-`, `@` are literals. Large integer text remains exact. Headers must be nonempty unique strings. Nested/object/binary values are rejected, as are XML-illegal characters and text longer than Excel's 32767-character limit. No implicit formula evaluation, schema inference or hidden schema sheet. Consumers perform explicit domain schema conversion.
4. Direct materialization is restricted to header-bearing A1 worksheet tables. No worksheet selector omission, credentials, query parameters, duplicate selector, unsupported URI, or alternate destination form. Reject all-null data rows for direct materialization because the existing worksheet reader omits them. Bounded range tables may preserve all-null rows.

## Publication and evidence

Reuse the existing local workbook provider for preflight, preservation checks, exclusive creation, revision conflicts, atomic replacement and physical verification. Verify persisted table content against normalized input before returning success. Return real commit and read receipts; never hash the input and call that readback. Preserve post-commit/unknown effects if later readback fails. Other local formats remain unsupported for materialize.

The table API must not overwrite unrelated sheets, formulas or styles. Provider preservation restrictions remain in effect. Use existing ArtifactLimits before allocating a large range matrix. SDK routing recognizes worksheet-qualified file URIs while the legacy CLI endpoint parser stays unchanged. LocalFilesCliAdapter exposes its native SDK connector for discovery so configured clients use the same table implementation as explicit registries.

## Acceptance

Targeted tests cover new/existing workbooks, preserved formula/style sheets, duplicate destination, lexical precision/formula-like strings, nulls, empty tables, malformed destinations, unsupported values, bounds/shape errors, stale revisions and injected readback failure. Existing workbook and local Excel read tests remain green. Do not run the repository-wide suite for this change. Record exact checks and completion in the implementation plan.
