# 输出模板逻辑说明

## 概念

本项目中的“输出模板”指最终交付物的 Excel/Word 模板，不是 AI prompt 模板。

输出模板负责提供最终文件的容器结构，例如：

- Excel/Word 版式
- Sheet 名
- 表头
- 合并单元格
- 样式
- Excel 公式
- 附录、脚注、环境图等固定内容

生成流程不会从零创建最终交付物，而是在输出模板基础上写入项目元数据、模块树、AI 或规则生成结果。

## 模板解析入口

核心入口是 `ai_gen_reimbursement_docs/pipeline.py` 中的 `_resolve_templates(file_path, cli_templates)`。

该函数负责解析四类输出模板：

| key | 配置项 | 默认模板 |
| --- | --- | --- |
| `fpa` | `fpa_out_template` | `FPA工作量评估-输出模板.xlsx` |
| `spec` | `spec_out_template` | `项目需求说明书-输出模板.docx` |
| `cosmic` | `cosmic_out_template` | `项目功能点拆分表-输出模板.xlsx` |
| `list` | `list_out_template` | `项目需求清单-输出模板.xlsx` |

返回值是一个字典，例如：

```python
{
    "fpa": ".../FPA工作量评估-输出模板.xlsx",
    "cosmic": ".../项目功能点拆分表-输出模板.xlsx",
    "list": ".../项目需求清单-输出模板.xlsx",
    "spec": ".../项目需求说明书-输出模板.docx",
}
```

## 优先级

模板路径按以下优先级解析。

### 1. CLI 参数或 Web UI 指定

这是最高优先级。

CLI 会从参数读取：

- `--fpa-out-template`
- `--cosmic-out-template`
- `--list-out-template`
- `--spec-out-template`

Web 端上传自定义模板后，会保存到任务目录下的 `custom_templates`，再构造成传给 pipeline 的 `templates` 字典。

### 2. 输出模板 profile

如果没有通过 CLI 或 Web 指定模板，则读取用户配置目录下的：

```text
~/.ai-gen-reimbursement-docs/system_config.yaml
```

如果配置了 `active_output_template_profile`，pipeline 会优先从 `output_template_profiles` 中解析模板：

```yaml
active_output_template_profile: standard_delivery
output_template_profiles:
  standard_delivery:
    template_pack: data/template_packs/standard_delivery
    templates:
      list_out_template: data/out_templates/项目需求清单-输出模板.xlsx
```

`templates` 支持 `fpa/spec/cosmic/list` 和 `fpa_out_template/spec_out_template/cosmic_out_template/list_out_template` 两类 key。`template_pack` 指向的目录应包含 `manifest.yaml` 或 `manifest.yml`，其中通过 `templates` 声明模板文件；模板包内的相对路径按模板包目录解析。

Web 配置页的模板配置区已支持基础 profile 选择：页面会读取 `output_template_profiles`，允许选择或清空 `active_output_template_profile`，并展示所选 profile 的 `template_pack` 与 `templates` key。

profile 可同时声明 Web 运行默认值：

```yaml
output_template_profiles:
  strict_delivery:
    template_pack: data/template_packs/strict_delivery
    fpa_profile: strict_fpa
    fpa_strategy: ai_first
    fpa_rule_set: strict_fpa_rs
    fpa_confirmation_mode: strict
```

Web/API 保存 `active_output_template_profile` 时，会把这些字段同步写入 `system_config.yaml` 的运行默认值。若同一次保存 payload 中显式提供了 `run_defaults`，显式值覆盖 profile 默认值。

### 3. 用户配置文件 `out_templates`

如果没有启用 profile，或 profile 中某类模板未配置可用路径，则继续读取 `out_templates` 配置段：

```yaml
out_templates:
  fpa_out_template: data/out_templates/FPA工作量评估-输出模板.xlsx
  cosmic_out_template: data/out_templates/项目功能点拆分表-输出模板.xlsx
  list_out_template: data/out_templates/项目需求清单-输出模板.xlsx
  spec_out_template: data/out_templates/项目需求说明书-输出模板.docx
```

相对路径会按项目根目录解析。

Web 导入的需求说明书 Word 模板草稿发布为正式版本后，会复制到用户配置目录的 `published_templates/spec/{import_id}` 下，并返回可写入 `spec_out_template` 的正式模板路径。

导入草稿在发布前支持基础在线调整：Web 可通过结构预览选择正文段落移动 `{{模块清单表}}` 和 `{{功能过程详情}}`，也可将指定段落或正文表格单元格中的文本替换为 `{{字段名}}` 占位符，并可选择正文表格作为 `module_table.sample_table.marker` 对应的模块清单样例表。调整会直接修改草稿 `.docx` 和配套 manifest，并重置确认/发布状态，避免旧确认状态继续作用于已变更模板。

导入草稿还支持基础版式渲染预览：Web 可请求草稿的 Word layout model，后端会返回页面尺寸、边距、页眉、正文、页脚、段落、表格、样式名和占位符位置，前端以页面式预览展示草稿版式骨架。该预览不依赖 Office 或 LibreOffice，定位为浏览器可渲染的结构近似，不承诺 Word 像素级分页还原。

导入草稿会检测文本框和内容控件等复杂 Word 结构：导入结果、结构预览和版式预览会展示复杂结构数量、位置和可读文本摘要，提示用户人工确认。内容控件中的可读文本已支持通过在线调整替换为 `{{字段名}}` 占位符；文本框和图片文字仍只做检测提示，不自动替换。

导入草稿还会检测 Word 目录状态：导入器会识别 TOC 字段和目录样式段落，生成 manifest 中的 `toc.present`、`toc.auto_update` 和 `toc.update_required`，并在导入结果、结构预览和版式预览中展示是否需要更新目录。生成需求说明书后，pipeline 会记录 `spec_toc_status` / `spec_toc_note`，Web 进度、Web 交付物清单和 CLI 完成摘要会展示“目录已更新”“需要手动更新目录”或“未检测到目录”。

### 4. 项目内置模板

如果用户配置也没有可用路径，则回退到项目内置模板：

```text
data/out_templates/FPA工作量评估-输出模板.xlsx
data/out_templates/项目功能点拆分表-输出模板.xlsx
data/out_templates/项目需求清单-输出模板.xlsx
data/out_templates/项目需求说明书-输出模板.docx
```

如果某类模板仍然缺失，pipeline 会记录明确错误，提示用户在 `system_config.yaml` 的 `out_templates` 中配置，或通过 CLI 参数指定。

## 生效链路

`_resolve_templates(...)` 解析出模板路径后，pipeline 会把 `templates_dict` 传给各生成步骤。

### FPA 工作量评估

入口：`_generate_fpa(...)`

使用方式：

1. 从 `templates_dict["fpa"]` 取得 FPA 模板路径。
2. 调用 `plan_fpa_md_from_tree(..., template_path=fpa_src)` 规划 FPA Markdown。
3. 调用 `generate_fpa_xlsx_from_md(..., fpa_src, fpa_xlsx)` 写入最终 `FPA工作量评估.xlsx`。

FPA 模板不仅用于最终 Excel 写入，在部分配置下也会用于读取模板附录中的判定原则，影响 AI 返回的“计算依据归类”约束。

FPA 结果写入器当前会读取 `fpa` manifest 的 `sheets.result`：

- `name`：FPA 结果 sheet 名。
- `header_row`：表头行。
- `data_start_row`：数据写入起始行。
- `style_source_row`：生成行复制样式的来源行。
- `columns`：按 manifest header 或模板表头定位关键列。
- `named_cells.data_start`：可用 Excel 命名单元格定位数据起始行，优先级高于 `data_start_row`。
- `named_cells.summary_total`：可用 Excel 命名单元格定位 FPA 工作量汇总公式写入位置，配置后接管默认 FPA 工作量汇总单元格。

公式列会按当前模板表头定位，生成公式和汇总公式会跟随数据起始行变化。当前命名单元格仅覆盖 result sheet 的数据起始和 FPA 工作量汇总位置；其他复杂锚点、图片/文本框和跨 sheet 公式重写仍不是当前 manifest 写入行为。

当 `judgement_rules_source: template` 时，FPA 判定原则会从模板附录读取。读取器当前会使用 `sheets.judgement_rules`：

- `name`：判定原则附录 sheet 名。
- `header_row` / `rule_header`：没有锚点时，可先在指定表头行按表头文本定位规则列。
- `data_start_row`：默认规则读取起始行。
- `data_end_row`：可选读取结束行；未配置时读取到 sheet 最后一行。
- `column` / `rule_column`：规则文本列，支持列号或 Excel 列字母。
- `max_rows`：可选，限制最多读取行数。
- `anchor.cell` 或 `anchor.contains`：定位规则标题所在单元格。
- `anchor.offset_rows` 和 `anchor.column`：从锚点定位第一条规则的位置。

`anchor` 配置优先级高于表头定位；没有锚点时，读取器优先用 `header_row` / `rule_header` 找列，找不到再回退到 `column` / `rule_column`。`system_config.yaml` 中历史 `fpa_appendix_sheet` 配置仍可覆盖 sheet 名。没有 manifest 的自定义模板仍使用旧契约：`附录1-FPA评估方法说明` 的 C 列第 2 行起。其他复杂锚点、图片/文本框和跨 sheet 公式重写仍不是当前 manifest 行为。

### COSMIC 功能点拆分表

入口：`_generate_cosmic(...)`

使用方式：

1. 从 `templates_dict["cosmic"]` 取得 COSMIC 模板路径。
2. 生成空白 COSMIC Markdown 模板。
3. 如果存在 API Key，调用 `generate_cosmic_items` 得到结构化 `CosmicItem`；如果没有 API Key，则以空列表进入校验。
4. 调用 `generate_cosmic_artifacts(...)` 生成 JSON 草稿、Markdown 审阅稿和校验报告。
5. 只有校验状态为 `passed` 时写正式 Excel；`review_required` 仅在 `gen_cosmic.allow_draft_excel_output=true` 时写草稿 Excel；`blocked` 不写正式 Excel。

COSMIC 结果写入器当前会读取 `cosmic` manifest 的 `sheets.result`：

- `name`：COSMIC 结果 sheet 名。
- `data_start_row`：数据写入起始行。
- `style_source_row`：生成行复制样式的来源行。
- `header_row`：表头扫描行。
- `columns`：按 manifest header 或模板表头定位项目、模块层级、用户、触发事件、功能过程、子过程描述、数据移动类型、数据组、数据属性、复用度和 CFP 等输出列。

生成数据写入、模块/过程合并列、warning 标记列、复用度数据校验列和 CFP 公式列会跟随 `columns` 映射。复杂锚点和跨 sheet 公式重写后续再推进。

COSMIC 写入过程会基于模板保留既有结构，并更新功能点拆分数据和环境图相关 sheet。CFP 总和只在正式 Excel 写入成功时更新，避免 `gen-list` 读取草稿或阻断结果。

### 项目需求清单

入口：`_generate_list(...)`

使用方式：

1. 从 `templates_dict["list"]` 取得需求清单模板路径。
2. 调用 `generate_list_xlsx_from_md(meta_md, tree_md, require_src, require_xlsx, ...)`。
3. 将项目元数据、模块树、FPA 核减工作量、CFP 总和写入最终 `项目需求清单.xlsx`。

需求清单生成器会读取模板旁的 `list` manifest。当前实际参与写入的配置包括：

- `sheets.project_info.name`、`sheets.function_list.name`：定位项目信息概览和功能清单 sheet。
- `header_row`：扫描表头所在行。
- `data_start_row`：确定项目概览和功能清单的数据写入起始行。
- `style_source_row`：确定功能清单生成行复制边框样式的来源行。
- `columns.<field>.header`：按表头定位项目名称、子系统、一级/二级/三级模块、类型、送审工作量和送审功能点等列。

如果模板缺少同名 manifest，则使用 `list` 默认契约。默认契约仍与内置模板结构一致。

### 项目需求说明书

入口：`_generate_spec(...)`

使用方式：

1. 从 `templates_dict["spec"]` 取得 Word 模板路径。
2. 生成并可选 AI 填充需求说明章节 Markdown。
3. 调用 `generate_spec_docx_from_md(spec_src, spec_docx, meta_md, tree_md, ...)` 写入最终 `项目需求说明书.docx`。

Word 生成会基于模板替换项目信息、模块章节、功能过程描述等内容。

## 输出模板的作用

输出模板的主要作用是让最终交付物符合客户或组织要求的格式。

具体包括：

- 复用既有 Excel/Word 版式。
- 保留公式、样式、合并单元格和固定说明。
- 让客户定制交付物外观，而不需要修改生成逻辑。
- 为不同项目、不同甲方维护不同模板。
- 在 FPA 场景中，部分模板内容还能作为判定原则来源。

## 单元格格式现状

当前单元格格式由模板和代码共同决定。

模板文件提供基础格式：

- 字体、颜色、边框。
- 列宽、行高。
- 合并单元格。
- 公式。
- Sheet 顺序。
- 固定说明、附录、脚注。

代码在写入时也会按固定假设处理部分格式：

- 删除旧数据行。
- 解除或重新合并单元格。
- 从模板中的某一行复制边框或对齐。
- 写固定单元格和固定列。
- 保留或复制公式。

因此当前机制可以理解为：

```text
模板提供基础格式
+
代码按固定假设写入和修补格式
```

如果模板的表头行、样式源行、关键列位置变化，但代码假设没有同步变化，就可能导致格式错位或写入失败。`template_manifest` 可以把这些格式规则显式声明出来，先用于说明和校验，再逐步驱动写入器按配置复制样式、保留公式和定位写入区域。当前 `gen-list` 已开始使用 manifest 定位 sheet、行和关键列；其他 Excel 写入器仍在逐步推进。

## 输出模板不能解决的问题

输出模板不等于业务规则配置。

以下内容主要不应依赖输出模板解决：

- FPA profile 选择
- FPA 类型判定策略
- AI prompt 内容
- 规则兜底逻辑
- 后处理审计逻辑
- 生成流程编排

这些应优先放在 `fpa_config.yaml`、规则配置、prompt 配置或代码逻辑中维护。

## 修改模板的约束

当前代码对模板结构仍有固定假设，因此模板可以定制，但不能任意改。

相对安全的修改：

- 调整样式、字体、列宽、行高。
- 修改固定说明文案。
- 修改不影响写入位置的公式。
- 增加不被代码依赖的说明 sheet。

高风险修改：

- 删除或重命名代码依赖的 sheet。
- 移动关键列位置。
- 删除关键表头。
- 删除 Word 占位符。
- 改坏 Excel 公式引用。
- 改变模板文件类型。

如果必须调整高风险结构，应同步修改对应写入函数和测试。

## 调试建议

排查输出模板问题时，建议按以下顺序确认：

1. 当前任务是否通过 CLI 或 Web 指定了自定义模板。
2. `~/.ai-gen-reimbursement-docs/system_config.yaml` 中的 `out_templates` 是否存在并指向有效文件。
3. 项目内置 `data/out_templates` 是否存在对应模板。
4. 日志中是否出现“未找到输出模板”或“模板文件不存在”。
5. 生成函数是否能找到期望 sheet、列、占位符。

如果输出文件内容错位，通常不是 AI 问题，而是模板结构与写入函数假设不一致。

## 当前预检机制

pipeline 解析输出模板后，会在生成最终交付物前执行模板预检：

- `gen-fpa` 校验 FPA 输出模板。
- `gen-cosmic` 校验 COSMIC 输出模板。
- `gen-list` 校验项目需求清单输出模板。
- `gen-spec` 校验项目需求说明书输出模板。
- `gen-all` 校验四类输出模板。
- `gen-basedata` 不校验输出模板。

预检优先读取模板旁的 manifest 文件：

```text
模板文件名.manifest.yaml
```

如果自定义模板旁没有 manifest，则按模板 kind 使用默认契约预检。预检失败会在生成正式文件前抛出模板错误，避免生成到一半才发现 sheet、表头或占位符缺失。

`gen-spec` 生成器还会读取 `spec` manifest 中的 `replacement_scopes` 和 `styles`。`gen-list` 生成器会读取 `list` manifest 中的 sheet、行号和列头配置。这些配置已经开始影响实际生成结果，不再只用于预检。

### manifest 查找规则

预检会按以下顺序查找 manifest：

1. `模板文件名去扩展名.manifest.yaml`
2. `模板完整文件名.manifest.yaml`
3. `模板文件名去扩展名.manifest.yml`
4. `模板完整文件名.manifest.yml`

例如：

```text
项目需求说明书-输出模板.manifest.yaml
项目需求说明书-输出模板.docx.manifest.yaml
```

如果都不存在，则使用对应 kind 的默认契约。默认契约只用于预检，不会写回文件。

### Excel 预检内容

Excel 预检当前支持：

- `sheets.<key>.name`：sheet 必须存在。
- `header_row`：表头行必须存在。
- `data_start_row`：数据起始行必须在模板现有范围或下一行内。
- `style_source_row`：样式源行必须存在。
- `columns`：必要表头必须出现在表头行。
- `sheets.judgement_rules.rule_header`：FPA 附录判定原则表头必须出现在声明的 `header_row` 上；对应 sheet `required: false` 时只产生 warning。
- `named_cells`：可校验 manifest 声明的 Excel 命名单元格是否存在、是否指向期望 sheet、是否为单一目标和单个单元格；`required: false` 时只产生 warning。
- `required_cells`：关键单元格必须包含指定文本或公式。

### Word 预检内容

Word 预检当前支持：

- `placeholders`：必要占位符必须存在。
- `replacement_scopes`：限定占位符查找范围。

当前查找范围支持：

- `body`：正文段落。
- `tables`：正文表格单元格。
- `headers`：页眉段落和页眉表格。
- `footers`：页脚段落和页脚表格。

内容控件当前支持在导入草稿预览中把可读文本替换为占位符。文本框仍仅做存在性检测和预览提示，不自动替换其中字段；暂不承诺图片文字中的占位符可被识别。

### 失败处理

预检发现 error 时会抛出 `TemplateError`，错误信息包含模板 kind 和具体缺失项。

warning 只记录日志和 pipeline activity payload，不阻断生成。当前默认契约以必要结构为主，主要产生 error。

### Web/CLI 展示

预检通过后，pipeline 会发出 `summary_type=template_preflight` 的 activity payload。CLI 会打印每类模板的 manifest 来源；Web 生成进度会在“输出模板”区域展示同一份摘要。

payload 中每个模板包含：

- `kind`：模板类型。
- `template_path`：实际使用的模板路径。
- `manifest_path`、`source`、`template_id`：manifest 来源和模板契约版本。
- `warnings`：预检 warning。
- `capabilities`：模板能力摘要。

`gen-spec` 的 `capabilities` 当前包括：

- `anchor_mode`：`split`、`full`、`legacy_full` 或 `optional`。
- `anchors`：完整章节、拆分章节和历史兼容锚点。
- `replacement_scopes`：占位符替换范围。
- `module_table.column_count`：模块清单表列数。
- `module_table.supports_sample_table`：是否启用样例表复制。

### gen-spec manifest 当前生成行为

`gen-spec` 当前使用 manifest 的范围：

- `replacement_scopes`
  - 控制是否替换正文、表格、页眉、页脚中的占位符。
  - 未列入 scope 的区域不会被替换。
- `styles`
  - `module_table`：模块清单表样式。
  - `heading_2`、`heading_3`、`heading_4`、`process_heading`：功能需求章节标题样式。
  - `body`、`body_indent`：功能描述和功能过程描述样式。
- `anchors`
  - `legacy_functional_requirements`：历史完整章节锚点，默认 `{{功能需求详情}}`，用于兼容旧自定义模板。
  - `functional_requirements`：新完整章节锚点，默认 `{{功能需求章节}}`。
  - `module_table`：只插入模块清单表，默认 `{{模块清单表}}`。
  - `module_details`：只插入模块和功能过程详情，默认 `{{功能过程详情}}`。
- `module_table`
  - `style`：模块清单表样式。
  - `columns`：模块清单表列配置，每列支持 `field`、`header`、`merge`。
  - `sample_table.marker`：可选，定位模板中的模块清单样例表；启用后生成器复制该表格和样式源行，再填充模块清单数据。

样式名不存在时，生成器会记录 warning 并使用 fallback 样式，不阻断生成。

模块清单表 `field` 当前支持 `entry`、`module_l1`、`module_l2`、`module_l3`、`client_type`、`description`，也可以直接填写模块树中的中文字段名。

样例表复制适合客户需要控制 Word 表格列宽、边框、底纹、字体等细节的场景。manifest 示例：

```yaml
module_table:
  sample_table:
    marker: "{{模块清单表示例}}"
  columns:
    - field: module_l1
      header: 一级模块
      merge: true
    - field: module_l3
      header: 三级模块
      merge: false
```

模板中包含 marker 的样例表会从最终输出中移除。样例表列数必须与 `module_table.columns` 一致；不一致时生成器记录 warning，并回退为按 `style` 新建模块清单表。

内置项目需求说明书 Word 模板当前采用拆分锚点，`{{模块清单表}}` 和 `{{功能过程详情}}` 为默认 manifest 的必要占位符；`{{功能需求详情}}` 不再是内置模板的必要占位符。

### gen-list manifest 当前生成行为

`gen-list` 当前使用 manifest 的范围：

- `sheets.project_info.name`：项目信息概览 sheet 名。
- `sheets.function_list.name`：功能清单 sheet 名。
- `header_row`：项目概览和功能清单表头扫描行。
- `data_start_row`：项目概览和功能清单数据起始行。
- `style_source_row`：功能清单生成行的边框样式来源行。
- `columns`：按表头定位项目名称、子系统、一级/二级/三级模块、类型、送审工作量和送审功能点。
- `sheets.project_info.named_cells`：项目概览字段可优先写入 Excel 命名单元格，例如项目名称、需求部门、送审工作量和送审功能点；未配置或命名区域不可用时回退到表头行列写入。

当前 `gen-list` 仅把命名单元格用于项目概览单格字段写入；功能清单复杂锚点、图片、文本框和跨 sheet 公式重写仍不是当前 manifest 行为。
