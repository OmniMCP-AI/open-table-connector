# Open Connectors

Open Connectors are independently released, framework-neutral integrations
for physical data systems. This workspace is intentionally independent of
FinClaw and Open Time Series.

```text
physical system
      |
      v
neutral Connector
  URI + capability + Arrow/Polars + receipt
      |                         |
      v                         v
FinClaw Binding          Open Time Series Binding
```

Connectors own vendor URI parsing, credentials injected by callers, physical
I/O, schema conversion, retries, limits, and neutral receipts. Bindings own
translation into a framework's interfaces. A Connector never owns framework
publication, temporal commit, OpenLineage assembly, business mapping, or
canonical acceptance.

The first workspace packages are:

- `open-connectors-contract`: closed v1 identity, URI, Base/Sheet coordinate,
  receipt, error, and Arrow/Polars read contracts;
- `open-connectors-conformance`: reusable parity and dependency-direction
  checks; and
- `open-connectors-local-files`: CSV and Excel read/inspect implementation.

The `open_connectors` Python namespace is PEP 420 based; framework packages
are never dependencies of the neutral packages.
