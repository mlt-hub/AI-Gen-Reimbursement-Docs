# gen-spec Word 输出模板优化方案

## 背景

`gen-spec` 负责生成《项目需求说明书.docx》。当前流程中，pipeline 解析到 Word 输出模板路径后，调用 `generate_spec_docx_from_md(...)`：

1. 读取 Word 模板 `.docx`。
2. 读取元数据 MD、模块树 MD、AI 填充后的 spec MD。
3. 替换模板里的固定占位符。
4. 插入功能需求章节内容。
5. 生成模块清单表、模块详情、功能过程描述。
6. 可选自动更新目录；如果不能自动更新，则给文件名前缀提醒用户手动更新目录。

当前 Word 模板已经能承载基础版式，但模板结构、占位符、章节插入点、表格样式和目录行为仍有不少固定假设。

## 当前主要限制

- 模板缺少可机器读取的结构说明。
- 必要占位符缺失时，缺少生成前预检。
- 功能需求章节插入逻辑偏固定，模板难以自由决定内容位置。
- 模块清单表主要由代码创建，表格样式不容易由模板控制。
- 标题、正文、表格样式缺少明确映射。
- 页眉、页脚、表格、复杂封面中的字段替换覆盖范围需要明确。
- Word 目录更新依赖外部能力，失败时只能提醒用户手动更新。

## Word manifest

建议为 `gen-spec` Word 模板增加 manifest。

示例：

```yaml
template_id: spec_default_v1
kind: spec
version: 1
file: 项目需求说明书-输出模板.docx
placeholders:
  project_name: "{{项目名称}}"
  project_summary: "{{项目说明}}"
  functional_requirements: "{{功能需求章节}}"
  module_table: "{{模块清单表}}"
  module_details: "{{功能过程详情}}"
styles:
  heading_1: "Heading 1"
  heading_2: "Heading 2"
  heading_3: "Heading 3"
  body: "Normal"
  module_table: "模块清单表"
toc:
  present: true
  auto_update: optional
replacement_scopes:
  - body
  - tables
  - headers
  - footers
```

作用：

- 让模板需要哪些占位符可读、可校验。
- 让代码知道使用哪些 Word 样式生成标题、正文和表格。
- 让 Web UI 可以展示模板版本、来源、校验状态和支持能力。
- 为上传 Word 自动转换成模板打基础。

## 占位符预检

生成前应检查模板是否包含必要占位符。

第一版建议检查：

- `{{项目名称}}`
- `{{功能需求章节}}`
- `{{模块清单表}}`
- `{{功能过程详情}}`

如果缺失，应在任务开始前给出清晰错误或 warning，而不是等生成完成后才发现章节没有插入。

需要同时检查：

- 正文段落。
- 表格单元格。
- 页眉。
- 页脚。

后续可扩展到文本框、内容控件等复杂结构。

## 章节锚点

当前功能需求章节生成逻辑偏固定。建议改为模板锚点驱动：

```text
{{功能需求章节}}
{{模块清单表}}
{{功能过程详情}}
{{FPA摘要}}
```

模板作者可以决定这些内容放在第几章、哪个段落之后。

第一版可先支持：

- `{{功能需求章节}}`：一次性插入完整功能需求章节。
- `{{模块清单表}}`：插入模块清单表。
- `{{功能过程详情}}`：插入各模块和功能过程说明。

后续再支持更细粒度章节组合。

## Word 样式继承

建议通过 manifest 声明样式名：

```yaml
styles:
  heading_1: "标题 1"
  heading_2: "标题 2"
  heading_3: "标题 3"
  body: "正文"
  module_table: "模块清单表"
```

生成器插入内容时只应用样式名，不直接硬编码字体、字号、颜色。

作用：

- 客户可以在 Word 模板里改样式集。
- 生成内容自动继承客户模板的视觉风格。
- 不同客户模板可以使用不同样式名。

## 功能需求章节样式复用

功能需求章节不应只插入文本内容，还应复用 Word 模板中的章节样式。

### 方案 A：按 Word 样式名复用

第一版建议优先使用样式名复用。manifest 声明功能需求章节中不同层级应使用的 Word 样式：

```yaml
requirement_section:
  anchor: "{{功能需求章节}}"
  styles:
    l1_heading: "标题 1"
    l2_heading: "标题 2"
    l3_heading: "标题 3"
    process_heading: "标题 4"
    body: "正文"
    table: "功能需求表"
```

生成器插入功能需求章节时：

- 一级模块使用 `requirement_section.styles.l1_heading`。
- 二级模块使用 `requirement_section.styles.l2_heading`。
- 三级模块使用 `requirement_section.styles.l3_heading`。
- 功能过程标题使用 `requirement_section.styles.process_heading`。
- 功能过程描述使用 `requirement_section.styles.body`。
- 章节内表格使用 `requirement_section.styles.table`。

这种方式实现稳定，适合第一阶段落地。模板作者只需要在 Word 中调整这些样式，生成结果就能继承模板视觉风格。

### 方案 B：从模板样例块提取样式

第二阶段可以支持从模板中的样例块提取样式。

模板示例：

```text
{{功能需求章节样式样例开始}}

4.1 一级模块样例
4.1.1 二级模块样例
4.1.1.1 三级模块样例
功能过程样例
正文样例：这里是功能描述。
表格样例...

{{功能需求章节样式样例结束}}

{{功能需求章节}}
```

生成器读取样例块中的段落、run 和表格样式，再用于真实章节：

- 段落样式。
- run 字体样式。
- 编号样式。
- 缩进。
- 段前段后。
- 表格样式。
- 表格列宽。

这种方式更灵活，适合客户 Word 模板样式名不规范或样式体系不稳定的情况。

风险是实现复杂度更高，需要处理样例块缺失、样例层级不完整、编号样式无法稳定复用等问题。因此不建议第一阶段直接做。

### 上传 Word 导入时的样式提取

如果用户上传已有 Word 文档并转换为模板，导入器可以扫描“功能需求”“功能说明”“功能模块”“系统功能”等章节附近的标题、正文和表格样式，并自动写入 manifest：

```yaml
requirement_section:
  detected_from: "功能需求"
  anchor: "{{功能需求章节}}"
  styles:
    l1_heading: "标题 1"
    l2_heading: "标题 2"
    l3_heading: "标题 3"
    body: "正文"
```

如果导入器无法稳定判断样式，应在检查结果中提示用户确认。

## 模块清单表模板化

当前模块清单表主要由代码创建，列和样式较固定。可改为模板中预留锚点或样例表。

方案 A：锚点插入

```text
{{模块清单表}}
```

manifest 声明表格列和样式：

```yaml
module_table:
  anchor: "{{模块清单表}}"
  style: "模块清单表"
  columns:
    - 入口
    - 一级功能模块
    - 二级功能模块
    - 三级功能模块
```

方案 B：样例表复制

模板中保留一个两行样例表：

- 第一行：表头。
- 第二行：样式源行。

代码复制样式源行填充模块数据。

方案 B 对客户定制格式更友好，当前已支持通过 marker 定位样例表：

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

生成器会复制包含 marker 的样例表，保留表格样式、列宽、边框和样式源行的单元格文本样式，再用 `columns` 配置写入表头和模块数据。原样例表会从输出文档中移除。样例表列数必须与 `module_table.columns` 一致；不一致时会回退为新建表格并记录 warning。

## 章节内容可组合

不同客户可能需要不同深度的需求说明书。

manifest 可声明章节组合：

```yaml
sections:
  include:
    - project_overview
    - construction_goal
    - module_table
    - functional_requirements
    - fpa_summary
  exclude:
    - cosmic_detail
```

可支持：

- 标准版。
- 简版。
- 内部审核版。
- 客户交付版。

该能力会提高生成流程复杂度，不建议第一阶段直接做。应先完成占位符、样式和预检。

## 目录处理优化

当前目录更新依赖配置和 Word COM，失败时会给文件名前缀提醒用户手动更新。

可以优化为：

- manifest 声明模板是否包含目录。
- 生成前检查目录字段是否存在。
- 生成后记录目录更新状态。
- Web/CLI 明确展示“目录已更新”或“需要手动更新目录”。
- 后续评估 LibreOffice 或其他 docx 字段更新方案。

manifest 示例：

```yaml
toc:
  present: true
  auto_update: optional
  fallback_notice: true
```

## 替换范围扩展

客户 Word 模板里的字段可能出现在：

- 正文段落。
- 表格单元格。
- 页眉。
- 页脚。
- 文本框。
- 内容控件。
- 封面复杂布局。

第一版至少应支持：

- 正文。
- 表格。
- 页眉。
- 页脚。

文本框、内容控件、图片文字不建议第一阶段承诺完全支持。图片里的文字无法可靠替换。

## 用户上传 Word 转占位符模板

用户上传的 Word 往往是客户已有成品或半成品，不一定包含本系统可识别的占位符。

建议做成“Word 模板导入向导”，而不是承诺任意 Word 自动完美转换。

### 推荐流程

```text
用户上传 Word
  -> 解析文档结构
  -> 识别封面/项目信息/目录/章节/表格/页眉页脚
  -> 自动插入占位符
  -> 生成模板草稿 docx
  -> 生成 template_manifest.yaml
  -> 用户预览/确认
  -> 保存为可用输出模板
```

### 可自动转换的内容

#### 1. 封面和基础字段

识别常见字段：

- 项目名称。
- 工单编号。
- 子系统名称。
- 需求部门。
- 需求负责人。
- 编写日期。

转换为占位符：

```text
{{项目名称}}
{{工单编号}}
{{子系统（模块）}}
{{需求部门}}
```

#### 2. 章节锚点

如果 Word 中存在“功能需求”“功能说明”“功能模块”“系统功能”等章节，可以在该章节下插入：

```text
{{功能需求章节}}
```

或更细：

```text
{{模块清单表}}
{{功能过程详情}}
```

#### 3. 目录

保留原目录结构，并在 manifest 中记录：

```yaml
toc:
  present: true
  update_required: true
```

#### 4. 页眉页脚

页眉页脚里的项目名、文档名、版本号也可以替换成占位符。

#### 5. 样式提取

读取 Word 中的样式名：

- 标题 1。
- 标题 2。
- 标题 3。
- 正文。
- 表格样式。

写入 manifest，让生成器后续按原 Word 风格生成内容。

### 不建议完全自动的内容

以下内容应让用户确认：

- 哪一章应该放“功能需求章节”。
- 哪个表格是模块清单表。
- 某些字段是固定文案还是动态字段。
- 客户模板里多个“项目名称”是否都要替换。
- 文本框、复杂封面、图片里的文字是否可处理。

### 导入输出

导入后生成：

```text
custom_templates/
  项目需求说明书-输出模板.docx
  项目需求说明书-输出模板.manifest.yaml
```

manifest 示例：

```yaml
template_id: imported_spec_20260608
kind: spec
file: 项目需求说明书-输出模板.docx
placeholders:
  project_name: "{{项目名称}}"
  work_order_no: "{{工单编号}}"
  subsystem: "{{子系统（模块）}}"
  functional_requirements: "{{功能需求章节}}"
styles:
  heading_1: "标题 1"
  heading_2: "标题 2"
  heading_3: "标题 3"
  body: "正文"
toc:
  present: true
  update_required: true
replacement_scopes:
  - body
  - tables
  - headers
  - footers
```

### 第一版导入目标

第一版建议支持：

- 上传 `.docx`。
- 扫描正文、表格、页眉、页脚。
- 自动替换常见元数据字段。
- 自动寻找“功能需求/功能说明/功能模块/系统功能”章节。
- 在识别到的章节下插入 `{{功能需求章节}}`。
- 生成 manifest。
- 给用户检查结果：识别了哪些字段、插入了哪些占位符、哪些需要人工确认。

## 风险

- Word 文档结构复杂，文本框、内容控件、嵌套表格、图片文字都可能影响识别。
- 自动识别章节可能误判，必须提供预览和确认。
- 生成器需要同步支持 manifest 和占位符，否则导入出来的模板不能完全发挥作用。
- 目录更新在不同环境下能力不同，需要明确反馈状态。

## 推荐实施顺序

1. 为 `gen-spec` 增加 Word manifest 读取和校验。
2. 扩展占位符替换范围到正文、表格、页眉、页脚。
3. 支持 `{{功能需求章节}}` 锚点插入。
4. 支持 manifest 声明 Word 样式名。
5. 支持模块清单表锚点和表格样式。
6. 增加 Word 模板导入向导的后端解析能力。
7. Web UI 增加导入检查结果和用户确认。
8. 再推进章节组合、模板 profile、模板包。

## 第一阶段最小目标

第一阶段应做到：

- Word 模板结构可描述。
- Word 模板能生成前预检。
- 占位符替换覆盖正文、表格、页眉、页脚。
- 用户上传 Word 可以生成带基础占位符的模板草稿。
- 生成结果明确告诉用户哪些内容已自动识别，哪些需要人工确认。

这样能显著提升 `gen-spec` Word 模板的可定制性，同时避免陷入“任意 Word 自动转换”的高风险目标。

## 当前实施状态

`gen-spec` 已接入 Word manifest 预检，并开始使用 manifest 驱动部分生成行为：

- 默认 Word 模板配套 `项目需求说明书-输出模板.manifest.yaml`。
- 预检会检查正文、表格、页眉、页脚中的必要占位符。
- 当前默认模板已使用 `{{模块清单表}}` 和 `{{功能过程详情}}` 拆分锚点，生成器仍兼容旧锚点。
- `replacement_scopes` 会控制正文、表格、页眉、页脚中的占位符替换范围。
- 页眉、页脚中的普通 `{{占位符}}` 已支持替换。
- 模块清单表、章节标题、正文段落开始使用 manifest 中的 `styles` 配置；样式不存在时记录 warning 并回退。
- `{{功能需求章节}}` 可插入完整功能需求章节。
- `{{模块清单表}}` 可只插入模块清单表。
- `{{功能过程详情}}` 可只插入模块和功能过程详情。
- `module_table.sample_table.marker` 可声明模块清单样例表，生成器会复制样例表样式并移除原样例表。
- 已新增 Word 模板导入后端基础能力：`import_spec_word_template(...)` 可读取客户 `.docx`，扫描正文、表格、页眉、页脚，替换常见元数据字段为占位符，在功能需求章节附近插入 `{{模块清单表}}` 和 `{{功能过程详情}}`，并生成配套 manifest 与待确认项。
- Web 已接入 Word 模板导入入口：配置页“模板”分区可以上传 `.docx`，调用 `/api/templates/spec/import` 生成模板草稿，并可将返回的 `spec_out_template` 路径应用到 `out_templates` 映射，仍需用户手动保存配置。
- Web 已支持已导入模板草稿列表管理：可查看预检状态、下载模板和 manifest、应用到模板映射、删除草稿。
- Web 已支持已导入模板草稿的结构预览：可查看正文/表格/页眉/页脚摘要、占位符位置、功能需求锚点位置和功能需求章节候选。
- Web 已支持已导入模板草稿的确认信息管理：可设置模板名称、版本备注和“已确认”状态，列表和预览接口会返回确认状态。

尚未实施：

- 文本框、内容控件、图片文字等复杂 Word 结构识别。
- 导入后的版式渲染预览、锚点/字段在线调整和正式版本发布。

### 当前默认 Word manifest

内置 Word 模板的 manifest 文件为：

```text
data/out_templates/项目需求说明书-输出模板.manifest.yaml
```

当前必要占位符：

```yaml
placeholders:
  document_title:
    token: "{{文档标题}}"
    required: true
  project_summary:
    token: "{{总体描述}}"
    required: true
  functional_requirements:
    token: "{{功能需求详情}}"
    required: false
  functional_requirements_section:
    token: "{{功能需求章节}}"
    required: false
  module_table:
    token: "{{模块清单表}}"
    required: true
  module_details:
    token: "{{功能过程详情}}"
    required: true
  subsystem:
    token: "{{调整因子中的子系统名称}}"
    required: true
```

当前支持的章节锚点配置：

```yaml
anchors:
  legacy_functional_requirements: "{{功能需求详情}}"
  functional_requirements: "{{功能需求章节}}"
  module_table: "{{模块清单表}}"
  module_details: "{{功能过程详情}}"
```

当前支持的样式配置：

```yaml
styles:
  heading_1: Heading 1
  heading_2: Heading 2
  heading_3: Heading 3
  heading_4: Heading 4
  process_heading: Normal
  body: Normal
  body_indent: Body Text Indent
  module_table: Table Grid
```

当前支持的模块清单表配置：

```yaml
module_table:
  style: Table Grid
  sample_table:
    marker: "{{模块清单表示例}}"
  columns:
    - field: entry
      header: 入口
      merge: true
    - field: module_l1
      header: 一级功能模块
      merge: true
    - field: module_l2
      header: 二级功能模块
      merge: true
    - field: module_l3
      header: 三级功能模块
      merge: false
```

`field` 当前支持 `entry`、`module_l1`、`module_l2`、`module_l3`、`client_type`、`description`，也可以直接填写模块树中的中文字段名。`merge` 控制该列是否合并连续相同值。

`sample_table` 是可选配置。只有 manifest 明确提供 marker 且模板中存在包含该 marker 的表格时，才会启用样例表复制；默认内置 Word 模板目前仍使用 `style` 新建模块清单表。

这里保留 `{{功能需求详情}}` 是为了兼容历史自定义 Word 模板。新自定义模板可以直接使用 `{{功能需求章节}}`，或用 `{{模块清单表}}` 和 `{{功能过程详情}}` 分别控制模块清单表与功能过程详情的位置；内置默认模板已采用拆分锚点。

### 当前 Word 导入后端能力

新增模块：

```text
ai_gen_reimbursement_docs/spec_template_importer.py
```

当前入口：

```python
import_spec_word_template(source_docx, output_dir)
```

Web 入口：

```text
POST /api/templates/spec/import
GET /api/templates/spec/imported
GET /api/templates/spec/imported/{import_id}/{filename}
GET /api/templates/spec/imported/{import_id}/preview
PUT /api/templates/spec/imported/{import_id}/metadata
DELETE /api/templates/spec/imported/{import_id}
```

导入输出：

```text
custom_templates/
  项目需求说明书-输出模板.docx
  项目需求说明书-输出模板.manifest.yaml
```

当前自动处理范围：

- 正文段落。
- 正文表格单元格。
- 页眉段落和页眉表格。
- 页脚段落和页脚表格。

当前可识别字段包括：

- `文档标题`
- `项目名称`
- `工单编号`
- `调整因子中的子系统名称`
- `子系统（模块）`
- `需求部门`
- `需求负责人`
- `文档日期`
- `编写日期`
- `总体描述`

导入器会识别 `功能需求`、`功能说明`、`功能模块`、`系统功能` 等章节标题，并在该章节后插入拆分锚点。如果未识别到功能需求章节，会在文档末尾插入锚点，并在 `pending_confirmations` 中提示人工确认位置。

当前不承诺识别：

- 文本框。
- 内容控件。
- 嵌套复杂结构中的特殊字段。
- 图片中的文字。

### 下一阶段建议

下一阶段建议补齐导入后的确认和管理流程：

1. 提供模板草稿版式渲染预览。
2. 让用户在线调整功能需求锚点位置和识别字段。
3. 支持确认后发布为正式模板版本。
4. 将正式模板版本保存到任务或用户自定义模板目录。

这样可以把已生成的模板草稿纳入完整管理流程，同时继续避免承诺任意 Word 自动完美转换。
