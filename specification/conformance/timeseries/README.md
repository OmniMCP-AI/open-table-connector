# Portable temporal conformance v1

This suite certifies the scale-down Open Time Series storage surface exposed by
Open Table Connector. It compares logical Arrow schemas and ordered values,
never provider-specific IPC bytes. Lifecycle cases are run only for providers
that explicitly advertise stage, idempotent commit, snapshot read, independent
readback, atomic visibility, and abort.

The normal JSON schemes are `json://` and `jsonl://`; managed lifecycle state is
selected by an out-of-band snapshot reference and is never encoded as a
`managed+` URI.

The provider inventory distinguishes offline evidence from configured-live
evidence. MaybeSheet remains import/export-only unless its real command probe
and receipts prove stronger capabilities.
