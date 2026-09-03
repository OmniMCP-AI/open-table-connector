# Deployment

## CLI deployment

Install the CLI and provider wheels into the same environment:

```console
uv tool install open-table-connector
otc list
```

For a managed application, install the exact package versions from a lockfile
or artifact manifest and validate the provider inventory before accepting
traffic.

## Process deployment

`otc-process` runs a framed stdio protocol for callers such as OTS:

```console
export OTC_PROCESS_CONFIG=/etc/ots/otc-process.json
export OTC_ARTIFACT_ROOT=/var/lib/ots/otc-artifacts
uv run --package open-table-connector-process otc-process
```

The bootstrap JSON is a closed regular file with no credentials. It binds one
provider, target, descriptor, and managed-storage choice. A deployment-owned
wrapper supplies the provider registry and credential resolver.

## Production checklist

- use absolute, owned, non-symlink config and artifact paths;
- keep credentials in the deployment secret store or environment;
- set finite row, byte, and duration limits;
- pin provider/package versions and capability identities;
- retain receipts and reconciliation references; and
- run the conformance and release verification gates before promotion.
