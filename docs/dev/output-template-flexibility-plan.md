# 输出模板灵活化方案

## 背景

当前输出模板主要作为最终 Excel/Word 的版式和公式容器。pipeline 通过 `_resolve_templates(...)` 解析模板路径，再把模板传给 FPA、COSMIC、需求清单、需求说明书等生成器。

这种机制已经支持内置模板、用户配置模板、CLI/Web 自定义模板，但模板本身仍然比较“被动”：代码知道要写哪个 sheet、哪一行、哪一列，模板文件只负责承载最终结果。

为了让模板发挥更大的作用，可以逐步把模板从“固定格式皮肤”升级为“可配置交付规格”。

## 目标

- 让模板结构对人和代码都可读。
- 生成前能提前校验模板是否符合要求。
- 减少写入器中对 sheet、列、行、占位符的硬编码。
- 支持不同客户、不同交付场景维护不同模板版本。
- 为后续模板包、模板 profile、模板能力声明打基础。

## 方案分层

### 方案 1：增加 `template_manifest`

为每个输出模板增加一个结构说明文件，例如：

```yaml
template_id: fpa_default_v1
kind: fpa
version: 1
file: FPA工作量评估-输出模板.xlsx
sheets:
  result: FPA工作量评估
data:
  start_row: 3
columns:
  function_point_name: 新增/修改功能点
  type: 类型
  classification_basis: 计算依据归类
  explanation: 计算依据说明
features:
  preserve_formulas: true
  judgement_rules_source: config
```

第一阶段的价值：

- 人能快速看懂模板结构。
- 代码可以读取 manifest 做生成前校验。
- 为后续列映射、能力声明、模板包提供基础。

建议不要把 `template_manifest` 只当文档清单，而是设计成“模板契约”。

### 方案 2：模板结构预检

生成任务启动前读取 manifest，并对照真实 Excel/Word 模板检查：

- 必要 sheet 是否存在。
- 必要表头是否存在。
- 必要占位符是否存在。
- 数据起始行是否存在。
- 公式区域是否存在。
- FPA 附录判定原则是否可读。

作用：

- 提前发现模板结构问题。
- 避免生成到一半才失败。
- 避免生成出错位但没有明显报错的文件。
- Web UI 可以直接展示模板校验状态。

### 方案 3：命名锚点替代固定行列

Excel 模板可以使用命名单元格或标记文本：

```text
{{FPA_DATA_START}}
{{PROJECT_NAME}}
{{CFP_TOTAL}}
```

Word 模板可以使用占位符：

```text
{{项目名称}}
{{功能需求章节}}
{{模块树}}
```

代码根据锚点定位写入区域，而不是写死第几行、第几列。

作用：

- 模板可以调整版式。
- 只要保留锚点，代码无需修改。
- 客户定制模板时更容易保持兼容。

风险：

- 需要规范模板制作方式。
- 需要处理锚点缺失、重复锚点、锚点位置不合法。

### 方案 4：模板 profile 化

把模板和生成口径绑定成 profile：

```yaml
output_template_profiles:
  strict_fpa_standard:
    fpa_profile: strict_fpa
    fpa_strategy: ai_first
    templates:
      fpa: data/out_templates/FPA工作量评估-严格口径.xlsx
      spec: data/out_templates/项目需求说明书-标准版.docx
```

作用：

- 用户选择一个 profile，就同时选中模板、FPA 口径、规则集和生成策略。
- 适合多客户、多交付场景。
- Web UI 可以把复杂配置收敛为“交付模板包”选择。

### 方案 5：模板驱动的派生内容

让模板不仅控制“写在哪里”，还能声明“生成哪些内容”：

```yaml
sections:
  spec:
    include:
      - project_summary
      - module_tree
      - functional_requirements
      - fpa_summary
  fpa:
    include_audit_sheet: true
    include_ai_raw_sheet: false
```

作用：

- 同一份输入可以生成不同深度的交付物。
- 可以支持客户交付版、内部审核版、简化版。
- 模板开始参与生成内容组合。

风险：

- 生成流程复杂度明显上升。
- 需要先把现有生成内容抽成可组合模块。
- 不建议第一阶段直接做。

## `template_manifest` 的作用

`template_manifest` 不只是让模板“可读”。它真正的价值是把模板从文件路径升级为可执行的模板契约。

### 1. 说明模板结构

manifest 记录模板有哪些 sheet、哪些关键列、数据从哪一行开始、哪些占位符必须存在。

这对人有价值，也对代码有价值。

### 2. 生成前校验

任务启动前可以读取 manifest 并校验真实模板：

- sheet 不存在，提前报错。
- 表头缺失，提前报错。
- 占位符缺失，提前报错。
- 数据起始行不合法，提前报错。

这比写入过程中才失败更可靠。

### 3. 减少硬编码

现在写入逻辑默认知道固定 sheet、固定行列。manifest 可以把这些信息配置化：

```yaml
sheets:
  result: FPA工作量评估
columns:
  function_point_name: 新增/修改功能点
  type: 类型
  basis: 计算依据归类
  explanation: 计算依据说明
data_start_row: 3
```

代码按 manifest 找位置，而不是写死第几列。

### 4. 支持多模板版本

同一种交付物可以维护多个模板：

- 默认版
- 客户 A 版
- 内部审核版
- 简化交付版

每个模板对应一个 manifest，代码可以知道它的结构和能力。

### 5. 声明模板能力

manifest 可以声明模板支持哪些能力：

```yaml
features:
  judgement_rules_source: template
  preserve_formulas: true
  supports_audit_sheet: false
  supports_complexity_columns: true
```

生成逻辑可以根据这些能力决定启用或禁用某些写入行为。

### 6. 描述单元格格式契约

模板格式也可以进入 manifest。这里的格式包括：

- 字体、字号、颜色。
- 边框、填充色、对齐、自动换行。
- 行高、列宽。
- 合并单元格。
- 数字格式。
- 公式。
- 数据验证。
- 冻结窗格。

第一版不一定要让代码完全按这些配置写格式，但应至少把关键格式契约显式写出来，便于校验和诊断。

示例：

```yaml
format:
  style_source_row: 3
  copy_row_style: true
  preserve_formulas: true
  preserve_column_widths: true
  preserve_row_heights: true
  preserve_merged_cells: true
  preserve_data_validations: true
```

更完整的 FPA 示例：

```yaml
template_id: fpa_default_v1
kind: fpa
file: FPA工作量评估-输出模板.xlsx
sheets:
  result:
    name: FPA工作量评估
    header_row: 2
    data_start_row: 3
    style_source_row: 3
columns:
  function_point_name:
    header: 新增/修改功能点
    required: true
  type:
    header: 类型
    required: true
  classification_basis:
    header: 计算依据归类
    required: true
  explanation:
    header: 计算依据说明
    required: true
format:
  preserve:
    - column_widths
    - row_heights
    - merged_cells
    - formulas
    - data_validations
    - freeze_panes
  copy_row_style:
    from_row: 3
    apply_to_generated_rows: true
  formulas:
    copy_down: true
    source_row: 3
  number_formats:
    workload: "0.00"
```

这类格式契约可以用于：

- 校验模板行是否有必要边框、公式、数字格式。
- 指导写入器从哪一行复制样式。
- 声明哪些模板区域不能删除或破坏。
- 帮助排查“生成结果格式乱了”的原因。

### 7. 和提示词、规则联动

FPA 模板如果声明“判定原则来自模板附录”，生成 prompt 时可以读取模板附录。

如果模板声明“不支持复杂度列”，AI 就不需要返回相关字段，或者相关字段只进入 check 文件。

### 8. Web UI 展示

Web 可以显示：

- 当前模板名称。
- 模板版本。
- 适用交付物。
- 来源：内置、配置、上传。
- 校验状态。
- 支持能力。

用户不再只看到一个文件名。

### 9. 作为模板包基础

后续可以支持模板包：

```text
template_pack/
  manifest.yaml
  FPA工作量评估.xlsx
  项目需求清单.xlsx
  项目需求说明书.docx
```

一个包同时定义模板、FPA 口径、规则集、文件命名规则。

## 当前单元格格式机制

当前单元格格式基本由两部分共同决定。

### 1. 模板文件自带格式

模板文件里原本存在的格式会作为基础格式：

- 字体、颜色、边框。
- 列宽、行高。
- 合并单元格。
- 公式。
- Sheet 顺序。
- 固定说明、附录、脚注。

生成器打开模板后往里面写值，因此这些格式可以保留一部分。

### 2. 代码写死或半写死的格式处理

部分生成器在写入时会主动处理格式：

- 删除模板里的旧数据行。
- 解除合并单元格。
- 重新合并某些列。
- 从某一行复制边框或对齐。
- 写固定单元格。
- 写固定列。
- 保留或复制公式。

因此当前机制不是“模板完全控制格式”，也不是“代码完全控制格式”，而是：

```text
模板提供基础格式
+
代码按固定假设写入和修补格式
```

问题在于：如果模板结构变化，例如表头行、样式源行、关键列位置变化，代码里的固定假设就可能导致格式错位或写入失败。

`template_manifest` 的价值之一，就是把这部分“代码默认知道的格式规则”显式写出来。第一阶段用于说明和校验，第二阶段再让代码真正按 manifest 执行。

## 第一版建议范围

第一版不建议追求“任意模板都能用”。建议先实现：

- 为每类输出模板支持 manifest。
- manifest 能说明模板文件、kind、version、关键 sheet、关键列、数据起始行、样式源行、基础能力。
- 生成前能校验 sheet、表头、占位符、样式源行、关键公式是否存在。
- Web/CLI 能提示当前使用的模板来源和校验结果。
- 写入器暂时可以继续使用旧硬编码，只把 manifest 用于说明和预检。

第二阶段再让写入器真正按 manifest 做列映射、锚点定位、样式复制和公式保留。

## 建议实施顺序

1. 新增 `template_manifest` 数据结构和读取逻辑。
2. 为内置四类输出模板增加 manifest 示例。
3. 增加模板预检模块。
4. 在 pipeline 启动阶段输出模板来源和校验结果。
5. 在 Web UI 展示当前模板、版本、来源、校验状态。
6. FPA 和需求清单优先支持按 manifest 列映射。
7. FPA 和需求清单继续支持按 manifest 复制样式源行、保留公式和关键合并区域。
8. Word 需求说明书再支持占位符锚点。
9. 最后做模板 profile 和模板包。

## 最实际的第一版目标

第一版应做到：

- 用户可以知道当前模板结构和来源。
- 系统可以在生成前告诉用户模板哪里不符合要求。
- 用户可以改样式、标题、公式、部分列名，但不能破坏 manifest 声明的关键结构和格式契约。
- 后续扩展列映射时，不需要重新设计配置模型。

这样模板的作用会从“固定格式皮肤”提升为“可校验、可描述、可扩展的交付规格”，实现风险仍然可控。

## 第一阶段实施状态

当前第一阶段已落地：

- 新增统一的输出模板 manifest 读取和预检逻辑。
- 为内置 FPA、COSMIC、需求清单、需求说明书四类输出模板增加 `.manifest.yaml`。
- pipeline 在生成前按当前模式校验实际会使用的输出模板。
- pipeline 预检 activity payload 会携带 manifest 来源和模板能力摘要；CLI 会打印该摘要，Web 生成进度会展示输出模板信息。
- Excel 预检覆盖 sheet、必要表头、数据起始行、样式源行和关键公式/单元格内容。
- Word 预检覆盖正文、表格、页眉、页脚中的必要占位符。

当前边界：

- manifest 只用于说明和生成前预检，尚未驱动写入器做列映射或锚点写入。
- 用户自定义模板如果没有同名 manifest，会按对应 kind 的默认契约预检。
- `gen-basedata` 不生成最终交付物，因此不执行输出模板预检。

### 已实施代码入口

第一阶段实现集中在：

- `ai_gen_reimbursement_docs/template_manifest.py`
  - `load_template_manifest(...)`：读取模板旁 manifest，缺失时使用默认契约。
  - `validate_output_template(...)`：校验单个模板。
  - `validate_output_templates(...)`：按当前生成模式批量预检。
  - `required_template_kinds_for_mode(...)`：定义不同 mode 需要校验的模板种类。
- `ai_gen_reimbursement_docs/pipeline.py`
  - `_resolve_templates(...)` 解析模板路径后调用预检。
  - 预检通过后通过 pipeline activity 事件输出模板预检结果。

manifest 文件命名规则：

```text
输出模板.xlsx.manifest.yaml
输出模板.docx.manifest.yaml
```

同时兼容当前内置模板采用的简短命名：

```text
输出模板.manifest.yaml
```

### 第一阶段验收标准

第一阶段的验收点是：

- 默认四类内置模板预检全部通过。
- 自定义模板缺少 manifest 时，按 kind 使用默认契约预检。
- Excel 模板缺少必要 sheet、表头、样式源行、数据起始行或关键公式时，生成前失败。
- Word 模板缺少必要占位符时，生成前失败。
- `gen-basedata` 不受输出模板预检影响。

已覆盖的测试：

- `tests/test_template_manifest.py`
- `tests/test_gen_spec_manifest.py`
- `tests/test_pipeline_units.py`
- `tests/test_pipeline.py`

### 第二阶段推进状态

`gen-spec` 已开始使用 Word manifest：

- `replacement_scopes` 控制正文、表格、页眉、页脚的占位符替换范围。
- 页眉和页脚中的普通占位符可被替换。
- `styles` 中的模块表、标题、正文样式会用于生成内容；样式缺失时回退到当前默认样式。
- 生成器支持 `{{功能需求章节}}`、`{{模块清单表}}`、`{{功能过程详情}}` 三个新锚点，并兼容旧 `{{功能需求详情}}`。
- `module_table.columns` 可配置模块清单表列、表头和连续相同值合并规则。
- `module_table.sample_table.marker` 可定位 Word 模板中的模块清单样例表；生成器会复制样例表样式和样式源行，填充真实模块数据，并移除原样例表。
- Web/CLI 会展示 spec Word 的锚点模式、模块清单表列数和样例表能力。
- Word 模板导入后端基础能力已落地：`import_spec_word_template(...)` 可将客户 `.docx` 转为带基础占位符、拆分锚点和 manifest 的模板草稿，并返回识别结果与待确认项。
- Web 配置页已接入 Word 模板导入入口，上传 `.docx` 后会生成模板草稿，并可将 `spec_out_template` 路径应用到 `out_templates` 映射。
- Web 配置页已支持已导入 Word 模板草稿的列表、下载、应用和删除。

默认 Word 模板文件已使用 `{{模块清单表}}` 和 `{{功能过程详情}}` 作为功能需求章节拆分插入点。`{{功能需求详情}}` 仍作为历史自定义模板的兼容锚点保留。

当前仍未落地：

- 导入后模板草稿的在线预览、确认和版本命名。
- 模板 profile 和模板包。
- Excel 写入器按 manifest 做列映射、锚点定位和样式复制。
- 文本框、内容控件、图片文字等复杂 Word 结构识别。
