# Troubleshooting

## Common failures

| Symptom | Check |
| --- | --- |
| `no connector advertises this endpoint scheme` | Install the provider package or use a supported scheme |
| `local destination format could not be inferred` | Supply `--to-format` for `convert` or use a recognized suffix |
| `connector sources do not support --from-format` | Remove the source format override for remote providers |
| `snapshot_unavailable` | Use the snapshot reference returned by the same managed target |
| `protocol_invalid` | Recompute the descriptor hash from the exact Arrow schema |
| `resource_limit_exceeded` | Reduce the range/projection or raise bounds deliberately |
| formula capability rejected | Check the provider's advertised grid/field identity and dialect |
| process exits before handshake | Check absolute bootstrap/artifact paths and provider registration |

## Get useful diagnostics

Run the smallest safe operation first:

```console
otc list --output-format json
otc inspect --from /absolute/path/source.csv --output-format json
```

Capture the stable error code, provider/capability identity, operation ID, and
safe details. Do not paste tokens, passwords, DSNs, or complete credential
environment dumps into an issue.

## Verify after a mutation

For writes and managed operations, inspect the destination or read back the
returned snapshot. An unknown commit outcome is a reconciliation case; do not
blindly retry a mutation with a new idempotency key.
