# Task 5 Report

Date: 2026-08-28

## Implementation Commit

`049ddc87c1d1f91370e022b9dd8ab9439d8315e7` —
`test: add universal dbt conformance`

## Files Changed

- `specification/conformance/universal/cases.py`
- `specification/conformance/universal/fixtures.py`
- `specification/conformance/universal/test_dbt_connector.py`

No production dbt connector implementation was changed.

## TDD Evidence

### Red

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_dbt_connector.py -q
```

Result:

```text
15 failed, 1 passed in 0.32s
```

The expected failures showed that `ConnectorCase` did not expose typed dbt
fixture state and that the recording runner lacked deterministic failure,
readback, credential-locality, and exact project-directory controls. The one
passing artifact test characterized the existing public artifact lookup path.

### Green

Command:

```bash
uv run python -m pytest specification/conformance/universal/test_dbt_connector.py -q
```

Result after fixture and case wiring:

```text
16 passed in 0.20s
```

An explicit repeated-run determinism test was then added. The final focused
result was:

```text
17 passed in 0.19s
```

## Coverage Added

- Exact compile and run argv construction, including project directory,
  selection, exclusion, target, and canonical JSON vars propagation.
- Stable invocation IDs, compiled artifact bytes and hashes, and repeated run
  results/recordings.
- Public run status/result/reference mapping, cancellation mapping, artifact
  lookup, and physical readback facts.
- Capability-driven bindings for compile, run, cancel, and artifact read,
  backed only by the recording runner.
- Unsupported-runner behavior, compile/run/cancel failure mapping, closed safe
  error details, and fixture credential exclusion from argv and metadata.
- A fixture-only dbt project and assertions preventing subprocess, `Popen`, or
  shell command launches.

## Verification

- Focused dbt universal tests:
  `uv run python -m pytest specification/conformance/universal/test_dbt_connector.py -q`
  — `17 passed in 0.19s`.
- All universal tests:
  `uv run python -m pytest specification/conformance/universal -q`
  — `187 passed in 1.77s`.
- Existing dbt regressions:
  `uv run python -m pytest packages/dbt/tests -q`
  — `3 passed in 0.20s`.
- Full workspace suite: `uv run python -m pytest -q`
  — `374 passed in 5.79s`.
- `uv run python -m compileall -q packages specification/conformance/universal`
  — passed.
- `git diff --check` — passed.

## Concerns

- Production dbt failure mapping intentionally remains unchanged and preserves
  `str(exc)` in `safe_details["reason"]`. The universal runner therefore emits
  credential-free diagnostics, while separate assertions prove fixture
  credentials never enter argv, recorded calls, operation metadata, or
  serialized safe errors. A runner that embeds credentials directly in its
  exception message could still expose them and would require a separately
  authorized production redaction change.
- Invocation identity includes the fixture project's absolute path. Repeated
  requests for the same project are deterministic, but moving an otherwise
  identical project intentionally changes the invocation ID under current
  production behavior.
- Pre-existing untracked `.DS_Store` files and `tmp-review-universal/` were left
  untouched as requested.
