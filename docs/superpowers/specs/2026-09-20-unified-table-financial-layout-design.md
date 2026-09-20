# Excel / MaybeSheet 统一 Table 财务版式接口

日期：2026-09-20。状态：提案，待评审；本文不表示功能已经实现或通过线上验收。
仓库基线：`ae8e16d`。

## 1. 目标和范围

Excel 与 MaybeSheet 的 Sheet-mode 报表必须通过统一 `Table` 接口写入正式财务版式，并通过独立读取证明实际存储的样式、尺寸和视图配置符合预期。写入确认、读取成功、预期匹配、重新打开后的持久化匹配是四种不同证据，不能互相替代。

必须交付：

1. `range.style.read`：bold、italic、font size、foreground、fill、number format，以及本次新增的 alignment 和 border。
2. `worksheet.config.read`：指定行的高度、指定列的宽度、gridline 和声明支持的 view config。
3. alignment 读写：至少 left/center/right；文本布局支持明确的 no_wrap、wrap、overflow、clip、shrink_to_fit 模式，映射与 provider 限制见第 5.2 节；vertical alignment 按 provider 声明支持。
4. border 读写：top/bottom/left/right，至少 `none`、`thin`；其他基础线型逐项声明。
5. 支持全部 Excel 单元格数值格式类别、内置格式与合法自定义 format code，包括日期、时间、货币、会计格式；不得限制为少量预设。保持现有 format、row height、column width 写入入口、单位与缓冲提交语义。
6. 独立 readback、可重算哈希的完整范围内物理证据，以及关闭并重新打开 workbook 后的重复验证。
7. 所有不支持的操作、属性和值域显式返回 capability error，不能静默丢弃或近似替换。

范围包含 Excel `.xlsx` 与 MaybeSheet Sheet-engine 的 `general/1.0`，两个 provider 均为必需交付，复用统一 spreadsheet extension。现有 Excel `literal-artifact/1.0` 保持更严格规则，不因新入口降级。Base-engine 不在范围内，混合文档中的 Base 工作表不得被修改。Google 不因共享接口新增而自动宣称支持。本文不增加财务计算、模板生成、打印/PDF、条件格式、合并操作或全目录能力；不解除已有 typed-value 写入限制。

“完整物理证据”指显式声明的范围、字段集合及已持久化样式/配置，包含空白单元格和默认值；不是整本无限网格、屏幕截图、条件格式渲染结果或 XLSX 字节证明。调用方必须把全部报表范围纳入覆盖集合。

这里的“所有 Excel format”按本次 number/date/currency 举例定义为完整单元格数字格式体系（Format Cells → Number），不是仅当前 SDK 的 kind 枚举；其余字体/边框等版式按本文明确字段交付。格式设置不得改变底层数值、公式或数据类型。

## 2. 现状与依据

以下路径和行号对应上述基线：

| 位置 | 已确认行为与缺口 |
| --- | --- |
| `packages/maybe_sheet/src/open_table_connector/maybe_sheet/spreadsheet.py:61–88` | 广告包含 `range.style`、`range.format`、尺寸写入及 `workbook.verify`，没有专门的 style/config read |
| 同文件 `204–233` | `worksheet.config` 只展开 `row_heights` 与 `column_widths_pixels` |
| 同文件 `250–433` | 样式白名单没有 alignment/border；已有 font、color、format 及尺寸校验 |
| 同文件 `580–622` | 样式编译到 `style.format`；行高从 point 按 96/72 转换为 px，列宽使用 px |
| 同文件 `640–816` | 多命令要求 partial opt-in；提交返回 remote acknowledgment；verify 只观察工作表列表，verification unavailable |
| `packages/spreadsheets/src/open_table_connector/spreadsheets/_session.py:92–183` | 共享缓冲、commit/observe/verify 和 expectation 入口；当前 `verify` 写入参数未驱动物理版式校验 |
| `packages/sdk/src/open_table_connector/sdk/workbook.py:441–442,498–564` | 现有 config/style/format 写入 facade 与 range read，可增量扩展 |

延续 [Excel/Maybe completion](2026-09-14-excel-maybe-sheet-completion-design.md) 的 provider/session 边界、独立 verifier 与诚实结果状态。已有发布证据见 [readiness](../../spreadsheet-readiness.md)；其中历史 mbs 版本记录不是本次新能力的兼容性证明。

补充 Excel/Table 基线：`sdk/table.py:46–63,196–289` 的 TableBinding/Table 没有物理版式入口；`local_files/spreadsheet_workbook.py:262–440` 已实现 alignment、border、行高、Excel 原生列宽和部分 view 写入；`1015–1107` 已有独立重载验证，但没有本次 style/config 观察接口。复用这些能力，不另写 Excel writer。`spreadsheets/model.py:109–121` 的 CellFormat 目前仅允许 text/general/number/percent/currency/date_time/native；本次需要扩展公共分类与原生代码通路。Excel `_style` 当前只有 wrap_text，尚无 shrink_to_fit 或明确 overflow/clip。

## 3. 方案选择

| 方案 | 取舍 |
| --- | --- |
| **推荐：Table.layout + 统一 observe + 版本化物理证据** | 复用当前 session/provider seam，style/config 读取独立可调用，验证复用同一观察模型；需要上游提供实际存储读取 |
| 从写入参数或 acknowledgment 生成“读取结果” | 实现简单，但无法发现静默忽略、存储转换或 reopen 丢失，不满足验收 |
| 新建财务专用 facade / 使用导出文件或截图验证 | 引入第二套 API；导出或视觉结果不能充分证明原 workbook 的逐字段物理状态，不采用 |

新增薄的 `Table.layout()` 入口，复用现有 workbook/session/range 对象；不新增通用样式引擎、结果包装层或独立财务 provider。实际 mbs 命令与 JSON 字段必须通过已安装版本的帮助、协议及真实响应确定；本文的操作 ID 不代表同名 mbs CLI 命令已经存在。

## 4. 公共接口与兼容性

新增 capability identities，版本均为 `1.0`：

- `spreadsheet.range.style.read`
- `spreadsheet.worksheet.config.read`
- `spreadsheet.range.alignment.read` / `.write`
- `spreadsheet.range.border.read` / `.write`
- `spreadsheet.range.text_layout.read` / `.write`

保留 `spreadsheet.range.style`、`range.format`、`worksheet.config`、`row.height`、`column.width` 的现有语义。alignment/border/text_layout 的细粒度身份用于能力发现与错误定位；读由 `range.style.read` 返回，写由 `range.style` 承载，不增加重复命令流。

拟新增统一 Table facade（`table` 由现有 Client 绑定为 Sheet-mode；切换 provider 只替换该绑定）：

```python
layout = table.layout()
sheet = layout.worksheet
sheet.range("A1:F40").read_style(fields=None)
sheet.read_config(rows=[1, 2, 40], columns=["A", "B", "F"], view_fields=None)

sheet.range("A1:F1").style(bold=True, horizontal="center", text_layout="wrap")
sheet.range("B2:F40").style(horizontal="right", vertical="center")
sheet.range("A40:F40").style(
    border={"top": {"style": "thin", "color": "#000000"}}
)
sheet.range("B2:F40").format(pattern='#,##0.00;[Red](#,##0.00);"-"')
# column_sizes 来自报告配置，使用 capability 声明的原生单位。
# Excel 示例：{"A": {"value": 24, "unit": "excel_character"}}
# MaybeSheet 示例：{"A": {"value": 180, "unit": "px"}}
sheet.config(row_heights={1: 24}, column_sizes=column_sizes)
result = layout.write(allow_partial=True, verify=True).with_results()
```

以上为目标 API，不是现有可运行示例。

`table.layout()` 返回绑定到该 Table 所属 worksheet 的受限 layout session，提供 `range(address)`、`read_config(...)`、`config(...)`、`write(...)`、`verify(expected=...)`、`capabilities()`、`close()` 和 context-manager；`layout.worksheet` 是同一绑定 worksheet 的现有 facade。例中的 `sheet.range(...)` 等价于 `layout.range(...)`，不要求调用方重新指定 workbook URI、worksheet 名称或 provider 类。关闭不保存；layout.write 只提交该 session 的版式队列，绝不自动执行 Table.insert/update/delete。Table.transaction 保持现有数据行语义，不隐式纳入版式事务。

绑定规则：通过现有 resolver 将 Table URI/selector 转成 workbook 资源及唯一 worksheet 身份，MaybeSheet 使用 document/gid，Excel 使用规范文件资源及 workbook sheetId。只接受真实 Sheet-mode；Base、CSV、SQL 等无版式目标返回 unsupported_capability。不能从数据 frame、表头行、第一张 sheet 或名称猜测目标；选择器有歧义时必须显式拒绝。范围始终采用绑定 worksheet 的绝对一基 A1 坐标，不因数据读取 header 或行偏移改变；不接受跨 worksheet 前缀。

layout session 复用现有 SpreadsheetSession 状态机和 provider 锁；不维护第二套缓存/提交引擎。旧 workbook 入口继续可用并委托相同逻辑。独立会话不共享未提交队列，同资源并发限制延续已有规则；陈旧绑定在读取/提交前检查并拒绝。新空 workbook 仍由现有 workbook.create 创建，随后可用 Table 绑定使用统一版式入口。

保持 `.style(...)` 和 `.config(...)` 为写入方法，不将它们替换成破坏调用兼容性的 namespace。读取返回现有 `OperationResult`，物理 payload 在 `value`，来源与 hash 在现有 receipt details。

`fields=None` 请求全部本规范 style 字段；任一字段不支持则整体 capability error。调用方可以显式选择字段子集，但响应必须声明实际覆盖字段，不能把子集冒充完整证据。`view_fields=None` 请求 descriptor 公布的全部持久化 view 字段；最小集合为 `zoom_percent`、`frozen_rows`、`frozen_columns`，gridline 独立必读。

rows/columns 必须显式给定、非空、去重并规范排序；行列坐标均为一基，列字母转换为列序数。读取已提交状态，pending edits 存在时继续显式拒绝，不自动 write，不从 pending overlay 合成结果。

CLI 增加对应 style/config 读取分支，复用 SDK 和现有 JSON result envelope；batch 写入仍使用已有 operation/arguments。不同 provider 未实现读取时应产生明确错误，而不是 AttributeError 或空对象。

## 5. 能力声明与写入规则

在现有 capability 名单之外提供可序列化的字段级 descriptor，通过 `layout.capabilities()` 返回，Table capability discovery 与 workbook inspect 均引用同一份 descriptor：provider/协议版本、operation、read/write、允许值、单位、精度、默认值来源、限制。名单继续兼容；descriptor 决定具体字段是否可用，不能只检查大类字符串。

| 字段 | 规范 |
| --- | --- |
| bold / italic | 真实 boolean；显式 `false` 必须写入并读回 |
| font_size | 正有限值；规范输出 points，provider 转换规则必须经过测试 |
| foreground / fill | 保持现有 `#RRGGBB` 写入；观察保留颜色类型、颜色值或无显式覆盖状态 |
| number_format | 全类别/内置/自定义 Excel 格式，返回完整 code 及内置格式上下文，详见 5.1；不能只给 kind 或显示文本 |
| horizontal | left / center / right 必须读写；其他值只在广告并测试后支持 |
| text_layout / wrap_text / shrink_to_fit | 明确模式及原始 boolean 状态按 5.2；保留 wrap_text 兼容入口；不能把 `false` 当作未提供 |
| vertical | top / center / bottom 按 descriptor 支持；provider 的 middle 等别名只可显式无损转换 |
| border | 四条边分别表达，最低线型 none / thin；medium/thick/dashed/dotted/double 仅在实测支持时公布；颜色同上 |
| row height / column width | 行高 points 通用；列宽必须携带 unit，Excel 原生 excel_character、MaybeSheet 原生 px；读取同时提供原生单位与精确可表示的规范值 |
| gridline / view | 必须读取 show_gridlines 与最小 view 集合；其他持久化 view 字段按 descriptor 枚举，不包含鼠标选择或本地滚动位置 |

统一尺寸参数新增 `column_sizes={"A": {"value": 18, "unit": "excel_character"}}` 或 `{"value": 180, "unit": "px"}`；同一接口由 descriptor 确定单位是否支持。保留 Excel 的 `column_widths` 与 MaybeSheet 的 `column_widths_pixels` 兼容入口，以及共同的 `row_heights`。新旧参数同列冲突时拒绝。跨 provider 调用使用带 unit 的 column_sizes，业务方法无需 provider 分支；报告配置保留各目标的原生尺寸要求。字符宽与像素受字体/渲染条件影响，不允许常数近似转换；未证明精确转换的单位返回 capability error。

写入是 patch：未提供字段/边保持不变；`border.top` 的修改不能清除其余三边。`style="none"` 显式移除该边；不能用遗漏或未知值清除。每条提供的边要求 style，color 省略时保持原色；none 清除边并以无颜色的规范状态读回。现有 null-as-omitted 行为保留，null 不作为新增清除协议；不扩展全局 reset。

范围 border 应用于每个单元格的指定边，不隐含“仅范围外框”。需要外框时调用方选择首末行/列，避免共享边语义歧义。读取包含存储的各单元格各边；相邻单元格冲突不得视觉合并。

同一个请求出现未知属性、合法但未支持值或无法读取的所需字段时，在任何写入 dispatch 前拒绝整个请求。preflight 校验整个已排队批次，即使 allow_partial=True，也不能先写已支持部分再发现不支持属性。

### 5.1 完整 Excel 数字格式

公共 `CellFormat.kind` 扩展为 general、number、currency、accounting、date、time、date_time、duration、percent、fraction、scientific、text、special、custom、native；保留旧 kind 名称和行为。kind 是调用便利分类，不是可接受格式的白名单；任意合法 Excel format code 都可以经 `.format(pattern=...)` 或 `.format(kind="custom", pattern=...)` 进入，custom/native 必须有 pattern。

| 类别 | 必须覆盖的代表行为 |
| --- | --- |
| General / Number | 整数、小数、千分位、前导零、缩放；正/负/零展示 |
| Currency / Accounting | 币种符号和位置、小数、负数括号、零值占位、会计对齐；保留代码中的填充/留白 |
| Date / Time / Date-time | 短/长日期、年月日、星期、12/24 小时、AM/PM、秒及小数秒、组合日期时间 |
| Duration | 累计时长，如 `[h]:mm:ss`；不能按一天取模 |
| Percent / Fraction / Scientific | 百分比、可变或固定分母、指数及指数位数 |
| Text / Special | `@`、邮编/电话号码等本地化模式；保留前导零 |
| Custom | Excel 支持的多段、条件、颜色、文字、转义、留白/填充以及区域/币种代码 |

必须覆盖 Excel format code 的完整语法，而不是通过有限正则识别上述示例：数位占位、分隔符、百分号、指数、分数、日期时间 token、累计时间、正/负/零/文本段、条件/颜色、字面量/转义、`_` 留白和 `*` 填充，以及格式中合法的 locale/currency/calendar 标记。内置格式与自定义格式均须读写。类别依据 Microsoft 的 [Format Cells 说明](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365-apps/excel/format-cells-settings)；具体代码语义依据 [Excel 格式代码指南](https://support.microsoft.com/en-us/excel/review-guidelines-for-customizing-a-number-format)。实施时把支持的 Excel/OOXML 版本及区域设置记录到 conformance corpus，避免“全部”指向未定义的未来格式。

API 规则：

- `pattern` 是权威精确代码；不能被 kind 的默认 pattern 覆盖。kind 若与代码冲突，拒绝而不是改写。未知自定义组合仍可用 custom/native，不要求推导类别。
- 新增 `.format(builtin_id=...)` 选择目标 Excel 格式 ID；builtin_id 与 pattern/kind 互斥。ID 的版本/locale 语义须可解析；MaybeSheet 必须映射到等价格式或 capability error，不能把 ID 当字符串代码。
- 无 pattern 的旧 kind 保持原默认值。新增默认代码固定为 date=`yyyy-mm-dd`、time=`hh:mm:ss`、duration=`[h]:mm:ss`、fraction=`# ?/?`、scientific=`0.00E+00`。accounting/custom/native/special 没有唯一默认，必须给 pattern；accounting 不自动推断币种。新默认不受执行机器 locale 影响。
- format code 保留原始 Unicode、空格、引号、反斜杠、分号、币种与区域标记；禁止格式化成文本值、替换为相近预设、去除条件/颜色，或把 date 代码改成 number。
- 不改变源值、类型、公式或 workbook 日期系统；日期系统（Excel 1900/1904）、适用 locale/calendar 信息必须作为观察上下文。日期格式验收同时检查 serial 值保持，包括 1900 系统 serial 60；不能偷偷用 Python 日期重写。
- `number_format` 观察使用结构化值：`storage_kind`（builtin/custom/provider）、`code`、`builtin_id`（适用时）、`locale`、`date_system` 与 provider 原生格式标识；不适用明确 null，未知则拒绝完整证据。builtin 的隐式代码通过对应标准/locale 解析，并记录来源；不能伪装成文件里显式写了自定义代码。
- 自定义格式表 ID 是序列化引用，写后可能重排：hash 保留语义代码与 storage_kind，不纳入自定义表索引；内置 ID 有语义，纳入 hash。格式类别是派生说明，不能作为 readback 的唯一实际值。

Excel provider 必须完整存储和读取合法 Excel 格式代码；MaybeSheet 必须用同一接口与证据模型支持上述完整格式目标。仅“保存了一段 code”但 provider 明知不会应用其语义，不算支持；不能静默退化为 General。实施需验证上游格式引擎的实际支持范围；缺失语法/类别是未完成交付，必须记录差距并 capability error，不能靠“provider 子集”宣称已支持所有格式。OTC 不实现替代 Excel 的计算/渲染引擎，但验收必须以目标应用验证过的格式语料证明其应用效果。

### 5.2 多种文本布局 / wrapping

统一 `.style(text_layout=...)`，各模式互斥：

| 模式 | 语义 | Excel 映射及约束 |
| --- | --- | --- |
| `no_wrap` | 不自动折行、不缩小，显示溢出由原生网格规则决定 | wrapText=false、shrinkToFit=false；不承诺相邻格被占用时仍显示全文 |
| `wrap` | 根据列宽自动折行，保留已有显式换行符 | wrapText=true、shrinkToFit=false；不自动改变行高 |
| `shrink_to_fit` | 单元格内缩小显示以适应宽度，不修改存储字体大小 | wrapText=false、shrinkToFit=true |
| `overflow` | 显式允许文本显示到相邻空单元格，遇阻挡按原生规则截止 | Excel 没有独立 overflow 标志；只有在受支持的单元格类型/对齐/合并约束下可保证语义时才映射到 no_wrap，否则 capability error |
| `clip` | 超出单元格可见边界的文本裁剪，不自动折行/缩小 | Excel 没有通用独立 clip 标志；没有无损持久化表示时 capability error，不填充邻格或改写对齐来模拟 |

Excel 的基础存储字段依据 [OOXML Alignment 定义](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.spreadsheet.alignment?view=openxml-3.0.1)。MaybeSheet 必须分别声明每个模式的 read/write/persist 能力，不能从 wrap=false 推断其支持 clip 或 overflow。两端必需基线为 no_wrap 与 wrap；Excel 还必须支持 shrink_to_fit。MaybeSheet 的 shrink_to_fit 及两端的显式 overflow/clip 按实际无损表示能力声明；不支持时显式 capability error。

保留 `.style(wrap_text=True/False)`，其为单字段 patch；新增 `.style(shrink_to_fit=True/False)` 原始字段读写。原始字段同 text_layout 一起提供时拒绝歧义；若最终原始组合 wrap=true 且 shrink=true，写前拒绝。模式切换必须同时更新 wrap/shrink 以清除上一模式残留，不得仅设置一个 flag。

readback 包含原生 wrap/shrink flags、provider 原生模式（如有）、可无损推导的 effective mode 以及第 6 节的默认/显式来源。Excel 无独立 overflow 属性时读回 no_wrap 和其条件性溢出语义，不伪造 stored overflow；写前 expectation 使用已公布的等价映射。读取外部 workbook 中无法唯一归类的原始组合，保留原始 flags 并令 derived mode 为明确的 `native_combination`，不得丢失证据或冒充已知模式。

手动换行符属于单元格内容，不是第六种 wrap 模式；样式写入不得增删换行或改动文本。自动行高、字体旋转、缩进不是 wrapping 的隐含副作用。固定行高下 wrap 可能隐藏部分行，读取必须如实返回行高；若需要完整可见性，由调用方显式设置尺寸或另用已声明的 auto-size 能力。

## 6. 物理观察模型

两种版本化 wire kind：`spreadsheet.range.style.observation/1.0` 与 `spreadsheet.worksheet.config.observation/1.0`。每个观察包含：

- `target`：provider、资源标识和 worksheet 标识；MaybeSheet 为 document ID/gid，Excel 为规范文件 URI/sheetId。名称仅作描述，worksheet rename 不改变身份；Excel 文件迁移属于新目标，不要求目标绑定 hash 不变。
- `coverage`：规范矩形或行列列表、字段列表；`complete=true` 只表示该覆盖集合完整。
- `physical`：读取到的逐项物理状态。
- `provenance`：provider/协议版本、读取 request ID、revision（若支持）、读取时间和一致性级别。
- `physical_hash`：第 7 节算法产物。

style physical 按 row-major 返回每个坐标，包括没有值的单元格。每个选中字段必须存在；alignment 包含选中的 horizontal/vertical/wrap_text/shrink_to_fit/text_layout；border 必须包含四边。禁止把混合样式返回成第一个单元格的样式或单个 `mixed` 标志。允许传输时使用去重表，但哈希前必须无损展开为同一规范矩阵。

每个样式字段以 `{source, stored, effective}` 表示：source 为 explicit、inherited 或 default；stored 是物理覆盖值，无覆盖时为 null；effective 是由此次 provider 响应及其默认/继承元数据确定的有效值。explicit 状态下 stored 必须与该字段类型一致，默认与继承来源必须提供可追溯 evidence。null 不代表“不支持”“没读到”或“未知”。缺乏来源信息、颜色解析或有效值证据时拒绝完整观察，不能靠客户端硬编码默认值填充。

颜色使用类型标签区分 rgb、theme、auto、none。rgb 为大写 `#RRGGBB`；theme 保存 token/tint 和 provider 可提供的 resolved rgb；不能把主题色无损性未知地降为 null。fill 的 none 与白色实填必须可区分。number format 的默认 General 与显式设置同一代码也须保留来源差异；第 5.1 节结构化格式对象作为该字段的 stored/effective 值。

config physical 对每个指定行/列包含显式尺寸、有效尺寸、单位、默认/继承来源、hidden 和 auto-size 状态，并返回相关 sheet 默认尺寸。hidden 与零高度、auto-size 与固定尺寸不得互换。gridline 和每个 view 字段使用同样的来源模型；冻结行列使用非负计数，zoom_percent 为正有限值。

合并单元格仍须覆盖每个请求坐标，携带与范围相交的 merge 区域及 anchor 信息，不能将 anchor 样式复制成不存在的物理覆盖。若 provider 不能给出所需物理状态则明确拒绝此类范围。

统一 Table 版式入口默认每次最多 10,000 cells、8 MiB 观察响应上限，provider 更严格限制优先；不放宽原有 Excel artifact 解析限制，并将 config 的行列条目总数限制为 10,000。超限显式拒绝；不能截断后返回 complete。分页只能在同一 revision/snapshot 下拼接；没有一致性机制时不得自动分页冒充单一快照。

## 7. 哈希与预期模型

`physical_hash = SHA-256(UTF-8(canonical_json(hash_payload)))`，输出 `sha256:<64 lowercase hex>`。hash_payload 精确定义为 kind、稳定 target、coverage、physical；provenance、时间、request ID、名称、会话标识、revision 和 hash 自身不参与。完整 payload 必须随结果返回，不能只返回 digest。

Canonical JSON：对象键按 Unicode code point 排序；无额外空白；UTF-8，不转义非 ASCII；数组依规范顺序；禁止重复键、NaN/Infinity、未知字段。坐标/计数使用 JSON integer；所有物理小数均为规范十进制字符串，无指数、无无意义尾零、负零化为 `"0"`。不对 format code 或字符串进行 trim/Unicode 归一化。

尺寸原生数值与单位参与 hash。point/px 用明确的 72/96 比率转换；重复小数的派生换算值放在非 hash 的展示 metadata，保留原生精确值作为证据。任何 provider 量化必须在 descriptor 定义，并在写前形成预期；不能以临时 epsilon 掩盖写入偏差。

聚合报表证据 `spreadsheet.financial-layout.evidence/1.0` 包含规范排序的 style/config observations，以及由其 hash payload 集合计算的 report physical hash。禁止重复或互相冲突的覆盖项。多个调用拼装的证据必须标明 single_revision 或 sequential_unversioned；后者不宣称原子 workbook snapshot。

跨 provider 不要求 physical hash 相同：目标、默认值、样式物理来源和原生尺寸可不同。共享 conformance 对照相同字段语义及显式单位，各 provider 分别验证自身 reopen hash 不变；不能为了哈希相等抹掉原生证据。

预期使用单独的 `spreadsheet.financial-layout.expectation/1.0`：稳定 target、coverage、要求比较的字段及预期物理值。预期 hash 与观察 hash 分离。写入校验以排队时冻结的用户 intent 为依据；patch 未触及字段的保存性比较以写前独立读取为依据，不能用写后观察生成“预期”。provider 规范化仅允许已声明的无损映射/量化。

重新打开后可传入已保留的 expectation 调用 `layout.verify(expected=...)`（旧 `book.verify` 使用同一验证逻辑）。没有 expectation 的新会话只能做观察，不能标记预期验证 passed。验收同时比较 expectation 和首次 readback 的完整 physical hash，后者用于证明持久化，不替代意图校验。

## 8. 写入、验证与结果状态

流程：解析并检查全部能力 → 冻结 intent → 独立读取 patch 基线 → 提交 → 新的 provider readback → 比较 expectation → 返回观察与差异。

`write(verify=True)` 必须验证本次声明支持的版式变更，覆盖所有变更字段及 patch 保存性边界。若读取能力缺失，在写前 capability error；`verify=False` 保持可写能力并返回 verification skipped。读回必须调用实际持久化读取路径：Excel 重新打开已保存字节，MaybeSheet 发起新的远端读取，不可复用写入 JSON、writer cache 或 acknowledgment。独立读取复用 decoder 可以，复用预期作为实际结果不可以。

| 情形 | 结果要求 |
| --- | --- |
| 所需能力不支持，未 dispatch | rejected / not_started / skipped，unsupported_capability |
| 写入确认，全部目标读回且匹配 | succeeded / committed / passed，附完整证据 |
| 写入确认，实际值不匹配 | failed / committed / failed，附字段坐标、expected/actual 差异 |
| 写入确认，读回超时或响应不完整 | failed / committed / unavailable，附读取错误；不得变成未提交或自动重写 |
| 写入副作用不确定 | 复用现有 unknown/partial 状态，保留已知 effects，要求 reconcile/rebind |
| 单独读取成功，没有 expectation 比较 | succeeded / not_applicable / not_applicable；读取成功不等于验证 passed |

MaybeSheet 多命令仍要求 `allow_partial=True`；本次不引入事务、CAS 或幂等保证。capability 错误使用现有 `UNSUPPORTED_CAPABILITY` / SDK `unsupported_capability`，safe details 至少包含 operation、capability、field、reason 和安全的支持值/版本信息。类型错误沿用参数校验错误；已广告能力返回缺字段/错误形状属于协议或执行失败，不能伪装成能力不支持。

无 revision 的顺序读回必须声明限制，不能证明并发一致性。验收使用隔离且无外部编辑的 workbook；生产环境如发生并发修改则报告实际差异或一致性不足，不伪造快照保证。

## 9. Provider 与交付边界

OTC 负责统一 Table layout facade、CLI、capability descriptor、参数校验、两个 provider 的映射、观察解码、规范哈希、独立比较和 result adaptation。Excel 使用现有 LocalSpreadsheetProvider，MaybeSheet 使用 MaybeSpreadsheetProvider。共享 session 保留 intent 并在清理 pending 前完成验证交接；provider 不导入 SDK。新增 Table layout 绑定不得要求先把整张报表物化为 DataFrame；现有数据行能力不足不能遮蔽该 provider 已具备的版式能力。

Excel 验证必须从独立、受限的已保存 XLSX byte snapshot 解析，结合原始 XML 与 decoded 状态保留显式/继承/default、原生尺寸和 sheetId；不能以 writer 的 openpyxl 对象为 actual。继续保留 ZIP/XML 安全边界、未修改对象保存性、原子发布以及 literal profile 的全部既有验收。Excel content_hash 与本规范 physical_hash 分开，ZIP 排列改变不应改变物理版式 hash。

MaybeSheet 上游 mbs/API/storage 必须支持实际存储样式及 worksheet 配置读取、alignment/border 持久化、默认值/单位/目标身份输出。实施时记录精确命令、envelope、版本或部署 revision，并为每一映射提供录制与 live 测试。若上游缺失，需要先交付上游协议能力；不能为了完成 OTC 适配而猜命令或读取本地缓存。

修改集中于现有 spreadsheets contract/session、sdk/table 与 sdk/workbook、local_files 的 spreadsheet_workbook/spreadsheet_verify、MaybeSheet spreadsheet provider、CLI 和相应测试。Table 绑定入口与能力发现属于必需交付，不能只在 workbook 层完成后宣称统一 Table 接口已完成。允许独立小型 decoder/verifier 模块作为 writer/verifier 边界，不复制 workbook facade。更新 capability exports、conformance 映射、使用指南和 readiness 矩阵。

## 10. 验收矩阵

F1–F11、F13–F15 必须使用同一套 Table layout 合约测试分别参数化运行 Excel 和 MaybeSheet；provider 只提供 fixture/绑定和能力描述，业务调用、观察 schema、错误码及断言复用。

| ID | 场景 | 必须通过的断言 |
| --- | --- | --- |
| F1 | 标题/表头/金额/合计/脚注组成的财务 fixture | bold/italic/font size/foreground/fill/format 的逐格物理值符合预期，含混合样式和空白单元格 |
| F2 | alignment | left/center/right 全部读写通过；必需的 wrap/no_wrap 与广告的各 vertical 值通过；未支持值写前报错 |
| F3 | border | 四边独立写/读、none 移除、thin 基线及所有广告线型通过；修改一边保持其余边，验证范围内逐格语义 |
| F4 | worksheet config | 自定义与默认行高/列宽、show_gridlines、zoom/freeze、hidden/auto-size 状态完整且有单位；view 非默认状态可由独立 fixture 预置 |
| F5 | 独立性 | writer 被模拟为成功但未应用、部分应用或服务端改写时，真实 reader 检出差异；直接编辑 provider 状态后 readback 立即反映变化 |
| F6 | 可哈希性 | 调用方用返回 payload 重算 hash 一致；键顺序/时间/request ID 变化不影响 hash；任一覆盖物理字段改变会改变 hash |
| F7 | reopen | 写入并首次独立验证后，关闭 SDK client/layout session 及文件句柄/mbs 子进程；全新 client/process 重新绑定同一文件/sheetId 或 document/gid，读取相同 coverage；hash 相等且保留 expectation 验证通过 |
| F8 | 持久化缺陷 | fixture 模拟只在 writer 内存生效或 reopen 丢失；F7 必须失败，不能使用原会话 receipt 代替重读 |
| F9 | capability fail-closed | 旧协议、缺读取能力、未知字段/线型、Base-engine、部分支持批次全部明确拒绝；写入 dispatch 数为零 |
| F10 | 缺失与边界 | 缺格/缺字段/重复格、错误 target、畸形颜色、超限、截断、跨 revision 页不能返回完整成功证据；默认/显式/无填充区分正确 |
| F11 | 状态与兼容性 | 写后读取失败保留 committed；partial/unknown 保留 effects；verify=False 为 skipped；旧 format/row height/column width 入口及单位回归通过 |
| F13 | 全格式 corpus | 每个格式类别、全部已声明 Excel 版本/locale 内置格式、合法自定义语法组合均经统一接口写入、逐格读回、重开校验；检查源值/类型不变，含日期系统、货币/会计、多段/条件/颜色/转义；MaybeSheet 不支持项必须列为交付缺口 |
| F14 | 格式语义与完整性 | 精确代码、内置 ID/locale/date_system 参与期望验证与 hash；服务端忽略代码、退化为 General、截断/丢段均失败；目标应用对代表格式的实际显示效果有独立证据，只有 code echo 不通过 |
| F15 | text layout 模式 | no_wrap/wrap/shrink_to_fit 与广告的 overflow/clip 逐项写读重开；覆盖模式往返切换、原始 false、长文本/中文/显式换行、邻格空白/占用、固定行高/合并；不改变值/字体大小/邻格，未支持模式零写入报错 |
| F12 | 端到端与发布 | 统一 Table API、兼容 workbook API、CLI、Excel 真实文件测试、MaybeSheet 录制协议测试及真实服务 F1–F7 通过；readiness 记录 OTC/mbs/service 版本、命令、expectation/physical hashes 和 reopen 证据 |

财务 fixture 使用预置数值单元格或已受支持的公式，避免用字符串假扮财务数值绕过现有 typed-value 限制。此限制针对 MaybeSheet；Excel fixture 必须使用真实数值。样式验收不证明数值写入或财务计算能力。

录制测试证明适配，真实服务 reopen 测试证明持久化；二者均需通过。缺凭据时保留 live gate 未通过状态，不能以 mock 或 skipped 判定验收完成。若最低 horizontal、border、style read、config read/view 集合任一缺失，核心交付仍未完成；正确返回 capability error 是必要行为，不是豁免该必需能力。

额外 Table 边界验收：两个 provider 均从真实 Table 绑定进入；验证非首张 worksheet、数据读取 header 偏移、陈旧绑定和错误 mode 不会选错物理范围；验证 layout.close 不保存、layout.write 不提交数据行事务、旧 workbook 与新 Table 入口产生相同的物理观察。Excel 单独验证原子发布及未修改公式/图表等对象的既有保存性门槛。

## 11. 完成标准

Excel 和 MaybeSheet 均通过统一 Table 入口实现本规范能力、F1–F15 和现有受影响回归；返回证据可离线重算 hash；重新打开验证由全新读取完成；能力广告与真实支持一一对应。完整 Excel 格式代码和第 5.2 节规定的必需文本布局模式均为交付门槛；只有该节明确标为按 provider 能力声明的模式、vertical 及额外线型/视图字段允许限制交付。最终 readiness 必须区分本次财务版式验收与仍独立存在的 typed-value、完整目录及 FinClaw 集成门槛。
