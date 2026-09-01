# Open Table Connector Time Series

This distribution provides the versioned portable temporal descriptor, plan,
capability, and storage contracts used by Open Table Connector backends.

The public managed-storage contract includes provider-neutral current recovery:
`ManagedCurrentRequest`, `ManagedCurrentResult`, and the immutable
`ManagedSnapshotState` returned by the SDK. The portable temporal operation
union is `ScanRange`, `Latest`, `BucketAggregate`, and `GapFill`; `AsOf` is a
typed helper rather than a SQL operation. Descriptor duplicate policy governs
whether order-sensitive `first` and `last` aggregates are valid.
