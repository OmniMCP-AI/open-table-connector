# Buffered spreadsheet operations

OTC exposes one buffered workbook surface for local `.xlsx` files and Maybe Sheet
Sheet worksheets. Google retains its existing immediate remote behavior and is
not evidence for this buffered contract.

## Create and edit

```python
from open_table_connector.local_files import LocalFilesConnector
from open_table_connector.sdk import Client, ConnectorRegistry

client = Client(registry=ConnectorRegistry([LocalFilesConnector()]))
book = client.workbook.create("file:///absolute/path/report.xlsx")
sheet = book.worksheet.create("Report")
planned = sheet.range("A1:B2").write([["Account", "Amount"], ["Cash", "42"]])
sheet.range("A1:B1").style(bold=True)
sheet.config(column_widths={"A": 30, "B": 20}, freeze_panes="A2")
book.write(dry_run=True)  # validates; retains pending edits
committed = book.write()
assert planned.with_results().outcome.value == "planned"
assert committed.with_results().commit.value == "committed"
```

Local creation defaults to `literal-artifact/1.0`: cells are text, formulas are
forbidden, the destination must not exist, and a successful write seals that
session. Choose `profile="general/1.0"` explicitly to create an editable workbook
with supported numeric/date values and formulas. Opening defaults to general.

```python
book = client.workbook("file:///absolute/path/model.xlsx")
sheet = book.worksheet("Model")
sheet.range("A2:B2").write([[2, 3]])
sheet.formulas().set("C2", "=A2+B2")
book.write()
book.close()
```

Edits queue until `write()`. Closing or leaving a context discards pending edits
and never saves. Each `.with_results()` returns that operation's captured result;
a planned result never becomes a commit receipt. Value strings beginning with
`=` remain strings; formulas require the explicit Formula view.

Local reads preview pending changes. Maybe rejects dirty reads because its CLI
has no tested pending overlay. Closed sessions reject use. Partial or unknown
writes block further mutation and retries; `reconcile()` observes only, and when
it cannot establish known state it requires opening a fresh session. Do not
interpret an uncertain result as proof that no operation occurred.

## Verification and retained intent

```python
import json
from pathlib import Path

expected = committed.to_wire()["receipts"][0]["details"]["expected"]
Path("expected.json").write_text(json.dumps(expected), encoding="utf-8")
book.verify()  # uses captured intent in this session
reopened = client.workbook("file:///absolute/path/report.xlsx",
                           profile="literal-artifact/1.0")
reopened.verify(expected=expected)
```

Strict verification checks one bounded immutable XLSX snapshot against independent
intent, including raw ZIP/XML structure, cells, declared layout, merges and image
bytes. Reopened strict verification requires retained intent. General verification
checks supported serialized content; Maybe verification reports observations and
never claims XLSX physical verification. Verification does not calculate formulas.

`failure_directory=` on local creation retains bounded owned diagnostic bytes
when possible. Error details distinguish the original failure from retention
failure. Diagnostic files are not verified published artifacts.

## Operation support and evidence

Workbook binding and preflight determine support for the specific target.
`book.capabilities` exposes bound operation verbs where the provider supplies them.
Local-file spreadsheet capabilities apply only to `.xlsx`, not CSV or JSON.

| Surface | Local Excel | Maybe Sheet | Evidence |
| --- | --- | --- | --- |
| Create/open, save, close | Buffered; exclusive new publication, general replacement | Buffered; actual CLI command boundaries | `test_local_buffer_preview_and_commit`, `test_create_is_buffered_and_retains_workbook_id` |
| Sheet list/create/rename/delete/move | Supported; structural edits reject unsafe references | Recorded commands, stable gids and engine checks | `test_local_general_operation_save_reopen`, `test_recorded_command_surfaces` |
| Range read/write/clear | Literal text; bounded matrices; pending preview | Committed read, validated raw values; dirty reads rejected | `test_workbook_open_and_concise_worksheet_and_range_operations`, `test_literal_range_and_stale_binding`, `test_pending_observation_is_explicitly_rejected` |
| Style and number format | Typed `CellStyle`/`CellFormat` and supported keyword patches | Tested CLI style fields only | `test_literal_layout_images_empty_and_receipt_roundtrip`, `test_recorded_command_surfaces` |
| Dimensions, print/view settings | Native Excel widths, point heights, declared supported layout | `config(row_heights=..., column_widths_pixels=...)`; point heights converted to pixels | `test_literal_layout_images_empty_and_receipt_roundtrip`, `test_recorded_command_surfaces` |
| Merge/unmerge | Rejects hidden populated interiors | Recorded range commands | `test_local_general_operation_save_reopen`, `test_recorded_command_surfaces` |
| Stable range sorting | Bounded supported values | Read/write sequence requires partial opt-in; no CAS | `test_local_general_operation_save_reopen`, `test_stable_sort_requires_partial_and_preserves_ties_blanks_header` |
| Formula storage | Explicit Formula calls; no recalculation engine | Existing CLI Formula command | `test_local_general_operation_save_reopen`, `test_recorded_command_surfaces` |
| Images | PNG/JPEG insertion, exact bytes/layout verification; `images()` and index deletion | Recorded insert/delete and observation commands; picture IDs | `test_literal_layout_images_empty_and_receipt_roundtrip`, `test_independent_image_bytes_anchor_and_limits`, `test_recorded_command_surfaces` |
| Atomic multi-operation write | Local staged verified publication/replacement | No multi-command transaction; default rejection before mutation | `test_competing_creator_cannot_delete_winner`, `test_reject_atomic_batch_without_dispatch` |
| Unknown effects and preservation | Retains committed destination after failure; rejects stale binding | Retains known created IDs/effects; no automatic retry | `test_postcommit_cleanup_failure_keeps_destination_and_freezes`, `test_partial_retains_created_id_and_unknown_dispatch` |

Maybe recorded tests use the installed `mbs 0.28.4`, JSON contract `1.0` command
surface. Recorded success is separate from authorized live acceptance. Multi-command
batches require `write(allow_partial=True)`. Unsupported CAS/idempotency guarantees
are rejected; these flags never invent provider guarantees.

The following catalog covers the buffered workbook API. **Unsupported** means no
public dispatch is implemented; **unproven** means code exists but the named
acceptance evidence is missing. Reading ordinary cells inside a table does not
provide a table-object read API. Preservation during an unrelated edit is listed
separately and does not establish create, update or delete support.

| Resource | Provider | Read | Create | Update | Delete | Preservation or restriction evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Tables | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local table fixture: `test_general_edit_preserves_objects_and_literal_strings`; Maybe preservation unproven |
| Defined names | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local workbook-scoped name fixture: `test_general_edit_preserves_objects_and_literal_strings`; scoped-name parity and Maybe preservation unproven |
| Hyperlinks | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local linked-sort rejection: `test_sort_rejects_hyperlinks_before_values_detach`; unrelated-edit and Maybe preservation unproven |
| Notes/comments | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local comment/VML parts are outside the preservation allowlist; Maybe preservation unproven |
| Data validation | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local validation fixture: `test_general_edit_preserves_objects_and_literal_strings`; reference guard: `test_sheet_rename_rejects_validation_references`; Maybe preservation unproven |
| Conditional formatting | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local snapshot comparison exists, but no dedicated preservation fixture; Maybe preservation unproven |
| Filters | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local snapshot comparison exists, but no dedicated filter fixture; Maybe preservation unproven |
| Charts | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local bar-chart fixture: `test_general_edit_preserves_objects_and_literal_strings`; other chart kinds and Maybe preservation unproven; strict profile rejects charts (`test_strict_chart_is_unsupported`) |
| Pivots | Both | Unsupported | Unsupported | Unsupported | Unsupported | Existing pivot/cache parts reject before editing until real cache-preservation fixtures pass (`test_pivot_parts_rejected_before_unproven_preservation`); strict profile also rejects them |
| Images | Local Excel | Placement/hash metadata | PNG/JPEG insertion | Unsupported | Index deletion | `test_literal_layout_images_empty_and_receipt_roundtrip`, `test_independent_image_bytes_anchor_and_limits`, `test_jpeg_bytes_are_not_transcoded`; deletion-specific preservation evidence remains unproven |
| Images | Maybe Sheet | Metadata and picture-ID read | Bounded PNG/JPEG insertion | Unsupported | Picture-ID deletion | Insert/delete dispatch: `test_recorded_command_surfaces`; image-byte readback: separately gated `test_live_disposable_sheet_contract`; explicit resize has no tested insertion contract |
| Protection | Both | Unsupported | Unsupported | Unsupported | Unsupported | Local protected-sheet fixture: `test_general_edit_preserves_objects_and_literal_strings`; Maybe preservation unproven |
| Visibility | Local Excel | Unsupported | Unsupported | `config(visibility=...)`; direct mutation acceptance unproven | Unsupported | Existing very-hidden sheet fixture: `test_general_edit_preserves_objects_and_literal_strings` |
| Visibility | Maybe Sheet | Unsupported | Unsupported | Unsupported | Unsupported | No buffered dispatch or preservation fixture |

The catalog is incomplete: unproven preservation and unsupported CRUD rows remain
release gaps. Native pivot creation and formula evaluation are unsupported. Google
catalog acceptance is deferred. See [readiness evidence](../spreadsheet-readiness.md)
for release gates.

## CLI

`otc spreadsheet` uses the same SDK session. A standalone mutation queues its one
operation and commits once:

```sh
otc spreadsheet operation --uri file:///absolute/path/report.xlsx --create \
  --operation worksheet.create --sheet Report
```

A batch file uses existing operation verbs and arguments:

```json
{"version":"1.0","changes":[
  {"operation_id":"worksheet.create","target_key":"Report","arguments":{}},
  {"operation_id":"range.write","target_key":"Report","arguments":{"address":"A1:B1","values":[["Account","Amount"]]}}
]}
```

```sh
otc spreadsheet batch --uri file:///absolute/path/report.xlsx --create \
  --commands commands.json --dry-run
otc spreadsheet batch --uri file:///absolute/path/report.xlsx --create \
  --commands commands.json
otc spreadsheet read --uri file:///absolute/path/report.xlsx --sheet Report --range A1:B1
otc spreadsheet verify --uri file:///absolute/path/report.xlsx \
  --profile literal-artifact/1.0 --expected expected.json
```

Input is bounded to 16 MiB and 10,000 changes; unknown envelope keys, duplicate
JSON properties and non-finite JSON numbers are rejected. `--allow-partial`,
`--expected-revision`, `--idempotency-key` and `--failure-directory` pass through
the existing session/provider contract. Image insertion arguments encode original bytes as
`content_base64` alongside `mime_type` and `anchor`. Commands emit existing SDK result JSON;
failed mutations preserve commit/uncertainty evidence on stderr.
