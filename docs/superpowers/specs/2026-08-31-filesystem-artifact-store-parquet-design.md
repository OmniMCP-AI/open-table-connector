# OTC Filesystem Artifact Store and Parquet Design

## Status

Approved as an architectural direction in chat on 2026-08-31. This document
records a future OTC upgrade prerequisite for `bean-etl`; it does not authorize
the implementation or the Bean runtime migration.

Architecture identifier: `otc-filesystem-artifact-store-parquet/v1`.

## Decision

Open Table Connector (OTC) will own Parquet as a physical table codec and will
provide the filesystem implementation used by an ETL artifact store.

The ownership boundary is:

- OTC owns Parquet encoding and decoding, codec versioning, physical checksums,
  filesystem layout, locking, atomic writes, durable replacement, integrity
  readback, and compare-and-swap persistence.
- ETL owns the meaning of an artifact: semantic manifests, schema contracts,
  membership meaning, lineage, pipeline materialization policy, and the logical
  meaning and naming policy of references.
- A Bean filesystem store is a thin adapter over OTC. It must not call Polars or
  PyArrow Parquet writers directly and must not implement its own files, locks,
  temporary-file protocol, or reference document.

Parquet support belongs in the existing
`open-table-connector-local-files` distribution. The neutral contract defines
the interface and capability identity; the local-files capability manifest
advertises and implements it. Parquet must not become a required concern of
every OTC connector or of the base ETL runtime.

The artifact capability must also have a small dependency closure. The current
local-files distribution depends mandatorily on the time-series and Excel
packages; the OTC upgrade must make those concerns optional or otherwise let
artifact-store users install the contract, Arrow/Polars, and local artifact
implementation without pulling temporal or spreadsheet behavior.

## Context

The current FinClaw local ETL store writes Parquet through Polars, hashes the
encoded bytes, stores JSON manifests, and maintains named references in an
atomically replaced JSON file. Moving that code into `bean-etl` would make the
new ETL package responsible for a file format and a crash-safe storage engine.
That is the wrong dependency direction: Parquet and filesystem persistence are
reusable table I/O capabilities, while ETL should remain concerned with
pipelines and artifact semantics.

OTC does not yet provide the required generic capability:

- `TableWriter` is a one-shot physical write interface and does not provide an
  immutable artifact lifecycle, independent integrity readback, or named-ref
  compare-and-swap.
- The newer managed snapshot implementation is temporal. It requires a
  `TemporalTableDescriptor` and event-time semantics, so it must not be used for
  ordinary ETL artifacts by inventing synthetic time fields.
- The OTC revision currently pinned by FinClaw predates even that temporal
  managed-storage implementation.

The Bean filesystem adapter therefore remains blocked until OTC gains a
generic, non-temporal filesystem artifact store and Parquet codec.

## Required OTC capability

The OTC upgrade must provide a generic immutable table-artifact lifecycle with
these behaviors:

1. Stage a table privately using a declared codec profile.
2. Commit the encoded content durably without changing a named reference.
3. Read the committed content back independently and verify its checksum,
   schema, shape, and codec before returning a table.
4. Abort an uncommitted stage idempotently.
5. Resolve a named reference atomically.
6. Compare-and-swap a named reference to a committed artifact.

Commit and reference publication are deliberately separate. This permits an
ETL materialization flow to commit immutable output, read it back, run its own
checks, and publish the logical reference only after those checks succeed.

OTC keeps two identities distinct:

- `PhysicalArtifactId` is OTC-owned and is the SHA-256 identity of the encoded
  Parquet bytes.
- `ArtifactKey` is an opaque caller-owned key. Commit binds it immutably to one
  physical artifact, and named references target this key.

This permits Bean to use its semantic `ArtifactId` as the caller key without
claiming that the semantic identity and Parquet-byte identity are equivalent.
Reusing a key for different physical content is an immutable-binding conflict.

The local implementation owns every filesystem operation. A binding may carry
one bounded opaque metadata document, stored and returned without OTC
interpreting it; this is sufficient for Bean's semantic artifact manifest.
Optional membership is stored as a separate table artifact under another
caller key chosen by the Bean adapter. OTC does not interpret ETL manifests,
membership, lineage, gates, or contracts. Logical reference policy remains
ETL-owned, while the physical reference update and its concurrency guarantees
are OTC-owned.

The binding record itself is immutable, durable, and independently
readbackable. Several caller keys may bind the same physical bytes while
carrying different metadata. For Bean, the main caller key is its semantic
`ArtifactId`; the adapter derives a separate membership key from that ID when
membership exists. Reading the main key returns its physical identity and
semantic manifest, and the adapter then verifies the derived membership
artifact against the checksum declared by that manifest. Named references
target the main caller key, never the raw Parquet checksum.

The generic store must not depend on the OTC time-series package. Temporal
storage may later reuse lower-level filesystem primitives from the generic
implementation, but the generic contract cannot require temporal descriptors,
event-time columns, ranges, windows, or snapshot-current semantics.

## Parquet codec profile

The first codec profile should be a closed, versioned OTC profile such as
`otc.parquet/v1`. It cannot mean “use the installed writer defaults.” At a
minimum, the profile fixes:

- the supported writer implementation and version envelope;
- compression algorithm and level;
- row-group, data-page, dictionary, and statistics behavior;
- Arrow chunk and schema-metadata normalization;
- row order and column order;
- timestamp unit, timezone, and truncation rules;
- decimal, categorical, null, NaN, infinity, and signed-zero handling; and
- the supported Arrow/Polars type matrix.

The same canonical table and codec profile must produce the same encoded bytes
and SHA-256 identity in every environment OTC claims to support. Golden vectors
must cover the encoded bytes and checksum across fresh processes and supported
platforms. A writer or option change that alters bytes requires a new codec
profile version; OTC must never silently change `otc.parquet/v1`.

Unsupported or lossy types fail before durable visibility. Readback verifies
the physical checksum before decoding and then verifies the observed schema,
row count, column count, and logical content facts recorded at commit.

## Filesystem guarantees

For the local implementation:

- Committed artifact bytes are immutable and content-addressed.
- Recommitting identical content is idempotent and reuses the existing bytes.
- Reusing an identity for different bytes fails closed and never overwrites the
  existing artifact.
- Staged content is not visible through committed reads or named references.
- Reference publication validates that the target artifact is committed and
  intact.
- Compare-and-swap first returns idempotent success when the current key already
  equals the requested target. Otherwise it publishes only when the current key
  equals `expected`; in that comparison, `expected=None` means absent. Every
  other mismatch is a zero-mutation conflict reporting the reference, expected
  key, actual key, and target key.
- Two processes racing to create the same absent reference with different
  targets have exactly one winner. Racers publishing the same target may both
  report success, with one result identified as an idempotent replay.
- Every mutating request has an idempotency key bound to a canonical request
  fingerprint. Reusing the key for the same request recovers the same durable
  outcome; reusing it for another request fails with an idempotency conflict.
- A retry after visibility but before receipt delivery reconciles from durable
  state and returns the original result rather than repeating or rolling back
  the mutation.
- Temporary writes, file flushes, atomic replacement, directory flushes, and an
  interprocess lock protect artifact and reference visibility across crashes.
- A reopened store either observes the previous complete state or the new
  complete state, never a partial document or partial artifact.
- Store roots and derived paths are confined, and symlinks, traversal, and
  non-regular artifact files are rejected.

Every operation returns a closed, versioned, credential-safe receipt with a
common operation identity, request fingerprint, and disposition. Mutating
receipts also carry the idempotency key and are durably recoverable. Artifact
lifecycle receipts contain the caller key, codec profile, physical checksum,
observed schema and shape facts, and durability or visibility result. Reference
receipts contain the reference and its observed or resulting caller key.
Receipts and errors must not contain table values, credentials, or unsafe
absolute paths.

## Bean integration boundary

After OTC implements this capability, `bean-etl` may supply an OTC-backed
adapter for its existing semantic `Store` interface.

The adapter may:

- translate Polars frames to OTC's canonical table carrier;
- construct and verify `etl.artifact-manifest/v1` documents;
- derive the existing semantic `ArtifactId` from that manifest;
- attach the semantic manifest as the OTC binding's one opaque metadata
  document and store optional membership under a separate OTC caller key;
- translate OTC reference conflicts to Bean's `PublicationConflict`; and
- return Polars frames after OTC-verified readback.

The adapter may not encode Parquet, open artifact paths, write JSON files,
acquire filesystem locks, or implement atomic replacement itself. No OTC types
need to appear in the small top-level `bean_etl` API.

## Compatibility boundary

The existing FinClaw store records `{"name": "parquet", "version": "1"}` but
uses Polars writer defaults. That label is not a deterministic codec contract
and must not be reinterpreted as `otc.parquet/v1`.

Because the current ETL artifact identity that Bean intends to preserve
includes checksums of encoded Parquet bytes, a deterministic OTC codec may
produce new artifact IDs for the same logical table. The later Bean migration
must explicitly choose between:

- an OTC-owned legacy layout/codec adapter that preserves lookup of existing
  IDs and allows old runs to retain their current resume behavior; or
- a declared cutover after which legacy runs remain readable evidence but are
  non-resumable and new runs rebuild artifacts and references.

Existing hash-chained event documents, run outputs, or artifact IDs must never
be rewritten during migration because doing so invalidates their recorded
hashes. The migration choice belongs to the Bean specification. Any legacy
physical reader remains an OTC adapter so Bean never opens the old layout or
decodes its Parquet directly. Serialized ETL identities such as
`etl.artifact-manifest/v1` remain ETL-owned.

## Non-goals

- Do not move ETL pipelines, transforms, checks, gates, contracts, lineage, run
  state, retries, or resume behavior into OTC.
- Do not adapt the temporal managed store with fake temporal descriptors.
- Do not require Parquet support from remote, spreadsheet, or database
  connectors.
- Do not add streaming, windows, watermarks, or exactly-once pipeline claims.
- Do not add mutable artifact updates, merge, deletion, garbage collection, or
  retention in the first generic store version.
- Do not require a `parquet://` CLI surface as part of this prerequisite; the
  codec and managed local store are sufficient for Bean integration.
- Do not implement this design as part of the `bean-etl` extraction.

## Upgrade completion criteria

OTC is ready for the Bean filesystem adapter when:

- the generic store is non-temporal and passes lifecycle, restart, corruption,
  symlink, resource-bound, and interprocess concurrency tests;
- the installable artifact path does not require the time-series or Excel
  implementations, and locking/durability behavior is tested on every platform
  OTC claims to support;
- `otc.parquet/v1` has a documented type matrix and golden byte/hash vectors;
- commit, independent readback, and named-ref compare-and-swap are covered by a
  reusable conformance suite;
- fault-injection tests cover crashes before and after artifact and reference
  visibility; and
- Bean can pin one exact OTC Git commit containing both the contract and local
  implementation.

The FinClaw filesystem implementation remains excluded from the `bean-etl`
extraction from the start. Only after these criteria pass should `bean-etl` add
its thin OTC adapter.
