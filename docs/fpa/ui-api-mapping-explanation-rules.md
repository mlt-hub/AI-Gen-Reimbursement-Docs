# ui_api_mapping 计算依据说明规则方案

## 背景

参考样例文件：

```text
F:\mlt\mlt-docs\AI-Gen-Reimbursement-Docs\05.FPA汇总\2、闽市移需【202501】17658 号-关于构建垂直行业场景化营销的需求（和乐业）-FPA工作量评估.xls
```

该样例中的 `FPA功能点估算` 表使用开发工作量友好的拆分方式：

- 界面开发行通常为 `EI`。
- 接口、查询、删除、导入、内部数据处理服务通常为 `ILF`。
- 导出、报表、文件输出通常为 `EO`。
- `计算依据说明` 使用“功能点名称 + 具体如下 + 编号清单”的格式，清单中说明事件流、页面要素、业务规则、业务数据、表、服务、接口等内容。

这些规则与 `ui_api_mapping` profile 的“每个功能过程默认生成界面开发和接口开发行，显式接口/后端调用单独补充”的口径一致，但不适合直接应用到 `strict_fpa`、`unified_ui` 或 `multi_uis`。

## 适用范围

本方案只应用于：

```yaml
profiles.ui_api_mapping
rule_sets.ui_api_mapping_rs
```

不得影响以下 profile：

```text
strict_fpa
unified_ui
multi_uis
```

## 目标行为

`ui_api_mapping` 继续保持现有行规划口径：

1. 每个功能过程默认生成 1 条 `界面开发` 行，类型为 `EI`。
2. 每个功能过程默认生成 1 条 `接口开发` 行，类型为 `ILF`。
3. 输入中明确出现接口、服务、调用、请求、对接、同步、外部系统、第三方或 API 时，额外生成明确接口/后端调用行，类型为 `ILF`。

新增约束只改变 `计算依据说明` 的组织方式，使其贴近样例 Excel：

```text
{新增/修改功能点}，具体如下：
1、...
2、...
3、...
```

## 配置表达建议

### profile 绑定

`profiles.ui_api_mapping.calculation_explanation_rules` 指向专属规则：

```yaml
profiles:
  ui_api_mapping:
    kind: ui_api_mapping
    strategy: rules_first
    rule_set: ui_api_mapping_rs
    adjustment_value_method: legacy_workload
    core_rules: ui_api_mapping_cr
    system_prompt: ui_api_mapping_sp
    user_prompt: ui_api_mapping_up
    calculation_explanation_rules: ui_api_mapping_workload_eval_ce
```

### prompt 规则

新增 `calculation_explanation_rules.ui_api_mapping_workload_eval_ce`：

```yaml
calculation_explanation_rules:
  ui_api_mapping_workload_eval_ce: |-
    ui_api_mapping 计算依据说明生成规则：
    1. 计算依据说明使用「{新增/修改功能点}，具体如下：」开头。
    2. 后续使用编号清单描述事件流、页面要素、业务规则、业务数据、表、服务、接口。
    3. EI 界面开发行必须说明页面或弹窗入口、搜索项、按钮、列表字段、翻页、校验和调用接口。
    4. ILF 接口/服务行必须说明接口或服务名称、入参或触发动作、数据表新增/更新/删除/查询、返回数据。
    5. EO 导出行必须说明导出触发方式、查询条件、导出字段和输出文件或报表。
    6. 删除服务必须说明点击删除、传输数据 ID、调用删除接口、匹配并删除数据。
    7. 查询服务必须说明查询条件，以及返回列表字段。
    8. 导入服务必须说明导入模板字段、数据校验和入库处理。
    9. 不得编造输入中没有的表、接口、字段、权限规则或外部系统。
```

### 规则集模板

在 `rule_sets.ui_api_mapping_rs` 中保留现有 `row_planning_rules.process_rows`，并增加可机器读取的场景模板：

```yaml
rule_sets:
  ui_api_mapping_rs:
    row_planning_rules:
      process_rows:
        enabled: true
        one_row_per_process: true
        default_name_suffix: "接口开发"
        type_suffixes:
          EI: "界面开发"
          ILF: "接口开发"
        explanation_template: "{name}，具体如下：\n1、{description}"

    explanation_patterns:
      merge: append
      items:
        - id: ui_list_page
          type: EI
          keywords: ["列表", "界面", "页面", "搜索", "查询按钮", "重置按钮"]
          required_points:
            - "新增或修改页面/列表界面"
            - "搜索条件、按钮和列表字段"
            - "列表翻页功能"
            - "调用列表数据展示接口"

        - id: create_or_edit_page
          type: EI
          keywords: ["新增界面", "编辑界面", "弹出", "跳转", "确认按钮", "取消按钮"]
          required_points:
            - "点击新增/编辑按钮进入界面"
            - "表单要素"
            - "必填项或权限校验"
            - "调用新增/编辑接口"

        - id: query_service
          type: ILF
          keywords: ["查询服务", "数据查询", "列表查询"]
          required_points:
            - "查询条件"
            - "根据查询条件返回列表数据"
            - "返回字段"

        - id: delete_service
          type: ILF
          keywords: ["删除服务", "删除接口", "删除"]
          required_points:
            - "点击删除按钮并传输数据 ID"
            - "调用或新增删除接口"
            - "后端匹配并删除对应数据"

        - id: import_service
          type: ILF
          keywords: ["导入", "导入模板"]
          required_points:
            - "新增或使用导入模板"
            - "校验导入数据"
            - "将正确数据存储至数据表"

        - id: export_service
          type: EO
          keywords: ["导出", "报表", "文件", "下载"]
          required_points:
            - "根据搜索或查询条件导出数据"
            - "说明导出字段"
            - "输出文件、报表或下载结果"
```

## 代码实施建议

### 数据结构

在 `ai_gen_reimbursement_docs/fpa_profiles.py` 中增加 `ui_api_mapping` 专属或通用但仅由该 profile 调用的数据结构：

```text
FpaExplanationPattern
FpaExplanationPatternsConfig
```

字段建议：

```text
id
type
keywords
required_points
```

如果后续需要更精细模板，可再扩展：

```text
name_keywords
description_keywords
template
priority
```

### 解析逻辑

`resolve_fpa_rule_set_config()` 解析 `rule_sets.*.explanation_patterns`，但只有 `UiApiMappingProfile` 使用这些规则。

这样可以做到：

- 配置格式统一。
- 行为影响收敛在 `ui_api_mapping`。
- 其他 profile 即使配置中存在该字段，也不会被改变。

### 生成逻辑

`UiApiMappingProfile` 的 fallback 行生成时：

1. 先按当前规则生成 `新增/修改功能点`、`类型`、`计算依据归类`。
2. 根据 `新增/修改功能点 + 源功能过程名称 + 描述 + 类型` 匹配 `explanation_patterns`。
3. 命中 pattern 时，使用：

   ```text
   {name}，具体如下：
   1、{从输入描述提取或概括的业务内容}
   2、{pattern.required_points[0]}
   3、{pattern.required_points[1]}
   ...
   ```

4. 未命中 pattern 时，退回 `row_planning_rules.process_rows.explanation_template`。

### AI prompt

`ui_api_mapping_up` 继续引用：

```text
${calculation_explanation_rules}
```

由于 `profiles.ui_api_mapping.calculation_explanation_rules` 指向专属规则，AI 只会在 `ui_api_mapping` 下收到样例 Excel 风格要求。

## 验收标准

1. `ui_api_mapping` AI prompt 中包含 `ui_api_mapping 计算依据说明生成规则`。
2. `ui_api_mapping` fallback 行的 `计算依据说明` 使用：

   ```text
   {新增/修改功能点}，具体如下：
   1、...
   ```

3. `ui_api_mapping` 列表界面行能说明搜索项、按钮、列表字段、翻页和调用接口。
4. `ui_api_mapping` 查询服务行能说明查询条件和返回字段。
5. `ui_api_mapping` 删除服务行能说明传 ID、删除接口和匹配删除。
6. `ui_api_mapping` 导出服务行能说明查询条件和导出字段。
7. `strict_fpa` fallback 行仍保持四段式：

   ```text
   来源场景
   业务数据
   业务规则
   计算说明
   ```

8. `unified_ui` 和 `multi_uis` 仍使用各自现有 `explanation_template`，不自动套用 `ui_api_mapping` 的编号清单模板。

## 推荐测试

```text
test_ui_api_mapping_prompt_uses_workload_eval_explanation_rules
test_ui_api_mapping_fallback_uses_numbered_explanation_template
test_ui_api_mapping_list_page_explanation_pattern
test_ui_api_mapping_query_service_explanation_pattern
test_ui_api_mapping_delete_service_explanation_pattern
test_ui_api_mapping_export_service_explanation_pattern
test_strict_fpa_fallback_explanation_not_affected_by_ui_api_mapping_rules
test_unified_ui_fallback_explanation_not_affected_by_ui_api_mapping_rules
```

测试应优先使用 fixture 和 mock AI，不调用真实外部模型。

## 风险与边界

- `explanation_patterns` 如果只写进配置但不加解析逻辑，只能作为文档或 prompt 约束，不能稳定影响 fallback 行。
- `ui_api_mapping` 当前主要支持 `EI/ILF` 默认行；若需要在该 profile 中输出 `EO` 导出行，需要确认是否继续通过显式接口/后端调用规则扩展，或引入 `type_suffixes.EO`。
- 样例 Excel 中存在个别类型与计算依据归类不一致的行，例如 `类型=ILF` 但归类写 `EI:1)`；实施时应以配置规则为准，并把冲突作为人工审阅 warning，而不是复制样例错误。
- 本方案不改变标准 FPA 口径，也不把开发工作项拆分规则扩散到 `strict_fpa`。
