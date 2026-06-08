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

### 2. 用户配置文件

如果没有通过 CLI 或 Web 指定模板，则读取用户配置目录下的：

```text
~/.ai-gen-reimbursement-docs/system_config.yaml
```

其中的 `out_templates` 配置段示例：

```yaml
out_templates:
  fpa_out_template: data/out_templates/FPA工作量评估-输出模板.xlsx
  cosmic_out_template: data/out_templates/项目功能点拆分表-输出模板.xlsx
  list_out_template: data/out_templates/项目需求清单-输出模板.xlsx
  spec_out_template: data/out_templates/项目需求说明书-输出模板.docx
```

相对路径会按项目根目录解析。

### 3. 项目内置模板

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

### COSMIC 功能点拆分表

入口：`_generate_cosmic(...)`

使用方式：

1. 从 `templates_dict["cosmic"]` 取得 COSMIC 模板路径。
2. 先生成并填充 COSMIC Markdown。
3. 调用 `generate_cosmic_xlsx_from_md(filled_md_path, cosmic_src, cosmic_xlsx, ...)` 写入最终 Excel。

COSMIC 写入过程会基于模板保留既有结构，并更新功能点拆分数据、CFP 汇总和环境图相关 sheet。

### 项目需求清单

入口：`_generate_list(...)`

使用方式：

1. 从 `templates_dict["list"]` 取得需求清单模板路径。
2. 调用 `generate_list_xlsx_from_md(meta_md, tree_md, require_src, require_xlsx, ...)`。
3. 将项目元数据、模块树、FPA 核减工作量、CFP 总和写入最终 `项目需求清单.xlsx`。

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

如果模板的表头行、样式源行、关键列位置变化，但代码假设没有同步变化，就可能导致格式错位或写入失败。后续 `template_manifest` 可以把这些格式规则显式声明出来，先用于说明和校验，再逐步驱动写入器按配置复制样式、保留公式和定位写入区域。

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
