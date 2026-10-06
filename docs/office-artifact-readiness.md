# Office artifact readiness

This document records the qualified subset of the optional artifact layer. It
does not make OfficeCLI a required OTC dependency or an XLSX authoring engine.

| Surface | Status | Evidence / boundary |
| --- | --- | --- |
| DOCX native tables | Implemented adapter contract and local unit coverage | Native table creation is delegated to an installed OfficeCLI runtime; real export remains pending until a qualified binary is available. |
| PPTX native tables | Implemented adapter contract and local unit coverage | Same runtime gate as DOCX; no claim of legacy `.ppt` output. |
| Local rich XLSX | Qualified for existing Excelize image workflow | Excelize remains the sole author; save/reopen and image-byte checks are covered by local tests. |
| MaybeSheet sheet-mode rich XLSX | Contract and recorded image evidence | Live disposable credentials/target were unavailable, so A10 remains pending. Base-mode mutation is excluded. |
| HTML view | Qualified bounded adapter path | Requires the optional OfficeCLI binary at qualified version `1.0.154`; source hash is checked before and after rendering and output is bounded. |
| PNG screenshot | Qualified capability-gated adapter path | Requires OfficeCLI plus an executable browser; nonblank PNG and browser absence are tested with fake runtimes. |
| Watch loop | Qualified owned disposable lifecycle | Loopback URL, owned process identity, snapshot/source hashes, crash/orphaned state, refresh replacement, and stop-without-publish are recorded. |

OfficeCLI never writes, recalculates, or resaves the authoritative XLSX. Rich
XLSX support uses only object methods already exposed by the installed
Excelize binding. Unsupported object families remain explicitly blocked until
provider-specific save/reopen evidence exists.

The release ledger records pending live gates separately from source-level and
fake-runtime coverage. Recorded tests cannot substitute for a real OfficeCLI
process or a live MaybeSheet disposable target.
