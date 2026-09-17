# OTC Commit-Date Version Labels

## Goal

Make the current OTC build identifiable by both its stable package version and
the date and short SHA of its latest Git commit, with no manual date update
required for future commits.

## Decision

The stable package release version remains `0.1.0`. A source checkout derives a
PEP 440-compatible local version label in this form:

```text
0.1.0+git.20260918.gdf9467c
```

The human-readable label is:

```text
OTC 0.1.0 · 2026-09-18 · df9467c
```

The date is read from the latest commit's recorded committer date using Git's
ISO date output (`%cs`), and the short SHA is read from the same commit. This
means each later commit automatically produces a new label without editing a
version file. If Git metadata is unavailable (for example, an installed wheel
or source archive), the code falls back to the stable package version and
reports that the commit metadata is unavailable.

## Scope

- Add one dependency-free version-label helper owned by the CLI package.
- Add `otc --version` and the equivalent existing CLI entry points.
- Document the label format and the current remote-main label.
- Add focused tests for Git-derived labels, unavailable Git metadata, and the
  CLI flag.
- Keep all connector identity versions, contract versions, process versions,
  capability versions, and wire schema versions unchanged.

## Non-goals

- Do not change package dependency ranges or the `0.1.x` compatibility line.
- Do not create a Git tag or GitHub release automatically.
- Do not make commit dates part of protocol negotiation or persisted receipt
  identity.

## Failure and reproducibility rules

The helper must use a bounded Git subprocess with a short timeout and treat
missing Git, a non-repository checkout, malformed output, or a failed command
as unavailable metadata rather than failing ordinary CLI startup. The stable
version remains deterministic when no repository metadata is present.

## Acceptance criteria

1. `otc --version` prints the stable version, latest commit date, and short
   SHA when run from this checkout.
2. The date and SHA come from the same latest commit.
3. A later commit changes the label automatically without a source edit.
4. Running outside a Git checkout still succeeds and prints the stable version.
5. Existing CLI behavior and all protocol/connector version assertions remain
   unchanged.
