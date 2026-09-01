# open-table-connector-conformance

Conformance fixtures and reusable assertions for Connector implementations,
including the provider-neutral Formula Extension.

Install with `pip install open-table-connector-conformance`; import
`open_table_connector.conformance`.

## Formula Extension

`open_table_connector.conformance.formulas` validates provider cases against
the closed Formula contract without prescribing a portable formula language.
It checks target-kind routing, provider-native dialect identity, explicit
Formula activation, bounded grid ranges, copy-fill semantics, independent
formula-text readback after mutation, calculated-value evidence, revision and
idempotency behavior, capability subsets, and safe Receipt/error surfaces.

Formula cases are either grid targets (`GridFormulaTarget` plus a worksheet)
or field targets (`FieldFormulaTarget` plus an opened base-mode `Table`). The
shared assertions do not make Formula capabilities available by themselves;
provider packages must opt in only after their adapter passes the focused
conformance suite.

At the core checkpoint, the real provider descriptors intentionally advertise
no Formula identities. The grid-provider and field-provider plans are the
follow-on boundaries where proven capabilities may be enabled.
