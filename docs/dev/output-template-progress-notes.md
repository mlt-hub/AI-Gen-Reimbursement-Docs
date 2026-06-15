# 输出模板进度说明

本文记录当前输出模板相关能力的已实现状态，便于后续继续推进 `gen-list`、`gen-spec`、`gen-fpa`、`gen-cosmic` 和模板 profile 配置时快速对齐现状。

## 已实现

- `gen-list` 已使用 `list` manifest 驱动项目需求清单写入：sheet 名、表头行、数据起始行、样式源行、关键列映射和项目概览命名单元格会影响实际输出。
- `gen-spec` 已使用 Word manifest 驱动占位符替换范围、功能需求锚点、模块清单列配置和样式配置。
- `gen-fpa` 已使用 `fpa` manifest 驱动 FPA 结果 sheet 名、表头行、数据起始行、样式源行、关键列定位、result sheet 的数据起始和 FPA 工作量汇总命名单元格；模板附录判定原则读取也已支持 `judgement_rules` sheet、表头定位、列、起始/结束行、最大读取行数和基础锚点配置，预检会校验声明的规则表头。
- `gen-cosmic` 已使用 `cosmic` manifest 驱动 COSMIC 结果 sheet 名、数据起始行、样式源行和结果字段列映射；合并列、warning 标记列、复用度校验列和 CFP 公式列会跟随列映射。
- pipeline 已支持 `active_output_template_profile` / `output_template_profiles` 基础解析，profile 可直接声明 `templates` 或通过 `template_pack` 指向带 `manifest.yaml` 的模板包目录。
- Web 配置页已支持输出模板 profile 基础选择能力：读取 `output_template_profiles`、选择或清空 `active_output_template_profile`，并展示所选 profile 的 `template_pack` 与 `templates` key。
- Web/API 保存 `active_output_template_profile` 时已支持联动 profile 中的 `fpa_profile`、`fpa_rule_set`、`fpa_strategy` 和 `fpa_confirmation_mode`。
- Word 导入模板草稿已支持发布为正式用户模板版本，发布后返回可应用到 `spec_out_template` 的正式模板路径。
- Word 导入模板草稿已支持基础在线调整：可移动 `{{模块清单表}}` / `{{功能过程详情}}` 锚点，并可将指定段落文本替换为 `{{字段名}}` 占位符；调整后会重置确认/发布状态。
- Word 导入模板草稿已支持基础版式渲染预览：后端提供页面尺寸、边距、页眉/正文/页脚、段落/表格、样式名和占位符的浏览器可渲染 layout model；Web 草稿列表可打开页面式预览。

## 未完成

- Office 级 Word 像素还原预览。
- 复杂 Word 结构识别。
- COSMIC/FPA/list 更复杂 Excel 锚点、复杂样式复制、图片/文本框和跨 sheet 公式重写。

## 说明

这份文档只记录当前状态，不承担计划管理职责。新进度继续时，优先更新这里和相关主题文档，避免把活的状态继续堆进 `AGENTS.md`。
