# Task 2 report — portable local JSON/JSONL materialization

## Changed files

- `packages/local_files/src/open_table_connector/local_files/portable_json.py`
  adds versioned envelope serialization/recovery, destination validation, and
  create-only private-file/link publication with file and directory fsync.
- `packages/local_files/src/open_table_connector/local_files/json_codec.py`
  recognizes the portable JSON/JSONL envelope while retaining legacy array and
  object-row decoding.
- `packages/local_files/src/open_table_connector/local_files/sdk_temporal.py`
  dispatches structured materialization requests to the JSON/JSONL path and
  independently reads the committed artifact before returning success.
- `packages/local_files/src/open_table_connector/local_files/manifest.py` and
  `local_files_connector.py` advertise `table.materialize.create/1.0` for the
  portable BASE surface.
- `packages/sdk/src/open_table_connector/sdk/client.py` accepts provider
  materialization modes represented by either SDK or contract enums and routes
  direct JSON/JSONL destinations as BASE mode.
- `packages/local_files/tests/test_portable_json_materialization.py` adds real
  file-backed golden-byte, scalar recovery, zero-row, legacy-read, conflict,
  and URI suffix-routing coverage.

## TDD evidence

RED:

```text
./.venv/bin/pytest packages/local_files/tests/test_portable_json_materialization.py -q
7 failed in 0.31s
```

The failures were the expected pre-feature capability/dispatch failures.

GREEN and regression verification:

```text
./.venv/bin/pytest packages/local_files/tests/test_portable_json_materialization.py packages/local_files/tests/test_json_codec.py packages/local_files/tests/test_json_connector.py packages/sdk/tests/test_portable_materialization.py -q
34 passed in 0.17s

./.venv/bin/ruff check <changed production files>
All checks passed!

git diff --check
exit 0
```

## Concerns

- The implementation uses POSIX `link` as the no-replace publication primitive;
  this is appropriate for the tested local filesystem but is not portable to
  filesystems that do not support hard links.
- Process-race and injected pre/post-publication failure tests were not added in
  this pass. The private temp cleanup and `FileExistsError` path are implemented,
  but those paths need dedicated fault-injection seams for complete evidence.
- Success currently returns commit/verification state without a dedicated
  materialization receipt; the committed byte SHA-256 is stored as the binding
  revision.

## Commit

`52f45e3 feat: materialize portable JSON tables`

## Fix round 1

RED evidence:

```text
./.venv/bin/pytest packages/local_files/tests/test_portable_json_materialization.py -q
2 failed, 8 passed
```

The new failures showed post-link directory fsync was incorrectly reported as
`NOT_STARTED`, and `file:///...json` had no BASE routing.

GREEN evidence:

```text
./.venv/bin/pytest packages/local_files/tests/test_portable_json_materialization.py packages/local_files/tests/test_json_codec.py packages/local_files/tests/test_json_connector.py packages/sdk/tests/test_portable_materialization.py -q
38 passed in 0.08s
git diff --check
exit 0
```

Fixes: publication now opens the parent with `O_DIRECTORY|O_NOFOLLOW`, creates
and links entries through that directory fd, and distinguishes post-link errors
with `PublicationError`. Committed failures return `FAILED/COMMITTED/FAILED`
with `READBACK_MISMATCH`. Success and committed readback paths carry ordered
mutation and read receipts. JSONL uses `otc.table-jsonl/v1`; the portable
profile rejects non-microsecond UTC datetime units before mutation.
