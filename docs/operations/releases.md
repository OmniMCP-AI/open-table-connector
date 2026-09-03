# Releases

OTC packages are versioned independently, with the workspace currently on the
`0.1.x` release line.

## Build and inspect

```console
uv lock --check
uv build --all-packages
uv run pytest -q
```

Before publication, inspect wheel metadata, package boundaries, dependency
direction, entry points, and the smoke surface. The repository includes
`scripts/smoke_wheels.py`, `scripts/check_package_boundaries.py`,
`scripts/check_package_independence.py`, and `scripts/verify_compatibility.py`.

## Release discipline

- publish the contract and provider identities that the wheel actually ships;
- keep package version constraints compatible with the published matrix;
- run conformance for every advertised provider capability;
- attach checksums and provenance to release artifacts; and
- document any compatibility boundary or unsupported capability explicitly.

Consumers should verify the artifact manifest before installing into a
production environment and should retain the package and connector versions
alongside operation receipts.
