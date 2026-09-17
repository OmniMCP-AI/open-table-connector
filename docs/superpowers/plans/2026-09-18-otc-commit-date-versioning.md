# OTC Commit-Date Version Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose an automatic OTC version label containing the stable package version, latest commit date, and short commit SHA.

**Architecture:** Keep `0.1.0` as the package and compatibility version. Add a dependency-free CLI-owned helper that reads Git metadata at runtime from the checkout and falls back safely when Git is unavailable; expose its human-readable label through `otc --version` and document the machine-readable PEP 440 form.

**Tech Stack:** Python 3.11+, `argparse`, `importlib.metadata`, `subprocess`, pytest, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-18-otc-commit-date-versioning-design.md`

## Global Constraints

- Stable package version remains `0.1.0` and the supported package release line remains `0.1.x`.
- The label format is `0.1.0+git.YYYYMMDD.g<shortsha>` and the human form is `OTC 0.1.0 · YYYY-MM-DD · <shortsha>`.
- Git metadata is optional; missing, malformed, or failed Git metadata must not prevent CLI startup.
- Connector identity, contract, process, capability, plan, receipt, and schema versions remain unchanged.
- Do not create or require Git tags or GitHub releases.

---

### Task 1: Add the Git-derived version helper

**Files:**
- Create: `packages/cli/src/open_table_connector/cli/version.py`
- Test: `packages/cli/tests/test_version.py`

**Interfaces:**
- Produces `get_version_label() -> str` for the human-readable label.
- Produces `get_machine_version() -> str` for the PEP 440-compatible label.
- Keeps the stable fallback `0.1.0` when package metadata or Git metadata is unavailable.

- [x] **Step 1: Write focused tests for stable and Git-derived labels**

  Add tests that monkeypatch the helper's package-version and Git probes and assert:

  ```python
  assert get_machine_version() == "0.1.0+git.20260918.gdf9467c"
  assert get_version_label() == "OTC 0.1.0 · 2026-09-18 · df9467c"
  ```

  Also assert that a missing Git result returns `0.1.0` and `OTC 0.1.0 · commit metadata unavailable`.

- [x] **Step 2: Run the focused tests and verify they fail**

  Run: `uv run pytest packages/cli/tests/test_version.py -q`

  Expected: FAIL because `open_table_connector.cli.version` does not yet exist.

- [x] **Step 3: Implement bounded Git metadata discovery**

  In `version.py`, use `importlib.metadata.version("open-table-connector")` with a `0.1.0` fallback. Locate the nearest checkout root containing `.git`, then run:

  ```text
  git -C <root> log -1 --format=%cs%x00%h
  ```

  with `check=True`, captured output, text mode, and a two-second timeout. Split the single record, require an ISO date and nonempty short SHA, and return `None` for `OSError`, `subprocess.SubprocessError`, malformed output, or invalid date text. Build the two labels from one metadata result so date and SHA cannot come from different commits.

- [x] **Step 4: Run the focused tests and verify they pass**

  Run: `uv run pytest packages/cli/tests/test_version.py -q`

  Expected: PASS.

- [x] **Step 5: Commit the helper and tests**

  ```bash
  git add packages/cli/src/open_table_connector/cli/version.py packages/cli/tests/test_version.py
  git commit -m "feat: add commit-dated OTC version labels"
  ```

### Task 2: Expose the label through the CLI

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/__main__.py:122-148`
- Modify: `packages/cli/tests/test_version.py`

**Interfaces:**
- Consumes `get_version_label()` from Task 1.
- Produces `otc --version` output without loading providers or requiring a subcommand.

- [x] **Step 1: Add a parser-level CLI test**

  Patch `open_table_connector.cli.__main__.get_version_label` and assert that:

  ```python
  with pytest.raises(SystemExit) as error:
      build_parser().parse_args(["--version"])
  assert error.value.code == 0
  captured = capsys.readouterr()
  assert captured.out == "OTC 0.1.0 · 2026-09-18 · df9467c\n"
  ```

- [x] **Step 2: Run the CLI test and verify it fails**

  Run: `uv run pytest packages/cli/tests/test_version.py -q`

  Expected: FAIL because the top-level parser has no `--version` option.

- [x] **Step 3: Add the top-level version option**

  Import `get_version_label` and add this argument immediately after constructing the top-level parser:

  ```python
  parser.add_argument("--version", action="version", version=get_version_label())
  ```

  Do not add provider discovery or command execution to the version path.

- [x] **Step 4: Run focused CLI tests**

  Run: `uv run pytest packages/cli/tests/test_version.py packages/cli/tests/test_cli_e2e.py -q`

  Expected: PASS, with existing CLI tests unchanged.

- [x] **Step 5: Commit the CLI exposure**

  ```bash
  git add packages/cli/src/open_table_connector/cli/__main__.py packages/cli/tests/test_version.py
  git commit -m "feat: expose OTC version label in CLI"
  ```

### Task 3: Document the current label and future behavior

**Files:**
- Modify: `docs/reference/compatibility.md:10-14`
- Modify: `docs/operations/releases.md:1-30`
- Modify: `packages/cli/README.md` near the CLI usage examples

**Interfaces:**
- Consumes the labels from Tasks 1 and 2.
- Produces user-facing instructions that remain correct for future commits.

- [x] **Step 1: Document the label format and a verified example**

  Record `OTC 0.1.0 · 2026-09-18 · df9467c` as a verified example for commit `df9467c4a97db7899c1c60095e531ed0d28631df`, clearly marking it as generated state rather than a release tag so the documentation does not become stale after the next commit.

- [x] **Step 2: Document how future labels update**

  State that `otc --version` reads the latest commit date and short SHA automatically, and that installed artifacts without Git metadata fall back to the stable package version.

- [x] **Step 3: Check documentation for consistency**

  Run: `rg -n "0\.1\.0|0\.1\.x|otc --version|df9467c|git\.YYYY" docs/reference/compatibility.md docs/operations/releases.md packages/cli/README.md`

  Expected: all version-label references use the exact formats from the spec and no protocol version is described as commit-dated.

- [x] **Step 4: Commit the documentation**

  ```bash
  git add docs/reference/compatibility.md docs/operations/releases.md packages/cli/README.md
  git commit -m "docs: document OTC commit-date version labels"
  ```

### Task 4: Run release checks and push

**Files:**
- No source changes; verification and Git state only.

- [x] **Step 1: Run focused and repository quality checks**

  Run:

  ```bash
  uv run pytest packages/cli/tests/test_version.py packages/cli/tests/test_cli_e2e.py -q
  uv run ruff check packages/cli/src/open_table_connector/cli packages/cli/tests/test_version.py
  git diff --check
  ```

  Expected: all commands exit 0.

- [x] **Step 2: Verify the live label against Git**

  Run: `uv run otc --version` and `git log -1 --format='%cs %h'`.

  Expected: the date and SHA in the first command match the second command, with the base version `0.1.0`.

- [x] **Step 3: Confirm only scoped commits are pending**

  Run: `git status --short --branch` and `git log origin/main..HEAD --oneline`.

  Expected: only the version-label commits are ahead, and no unrelated `.gitignore` or `.ignore` changes are staged.

- [x] **Step 4: Push the implementation to remote main**

  ```bash
  git push origin HEAD:main
  ```

  Expected: remote `main` advances to the final version-label commit.

- [x] **Step 5: Mark all plan tasks complete**

  Update every checkbox in this plan to `[x]` only after its corresponding command succeeds.
