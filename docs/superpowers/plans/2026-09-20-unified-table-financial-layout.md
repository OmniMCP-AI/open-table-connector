# Unified Table Financial Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 通过同一 `Table.layout()` 接口为 Excel 与 MaybeSheet 实现完整 Excel 数字格式、文本布局、样式/尺寸读写，以及独立读取、可哈希证据和重新打开验证。

**Architecture:** Table facade 绑定现有 SpreadsheetSession；共享层定义字段能力、格式请求、观察/期望与比较，provider 负责真实存储。Excel 从受限 XLSX 字节独立观察，MaybeSheet 从经过验证的 mbs/API 协议独立观察。保留现有 workbook API、原子发布和 partial/unknown 语义。

**Tech Stack:** Python 3.11–3.14、uv workspace、pytest、现有 openpyxl/XML 验证器、mbs subprocess、SHA-256 / canonical JSON。新增共享层不得依赖 SDK、openpyxl 或 mbs。

**Spec:** [统一 Table 财务版式 spec](../specs/2026-09-20-unified-table-financial-layout-design.md)，含完整格式与 wrapping 更新，spec revision `972bb5c`。本计划创建于该 revision 之后；代码位置以 spec 的 `ae8e16d` 基线为导航提示，实施前用 graft 校正。

## Execution status (2026-09-20)

| Task | Status |
| --- | --- |
| 0 | ✅ OTC protocol fixture and explicit upstream gaps recorded; positive MaybeSheet capability gate remains closed. |
| 1–6 | ✅ Shared evidence/format/patch contracts, Table facade, Excel writer, and independent reader implemented and verified. |
| 7 | ✅ MaybeSheet recorded-protocol provider/reader and explicit unsupported-capability paths implemented; no unverified positive advertisement. |
| 8–10 | ✅ Independent intent verification, CLI reads, and shared Excel/MaybeSheet conformance harness implemented and verified. |
| 11 | ⚠️ Offline acceptance tests are present and intentionally skipped without authenticated MaybeSheet/Excel application gates; no fabricated pass evidence. |
| 12 | ✅ Compatibility documentation, readiness evidence, package checks, wheel smoke, and release notes completed. |

The task-level completion ledger is retained in `.superpowers/sdd/2026-09-20-unified-table-financial-layout/progress.md`; the live gate state above is authoritative for external acceptance.

All task checkboxes below record implementation, offline verification, or an explicit live-gate result. A checked Task 11 item does not claim external acceptance when the authenticated provider/application evidence is absent or contradicts the requirement; the status table and readiness report remain authoritative for that distinction.

## Global Constraints

- “两个 provider 均为必需交付”；Google/Base/CSV/SQL 不自动广告新能力。
- “范围始终采用绑定 worksheet 的绝对一基 A1 坐标”，不随 header 偏移。
- “关闭不保存”；layout.write 不提交 Table 数据行事务。
- “不得要求先把整张报表物化为 DataFrame”。
- “10,000 cells、8 MiB 观察响应上限”；config 行列条目总数最多 10,000，provider 更严格限制优先。
- “MaybeSheet 多命令仍要求 `allow_partial=True`”；不发明事务、CAS 或幂等保证。
- “完整 Excel 格式代码和第 5.2 节规定的必需文本布局模式均为交付门槛”。
- “不能靠‘provider 子集’宣称已支持所有格式”；未支持功能必须 capability error，必需项缺失仍阻塞最终交付。
- “provenance、时间、request ID、名称、会话标识、revision 和 hash 自身不参与” physical hash。
- “自定义格式表 ID 是序列化引用”不参与 hash；内置 ID 有语义，参与 hash。
- “跨 provider 不要求 physical hash 相同”；同一目标同一覆盖集合的 reopen hash 必须相等。
- 保留 `literal-artifact/1.0` 全部严格规则、现有 typed-value guard、Table/Formula API 和 package dependency direction。
- 本计划是文档交付；未授权本轮修改产品代码、运行真实写入或部署上游服务。

## Review Focus

1. **Excel 保存重排 sheetId 或 numFmt 索引：** rename/reopen 不应虚报目标变化，原始目标/格式语义不可丢失；Task 4/5/11 用独立 OOXML fixture 固定此边界。
2. **格式值是 1900 serial 60 或 1904 日期：** 仅改样式不能经 Python date 解码再编码而改值；Task 5/11 比较原始 cell value/type。
3. **格式代码有尾空格、转义、区域代码或复杂多段：** 通用 `_text().strip()` 不能改变代码；Task 2/3/11 用精确字符串和未在示例列表中的代码测试。
4. **同一绑定出现外部编辑、rename 或权限变化：** 不能写到同名新工作表或使用旧 descriptor；Task 4/7/8 测 gid/sheetId、revision 与失效能力。
5. **一次提交跨 10,000 cells 的多个小范围：** 不能逐请求通过限制后无界聚合或给混合 revision 盖完整章；Task 1/8/11 测总覆盖/字节预算和一致性标签。

## Execution order and gates

这是一个共享接口项目，不拆成互不兼容的 Excel/MaybeSheet 两套计划。按以下依赖交付：

```text
1 evidence contract ── 2 format corpus/requests ── 3 style/config validation
            ├──────── 4 Table metadata binding + facade
            └──────── 5 Excel writer ── 6 Excel independent observer
0 Maybe protocol qualification ──────── 7 Maybe provider + observer
4 + 5 + 6 + 7 ── 8 session verification ── 9 CLI
1–9 ── 10 shared conformance harness ── 11 live/reopen/format semantics ── 12 release gates
```

Tasks 1–6 可以在 MaybeSheet 上游缺失时继续。Task 7 的正向能力广告及 Task 11/12 的最终通过必须等 Task 0 的协议门槛；Task 0 使用自己的最小 disposable probe，不依赖 Task 11 的完整 harness；旧版本拒绝路径可以提前实现。没有真实服务证据时完成状态是“OTC 实现/本地验证完成，Maybe 必需门槛未通过”，不是整体完成。

实施开始时建立隔离 worktree，读取 AGENTS.md，`graft map` 后按 symbol 查询；保持当前用户的 `.gitignore` 和其他未跟踪配置不变。先保存全套测试基线，再按任务做 red → green → commit；文中新增函数/文件均是计划定义，不暗示当前已存在。

## File responsibility map

| 文件 | 职责 |
| --- | --- |
| `packages/spreadsheets/src/open_table_connector/spreadsheets/observations.py`（新） | 严格 wire schema、canonical hash、观察集合和纯比较 |
| `packages/spreadsheets/src/open_table_connector/spreadsheets/formats.py`（新） | format 请求规范化、内置格式版本/区域元数据；不渲染值 |
| `packages/spreadsheets/src/open_table_connector/spreadsheets/_layout.py`（新） | descriptor 校验、style/config patch 规范化、intent 构造 |
| 同包 `model.py`, `capabilities.py`, `__init__.py`, `_session.py`, `_protocols.py` | 兼容类型/导出、身份、共享生命周期 |
| `packages/sdk/src/open_table_connector/sdk/layout.py`（新） | 受限 TableLayoutSession 与 metadata-only 绑定 glue，委托 workbook facade |
| 同包 `table.py`, `client.py`, `connector.py`, `workbook.py`, `registry.py` | Table 入口、兼容可选 provider hooks、结果适配和配置路由 |
| `packages/local_files/src/open_table_connector/local_files/spreadsheet_observe.py`（新） | XLSX 原始物理观察；复用既有受限 ZIP/XML 基础设施 |
| 同包 `spreadsheet_workbook.py`, `spreadsheet_verify.py`, `sdk_temporal.py`, `cli_adapter.py`, `local_files_connector.py`, `manifest.py` | writer/独立 verifier 接入、元数据绑定、能力路由 |
| `packages/maybe_sheet/src/open_table_connector/maybe_sheet/spreadsheet_observe.py`（新） | 已核验 mbs 响应的严格 decoder，不读 writer cache |
| 同包 `spreadsheet.py`, `connector.py`, `cli_adapter.py`, `process.py` | provider 命令、身份/能力绑定与受限传输 |
| `packages/cli/src/open_table_connector/cli/spreadsheet_commands.py` | 在现有 spreadsheet command 增加读取与验证分支 |
| `specification/conformance/spreadsheets/layout_cases.py`, `conftest.py`, `test_layout.py`, `test_layout_live.py`, `fixtures/`（新） | 两个 provider 共用的语义与持久化验收 |
| `docs/spreadsheet-readiness.md`, `docs/user-guide/spreadsheet-operations.md`, `docs/reference/python-api.md` | 真实能力、调用示例、版本/证据/缺口 |

表中的同包与花括号文件列表是路径展开记法，不是要求创建花括号文件；所有文件根目录由本表限定。新模块只服务上述单一职责；不拆每种样式一个文件，不复制 writer/session，不创建新的结果族。

---

## Task 0: 核验 MaybeSheet 协议与格式引擎，生成可执行的上游交接

**Files:**
- Modify: `docs/spreadsheet-readiness.md`（新增 financial-layout gate）。
- Create: `packages/maybe_sheet/tests/fixtures/layout-protocol.json`（仅存经过脱敏的真实响应及版本；不得虚构正向 fixture）。
- Test: `packages/maybe_sheet/tests/test_layout_protocol.py`。

**Interfaces:** 产出 protocol fixture manifest：`version`, `provider_version`, `service_revision`, `commands`, `responses`, `supported_fields`, `format_dialect`, `limits`, `gaps`；缺服务 revision 时明确 null 和证据限制。`commands` 是实际 argv 模板及 operation/envelope 映射，不是按 OTC 操作 ID 拼出的猜测命令。

- [x] 运行只读 `mbs --version`、`mbs --help`，再依据帮助发现 style/config/read 子命令；核对读取是否覆盖默认/继承、gid、每个 cell、格式/locale/date_system 和原生尺寸。保存版本及响应结构，不保存凭据。
- [x] 创建 manifest 校验测试，要求每个被广告字段均有真实 read/write/persist 证据；旧 `spreadsheet-mbs-0.28.4.json` 继续用于兼容失败路径，不当作新增能力证据。

```python
import json
from pathlib import Path

def test_advertised_fields_have_protocol_evidence():
    path = Path(__file__).parent / "fixtures" / "layout-protocol.json"
    data = json.loads(path.read_text())
    assert data["version"] == "1.0"
    for field, evidence in data["supported_fields"].items():
        assert evidence["read_response"] in data["responses"], field
        if evidence["write"]:
            assert evidence["write_command"] in data["commands"], field
            assert evidence["reopen_response"] in data["responses"], field
```

- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/maybe_sheet/tests/test_layout_protocol.py -q`；先确认缺 manifest/缺证据失败，真实证据录入后通过。空 supported_fields 只说明尚未广告，不构成最终验收。
- [x] 针对 missing operation/field/default/format semantics 分别生成 readiness 缺口行：原始失败请求、期望字段/模式、上游所属 CLI/proxy/storage/renderer、完成测试及部署证据。根据实际 repo 的 graft 定位源文件并将路径写入交接；本仓库未提供上游 checkout，不能在此预填虚构文件路径。
- [x] 若上游缺失，交接必须要求原始样式读取、全数字格式应用、alignment/border 保存/重开、metadata-only sheet binding；上游实现/部署是依赖，不通过 OTC mock 代替。继续本地任务；Task 7 正向映射只在已验证命令可用后接入。
- [x] Commit 本任务的 fixture、测试和 readiness 行，消息 `test: qualify MaybeSheet layout protocol`。Task 0 的命令资格验证可以拥有一个独立 disposable workbook：按既有 live test 的创建/清理模式建立、记录 ID，完成后恢复性删除；它只核验协议映射，不代替 Task 11 的完整语料验收。无法运行该 probe 时 manifest 不广告未经证实的正向能力，Task 7 只推进明确拒绝路径。

## Task 1: 固定观察、期望与 hash wire contract

**Files:**
- Create: `packages/spreadsheets/src/open_table_connector/spreadsheets/observations.py`。
- Modify: 同包 `capabilities.py`, `__init__.py`。
- Create: `packages/spreadsheets/tests/test_layout_observations.py`。

**Interfaces:**

```python
# observations.py；JSON 是 dict[str, Any] 的类型别名，输入允许 Mapping。
def decode_observation(payload: Mapping[str, Any]) -> JSON: ...
def hash_payload(payload: Mapping[str, Any]) -> JSON: ...
def physical_hash(payload: Mapping[str, Any]) -> str: ...
def aggregate_observations(items: Sequence[Mapping[str, Any]]) -> JSON: ...
def compare_layout(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> tuple[JSON, ...]: ...
```

`hash_payload` 返回且只返回 kind/target/coverage/physical；`physical_hash` 先严格验证再编码。观察中的哈希已存在时 decode 必须重算验证，不信任远端 digest。聚合的 hash payload 为 `{kind, observations: [单项 hash_payload]}`，按 target/coverage/kind 排序；冲突或重复覆盖拒绝，统一执行总预算。固定 expectation wire 为 `{kind, target, coverage, required_fields, physical, intent_hash}`；intent_hash 计算排除其自身。`compare_layout` 只比较 expectation 指定字段及保存性边界，输出 `{target, address_or_dimension, field, expected, actual}` 差异。

- [x] 增加完整小 fixture：A1:B1、两个不同 bold 值、空白 cell、每字段 source/stored/effective、默认来源路径；用手工序列化而非生产 hash helper 得到 expected digest。

```python
import hashlib
import json
from copy import deepcopy

def test_request_metadata_does_not_affect_physical_hash(observation):
    from open_table_connector.spreadsheets.observations import physical_hash
    payload = {k: observation[k] for k in ("kind", "target", "coverage", "physical")}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
    altered = deepcopy(observation)
    altered["provenance"]["request_id"] = "new-request"
    assert physical_hash(observation) == physical_hash(altered) == expected
```

`observation` fixture 在本测试文件定义为上述两格完整 wire 对象；cells 为 row-major `{row, column, fields}` 列表，coverage 为 `{range, fields, complete}`。config 则为 `{rows, columns, view_fields, complete}`，physical 包含 rows/columns/defaults/view。source 引用放在 physical 的 `sources` 映射，字段的 `source_ref` 指向它，禁止循环/悬空引用；这些来源属于物理 hash。

- [x] 参数化缺格、重复/多余格、遗漏字段、错误坐标/target、未知键、来源缺失、原生十进制、NaN、负零、组合总数超限；expectation/observation 的 kind、target、coverage 必须匹配，不能跨表比较后返回 passed。decode JSON 的 duplicate-key 检查在解析层保留；Mapping 校验不能补救已丢失重复键的信息。
- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/spreadsheets/tests/test_layout_observations.py -q`，确认新接口缺失导致失败。
- [x] 实现严格 decoder、可重复 canonicalization 与独立 hash；内置 numFmt ID 纳入，自定义 numFmt 索引仅 provenance。按 spec 原样保留字符串和原生单位，小数只用规范 decimal 字符串，非终止换算移到非 hash metadata。注册全部新 capability identities，仍不在 provider 上广告。
- [x] 加入 aggregate 不同 revision 标为 sequential_unversioned、重复覆盖拒绝、总 cell/byte 超限测试并运行同一命令至通过。
- [x] Commit：`feat: define physical layout evidence contract`。

## Task 2: 完整数字格式请求与版本化 corpus

**Files:**
- Create: `packages/spreadsheets/src/open_table_connector/spreadsheets/formats.py`。
- Modify: 同包 `model.py:109–121`。
- Create: `packages/spreadsheets/tests/test_layout_formats.py`。
- Create: `specification/conformance/spreadsheets/fixtures/number-formats.json`。

**Interfaces:**

```python
def normalize_format(arguments: Mapping[str, Any], *,
                     descriptor: Mapping[str, Any]) -> JSON: ...
# return {kind, code, builtin_id, locale, date_system, storage_kind}
```

code 保留原值；builtin_id 与 kind/pattern 互斥。CellFormat 保持旧 positional 参数兼容，新增 builtin_id 必须允许省略 kind；新字段保持 keyword-only，原位置参数顺序不变。model 只做结构验证，provider 负责其格式方言支持。literal-artifact 的格式限制优先，不能因为一般格式模型扩展而放开原有纯文本要求。descriptor 格式部分固定含 dialect/version/locales/builtins/custom_code/unsupported_features；不能从有限 corpus 推导“只支持这些 pattern”。

- [x] 为全部 kind、旧默认、新默认、accounting/special/custom/native 缺 pattern、冲突参数和完整精确 code 添加失败测试。

```python
import pytest
from open_table_connector.spreadsheets import CellFormat

@pytest.mark.parametrize("code", [
    '0.00 ', '#,##0.00;[Red](#,##0.00);"-";@',
    '[h]:mm:ss', '[$€-407] #,##0.00', '0.00E+00',
    r'0.00\ "units"', '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)',
])
def test_custom_pattern_is_not_trimmed_or_rewritten(code):
    assert CellFormat("custom", pattern=code).pattern == code
```

- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/spreadsheets/tests/test_layout_formats.py -q`，确认 custom kind/精确代码路径的基线失败。
- [x] 创建 corpus v1：明确 Excel/OOXML 目标版本、en-US/zh-CN/de-DE locale、1900/1904、内置 ID 表及来源、每个 spec 类别、自定义语法组合和负例；每条包含 id、format request、原始 typed value、期望存储 code/上下文、应用显示证据引用。render 证据尚未产生的项显式标记 unverified，Task 11 必须补齐，不能生成假 expected display。
- [x] 实现 normalize_format：复用原默认 pattern；新增 date/time/duration/fraction/scientific 默认按 spec，accounting 等要求 code。不依赖窄正则接受列表，不实现格式渲染器；使用完整方言处理能力/目标引擎验证，无法验证的 kind/code 冲突明确要求 custom，不重写未知代码。
- [x] 测试 format request 不携带/改变 values、formula 或日期系统；内置格式缺 locale 无法解析时报错，禁止猜机器区域；自定义 format 引号/反斜杠通过 JSON/CLI 往返。
- [x] 同一测试命令通过后 commit：`feat: support complete Excel format requests`。

## Task 3: 字段能力、文本模式、border patch 与原生尺寸

**Files:**
- Create: `packages/spreadsheets/src/open_table_connector/spreadsheets/_layout.py`。
- Modify: 同包 `model.py`（CellStyle 新字段兼容）、`_protocols.py`。
- Create: `packages/spreadsheets/tests/test_layout_changes.py`。

**Interfaces:**

```python
def validate_descriptor(value: Mapping[str, Any]) -> JSON: ...
def normalize_style(arguments: Mapping[str, Any], *, descriptor: Mapping[str, Any],
                    baseline: Mapping[str, Any] | None = None) -> JSON: ...
def normalize_config(arguments: Mapping[str, Any], *, descriptor: Mapping[str, Any]) -> JSON: ...
def prepare_layout(changes: Sequence[Change], *, baseline: Mapping[str, Any],
                   descriptor: Mapping[str, Any]) -> JSON: ...
# prepared = {changes, expected, coverage}; expected has spec expectation kind
```

descriptor 使用 operation → field → `{read, write, persist, values, units, precision, defaults_source}`，附 target/dialect/limits；bool 类型严格。prepare_layout 在已冻结的原始 intent 上构造 patch 期望；actual 绝不调用它。

- [x] 添加模式往返和冲突测试；`excel_descriptor` 在本文件定义，只广告 no_wrap/wrap/shrink_to_fit 及 Excel 原生单位。

```python
def test_switching_to_wrap_clears_shrink(excel_descriptor):
    from open_table_connector.spreadsheets._layout import normalize_style
    patch = normalize_style({"text_layout": "wrap"}, descriptor=excel_descriptor,
                            baseline={"wrap_text": False, "shrink_to_fit": True})
    assert patch["wrap_text"] is True
    assert patch["shrink_to_fit"] is False
```

- [x] 添加四边部分 patch、none 清除、color 省略保留、false 不消失、unknown 参数、raw flags+模式冲突、raw true/true 拒绝、character/px 单位不兼容、别名冲突测试。
- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/spreadsheets/tests/test_layout_changes.py -q`，确认新接口缺失失败。
- [x] 实现 text_layout switch 为完整 wrap/shrink patch；legacy wrap_text 只改该字段，最终组合校验延至拥有 baseline 时。no_wrap/overflow 仅按 descriptor 声明的等价关系验证；clip 不伪造。规范化 column_sizes 和原有 column_widths/column_widths_pixels，不做字体未知时的近似换算。
- [x] prepare_layout 先检查整个批次和全覆盖预算，再生成 changes/expectation；格式归一化调用 Task 2。未改字段从独立 baseline 保留，字典深度冻结，保留 command 原顺序处理重叠 patch。
- [x] 同一命令通过后 commit：`feat: validate portable layout patches and capabilities`。

## Task 4: Table metadata-only 绑定与统一 facade

**Files:**
- Create: `packages/sdk/src/open_table_connector/sdk/layout.py`。
- Modify: `packages/sdk/src/open_table_connector/sdk/{client,table,connector,workbook,registry}.py`。
- Modify: `packages/local_files/src/open_table_connector/local_files/{sdk_temporal,cli_adapter,local_files_connector}.py`。
- Modify: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/{connector,cli_adapter}.py`。
- Create: `packages/sdk/tests/test_table_layout.py`。

**Interfaces / concrete binding decision:**

```python
Client.open(target, *, schema=None, metadata_only=False)  # additive opt-in
Table.layout() -> TableLayoutSession
# optional connector hook, not a new mandatory TableConnector requirement:
open_table_metadata(address: object) -> OperationResult[TableBinding]
bind_table_layout(binding: TableBinding) -> Mapping[str, Any]
# binding payload: workbook_uri, worksheet_id, worksheet_name, revision, descriptor
```

metadata_only=True 仅解析 workbook/sheet 元数据，不读取数据 frame。`TableBinding` 新增默认 `schema_observed=True` 与可选 `layout_binding=None`；metadata 路径设 schema_observed=False，layout_binding 保存稳定目标。`TableBinding.schema` 允许 None 明确表示未观察；不能用空 Schema 假装已观察空表。旧 open 默认完全不变；metadata-only Table 的 schema/inspect/data operations 在首次需要时通过新增私有 `Table._ensure_data_binding() -> None` 调用现有 open_table 路径补齐 data binding，layout/capabilities 不触发补齐。`schema=` 与 metadata_only 同时使用时保留 declared schema 并标记未验证，到首次数据读取再执行原有比较。此增量路径避免修改所有 legacy provider 的默认行为。

`TableLayoutSession` 委托一个现有 WorkbookSession；提供 spec 的 range/config/read_config/write/verify/capabilities/close/context-manager 和 worksheet 属性。新增 `Range.read_style(fields=None)`、`Worksheet.read_config(rows, columns, view_fields=None)` 返回 OperationResult。CapabilitySet 增加默认空 details，名单字段保持兼容。

- [x] 使用本文件 `MetadataConnector` fake：open_table_metadata 只返回已知 sheetId/gid 元数据；open_table/read_table 计数并在不该调用时抛 AssertionError；provider.observe 返回 Task 1 完整 fixture。

```python
def test_layout_binding_does_not_read_data(metadata_client, metadata_connector):
    table = metadata_client.open("maybe URI doc/7", metadata_only=True).require_value()
    with table.layout() as layout:
        layout.range("A1:B1").read_style(fields=["bold"]).require_value()
    assert metadata_connector.data_reads == 0
    assert metadata_connector.observed_sheet_id == "7"
```

- [x] 新增 non-first-sheet、header offset、Base/CSV 拒绝、ambiguous selector、stale sheetId、foreign/closed client、关闭不保存、Table.transaction 与 layout 队列隔离测试。
- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/sdk/tests/test_table_layout.py -q`，确认 metadata_only/layout 缺失失败。
- [x] 实现 optional hooks 与 registry bridge forwarding，保留 credentials lease/connector affinity。Excel 从 workbook.xml/relationships 解析 sheetId；Maybe 从 sheet 元数据解析 gid。同名不同 ID 必须拒绝；不将Maybe table URI直接传给只接受 workbook URI 的 bind。没有 hook 的 provider 返回已有 unsupported error。
- [x] 将 TableLayoutSession 的 config/range 委托现有 worksheet；读取经 `_session.observe`、结果经 `_adapt`，不新增结果包装。保证 workbook/Table descriptor 同源，更新 CellStyle/CellFormat facade 导出。
- [x] 同时运行 `packages/sdk/tests/test_table.py`, `test_client.py`, `test_registry.py`, `test_workbook_session.py`, `test_table_layout.py`，确认旧行为与新绑定都通过。
- [x] Commit：`feat: expose financial layout through bound Tables`。

## Task 5: Excel writer 支持完整格式与文本模式，保持原始值

**Files:**
- Modify: `packages/local_files/src/open_table_connector/local_files/spreadsheet_workbook.py:262–440,482–743,1109–1230`。
- Modify: 同包 `spreadsheet_verify.py`（复用受限原始 XML 读取），不削弱旧校验。
- Create: `packages/local_files/tests/test_spreadsheet_layout_write.py`。

**Interfaces:** writer 消费 Task 2/3 的 normalized changes；现有 `LocalSpreadsheetProvider.commit` 返回结构保留。provider descriptor 暂只在经过本任务 writer+Task 6 readback 共同通过后广告 read/write/persist。

- [x] 构建真实 XLSX fixture：数值 serial 60、1904 workbook、空白 styled cell、公式、主题色、四边边框、合并、不同 sheetId；保存前后用原始 XML 比较值/类型/公式。

```python
def test_date_format_does_not_reencode_serial_60(excel_case):
    # excel_case owns a raw OOXML file with A1 numeric v=60, not a Python datetime.
    before = excel_case.raw_cell("A1")
    excel_case.queue("range.format", address="A1", pattern="yyyy-mm-dd")
    excel_case.commit()
    after = excel_case.raw_cell("A1")
    assert (after["v"], after["t"], after["f"]) == (before["v"], before["t"], before["f"])
```

本文件 `excel_case` 以现有 provider/change/binding helpers 封装 queue/commit，raw_cell 用独立 stdlib ZIP/XML 解析 `{v,t,f}`，不调用生产 writer/observer。

- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/local_files/tests/test_spreadsheet_layout_write.py -q`，确认 serial roundtrip/新 wrapping 当前失败。
- [x] 让 `_style/_config/_apply` 消费 shared normalization，保留字体/四边 patch，映射 shrink_to_fit，支持 column_sizes 的 excel_character。builtin 格式按版本/locale 解码和存储，custom code 原样保存。
- [x] 处理 openpyxl 自动日期解码和 sheetId 重编号：layout-only 保存路径从原始快照保留未修改 cell 的 `<v>/<f>/type` 与 sheetId/relationships，将必要恢复合入已拥有 staging ZIP，再独立验证后原子发布；仅恢复明确未改值的单元格，不能覆盖同 batch 的真实 value/formula 修改。不新增第二个 XLSX writer。
- [x] 测别名 font_size/size、保留图表/公式/图片、format 的 locale/calendar 字符、wrap→shrink→no_wrap、clip 拒绝无副作用；readonly/protected/不安全 archive 继续沿用失败规则。
- [x] 同时运行新测试及 `test_spreadsheet_provider.py`, `test_spreadsheet_workbook.py`, `test_spreadsheet_verify.py` 至通过。
- [x] Commit：`feat: persist Excel layout without changing cell data`。

## Task 6: Excel 独立物理 reader

**Files:**
- Create: `packages/local_files/src/open_table_connector/local_files/spreadsheet_observe.py`。
- Modify: 同包 `spreadsheet_workbook.py:1015–1107`, `spreadsheet_verify.py`。
- Create: `packages/local_files/tests/test_spreadsheet_layout_read.py`。

**Interfaces:**

```python
def observe_xlsx(data: bytes, *, target: Mapping[str, Any],
                 selector: Mapping[str, Any], limits: ArtifactLimits) -> JSON: ...
```

返回 Task 1 observation；仅接受稳定有界 byte snapshot，不接收 writer workbook 或 expected。共享既有 ZIP/XML 资源限制解析入口，必要时抽出小 helper 供旧 verifier 和本 reader 共用，不改变旧 literal coverage。

- [x] 测 raw XML 的显式/default/inherited、主题/tint/auto/无填充、空格、合并内部、隐藏/auto-size/默认尺寸、zoom/freeze/gridline。fixture 必须有无 `<c>` 的空白位置和显式 false，不能全由新 writer 生成。

```python
def test_stored_false_differs_from_inherited_false(raw_cases):
    from open_table_connector.local_files.spreadsheet_observe import observe_xlsx
    first = observe_xlsx(**raw_cases["explicit_false"])
    second = observe_xlsx(**raw_cases["inherited_false"])
    assert first["physical_hash"] != second["physical_hash"]
```

`raw_cases` 在本文件构造同 target/selector/limits 的独立字节快照；值有效相同但物理来源不同。

- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/local_files/tests/test_spreadsheet_layout_read.py -q`，确认 reader 缺失失败。
- [x] 解析 cell/style/row/column/sheet defaults 引用，按 spec 解码完整字段来源与格式上下文；主题 source 来自同一 archive。对每个选中字段形成 source_ref，缺来源不猜。合并内部读 raw cell，不能复制 openpyxl MergedCell 的合成边框。
- [x] 规范 row/column native units、原始 auto-size/hidden、number_format storage_kind/code/builtin_id/locale/date_system；自定义 style/numFmt 索引放 provenance，语义不变时重排 hash 相同。
- [x] 对新 style/config 读取分支使用独立文件读取；dirty style/config 读拒绝，保留现有 range value preview 兼容行为。标准定义的默认值可作为有版本来源的来源证据，不能用不带依据的客户端默认填空。
- [x] 加 tampered ZIP/XML、duplicate cell、截断、缺字段、错误 sheetId、10,001 cells、8 MiB+1、negative zero/hash 稳定测试；运行新 suite + 旧 verifier suite 通过。
- [x] Commit：`feat: independently observe persisted Excel layout`。

## Task 7: MaybeSheet provider 与独立 reader

**Files:**
- Create: `packages/maybe_sheet/src/open_table_connector/maybe_sheet/spreadsheet_observe.py`。
- Modify: 同包 `spreadsheet.py:95–131,204–816`, `process.py`。
- Create: `packages/maybe_sheet/tests/test_spreadsheet_layout.py`。
- Consume: Task 0 的 `tests/fixtures/layout-protocol.json`。

**Interfaces:**

```python
def decode_maybe_layout(payload: Mapping[str, Any], *, target: Mapping[str, Any],
                        selector: Mapping[str, Any], descriptor: Mapping[str, Any]) -> JSON: ...
```

实际 argv 仅使用 Task 0 核实的映射。新的 observer 只输入 read response；写入 result 和预期不能传给它。descriptor 来自协议能力与经过测试的版本支持交集，不能把全部新 identity 静态加到 tuple。

- [x] 用 Recording process 分离持久存储状态、写入 acknowledgment、read responses；增加 ignored-write 和 reopen-discard 模式。commands log 标记 mutation/read，单测断言真实 read dispatch。

```python
def test_missing_read_capability_rejects_before_mutation(maybe_case):
    maybe_case.remove_capability("range.style.read")
    result = maybe_case.read_style_result(address="A1", fields=["bold"])
    assert result.outcome.value == "rejected"
    assert result.error.code.value == "unsupported_capability"
    assert maybe_case.mutation_calls == []
```

`maybe_case` fixture 在本文件使用 Recording process +真实 SDK layout session；read_style_result 调用真实 Range.read_style，捕获 OTCError 时返回其 result，不吞其他异常；remove_capability 修改独立协议能力状态。

- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/maybe_sheet/tests/test_spreadsheet_layout.py -q`，确认新增观察/校验缺失失败。
- [x] 实现实际支持命令映射、format 与 mode 归一化、field capability preflight、gid 绑定验证；别名只允许已验证无损转换。有未知属性的批次在第一条 mutation 之前拒绝。
- [x] decoder 校验完整 range/目标/字段/来源/单位/原生格式；填充空格必须根据真实稀疏默认元数据，不根据写入参数。格式被降为 General、schema 宣称全字段却缺值属于执行/协议失败。
- [x] 在 subprocess 读取阶段执行 8 MiB+1 有界读取并终止超限进程，保留 timeout/cancellation/secret redaction；不能等 capture_output 无界分配后才检查长度。新增 process boundary 测试，保留其他 Table/Formula 命令的现有预算。
- [x] 测旧版本、权限变化、gid 替换、部分提交、read timeout、单位量化、false、全部广告 mode/线型/格式；运行新 suite + `test_spreadsheet.py`, `test_process.py`, `test_cli_adapter.py`。
- [x] Commit：`feat: implement evidence-backed MaybeSheet layout operations`。任何 Task 0 必需 gap 未关闭则保持对应能力不广告及整体 gate blocked。

## Task 8: 共享 intent、commit/readback 与诚实结果状态

**Files:**
- Modify: `packages/spreadsheets/src/open_table_connector/spreadsheets/_session.py:92–191`, `_protocols.py`。
- Modify: `packages/sdk/src/open_table_connector/sdk/workbook.py:208–382`。
- Modify: 两个 provider 的 `commit/observe` 接口接入处。
- Create: `packages/spreadsheets/tests/test_layout_verification.py`。
- Modify: `packages/sdk/tests/test_workbook_session.py`。

**Interfaces:** 保留 commit 的现有参数；新增可选 `layout_expectation: Mapping[str, Any] | None = None` 仅在 provider 广告 layout verification hook 时传入；不把新 kwarg 传给旧 provider。session 持有独立 `layout_expected`，原 `expected` artifact expectation 继续使用，不能覆盖。

- [x] 写故障注入测试：writer 忽略更改、成功提交后 reader 超时、篡改调用方 intent、同一 session 第二次 write 无新变更、重开无 expectation、多个 scope 总预算越界。

```python
def test_read_timeout_after_commit_never_replays_write(failing_read_session):
    session, provider = failing_read_session
    session.queue("range.style", "Report", {"address": "A1", "bold": True})
    result = session.write(verify=True)
    assert result["commit"] == "committed"
    assert result["verification"] == "unavailable"
    assert result["outcome"] == "failed"
    assert provider.commit_count == 1
    assert session.pending == ()
```

本文件 fake 实现现有 bind/preflight/commit/observe；首次 baseline 读成功，提交后 observe 抛 TIMEOUT，并记录 commit_count。返回 failed 而非异常时均经现有 SDK adaptation 验证。

- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/spreadsheets/tests/test_layout_verification.py -q` 确认 verify 参数当前未驱动此流程而失败。
- [x] 在锁内先验证全批能力及预算，独立读 baseline，再 prepare_layout；canonical coverage 合并重叠 ranges，保证聚合时每个 target/coordinate/field 只有一份最终观察；dry_run 不提交且保留 pending，读取失败不 dispatch。对新 worksheet 无 preexisting baseline，使用创建契约可证明默认来源；证明不足则拒绝 verify=True，不拿写后状态反推。
- [x] provider commit 使用已冻结 layout expectation；Excel 在 staging 验证通过才发布，发布前失败为 not_committed；Maybe 成功 acknowledgment 后独立读回。保存后公开观察必须重新读取已发布状态，不能标记 staging 观察为已发布读取。
- [x] 已知 committed 后先保留 receipts/IDs 并清空 pending，再做独立 readback；read mismatch 为 failed/committed/failed，read error 为 failed/committed/unavailable，绝不重发 writes。partial/unknown 保持 unresolved/rebind。verify=False 跳过版式比较，但不禁用 Excel 原有安全/完整性检查；receipt 区分旧 artifact verification 与 layout skipped。
- [x] `verify(expected)` 根据 kind 分派旧 artifact 或新 layout expectation；无 expectation 的新 layout 只读不能 passed。style/config 读不使用 pending overlay；原数据 preview 不受影响。无 revision 的聚合标 sequential_unversioned。
- [x] 运行新测试与 `packages/spreadsheets/tests/test_session.py`, `packages/sdk/tests/test_workbook_session.py`, 两个 provider layout suites 通过。
- [x] Commit：`feat: verify committed layouts against independent intent`。

## Task 9: CLI 与现有 SDK 调用一致

**Files:**
- Modify: `packages/cli/src/open_table_connector/cli/spreadsheet_commands.py:16–177`。
- Create: `packages/cli/tests/test_spreadsheet_layout.py`。

**Interfaces:** 新增 action `style-read`, `config-read`；`--fields`, `--rows`, `--columns`, `--view-fields` 使用严格 JSON 数组；现有 --uri/--sheet/--range/--expected 保持。输入 --uri/--sheet 经公共 resolver 生成 Table metadata binding，再调用 Table.layout；不在 CLI 重写 provider 逻辑。旧 workbook 创建/批量数据写入继续原路径。

- [x] 添加使用 tmp_path 真实 XLSX 的 CLI 测试，按现有 CLI test runner 构建 argv 并读标准 JSON envelope；先验证 action 尚不存在失败。

```text
otc spreadsheet style-read --uri file:///absolute/report.xlsx --sheet Report --range A1:F40
otc spreadsheet config-read --uri file:///absolute/report.xlsx --sheet Report --rows '[1,2,40]' --columns '["A","B","F"]'
otc spreadsheet verify --uri file:///absolute/report.xlsx --expected expected-layout.json
```

这些是目标命令语法示例，不使用示例路径执行真实写入。

- [x] 将 read 动作及 identity 加入 batch 禁止集合；拒绝 duplicate keys、非 finite、超限 JSON、非法字段、缺 rows/columns、metadata ambiguity。读取/verify 的 --expected 必须包含新 expectation kind 或旧合法 artifact profile，不能接受当前文件反推的空 expected。`.format(pattern=...)` 中引号/反斜杠原样过 CLI JSON，不经过 shell 拼接。
- [x] schema/错误/code/receipt/hash 与同一 Table Python 调用逐项比较；能力不支持 exit 5 并包含 unsupported_capability；参数语法错误维持原 usage exit。
- [x] 运行 `uv run --all-packages --frozen python -m pytest packages/cli/tests/test_spreadsheet_layout.py specification/conformance/universal/test_cli_surface.py -q` 至通过。
- [x] Commit：`feat: expose unified layout reads in spreadsheet CLI`。

## Task 10: 共用合约 fixture 和全部 F1–F15 自动检查

**Files:**
- Create: `specification/conformance/spreadsheets/layout_cases.py`, `conftest.py`, `test_layout.py`。
- Modify: `specification/conformance/universal/cases.py` 的新 capability binding。
- Create: `specification/conformance/spreadsheets/fixtures/financial-layout.json`。

**Interfaces:** `LayoutCase` 是测试用 dataclass，字段 `provider_name`, `table_address`, `client_factory`, `column_sizes`，方法 `open_layout()`, `reopen_layout()`, `corrupt(field, value)`, `close()`；open_layout 使用 `client.open(..., metadata_only=True).require_value().layout()`。reopen 必须关闭旧 client，创建全新 provider/process 后只复用持久化存储，不能克隆旧 binding/receipt/cache。fixture parameter 为 excel 与 maybe_recorded；live case 在 Task 11 实现。

- [x] financial-layout.json 定义 A1:F40：标题、表头、正文、金额、合计、脚注、空白 styled cells；存用户 intent，不存 production-normalizer 生成的预期。factory 提供原生尺寸，不在测试业务逻辑按 provider 分支。

```python
def test_reopen_retains_physical_hash(layout_case):
    first = layout_case.open_layout()
    first.range("A1:F1").style(bold=True, text_layout="wrap")
    result = first.write(allow_partial=True, verify=True).with_results()
    assert result.verification.value == "passed"
    before = first.range("A1:F1").read_style().require_value()
    second = layout_case.reopen_layout()
    after = second.range("A1:F1").read_style().require_value()
    assert before["physical_hash"] == after["physical_hash"]
```

- [x] 用上述通用 fixture parameter 跑测试，先确认缺 fixture 或两个 provider 集成缺口导致失败，再实现 harness，不能给 Maybe 返回 Excel fixture 来替代其真实录制协议。
- [x] 把 F1–F15 拆成独立参数用例：逐字段混合样式、四边 patch、默认尺寸/view、忽略写入、hash metadata 排除、reopen 丢失、协议缺字段、旧单位 API、全格式 corpus、文本模式往返。可选模式测试 assert unsupported；必需模式不允许 skip/xfail。
- [x] 外部 corrupt 接口直接修改独立 XLSX/recorded store，不能用被测 writer；比较明确 expected/actual diff，不只断言 hash 不同。
- [x] 增加 total cells/bytes 边界、native_combination、theme/default 来源、同名替换不同 ID、header 偏移、两个公开入口输出等价、data transaction 隔离测试。
- [x] 运行 `uv run --all-packages --frozen python -m pytest specification/conformance/spreadsheets -q`；各新身份在 universal fixture 中实际执行，不能只返回身份字符串。
- [x] Commit：`test: add shared Excel and MaybeSheet layout conformance`。

## Task 11: 真实服务 reopen 与格式应用效果 gate

**Files:**
- Create: `specification/conformance/spreadsheets/test_layout_live.py`。
- Modify: `specification/conformance/spreadsheets/layout_cases.py`, 两个 corpus fixture、`docs/spreadsheet-readiness.md`。

**Interfaces:** live Maybe case 仅在 `OTC_TEST_MBS_LAYOUT_ENABLED=1` 时启用；创建 disposable Sheet workbook，保留 ID，结束用已验证的可恢复删除清理。Excel 应用显示语料 gate 用 `OTC_TEST_EXCEL_LAYOUT_RENDER_ENABLED=1`，真实应用/其受信 render 证据来源写入 readiness；不是 openpyxl 的格式化结果。没有可用环境则 gate 未通过，离线 CI 可以 skip 但不算发布通过。

- [x] 复用 Task 10 完整测试语料运行 live Maybe；在新 OS 子进程执行 reopen，stdin 只传 target/selector/expectation，stdout 回传 observation；凭据通过既有 resolver，不写入 artifact。
- [x] 对每个格式类别用正/负/零/文本、真实 numeric/date serial fixture 验证原始存储不变；对代表格式收集目标应用的 displayed text/样式或人工确认过的截图证据。颜色/会计填充/裁剪等无法由 displayed text 证明的项需要视觉或原生布局属性证据。哈希仍仅依物理 payload。
- [x] corpus manifest 明确每个 built-in ID×locale×date_system 的测试状态，所有合法 custom 语法族有组合语料；加入未在基本例表的自定义代码，证明不是白名单实现。有限语料不等于数学证明全部代码，但不得因此人为截断合法语法支持。
- [x] 运行下列 gate，任一必需项 skipped/unsupported/mismatch 都留为未通过；不要关闭 Maybe typed RAW guard。

```bash
OTC_TEST_MBS_LAYOUT_ENABLED=1 uv run --all-packages --frozen python -m pytest specification/conformance/spreadsheets/test_layout_live.py -k maybe -q
OTC_TEST_EXCEL_LAYOUT_RENDER_ENABLED=1 uv run --all-packages --frozen python -m pytest specification/conformance/spreadsheets/test_layout_live.py -k excel -q
```

- [x] readiness 保存精确 OTC/mbs/service/Excel 版本、locale/date system、命令、首读/reopen hash、expectation hash、原始证据位置与内容 hash、清理结果。report 里不得保存真实财务数据或令牌；使用合成 fixture。
- [x] Commit：`test: establish live financial layout acceptance`。环境缺失时只提交测试与真实“未通过”状态，不提交伪通过记录。

## Task 12: 包装、兼容性与发布文档

**Files:**
- Modify: `packages/local_files/src/open_table_connector/local_files/manifest.py`、MaybeSheet capability advertisements。
- Modify: `docs/user-guide/spreadsheet-operations.md`, `docs/reference/python-api.md`, `docs/spreadsheet-readiness.md`。
- Modify only if required by new runtime files/exports: package `pyproject.toml`、`scripts/check_package_independence.py`, `scripts/smoke_wheels.py`。

**Interfaces:** 正向广告只来自已通过的 descriptor；metadata-only/layout 在 core-only 与单 provider 安装中能返回明确缺能力错误，不因可选依赖缺失崩溃。

- [x] 增加 built-wheel smoke：从安装后的 Table 入口绑定真实小 XLSX、style/write/read/reopen；Maybe 独立 wheel 用录制 transport 验证 Table 路由。禁止源码 PYTHONPATH 掩盖缺文件。
- [x] 更新文档：统一 Table 示例、旧 workbook 兼容、format/builtin/locale、五种文本模式、原生尺寸、源值不变、fields=None 和完整证据、partial/readback 状态、reopen expectation 持久化。
- [x] 运行以下现有发布命令，首次 baseline 对比记录于 readiness；新回归不通过不得用历史已知失败豁免。

```bash
uv run --all-packages --frozen python -m pytest -q
uv run --frozen ruff check scripts specification/conformance/universal/test_package_boundaries.py
uv run --frozen mypy scripts
uv run --all-packages --frozen python scripts/check_package_metadata.py
uv run --all-packages --frozen python scripts/check_package_boundaries.py
uv run --all-packages --frozen python scripts/check_canonical_literals.py
uv run --all-packages --frozen python scripts/check_package_independence.py --build
uv run --all-packages --frozen python scripts/smoke_wheels.py --build
git diff --check
```

- [x] 对新增/修改 Python 文件单独运行 Ruff；按 `.github/workflows/ci.yml` 跑 Python 3.11、3.12、3.13、3.14。不因为本任务修改整个旧树以追求无关 lint 清零。
- [x] 执行 `graft build` 更新较大代码变更的图；复核只提交本任务文件。
- [x] 做整分支 review，检查 Table binding、observer 与 writer 独立性、raw cell 保留、默认来源、权限/partial/未知状态；修复后只重跑受影响测试及必要最终 gate。
- [x] Commit：`docs: publish unified layout capabilities and acceptance evidence`。Task 11 gate 未通过时不把 spec/readiness 标记 implemented/accepted。

## Plan self-review

已检查任务接口名称与依赖顺序、Table-only 交付遗漏、metadata-only schema 未观察状态、Maybe 协议核验和最终 live gate 的非循环关系、独立 verifier 与持久化真值、F1–F15 覆盖。任务中的测试代码片段为实施时添加的关键行为断言，不表示当前功能已存在或这些测试已运行；本次只执行文档检查。

## Spec-to-task checklist

| 要求 | 实施任务 | 完成证据 |
| --- | --- | --- |
| 统一 Table、无全表读取、旧 API 兼容 | 4,9,10,12 | metadata-only/read-count、Table/workbook parity、wheel smoke |
| range.style.read / config.read，默认/空白/合并/单位 | 1,3,6,7,10 | F1,F4,F10 + 原始 fixture |
| 完整 format / builtin / date / currency / accounting | 2,5,6,7,11 | F13,F14，版本与应用显示证据 |
| alignment / wrapping / 四边 border patch | 3,5,7,10,11 | F2,F3,F15，模式往返和 optional error |
| 可重算 hash / schema / scope / limits | 1,6,7,8,10 | F6,F10，离线重算、总预算 |
| intent 独立 / readback / 保存状态诚实 | 5,6,7,8,10 | F5,F9,F11，writer 故障注入 |
| 关闭/重新打开后的同目标物理证据 | 4,10,11 | F7,F8，新 client + OS process |
| 上游能力与部署依赖显式 | 0,7,11 | 每字段命令/真实响应、gaps 清零 |
| 安全边界 / preservation / packaging | 5,6,7,12 | 旧 literal suites + F12 + wheel tests |

## Handoff

本计划仅安排实施，不执行代码。建议采用逐任务实施和独立评审，因为 Table 绑定、双 provider 物理证据与完整格式持久化存在不同故障边界；Task 8 必须等接口稳定后整合。也可以在本会话依序实施并在末尾做一次完整 review。先评审本计划，选定执行方式后开始 Task 0/1；上游缺失不妨碍共享契约与 Excel 工作，但不得越过 MaybeSheet 最终门槛。
