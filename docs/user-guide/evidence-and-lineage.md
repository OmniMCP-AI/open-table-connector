# Evidence and lineage

OTC treats explainability as a contract. Each physical read, local plan
evaluation, formula mutation, and managed-storage phase emits credential-safe
receipt facts.

## What a receipt contains

A receipt may include:

- connector and capability identities;
- safe target and table mode;
- operation ID and source revision;
- descriptor, portable-plan, and definition hashes;
- requested/observed ranges and deterministic output order;
- examined and returned rows/bytes plus elapsed time;
- schema/content fingerprints; and
- stage, snapshot, or reconciliation references.

Raw tokens, passwords, DSNs, formula text where unsafe, and credential-bearing
URIs do not belong in receipts or diagnostics.

## Verify a temporal result

```python
result = client.collect(query)
assert result.require_value() is not None
for receipt in result.receipts:
    print(receipt.kind, receipt.operation, receipt.details)
```

For managed storage, treat commit acknowledgement and readback as separate
facts. Readback must independently prove the committed snapshot; a staged
request is not evidence that a snapshot is visible.

## Explainability boundary

OTC receipts explain physical connector work and portable evaluation. The
application or OTS layer may combine those receipts with domain decisions,
policy outcomes, or OpenLineage graphs. OTC does not invent business lineage
or claim that a local execution interacted with a remote provider.
