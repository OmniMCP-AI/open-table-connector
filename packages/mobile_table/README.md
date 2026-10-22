# OTC mobile table contract

This package contains the versioned `otc.mobile.table/1.0` wire models and the
reference HTTP adapter used by H5 and WeChat mobile table clients. It keeps
record editing optional: hosts without stable IDs, revisions, idempotency, and
canonical readback remain read-only.

See [the HTTP reference](../../docs/reference/mobile-table-http.md) for the
endpoint envelopes, limits, host qualification rules, and rollout metrics.

The package has no renderer dependency. `packages/mobile_table/tests` validates
the JSON schemas and shared fixtures; the H5 and WeChat packages consume the
same fixtures through the shared TypeScript controller.
