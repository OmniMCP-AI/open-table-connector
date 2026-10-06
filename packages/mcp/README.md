# open-table-connector-mcp

Optional typed MCP transport for Open Table Connector discovery, inspection,
and execution. The adapter is policy-gated and can be removed without
affecting the core SDK or CLI.

Install with `pip install open-table-connector-mcp`; the `otc-mcp` entry point
starts the bounded stdio adapter.

The server registers exactly three tools:

- `otc_discover` lists versioned operations and capability evidence;
- `otc_inspect` inspects a typed target through the configured SDK; and
- `otc_execute` runs a typed operation and returns normalized result/receipt
  evidence.

Set `OTC_MCP_CONFIG` to an explicit fail-closed policy before deployment. The
policy constrains allowed roots, remote origins, providers, and output parents.
Requests reject shell commands, arbitrary module names, and credential values;
stdout remains reserved for MCP protocol framing. Host-backed execution and
live provider acceptance remain runtime-dependent.
