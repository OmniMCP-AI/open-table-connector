# Deferred OTC Rust Adapter SDK and OTS Integration

**Status:** deferred compatibility design; OTS integration is on hold; no
implementation plan is authorized by this document.

**Date:** 2026-08-31

**Depends on:** the Polars-first OTC Python SDK, its Connector seam, managed
operation lifecycle, and internal host port reaching a stable contract.

## Decision

OTS remains predominantly Rust. It may later use OTC through a neutral Rust
Adapter SDK, but that work is separate from the Python SDK refactor:

```text
OTS Rust
    |
    | typed, versioned adapter protocol
    v
OTC Rust Adapter SDK
    |
    | internal SDK host port
    v
OTC Python SDK
    |
    v
pluggable physical-medium Connectors
```

The local Python host or subprocess that realizes the internal host port is an
implementation detail. It is not a fourth public architecture layer, a second
provider runtime, or an application API.

The adapter boundary carries closed, canonical plans and typed physical
identities. It never carries SQL text, Python objects, Connector instances,
credential values, or OTS kernel types. OTS retains ownership of OTS query
parsing, lowering, semantic acceptance, retry policy, and fallback policy.

## Goals

1. Preserve one OTC provider discovery, credential, routing, capability, and
   execution runtime in the Python SDK.
2. Let a future OTS integration use OTC without embedding Python in OTS or
   rewriting OTS in Python.
3. Provide a reusable, framework-neutral Rust crate for protocol framing,
   compatibility, artifacts, cancellation, errors, and lifecycle recovery.
4. Preserve bounded portable-plan semantics and independently verifiable
   physical Receipts across the language boundary.
5. Make Python/Rust plan parity and normalized-result parity testable from an
   independent language-neutral corpus.
6. Preserve managed stage, commit, readback, abort, and reconciliation
   semantics across transport and process failures.

## Non-goals

- Starting OTS integration, extraction, or protocol migration now.
- Rewriting the OTS kernel, CLI, MCP server, SQL frontend, or storage policy in
  Python.
- Embedding a Python runtime in OTS through PyO3, CPython FFI, or a similar
  mechanism.
- Making the Rust Adapter SDK another Connector runtime, provider registry, SQL
  frontend, or semantic planner.
- Exposing the complete Python SDK surface to Rust before a concrete OTS need
  exists.
- Sending relational or temporal SQL text, arbitrary Python imports, code,
  provider objects, or untyped option maps over the adapter protocol.
- Choosing a long-lived daemon, remote service, or multiplexed network
  deployment in this deferred phase.

## Relationship to the Python SDK Model

The Python SDK defines three core concepts:

| Concept | Meaning | Adapter boundary |
| --- | --- | --- |
| `polars.DataFrame` | Concrete in-memory Python table value | never crosses the wire |
| `Query` | Immutable deferred table-producing computation | its OTS-used meaning is represented by a canonical Portable Plan and one typed physical source, not serialized as a Python object |
| `Table` | Physical Connector-backed table handle | represented by a closed physical target/identity message, not serialized as a Python object |

A Query is not a DataFrame, arbitrary SQL text, or provider plan. A Table is
not an in-memory result. OTS never receives a Python DataFrame, Query, Table,
Connector, credential resolver, or provider handle.

The adapter accepts only closed members of the versioned OTC Portable Plan
family, initially the OTS-required temporal subset. The Python SDK's SQLGlot
frontend is not invoked by OTS requests. OTS retains Timescale-compatible SQL
parsing and lowers accepted OTS semantics to the same canonical plan model.

Protocol v1 is intentionally narrower than Python `TableSource`: an
`execute_plan` request accepts exactly one descriptor-bound physical Table
source. It rejects DataFrame, Query-as-source, sheet-range, and multi-source
bindings. A later source expansion requires a new reviewed protocol version.

## Component Ownership

### OTC Python SDK

The Python SDK remains authoritative for:

- installed-Connector discovery and route selection;
- provider configuration and credential leases;
- physical target resolution and effective-capability preflight;
- source snapshot binding, resource admission, and execution strategy;
- Connector and temporal-extension execution;
- managed stage, commit, readback, abort, and reconciliation;
- Arrow carrier validation and public Polars conversion;
- normalized operation state, Receipts, errors, and cleanup; and
- the internal carrier-preserving host port.

The SDK imports no OTS code and contains no OTS plan, evidence, or storage
types.

### Internal SDK host port

The host port is a non-public SDK interface used by the protocol host. It
owns:

- closed-schema request validation and dispatch into one SDK Client;
- mapping SDK operation state and Receipt variants to versioned wire models;
- use of verified internal Arrow carriers without a Polars round trip;
- bounded artifact publication and cleanup;
- cancellation propagation; and
- safe serialization and redaction.

An initial implementation may be a supervised local Python subprocess. That
host must use the SDK's existing discovery, credential, and execution runtime;
it must not maintain a second provider registry or reconstruct Connector
semantics.

### OTC Rust Adapter SDK

The framework-neutral Rust crate owns:

- versioned request, response, capability, Receipt, error, and artifact wire
  models;
- transport startup/shutdown and injectable test transports;
- framed message correlation and compatibility negotiation;
- deadlines, cancellation, and host-exit handling;
- Arrow artifact confinement, media/version checks, size checks, digest
  verification, and lease cleanup;
- stable Rust error mapping; and
- validation, transport, and persistence of opaque versioned
  managed-operation and reconciliation identity records.

It owns no OTS kernel types, SQL parsing, Portable Plan semantics, provider
selection, credential values, semantic retries, or fallback decisions. It
does not construct, reinterpret, or extend the SDK's idempotency or
reconciliation binding rules. It must be releasable from the OTC repository
independently of OTS.

### OTS integration code

Ordinary OTS-owned integration code remains in the OTS repository and owns:

- implementation of the OTS storage adapter seam;
- Timescale Core/Add-ons SQL parsing and OTS semantic acceptance;
- lowering the supported OTS subset to canonical OTC Portable Plans;
- selecting required capability identities and explicit bounds;
- selecting an OTS-configured logical target and supplying a typed requested
  physical address, descriptor, expected-identity constraints, and required
  snapshot/uniqueness policy;
- translating neutral operation state and Receipts into OTS evidence;
- independently checking returned identity, schema, ordering, range, snapshot,
  bounds, and visibility against the original request;
- OTS retry, reconciliation, fallback, and lifecycle policy; and
- rejecting a transport-successful result that is semantically inadequate for
  OTS.

No OTS kernel type crosses the neutral adapter protocol.

## Adapter Protocol

### Identity and compatibility

The future protocol identity is:

```text
otc.rust-adapter/v1
```

It is a new closed protocol. It does not silently widen or claim wire
compatibility with the existing `otc.connector-process/v1` transport. Existing
process code and schemas are migration inputs only.

Compatibility is negotiated from explicit protocol, schema, capability,
Portable Plan, descriptor, Receipt, artifact-media, and corpus versions. A
repository commit hash is not a compatibility contract. Unsupported versions
or capability combinations fail before data-bearing I/O.

### Operation families

The initial closed operation set is:

```text
hello / negotiate
describe
execute_plan
stage
commit
readback
abort
reconcile
cancel
```

- `hello / negotiate` selects one exact compatible protocol/schema set.
- `describe` asks the SDK to resolve the physical Table and returns its
  canonical identity, Table Mode, observed schema, descriptor validation, and
  effective capabilities. It does not mint an execution snapshot.
- `execute_plan` accepts canonical Portable Plan JSON and typed execution
  metadata, never source SQL.
- `stage`, `commit`, `readback`, and `abort` preserve managed-operation
  lifecycle semantics.
- `reconcile` performs a read-only lookup after an uncertain effect.
- `cancel` requests bounded cancellation by correlated request identity.

Generic table mutation and relational-query operations are not added until a
concrete Rust consumer needs them and their semantics are separately approved.

### Request envelope

Every request contains only closed, versioned fields, including as applicable:

- protocol and message-schema versions;
- request and operation identities;
- operation kind and required capability identities;
- effective finite per-source, total-input, intermediate, and output row/byte
  bounds, plus duration, local-memory, spill, frame, and artifact bounds;
- a typed requested physical address with exact selection and an optional
  expected canonical identity;
- canonical Portable Plan plus plan/schema/descriptor identities;
- opaque credential reference;
- requested or expected snapshot constraints and required uniqueness policy;
- an optional bounded Arrow IPC input-artifact reference for `stage`;
- stage and idempotency identities; and
- cancellation or reconciliation reference.

The physical target message represents a typed existing-Table address plus an
optional expected identity. The SDK alone resolves it to the canonical
physical Table. The message does not expose a public Python wrapper, provider
object, or unvalidated options mapping.

Unknown or duplicate fields, missing required bounds, unrecognized operations,
invalid identities, noncanonical plans, unsupported versions, and capability
mismatches fail closed.

### Response envelope

Responses contain only:

- the independent `Outcome`, `CommitState`, and `VerificationState` values;
- a typed value/artifact descriptor when the outcome permits one;
- safe capability, target, snapshot, and schema facts;
- ordered immutable Receipts;
- ordered warnings and a safe `ErrorInfo` equivalent;
- normalized result metadata;
- an optional Arrow IPC artifact reference for table data;
- a typed reconciliation reference on every unsafe post-dispatch failure and
  a typed reconciliation disposition for `reconcile`; and
- cancellation acknowledgement.

Python `OperationResult` is not serialized as a Python object. The versioned
wire envelope preserves its semantic state and evidence so the Rust Adapter
SDK and OTS can make independent decisions.

Rejected, failed, partial, and unknown effects remain trusted operation
envelopes when their schema and evidence validate; they are not collapsed into
transport errors. No physical failure discards Receipts. A malformed or
untrusted frame is instead a transport/protocol error and cannot be treated as
proof that a mutation did not commit.

## Data Plane

Across the process boundary, table payloads use content-addressed Arrow IPC
artifacts only. Each reference contains:

```text
confined relative path
Arrow IPC media type and version
declared byte length
SHA-256 digest
ownership/lease identity
expiry and cleanup disposition
```

Both sides verify confinement, ownership, media type, length, digest, schema,
and configured limits before decode. They reject absolute paths, traversal,
symlinks, ownership/mode violations, unexpected files, oversized values, and
expired leases.

Artifact ownership follows one direction-independent state machine:

```text
publisher-owned temporary
  -> atomically published and digest-bound
  -> receiver-validated read lease
  -> receiver release acknowledgement
  -> publisher deletion after all leases close
```

For `stage` input, the Rust side is publisher, digest author, and sole deletion
authority; the host holds only a read lease. For result/readback output, the
host is publisher, digest author, and sole deletion authority; Rust holds only
a read lease. Publishers write only inside their assigned workspace, publish
by atomic rename after complete write and local verification, and never mutate
a published artifact. Receivers validate before acknowledging acquisition and
never delete publisher-owned files.

Cancellation or host exit closes live read leases only after bounded cleanup;
the publisher reclaims an unreferenced artifact at lease expiry. Before a
mutation can depend on input bytes, the host must copy or pin them into its
durable stage state. A transport artifact is never the only durable evidence
for an uncertain commit or reconciliation. Terminal responses and explicit
release acknowledgements permit earlier deletion.

Arrow C Data or C Stream may be used only inside the SDK's process-local host
implementation where lifetime ownership is explicit. C pointers, Python,
PyArrow, or Polars objects, provider handles, and file descriptors never cross
the Rust protocol.

The artifact digest proves transported bytes. It is not a cross-language
semantic-result identity: equivalent Arrow values may differ in chunking,
dictionary encoding, metadata, or IPC bytes. Public Python users continue to
receive Polars DataFrames; Arrow is an internal carrier.

## Portable Plan and Result Parity

### Plan parity

The Python compiler and OTS-owned Rust compiler/codec consume one independently
maintained, language-neutral corpus. For every shared accepted case they emit
byte-identical canonical Portable Plan JSON and the same plan hash. Canonical
encoding, field ordering, numeric forms, temporal precision, schema identity,
and hash domain are specified by the corpus; neither implementation generates
the other's expected fixtures. The Rust Adapter SDK validates the closed plan
schema and hash but does not acquire plan-semantic ownership.

The adapter never accepts a SQLGlot AST, OTS AST, Polars LazyFrame, provider
plan, or noncanonical plan JSON as a substitute.

### Result parity

Result comparison uses a defined normalized logical form, not Arrow IPC bytes,
DataFrame chunking, artifact layout, observation timestamps, or raw
provider-specific Receipt bytes. The corpus pins:

- typed source definitions and parameters;
- accepted or rejected outcome;
- canonical Portable Plan JSON and hash;
- logical fields, types, nullability, and order;
- canonical row order and scalar normalization;
- descriptor, range, snapshot, and validated uniqueness requirements;
- normalized result fixture/hash or expected rejection;
- normalized operation-state and required Receipt facts;
- protocol, cancellation, and artifact-integrity errors; and
- stage, commit, readback, abort, and reconciliation cases.

Receipt comparison checks required semantic facts: operation, logical and
physical target identity, descriptor/content/plan identity, snapshot, requested
and observed bounds, execution location, visibility, verification, and
idempotency outcome. Incidental timestamps and provider payload bytes are not
portable equality.

The normalized result encoding is `otc.logical-result/v1`: canonical UTF-8
JSON with lexicographically sorted object keys, no insignificant whitespace,
arrays preserving declared field and row order, and no Unicode normalization.
Keys sort by unsigned UTF-8 bytes. Strings emit non-ASCII UTF-8 directly,
escape only JSON-required quote, backslash, and control characters, and use
lowercase hexadecimal for control escapes.
Its schema records each field's exact name, canonical OTC logical type,
nullability, and position. Every cell is explicitly tagged: null, boolean,
integer decimal text, decimal coefficient plus scale, finite IEEE-754 binary64
hex, exact UTF-8 text, base64url binary, epoch-day date, UTC epoch count plus
declared timestamp unit, or the profile's canonical interval tuple. Bare JSON
numbers and NaN/infinity are forbidden. The scalar rules are those of the
Python SDK's normative SQL semantic matrix.

Rows use the order proved and declared by the Portable Plan and execution
Receipt; a case without deterministic row order is rejected from parity v1.
The result hash is
`SHA-256("otc.logical-result/v1\0" || canonical_json_bytes)` and covers only
the logical schema and rows. It excludes Receipts, provider metadata,
artifacts, chunking, and observation timestamps, which are validated through
their own schemas.

## Managed Lifecycle and Recovery

The adapter preserves these invariants:

- stage is invisible and bound to target, schema, descriptor, content, and
  idempotency identity;
- commit is idempotent on target, stage, and idempotency key;
- reusing a key with different bound content fails deterministically;
- readback is a fresh independent observation with a mandatory Receipt;
- abort is idempotent and returns a closed disposition;
- an unknown commit state enters `reconcile` using durable operation, stage,
  target, and idempotency identities;
- reconciliation is read-only and never mutates or guesses state; and
- a transport retry is permitted only when the operation contract proves it
  safe.

A timeout, lost acknowledgement, or host exit never means rollback. Neither
the Rust Adapter SDK nor the host blindly repeats a mutation. OTS decides
semantic retry and fallback only after validating reconciliation evidence. A
mutation may be replayed or sent through another execution path only when it
was rejected before dispatch with `commit=not_started`, or when reconciliation
has positively established `not_committed`. A committed, in-flight, unknown,
or expired reconciliation disposition prohibits replay and fallback. OTS must
surface that state for operator or application policy instead of guessing.

Before mutation dispatch, the host must durably persist the reconciliation
record and all neutral identities needed to distinguish not-started, in-flight,
committed, and unknown states after a crash. Persisting only after a timeout or
before reporting an unknown outcome is too late. If that durability cannot be
provided, the capability is not advertised.

## Process, Cancellation, and Credentials

The initial deployment should be a supervised local subprocess because it
provides language isolation, explicit lifetime, stderr separation, and a
small boundary without embedding Python. The transport remains injectable for
tests.

The supervisor pins or allowlists the host executable and closed deployment
configuration. It never accepts a command, module path, import, or executable
from an OTS request or host response. Environment inheritance is allowlisted.

OTS sends only an opaque credential reference. The host resolves it through
the SDK's injected resolver. Credential values are excluded from frames,
echoes, arguments, environment, hashes, Receipts, errors, logs, debug
representations, and artifacts.

Cancellation is correlated by request identity and has a bounded
acknowledgement interval. Unexpected host exit fails every pending request,
invalidates unverified artifacts, closes leases, and preserves durable
reconciliation records. Cancellation after dispatch does not imply that a
mutation was not committed.

## Security Boundary

Before implementation, the threat model and conformance suite must cover:

- malicious or compromised Connector/provider output;
- stale, substituted, or incompatible host executables;
- hostile paths, symlinks, file ownership, and artifact replacement;
- oversized, deeply nested, duplicated, or malformed frames;
- excessive rows, bytes, duration, memory, and artifact retention;
- secret leakage through stderr, errors, configuration, process arguments, or
  inherited environment;
- cancellation races, orphaned children, and host-exit ambiguity;
- replay, idempotency conflict, and forged reconciliation references; and
- untrusted configuration ownership or mutation.

All returned provider artifacts and host output are hostile until validated.
The protocol is closed-schema and bounded. Artifact workspaces are confined
and lease-owned. Cleanup is deterministic. Safe errors never include raw
provider bodies, SQL literals, credential-bearing URIs, or unrestricted local
paths.

## Migration When Work Resumes

1. **Freeze/hold:** perform no OTS implementation, extraction, or protocol
   migration while the Python architecture is under review.
2. **Complete the Python SDK:** stabilize public DataFrame, deferred Query,
   physical Table, OperationResult/Receipts, managed lifecycle, reconciliation,
   and the internal host port; move the CLI onto that SDK.
3. **Specify protocol and corpus first:** approve the closed adapter schemas,
   canonical encoding, normalized-result rules, artifact ownership, security
   model, and independent fixtures.
4. **Build the Rust Adapter SDK against fakes:** test framing, compatibility,
   cancellation, artifacts, Receipts, and reconciliation without an OTS or
   live-provider dependency.
5. **Run an opt-in OTS pilot:** add a feature-gated integration only after plan
   parity and lifecycle conformance pass; retain the existing OTS storage path
   as rollback.
6. **Adopt managed operations:** use shadow or dual verification where
   feasible; enable staged lifecycle only after unknown-commit reconciliation
   is proven.
7. **Gate release:** publish supported SDK/adapter/OTS version ranges,
   deployment requirements, upgrade order, failure behavior, and rollback or
   removal instructions.

The detailed implementation plan is written only after the Python SDK is
implemented and the resume gates below are explicitly approved.

## Resume Gates

No Rust/OTS implementation plan is created until:

1. The Python SDK public surface and Connector-extension seam are stable.
2. The CLI uses the SDK and contains no independent execution runtime.
3. Temporal writes and managed stage/commit/readback/abort/reconcile have
   executable conformance tests.
4. The internal carrier-preserving host port is specified and tested without
   OTS.
5. OTS identifies the exact Portable Plan and capability subset it will use.
6. The closed protocol schemas and independent Python/Rust corpus are
   approved.
7. Artifact ownership, cancellation, credentials, process supervision, and
   uncertain-commit recovery pass security review.
8. Rust crate placement, release ownership, compatibility ranges, and rollback
   policy are agreed by both repositories.

## Deferred Acceptance Criteria

When eventually implemented:

1. OTS uses an OTC-backed storage configuration without importing or embedding
   Python.
2. The Rust Adapter SDK contains no OTS-specific type, SQL frontend, provider
   discovery, credential value, or semantic fallback logic.
3. The Python host contains no second provider registry or physical runtime.
4. Every transported table artifact is bounded, confined, lease-owned, and
   integrity-verified.
5. Credential values never cross the protocol.
6. Portable Plan fixtures are byte-identical across Python and Rust; results
   compare through the normalized logical form rather than Arrow bytes.
7. OTS independently accepts or rejects operation state and Receipt evidence.
8. Order-sensitive temporal semantics require matching validated uniqueness
   and snapshot evidence.
9. Managed mutations preserve idempotency and enter read-only reconciliation
   after uncertain outcomes instead of blind replay.
10. Removing the adapter leaves the Python SDK, CLI, and Connectors fully
    functional.
