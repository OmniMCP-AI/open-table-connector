# Critical Review Process Transport and Security Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make connector-process framing, concurrency, cancellation, state lifecycle, credential handling, query reads, bootstrap loading, and diagnostics bounded and fail-closed.

**Architecture:** Keep `otc.connector-process/v1` wire fields unchanged while giving the server and client context-specific decoders. Backpressure limits work before dispatch; state entries have explicit completion/retirement paths; cancellation never calls provider code while holding the global lock. Credential defenses operate on structured keys and post-open file metadata rather than substrings and pre-open path checks.

**Tech Stack:** Python 3.11–3.14, binary stdio framing, `concurrent.futures`, threading primitives, DB-API/psycopg2, weak references, POSIX `open`/`fstat`, pytest 9, and uv workspace commands.

**Spec:** `docs/superpowers/specs/2026-08-31-critical-review-remediation-design.md`

**Owned findings:** B1, B2, B3, B4, B5, B6, D2, D3, D4, D5, D6, D7, and the shared E9 error-detail defect. D1 is closed with hosted write correctness because its no-mutation tests share that boundary.

**Prerequisite:** Complete Task 4 of `docs/superpowers/plans/2026-08-31-critical-review-specification-conformance.md` so request/response payload rules are pinned before decoder changes.

## Global Constraints

- Do not add a required `direction` field to process protocol v1.
- The server decodes requests with `ConnectorProcessEnvelope.from_request_wire()`; clients decode responses with `from_response_wire()`.
- A 16 MiB frame-size limit does not substitute for bounded pending work.
- Provider callbacks, credential resolvers, and artifact I/O do not run while `_state_lock` is held.
- Rejected identifiers are retained only after admission; a request rejected before admission may be retried with the same `message_id`.
- Credential values never enter frames, receipts, exception messages, diagnostics, reprs, or process argv.
- PostgreSQL arbitrary query reads execute in a database-enforced read-only transaction.
- Bootstrap paths and executables are absolute; config files are opened no-follow and validated with `fstat` after opening.
- Work red-green-refactor; every task ends with focused tests, the owning package tests, `git diff --check`, a ledger update, and one Conventional Commit.

---

## File Map

- `packages/process/src/open_table_connector/process/framing.py` — exact header/payload reads and bounded JSON frames.
- `packages/process/src/open_table_connector/process/envelope.py` — request/response-context v1 decoders.
- `packages/process/src/open_table_connector/process/server.py` — bounded admission, future observation, state retirement, cancellation, NACKs, and diagnostics.
- `packages/process/src/open_table_connector/process/bootstrap.py` — no-follow config loading and absolute executable validation.
- `packages/contract/src/open_table_connector/contract/uri.py` — secret query/fragment rejection.
- `packages/contract/src/open_table_connector/contract/resolve.py` — secret-free repr.
- `packages/contract/src/open_table_connector/contract/errors.py` — safe detail preservation without secret values.
- `packages/postgres/src/open_table_connector/postgres/reader.py` — database-enforced query read-only mode.
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py` — collision-safe environment mapping and absolute executable.
- `packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py` — object-safe capability cache.
- `packages/conformance/src/open_table_connector/conformance/assertions.py` — structured receipt-safety checks.

### Task 1: Make framing short-read safe and observe worker serialization failures

**Files:**
- Modify: `packages/process/src/open_table_connector/process/framing.py:35-75`
- Modify: `packages/process/src/open_table_connector/process/server.py:377-425`
- Modify: `packages/process/src/open_table_connector/process/__main__.py`
- Modify: `packages/process/tests/test_framing.py`
- Modify: `packages/process/tests/test_server.py`
- Modify: `packages/process/tests/test_bootstrap_process.py`

**Interfaces:**
- Produces: `_read_exact_or_eof(stream, size, label) -> bytes | None`; `run_server()` always observes submitted futures and converts serialization failures to a redacted error response when the request identity is valid.
- Consumes: existing `_read_exact`, `write_frame`, `ConnectorProcessServer.error_response`, and `BoundedDiagnostics`.

- [ ] **Step 1: Write segmented-header and unserializable-result tests**

```python
class OneByteStream(BytesIO):
    def read(self, size: int = -1) -> bytes:
        return super().read(1 if size < 0 else min(size, 1))

def test_frame_header_may_arrive_one_byte_at_a_time() -> None:
    source = OneByteStream(encoded_frame({"ok": True}))
    assert read_frame(source, 1024) == {"ok": True}

def test_worker_serialization_failure_returns_redacted_error(server_streams) -> None:
    handler = HandlerReturning({"bad": object()})
    exit_code, responses, diagnostics = run_case(handler)
    assert exit_code == 0
    assert responses[0].payload["ok"] is False
    assert responses[0].payload["error"]["code"] == "execution_failed"
    assert "object at 0x" not in diagnostics
```

- [ ] **Step 2: Run focused tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/process/tests/test_framing.py packages/process/tests/test_server.py -q
```

Expected: short header raises `truncated frame header` or the worker response is missing.

- [ ] **Step 3: Implement exact header reads and one response boundary**

`_read_exact_or_eof` returns `None` only when zero bytes are read for the first
byte; after any byte, EOF raises `FrameError`. `read_frame` uses it for the
four-byte header. Move response serialization into `handle_and_write`; catch
`FrameError`, build a fixed `ProcessError("execution_failed", "connector result is not serializable")`,
and write that response once under `output_lock`.

- [ ] **Step 4: Observe every future**

Maintain a local set of futures. Add a done callback that calls
`future.exception()` inside a try/except and reports only the fixed redacted
diagnostic if an unexpected exception escaped. At EOF, wait for submitted
futures before returning so no response is silently abandoned.

- [ ] **Step 5: Run process tests and commit**

```bash
uv run --frozen python -m pytest packages/process/tests -q
git diff --check
git add packages/process/src/open_table_connector/process/framing.py packages/process/src/open_table_connector/process/server.py packages/process/src/open_table_connector/process/__main__.py packages/process/tests/test_framing.py packages/process/tests/test_server.py packages/process/tests/test_bootstrap_process.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: make process framing and responses observable"
```

### Task 2: Add bounded admission and retire completed state

**Files:**
- Modify: `packages/process/src/open_table_connector/process/server.py:64-112,377-425`
- Modify: `packages/process/tests/test_server.py`
- Modify: `packages/process/README.md`

**Interfaces:**
- Produces: `ConnectorProcessServer(..., max_completed_messages: int = 4096)`; `retire_session(session_id: str) -> None`; `run_server(..., max_pending_requests: int = 8)`.
- Consumes: four worker threads and the existing per-frame byte bound.

- [ ] **Step 1: Write failing bounds and retirement tests**

```python
def test_completed_message_ids_are_bounded(server, hello) -> None:
    for index in range(5000):
        server.handle(replace(hello, message_id=f"hello-{index}", session_id=f"s-{index}"))
        server.retire_session(f"s-{index}")
    assert server.state_counts() == {"messages": 4096, "sessions": 0, "cancelled": 0}

def test_run_server_never_exceeds_pending_limit(blocking_handler) -> None:
    run = start_server(blocking_handler, max_pending_requests=2)
    send_requests(run.stdin, 10)
    assert blocking_handler.started_count == 2
```

Expose `state_counts()` only as a private-test helper named `_state_counts()`
returning immutable integer counts.

- [ ] **Step 2: Run server tests and confirm unbounded behavior**

```bash
uv run --frozen python -m pytest packages/process/tests/test_server.py -q
```

- [ ] **Step 3: Implement bounded IDs and explicit session retirement**

Store completed message IDs in `collections.OrderedDict[str, None]`; reject a
duplicate still in the window and evict the oldest after a successful terminal
response. `retire_session` removes the session and cancellation marker under
the lock. CANCEL retires the target after its callback returns; an explicit
same-session HELLO replaces only a compatible retired session.

- [ ] **Step 4: Backpressure before executor submission**

Use `threading.BoundedSemaphore(max_pending_requests)`. Acquire before
`workers.submit`; the done callback releases exactly once. The read loop stops
reading additional frames while no permit is available. Validate
`max_pending_requests` as a positive non-bool integer.

- [ ] **Step 5: Run bounded concurrency tests and commit**

```bash
uv run --frozen python -m pytest packages/process/tests/test_server.py -q
git diff --check
git add packages/process/src/open_table_connector/process/server.py packages/process/tests/test_server.py packages/process/README.md docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: bound process work and state"
```

### Task 3: Move cancellation outside the lock and decode by transport context

**Files:**
- Modify: `packages/process/src/open_table_connector/process/envelope.py:100-155`
- Modify: `packages/process/src/open_table_connector/process/server.py:87-130,215-230,405-418`
- Modify: `packages/process/tests/test_envelope.py`
- Modify: `packages/process/tests/test_server.py`
- Modify: `packages/process/tests/test_bootstrap_process.py`

**Interfaces:**
- Produces: `ConnectorProcessEnvelope.from_request_wire(document)`; `from_response_wire(document)`; private `_from_wire(document, *, response: bool)`; `_cancel()` returns `(ProcessResult, callback)` and caller invokes callback after releasing `_state_lock`.
- Consumes: closed payload schemas from specification Plan Task 4.

- [ ] **Step 1: Write failing direction, lock, and retry tests**

```python
def test_request_with_ok_is_rejected_as_request_not_parsed_as_response() -> None:
    wire = envelope_wire(operation="execute", payload={"ok": True})
    with pytest.raises(ValueError, match="execute payload"):
        ConnectorProcessEnvelope.from_request_wire(wire)

def test_cancel_callback_runs_without_state_lock(server, cancel, handler) -> None:
    lock_results: list[bool] = []
    handler.abort_session = lambda _session: lock_results.append(
        server._state_lock.acquire(blocking=False)
    )
    response = server.handle(cancel)
    assert response.payload["result"]["cancelled"] is True
    assert lock_results == [True]

def test_failed_hello_message_id_can_be_retried(server, invalid_hello, valid_hello) -> None:
    rejected = server.handle(invalid_hello)
    assert rejected.payload["ok"] is False
    assert rejected.payload["error"]["code"] == "protocol_invalid"
    assert server.handle(replace(valid_hello, message_id=invalid_hello.message_id)).payload["ok"]
```

- [ ] **Step 2: Run envelope/server tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/process/tests/test_envelope.py packages/process/tests/test_server.py -q
```

- [ ] **Step 3: Split the decoders without changing v1 wire fields**

Request decoding applies the closed operation payload validator and prohibits
`ok`; response decoding requires `ok` and the matching result/error branch.
Keep `from_wire` as a deprecated request alias for one release and update every
internal response call site to `from_response_wire`.

- [ ] **Step 4: Narrow lock scope and admission timing**

Check duplicate ID under lock but add the ID only after envelope/session
admission succeeds. For HELLO and CANCEL, catch errors and discard the ID.
When a validly framed envelope is rejected during session or operation
admission, return one bounded error response keyed by its message/session IDs
instead of diagnostics-only failure; the client must always receive a NACK.
Resolve the cancellation callback under lock, set the marker, release the
lock, invoke the callback, then retire the session under lock. Convert callback
failure to a bounded successful cancellation acknowledgement with
`callback_failed: true`; never expose the exception.

- [ ] **Step 5: Run process e2e tests and commit**

```bash
uv run --frozen python -m pytest packages/process/tests specification/conformance/timeseries/test_process_e2e.py -q
git diff --check
git add packages/process/src/open_table_connector/process/envelope.py packages/process/src/open_table_connector/process/server.py packages/process/tests/test_envelope.py packages/process/tests/test_server.py packages/process/tests/test_bootstrap_process.py specification/conformance/timeseries/test_process_e2e.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: harden process cancellation and decoding"
```

### Task 4: Enforce PostgreSQL query reads with read-only transactions

**Files:**
- Modify: `packages/postgres/src/open_table_connector/postgres/reader.py:56-72,238-274`
- Modify: `packages/postgres/tests/test_reader.py`
- Modify: `packages/postgres/tests/test_transaction_isolation.py`

**Interfaces:**
- Produces: `_begin_read_only(connection) -> None`; arbitrary `query` reads are rejected inside an existing writable `PostgresTransaction`.
- Consumes: DB-API cursor and `PostgresReadOptions`.

- [ ] **Step 1: Write failing multi-statement and writable-CTE tests**

```python
@pytest.mark.parametrize("query", [
    "SELECT 1; DELETE FROM accounts",
    "WITH d AS (DELETE FROM accounts RETURNING *) SELECT * FROM d",
])
def test_query_read_starts_database_read_only_transaction(connector, factory, query) -> None:
    connector.read_arrow(request(query=query))
    assert factory.statements[0] == "SET TRANSACTION READ ONLY"
    assert factory.statements[1] == query
```

The recording cursor raises if a mutating statement executes while its
connection is not marked read-only.

- [ ] **Step 2: Run PostgreSQL reader tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/postgres/tests/test_reader.py packages/postgres/tests/test_transaction_isolation.py -q
```

- [ ] **Step 3: Start read-only mode before arbitrary SQL**

For owned read connections, execute `SET TRANSACTION READ ONLY` before the
requested statement and roll back on close. For an active writable transaction,
allow generated table reads but reject `options.query` with
`UNSUPPORTED_CAPABILITY` before cursor execution. Remove the `startswith`
check as a security boundary; keep only a single-statement/read-shape usage
validation for helpful errors.

- [ ] **Step 4: Run PostgreSQL tests and commit**

```bash
uv run --frozen python -m pytest packages/postgres/tests -q
git diff --check
git add packages/postgres/src/open_table_connector/postgres/reader.py packages/postgres/tests/test_reader.py packages/postgres/tests/test_transaction_isolation.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: enforce read-only postgres query reads"
```

### Task 5: Reject all credential-bearing URIs and keep secrets out of reprs/errors

**Files:**
- Modify: `packages/contract/src/open_table_connector/contract/uri.py:7-40`
- Modify: `packages/contract/src/open_table_connector/contract/resolve.py:28-31`
- Modify: `packages/contract/src/open_table_connector/contract/errors.py:21-77`
- Modify: `packages/contract/tests/test_uri.py`
- Modify: `packages/contract/tests/test_errors.py`
- Modify: `specification/conformance/universal/conftest.py`
- Modify: `specification/conformance/universal/test_contract.py`

**Interfaces:**
- Produces: `_secret_parameter_keys(text: str) -> set[str]`; `ResolveContext.credentials` has `repr=False`; `_REDACTED` sentinel distinguishes a removed secret from legitimate `None`.
- Consumes: `parse_qsl(..., keep_blank_values=True)` for query and fragment key/value forms.

- [ ] **Step 1: Write failing URI, repr, and safe-None tests**

```python
@pytest.mark.parametrize("value", [
    "https://example.test/x?token=",
    "https://example.test/x#access_token=abc",
    "https://example.test/x#api_key=",
])
def test_uri_rejects_blank_and_fragment_credentials(value: str) -> None:
    with pytest.raises(ValueError, match="credential"):
        TableURI(value)

def test_resolve_context_repr_omits_credentials() -> None:
    assert "fixture-secret" not in repr(ResolveContext(credentials={"token": "fixture-secret"}))

def test_safe_details_preserve_legitimate_none() -> None:
    error = ConnectorError(ConnectorErrorCode.EXECUTION_FAILED, "failed", {"attempt": None, "token": "x"})
    assert error.safe_details == {"attempt": None}
```

- [ ] **Step 2: Run contract tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/contract/tests/test_uri.py packages/contract/tests/test_errors.py -q
```

- [ ] **Step 3: Implement structured secret handling**

Parse both query and fragment with blank preservation; reject secret keys
case-insensitively. A non-key/value fragment such as `gid=0` remains valid.
Set `credentials: Any = field(default=None, repr=False)`. `_safe_value` returns
the private sentinel for secret keys and preserves actual `None`; mapping
construction skips only the sentinel. Change `authentication(...,
safe_details=None)` and normalize `None` to `{}`.

- [ ] **Step 4: Run contract and universal tests, update D3/D4/E9, and commit**

```bash
uv run --frozen python -m pytest packages/contract/tests specification/conformance/universal/test_contract.py -q
git diff --check
git add packages/contract/src/open_table_connector/contract/uri.py packages/contract/src/open_table_connector/contract/resolve.py packages/contract/src/open_table_connector/contract/errors.py packages/contract/tests/test_uri.py packages/contract/tests/test_errors.py specification/conformance/universal/conftest.py specification/conformance/universal/test_contract.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: close credential representation gaps"
```

### Task 6: Make MaybeSheet credential mapping and capability caching collision-safe

**Files:**
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py:14-78`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py:103-138`
- Modify: `packages/maybe_sheet/tests/test_connector.py`
- Modify: `packages/maybe_sheet/tests/test_temporal_capabilities.py`

**Interfaces:**
- Produces: `_credential_environment(credentials) -> dict[str, str]` that rejects normalized collisions; weak-key capability cache with no `id()` keys.
- Consumes: `weakref.WeakKeyDictionary` for hashable/weak-referenceable clients; uncacheable clients are probed on every call.

- [ ] **Step 1: Write failing collision and recycled-client tests**

```python
def test_credential_environment_rejects_normalized_collision() -> None:
    with pytest.raises(ConnectorError) as raised:
        _credential_environment({"api-key": "one", "api_key": "two"})
    assert raised.value.code is ConnectorErrorCode.CONFLICT

def test_capability_cache_never_uses_recycled_integer_identity(recording_clients) -> None:
    first, second = recording_clients.with_same_forced_identity()
    assert probe_temporal_capabilities(first) != probe_temporal_capabilities(second)
```

- [ ] **Step 2: Run MaybeSheet tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_temporal_capabilities.py -q
```

- [ ] **Step 3: Implement collision detection and object-keyed caching**

Build the full normalized-name map before updating `env`; if two original keys
map to one name, raise before spawning. Replace `_CACHE: dict[int, ...]` with
`WeakKeyDictionary[object, frozenset[str]]`. Under the cache lock, catch
`TypeError` for unhashable/non-weak-referenceable clients and skip caching.

- [ ] **Step 4: Run MaybeSheet tests and commit**

```bash
uv run --frozen python -m pytest packages/maybe_sheet/tests -q
git diff --check
git add packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py packages/maybe_sheet/tests/test_connector.py packages/maybe_sheet/tests/test_temporal_capabilities.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: isolate MaybeSheet credentials and capability cache"
```

### Task 7: Open bootstrap files safely and require absolute executables

**Files:**
- Modify: `packages/process/src/open_table_connector/process/bootstrap.py:73-180`
- Modify: `packages/process/tests/test_bootstrap_process.py`
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py:14-42`
- Modify: `packages/maybe_sheet/tests/test_connector.py`

**Interfaces:**
- Produces: `_open_config(path: Path) -> TextIO` using `os.open`/`os.fstat`; `_absolute_executable(value: str) -> str`.
- Consumes: POSIX `O_NOFOLLOW` when available and post-open inode metadata on every platform.

- [ ] **Step 1: Write failing swap/symlink and bare-binary tests**

```python
def test_config_swap_to_symlink_is_rejected(tmp_path, monkeypatch) -> None:
    config, secret = regular_config_and_secret(tmp_path)
    monkeypatch.setattr(os, "open", swapping_open(config, secret))
    with pytest.raises(ValueError, match="regular non-symlink"):
        build_process_runtime(config, tmp_path / "artifacts")

def test_maybe_sheet_binary_must_be_absolute() -> None:
    with pytest.raises(ValueError, match="absolute"):
        SubprocessProcessClient(binary="mbs")
```

- [ ] **Step 2: Run bootstrap/client tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/process/tests/test_bootstrap_process.py packages/maybe_sheet/tests/test_connector.py -q
```

- [ ] **Step 3: Implement descriptor-relative no-follow loading**

Open with `O_RDONLY | O_CLOEXEC | O_NOFOLLOW` where supported. Validate
regular-file type, owner, mode, and one-MiB bound from `fstat(fd)`, then read
through `os.fdopen`. On platforms without `O_NOFOLLOW`, compare pre-open
`lstat` and post-open `fstat` device/inode and reject a mismatch.

- [ ] **Step 4: Validate executable paths**

Require an absolute, existing regular file with at least one execute bit.
Store the resolved absolute path and require `argv[0]` to equal it. The
bootstrap config's `maybe_sheet_binary` uses the same validator before any
credential environment is built.

- [ ] **Step 5: Run tests and commit**

```bash
uv run --frozen python -m pytest packages/process/tests/test_bootstrap_process.py packages/maybe_sheet/tests -q
git diff --check
git add packages/process/src/open_table_connector/process/bootstrap.py packages/process/tests/test_bootstrap_process.py packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py packages/maybe_sheet/tests/test_connector.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: harden process bootstrap file loading"
```

### Task 8: Redact structured secrets without identifier false positives

**Files:**
- Modify: `packages/process/src/open_table_connector/process/server.py:275-374`
- Modify: `packages/process/tests/test_security.py`
- Modify: `packages/conformance/src/open_table_connector/conformance/assertions.py:46-51`
- Modify: `packages/conformance/tests/test_reference_reader.py`
- Modify: `specification/conformance/universal/assertions.py`

**Interfaces:**
- Produces: `_contains_secret_key(value: object) -> bool`; `redact_text()` recognizes query/assignment and JSON key/value forms; diagnostics use a per-message byte cap.
- Consumes: the shared closed set of secret key spellings.

- [ ] **Step 1: Write failing JSON-redaction and safe-token-name tests**

```python
def test_redact_text_covers_json_assignments() -> None:
    assert redact_text('{"token": "fixture-secret", "ok": true}') == (
        '{"token": "[REDACTED]", "ok": true}'
    )

def test_receipt_table_named_tokens_is_not_a_secret(receipt_factory) -> None:
    receipt = receipt_factory(safe_uri=TableURI("sqlite:///db#table=tokens"))
    assert_receipt_safe(receipt)
```

Add a diagnostics test that writes two messages above the old lifetime budget
and asserts each is independently truncated and the second is still emitted.

- [ ] **Step 2: Run security/conformance tests and confirm the red phase**

```bash
uv run --frozen python -m pytest packages/process/tests/test_security.py packages/conformance/tests/test_reference_reader.py specification/conformance/universal/test_contract.py -q
```

- [ ] **Step 3: Implement structured key checks and per-message diagnostics**

`assert_receipt_safe` recursively inspects mapping keys, not arbitrary
substrings in serialized values, then round-trips the receipt. `redact_text`
adds a JSON assignment regex that retains quote/colon formatting and replaces
only the value. `BoundedDiagnostics` stores `max_bytes_per_message`; each call
redacts then UTF-8 truncates independently.

- [ ] **Step 4: Run process, conformance, and universal suites**

```bash
uv run --frozen python -m pytest packages/process/tests packages/conformance/tests specification/conformance/universal -q
git diff --check
```

- [ ] **Step 5: Update B2/B6/D7 and commit**

```bash
git add packages/process/src/open_table_connector/process/server.py packages/process/tests/test_security.py packages/conformance/src/open_table_connector/conformance/assertions.py packages/conformance/tests/test_reference_reader.py specification/conformance/universal/assertions.py docs/reviews/2026-08-31-critical-review-remediation.md
git commit -m "fix: redact structured diagnostics safely"
```

## Plan Verification

After all eight tasks:

```bash
uv run --frozen python -m pytest packages/process/tests packages/contract/tests packages/postgres/tests packages/maybe_sheet/tests packages/conformance/tests specification/conformance/timeseries/test_process_e2e.py specification/conformance/universal -q
git diff --check
```

Expected: all selected tests pass; segmented frames decode; pending work and
state stay bounded; callbacks run outside locks; arbitrary PostgreSQL query
reads are database-read-only; and every B/D finding has a ledger disposition.
