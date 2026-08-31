# Deferred OTC Rust Client and OTS Binding Bridge

**Status:** deferred; design boundary only; no implementation plan

**Date:** 2026-08-31

**Depends on:** the Polars-first OTC Python SDK reaching a stable public and
provider-extension interface.

## Decision

OTS integration is not part of the Python SDK refactor. It will be implemented
later as a separate wrapper and transport project.

The intended dependency chain is:

```text
OTS Rust
   |
   v
OTS OTC Binding
   |
   v
OTC Rust Client
   |
   v
OTC Python bridge host
   |
   v
OTC Python SDK
   |
   v
Connector plugins
```

Requests flow downward and results, artifacts, receipts, errors, and
cancellation acknowledgements flow upward. The arrows describe calls, not
shared semantic ownership.

## Terminology

- **OTC Python SDK**: the authoritative application/runtime interface for
  provider discovery and Connector execution.
- **OTC Python bridge host**: a narrow process wrapper that exposes a versioned
  transport over an SDK client. It contains no second provider runtime.
- **OTC Rust Client**: an OTC-owned Rust crate containing wire models,
  transport, artifact verification, cancellation, and safe error mapping.
- **OTS OTC Binding**: OTS-owned Rust code translating between OTS kernel
  concepts and the neutral OTC client.
- **Connector**: a physical-medium implementation owned by OTC provider
  packages.
- **Binding**: framework-specific translation owned by the consuming
  framework, here OTS.

The Rust component is deliberately called a Client, not an Adapter SDK. In the
existing domain language, `Adapter` or `Binding` implies semantic translation;
that translation belongs in OTS. The Rust crate must remain reusable by other
Rust callers that speak the neutral OTC protocol.

## Goals

- Let the Rust OTS kernel use OTC-backed storage without rewriting OTS in
  Python.
- Keep the Python SDK as the only provider discovery, credential, routing, and
  execution runtime.
- Extract reusable neutral Rust transport code from the current OTS-local OTC
  process implementation.
- Preserve OTS control over logical plans, semantic acceptance, evidence, and
  fallback policy.
- Preserve typed, versioned, bounded temporal requests and independently
  verifiable receipts.
- Use a control plane for small messages and Arrow IPC artifacts for table
  data.
- Allow protocol conformance to be tested independently in Python and Rust.

## Non-goals

- This design does not authorize implementation while the bridge is on hold.
- It does not rewrite the OTS semantic kernel, CLI, MCP server, or lifecycle in
  Python.
- It does not embed Python into OTS with PyO3 or expose Python objects over FFI.
- It does not move OTS-specific plan lowering or acceptance rules into OTC.
- It does not make the Rust client a second Connector implementation runtime.
- It does not expose arbitrary Python imports, code execution, relational or
  temporal SQL text, or provider objects across the bridge. The bridge remains
  typed-plan-only even though the Python SDK has SQL frontends.
- It does not require every Python SDK operation to become an OTS operation.
  The bridge exposes the neutral capability subset OTS needs.
- It does not select a long-term daemon, remote service, or multiplexed network
  deployment in this deferred phase.

## Component Ownership

### OTC Python SDK

The SDK owns:

- installed-provider discovery and route selection;
- provider configuration and credential leases;
- Connector and temporal-extension construction;
- capability preflight;
- physical reads, writes, temporal execution, and managed lifecycle;
- OTC SQL Lite compilation for Python applications, which the bridge does not
  invoke for OTS requests;
- Polars application results and internal Arrow conversion;
- neutral and temporal receipts; and
- provider-safe errors and cleanup.

It has no imports from OTS and no OTS plan types.

### OTC Python bridge host

The bridge host adapts framed transport messages to one SDK client. It owns:

- handshake and protocol-version negotiation;
- request decoding and closed-schema validation;
- operation dispatch into the SDK;
- use of the SDK's carrier-preserving host port so verified Arrow evidence is
  not round-tripped through Polars;
- bounded artifact creation and cleanup;
- cancellation propagation;
- credential-reference resolution at the deployment boundary; and
- safe serialization of receipts and errors.

It does not rediscover providers independently of the SDK, reconstruct
provider-specific process bindings, or implement temporal semantics. The
existing `otc-process` code is an input to this component, not an additional
authoritative runtime.

### OTC Rust Client

The Rust crate is framework-neutral and owns:

- versioned request, response, receipt, error, and capability wire models;
- child-process or injected transport lifecycle;
- framed message correlation;
- deadlines and cancellation;
- Arrow artifact path confinement, size checks, media-type checks, and digest
  verification;
- protocol compatibility checks; and
- conversion from wire failures into stable neutral Rust errors.

It does not own OTS plan types, OTS storage traits, OTS evidence types,
provider routing, credential values, SQL lowering, result acceptance, retries
at the semantic-operation level, or fallback selection.

The crate should live in the OTC repository and be released independently of
OTS. OTS depends on an explicit compatible version.

### OTS OTC Binding

The Binding remains in the OTS repository and owns:

- implementing the OTS storage adapter seam;
- retaining OTS parsing and acceptance of Timescale Core SQL and Add-ons;
- lowering the supported subset of OTS plans into neutral portable temporal
  plans;
- selecting required capability identities;
- supplying logical target, descriptor, bounds, operation IDs, credential
  references, and snapshot references;
- binding provider-enforced or snapshot-validated temporal unique constraints
  required by order-sensitive SQL and duplicate resolution;
- translating neutral results and receipts into OTS evidence;
- verifying that returned identity, schema, ordering, range, snapshot, and
  bounds satisfy the OTS request;
- OTS retry, fallback, and lifecycle policy; and
- rejecting semantically unacceptable results even when transport succeeded.

No OTS kernel type crosses the neutral OTC wire.

## Interface Boundary

### Control plane

The initial Rust client preserves the existing
`otc.connector-process/v1` framed JSON protocol unchanged. A resumed project
must first codify its current language-neutral schema and golden corpus; any
widening then requires an explicitly versioned successor rather than a silent
change. The initial operation families are:

```text
hello
describe
execute
stage
commit
readback
abort
cancel
```

These cover the current OTS use case. The bridge host invokes the Python SDK's
non-public carrier-preserving evidence port, never the bare-dataframe
convenience methods and never a Polars-to-Arrow reconstruction. The verified
carrier or artifact and its receipt therefore continue to describe the same
bytes and schema. Generic table operations are added only if a concrete Rust
consumer requires them; Python SDK completeness alone does not justify
widening version 1.

The current `describe` and receipt shapes do not carry the validated unique
constraint evidence required by the shared temporal SQL profile. Before the
bridge can claim that profile, an explicitly versioned protocol successor must
add ordered constraint fields, enforcement or validation identity, and the
matching snapshot identity. This is a conformance extension, not permission to
send SQL text over the bridge.

Every request carries a protocol version, request ID, operation identity,
deadline or resource bounds, and required capability identities as applicable.
Unknown fields, duplicate fields, unsupported versions, missing bounds, and
unrecognized operations fail closed.

The initial transport should remain a supervised local subprocess because it
provides language isolation, explicit lifetime, stderr separation, and a small
security boundary without embedding Python in the Rust process. The Rust
client transport must be injectable so conformance tests do not require a real
child process.

### Data plane

Large table data uses content-addressed Arrow IPC artifacts rather than JSON
rows or FFI-owned memory. Artifact references contain only a confined relative
path, media type, byte size, and SHA-256 digest. Both sides verify the artifact
before use, enforce configured byte limits, reject traversal and symlinks, and
clean up according to explicit ownership rules.

Polars remains the Python application table type. Arrow is a bridge artifact
format, not evidence that the Python SDK public interface has changed.

### Credentials

OTS sends opaque credential references, never credential values. The bridge
deployment resolves them through the SDK's injected credential resolver.
References and safe provider IDs may appear in diagnostics; values may not.

Credential values are excluded from wire echoes, hashes, receipts, structured
errors, debug representations, and child-process arguments. Environment
inheritance is allowlisted rather than copied wholesale.

## Protocol and Semantic Compatibility

Transport success is not semantic acceptance.

The Python bridge validates message shape and dispatch preconditions. The OTC
runtime validates Connector capabilities and physical execution. The OTS
Binding then validates returned evidence against the original OTS request.
Each layer rejects only facts it owns.

Compatibility is based on explicit protocol and capability versions, not a
repository commit hash. Artifact SHA-256 identifies transported bytes. Result
evidence is revalidated by OTS after decoding rather than assuming
cross-language in-memory identity. The canonical `PortableTemporalPlan` JSON
is the deliberate exception: for the shared portable temporal SQL corpus, the
OTC Python compiler and OTS Rust compiler must emit byte-identical plan JSON
and plan hashes. A compatibility record should pin:

- Rust client crate version;
- Python bridge/SDK distribution version range;
- control protocol version;
- portable plan and descriptor schema versions;
- portable temporal SQL profile, result-shape schema, and corpus versions;
- temporal unique-constraint evidence schema and snapshot-binding version;
- receipt schema versions;
- Arrow artifact media type/version expectations; and
- identity and hash of the neutral conformance corpus.

Python and Rust codecs must run the same language-neutral golden corpus for
valid messages, invalid messages, canonical hashes, temporal boundary cases,
errors, cancellation, and artifact verification. The temporal SQL corpus must
contain source, typed parameters, descriptor/schema binding, expected portable
plan JSON and hash, expected result shape and hash, and validated unique
constraint evidence or an expected missing-evidence rejection—not only
accepted/rejected status. Evidence-bound cases also pin the source snapshot.
One neutral corpus is maintained independently of both compiler
implementations; separate Python and Rust harnesses consume it. Expected
outputs must not be generated at test time by either implementation under
test. Relational SQL Lite is outside this bridge because OTS does not consume
it.

## Failure and Lifecycle Model

The Rust client distinguishes at least:

- bridge unavailable or startup failure;
- incompatible protocol;
- malformed response;
- unsupported capability;
- authentication/configuration failure;
- deadline or cancellation;
- artifact integrity or confinement failure;
- provider execution failure; and
- OTS semantic rejection after a valid OTC response.

The OTS Binding decides which failures permit fallback. The Rust client never
retries a semantic operation implicitly. Transport retries are permitted only
when the operation contract and idempotency identity make them safe.

The OTS-owned process supervisor starts the bridge with an explicit config and
artifact root, performs `hello`, and closes or kills it on adapter shutdown.
In-flight cancellation uses a request ID and has bounded acknowledgement time.
Unexpected process exit fails all pending requests and invalidates unverified
artifacts.

Managed stage, commit, readback, and abort preserve their existing idempotency
and visibility semantics across process failure. The Binding must retain
enough neutral identity to reconcile an uncertain commit rather than assuming
success or replaying with different content.

## Security Boundary

Before implementation resumes, the threat model must cover:

- malicious or compromised provider output;
- a stale or incompatible bridge executable;
- hostile artifact paths and symlinks;
- oversized frames and artifacts;
- stderr or error-body secret leakage;
- child environment leakage;
- cancellation races and orphaned children; and
- untrusted config-file ownership and mutation.

The bridge uses a closed deployment-owned configuration. The Rust client never
accepts an arbitrary command supplied by an OTC response. The Python bridge
never accepts arbitrary module paths or code supplied by OTS.

## Extraction from the Current OTS Code

When resumed, the current OTS OTC implementation should be divided by
ownership rather than moved wholesale:

- neutral portions of `process.rs` and `wire.rs`, process framing, artifact
  verification, and neutral errors move or are reimplemented in the OTC Rust
  Client;
- `storage.rs`, OTS storage traits, plan lowering, evidence conversion, and
  semantic acceptance remain in the OTS Binding;
- `capabilities.rs` and all mapping from neutral claims into OTS profiles remain
  in the OTS Binding;
- the current configuration splits into neutral client settings (executable,
  artifact root, protocol limits, and compatible OTC versions) and OTS Binding
  settings (logical Store mapping, allowed profiles, evidence pins, credential
  reference selection, and OTS resource policy); and
- provider bootstrapping is replaced by calls into the completed Python SDK.

This permits incremental replacement behind the existing OTS storage adapter
tests. It does not require an OTS language rewrite.

## Gates for Resuming Work

No implementation plan should be created until all of these are true:

1. The Python SDK public interface and provider-extension seam are stable.
2. The CLI uses the SDK, proving that SDK orchestration is complete.
3. Temporal append/upsert and managed lifecycle protocols have executable
   conformance tests.
4. OTS has identified the exact portable capability subset it will consume.
5. A versioned control schema and independent golden corpus are approved,
   including shared Python/Rust temporal SQL-to-plan cases and validated
   uniqueness evidence.
6. Artifact ownership, cancellation, credential resolution, and uncertain
   commit recovery have written security/lifecycle decisions.
7. Rust crate placement, release ownership, and supported version policy are
   agreed by both repositories.

## Deferred Acceptance Criteria

When eventually implemented:

- OTS can use an OTC-backed storage configuration without importing or
  embedding Python.
- The OTC Rust Client contains no OTS-specific types or semantics.
- The Python bridge contains no second provider registry or physical runtime.
- All transported table data is bounded and integrity-verified.
- Credential values never cross the control protocol.
- OTS independently accepts or rejects returned evidence.
- Python and Rust pass the same protocol and temporal conformance corpus and
  emit identical portable plans and result shapes for the shared temporal SQL
  profile.
- Order-sensitive temporal SQL is accepted only with matching validated
  uniqueness and snapshot evidence across the language boundary.
- Bridge removal leaves the Python SDK and CLI fully functional.
