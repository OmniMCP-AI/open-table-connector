# Office artifact readiness

This document records the qualified subset of the optional artifact layer. It
does not make OfficeCLI a required OTC dependency or an XLSX authoring engine.

| Surface | Status | Evidence / boundary |
| --- | --- | --- |
| DOCX native tables | Implemented adapter contract and local unit coverage | Native table creation is delegated to an installed OfficeCLI runtime; real export remains pending until a qualified binary is available. |
| PPTX native tables | Implemented adapter contract and local unit coverage | Same runtime gate as DOCX; no claim of legacy `.ppt` output. |
| Local rich XLSX | Qualified for existing Excelize image workflow | Excelize remains the sole author; save/reopen and image-byte checks are covered by local tests. |
| MaybeSheet sheet-mode rich XLSX | Contract and recorded image evidence | Live disposable credentials/target were unavailable, so A10 remains pending. Base-mode mutation is excluded. |
| HTML view | Implemented bounded view facade | Requires the optional OfficeCLI binary; renderer version and source hash belong in the result. |
| PNG screenshot | Implemented bounded view facade | Requires OfficeCLI plus its browser prerequisite; nonblank screenshot acceptance is pending. |
| Watch loop | Implemented disposable preview-session store and parser | Sessions are preview-copy-only and discard on stop. External edits are not assumed to refresh automatically. |

OfficeCLI never writes, recalculates, or resaves the authoritative XLSX. Rich
XLSX support uses only object methods already exposed by the installed
Excelize binding. Unsupported object families remain explicitly blocked until
provider-specific save/reopen evidence exists.

The release ledger records pending live gates separately from source-level unit
coverage. Recorded tests cannot substitute for a real OfficeCLI process or a
live MaybeSheet disposable target.
