# Task 7 Report

Date: 2026-08-28

## Implementation Commit

`23e73e8c043def85595143ee420a92dc27b2d993` —
`test: enforce universal conformance suite size`

## Files Changed

- `specification/conformance/universal/test_suite_count.py`
- `specification/conformance/universal/README.md`

`pyproject.toml` did not require a marker or collection-setting change. The
concurrent plan edits, table behavior tests, `.DS_Store` files, and
`tmp-review-universal/` were not edited, staged, reset, or discarded.

## Red/Green Evidence

### Red

No Task 7 red run occurred. The supplied untracked implementation candidate
already existed when Task 7 began, and the suite was already above the
120-test floor. The first focused guard run was green, so no failing result is
claimed:

```bash
uv run python -m pytest specification/conformance/universal/test_suite_count.py -q
```

```text
.                                                                        [100%]
1 passed in 0.84s
```

### Green

The guard collects the dedicated directory in a subprocess, parses pytest's
summary line with `parse_collected_count`, and reports the executed command,
observed count, and required floor if the assertion fails. A focused parser
exercise proved that a pytest summary is accepted and a node ID containing
similar words is rejected. The ordered node-ID lists from two consecutive
collections were identical and contained 238 unique node IDs in the shared
working tree.

Shared-tree collection, including the concurrent uncommitted table behavior
tests:

```bash
uv run python -m pytest specification/conformance/universal --collect-only -q
```

```text
238 tests collected in 0.05s
```

Shared-tree dedicated and full verification:

```bash
uv run python -m pytest specification/conformance/universal -q
uv run python -m pytest -q
```

```text
238 passed in 4.32s
425 passed in 8.60s
```

## Exact Committed-Snapshot Verification

Commit `23e73e8c043def85595143ee420a92dc27b2d993` was exported to a clean
temporary directory, installed with `uv sync --frozen --all-packages --group
dev`, and verified independently of concurrent working-tree changes.

- Count guard: `1 passed in 1.22s`.
- Collect-only count: `235 tests collected in 0.04s`.
- Dedicated universal suite: `235 passed in 4.23s`.
- Full workspace suite: `422 passed in 8.06s`.
- Parser/stable-ID check: `235 unique stable node IDs`; the ordered node-ID
  lists from the repeated collections were identical.
- `uv run python -m compileall -q packages specification/conformance/universal`
  — passed.
- `git diff 84d7873..23e73e8 --check` — passed.
- The commit contains exactly the two Task 7 files listed above.

## Documentation

The README records the repeatable required commands:

```bash
uv run python -m pytest specification/conformance/universal --collect-only -q
uv run python -m pytest specification/conformance/universal -q
```

It also documents the offline fixture policy, supported connector families,
120-test minimum, behavior-focused test organization, and stable descriptive
parameter IDs.

## Concerns

- The count guard intentionally adds one collected case to the directory it
  measures. The committed suite still has 235 collected cases, leaving a
  margin of 115 above the required floor.
- Running the dedicated suite executes one nested collect-only subprocess for
  the guard; this is deterministic and adds roughly one second to the focused
  guard run.
