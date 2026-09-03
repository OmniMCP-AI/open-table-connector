# Error codes

Errors are stable structured evidence. CLI callers receive one JSON object on
stderr; SDK callers receive an `OTCError` whose `result.error` contains the
code, safe message, and safe details.

Common codes include:

| Code | Meaning |
| --- | --- |
| `invalid_uri` | Endpoint is malformed or contains forbidden credentials |
| `unsupported_capability` | Selected provider does not advertise the operation |
| `authentication` | Credential resolution or provider authentication failed |
| `conflict` | Create-only destination already exists or write conflicts |
| `timeout` | Provider or bounded execution exceeded its deadline |
| `cancelled` | Caller cancellation was accepted |
| `execution_failed` | Provider operation failed without a more specific code |
| `readback_mismatch` | Returned data does not match the committed/requested identity |
| `protocol_invalid` | Connector or process response violates its contract |
| `protocol_version_unsupported` | Protocol version cannot be negotiated |
| `resource_limit_exceeded` | Row, byte, or duration bound was exceeded |
| `snapshot_unavailable` | Requested managed snapshot cannot be read |
| `idempotency_conflict` | Reused idempotency key has different request content |
| `visibility_incomplete` | Commit did not prove atomic visibility |
| `invalid_sql` | SQL is outside the selected portable/native policy |
| `invalid_configuration` | Provider configuration is malformed or unsafe |

Treat `code` as the machine interface. Human messages and safe detail keys may
grow while preserving the code contract.
