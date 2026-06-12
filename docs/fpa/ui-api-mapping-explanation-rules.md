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

本节是实施约束，不是方向性建议。实现时按下面切片执行，除非已有代码结构发生变化。

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

最小字段定义：

```python
@dataclass(frozen=True)
class FpaExplanationPattern:
    """计算依据说明场景模板。"""

    pattern_id: str
    fpa_type: str
    keywords: tuple[str, ...]
    required_points: tuple[str, ...]

    def matches(self, text: str, fpa_type: str) -> bool:
        return self.fpa_type == fpa_type.upper() and any(keyword in text for keyword in self.keywords)
```

把 `FpaRuleSetConfig` 增加字段：

```python
explanation_patterns: tuple[FpaExplanationPattern, ...] = field(default_factory=tuple)
explanation_patterns_merge: str = "append"
```

字段命名说明：

- 配置中使用 `id`，解析后进入 `pattern_id`，避免覆盖 Python 内置名。
- 配置中使用 `type`，解析后进入 `fpa_type`，保持与现有 `KeywordTypeRule` / `TypeMappingRule` 风格一致。
- `keywords` 和 `required_points` 必须去空、去首尾空白；空项忽略。
- `fpa_type` 必须是 `EI / ILF / EO / EQ / EIF` 之一；非法类型忽略并写入 config warning，或直接沿用现有 rule_set 校验风格抛错。建议第一版抛错，避免静默配置失效。

### 解析逻辑

`resolve_fpa_rule_set_config()` 解析 `rule_sets.*.explanation_patterns`，但只有 `UiApiMappingProfile` 使用这些规则。

这样可以做到：

- 配置格式统一。
- 行为影响收敛在 `ui_api_mapping`。
- 其他 profile 即使配置中存在该字段，也不会被改变。

需要修改的具体位置：

| 文件 | 位置 | 修改内容 |
|---|---|---|
| `ai_gen_reimbursement_docs/fpa_profiles.py` | dataclass 区域，`InternalDataGroupRule` 或 `FpaCoverageRules` 附近 | 新增 `FpaExplanationPattern` |
| `ai_gen_reimbursement_docs/fpa_profiles.py` | `FpaRuleSetConfig` | 新增 `explanation_patterns` / `explanation_patterns_merge` |
| `ai_gen_reimbursement_docs/fpa_profiles.py` | `_rule_set_from_dict()` | 解析 `explanation_patterns` |
| `ai_gen_reimbursement_docs/fpa_profiles.py` | `_merge_rule_sets()` | 合并 `explanation_patterns` |
| `ai_gen_reimbursement_docs/fpa_profiles.py` | `UiApiMappingProfile` | 新增匹配和格式化方法，并在 fallback 生成时调用 |
| `config/fpa_config.yaml.example` | `profiles.ui_api_mapping` | 改为引用 `ui_api_mapping_workload_eval_ce` |
| `config/fpa_config.yaml.example` | `calculation_explanation_rules` | 新增 `ui_api_mapping_workload_eval_ce` |
| `config/fpa_config.yaml.example` | `rule_sets.ui_api_mapping_rs` | 新增 `explanation_patterns` |

解析函数建议：

```python
def _explanation_pattern_from_dict(item: dict[str, object]) -> FpaExplanationPattern | None:
    ...

def _explanation_patterns_from_dict(data: dict[str, object]) -> tuple[str, tuple[FpaExplanationPattern, ...]]:
    merge, raw_items = _rule_section_from_dict(data, "explanation_patterns")
    ...
    return merge, tuple(patterns)
```

这里复用现有 `_rule_section_from_dict()`，让配置结构与 `keyword_rules`、`type_mapping_rules` 一致：

```yaml
explanation_patterns:
  merge: append
  items:
    - id: query_service
      type: ILF
      keywords: ["查询服务", "数据查询"]
      required_points: ["查询条件", "返回字段"]
```

合并规则：

- `merge: append`：父 rule_set 的 patterns 在前，子 rule_set 的 patterns 在后。
- `merge: replace`：只使用子 rule_set 的 patterns。
- 第一版不做同 `id` 去重，保持与现有 `_merge_rule_section()` 行为一致。

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

需要修改的具体位置：

```text
UiApiMappingProfile.fallback_rows_for_l3()
```

当前代码在默认行和显式后端行中都直接调用：

```python
explanation_template.format(name=point_name, description=desc or raw_name)
```

实施后改为：

```python
"计算依据说明": self._mapping_explanation(
    name=point_name,
    fpa_type=fpa_type,
    process_name=raw_name,
    description=desc,
    fallback_template=explanation_template,
)
```

显式后端行使用 `fpa_type="ILF"`。

新增私有方法：

```python
def _mapping_explanation(
    self,
    *,
    name: str,
    fpa_type: str,
    process_name: str,
    description: str,
    fallback_template: str,
) -> str:
    ...
```

配套私有方法：

```python
def _matching_explanation_pattern(self, text: str, fpa_type: str) -> FpaExplanationPattern | None:
    ...

def _format_pattern_explanation(
    self,
    *,
    name: str,
    process_name: str,
    description: str,
    pattern: FpaExplanationPattern,
) -> str:
    ...
```

命中优先级：

1. 只匹配 `pattern.fpa_type == 当前行类型` 的 pattern。
2. 匹配文本为：

   ```text
   {新增/修改功能点} {源功能过程名称} {源功能过程描述}
   ```

3. 按配置顺序返回第一个命中 pattern。
4. 未命中时使用 `fallback_template`。

编号生成规则：

1. 第 1 条优先使用源描述：

   ```text
   1、{description or process_name}
   ```

2. 后续追加 `required_points`。
3. 若 `required_points` 中的文本已经被第 1 条包含，则跳过，避免重复。
4. 说明整体格式固定为：

   ```text
   {name}，具体如下：
   1、{description or process_name}
   2、{required_point_1}
   3、{required_point_2}
   ```

5. 不做复杂 NLP 字段抽取；第一版只负责稳定模板化。AI prompt 负责更细致的字段展开。

示例：

输入：

```python
{
    "name": "驿站列表数据查询服务",
    "desc": "查询条件为驿站名称，根据查询条件返回列表数据包含序号、驿站名称、添加时间、状态。"
}
```

输出：

```text
【业务端】...-驿站列表数据查询服务-接口开发，具体如下：
1、查询条件为驿站名称，根据查询条件返回列表数据包含序号、驿站名称、添加时间、状态。
2、查询条件
3、根据查询条件返回列表数据
4、返回字段
```

### EO 边界

第一版不改变 `ui_api_mapping` 的行规划能力，不新增 `EO` fallback 行。

`export_service` pattern 的用途：

- 给 AI prompt 使用。
- 预留给后续如果 `ui_api_mapping` 增加 `type_suffixes.EO` 或导出类显式行时复用。

因此本轮实施验收不要求 `ui_api_mapping` fallback 自动生成 `EO` 导出行。若要支持导出 fallback，需要单独切片定义：

```text
导出关键词如何从默认 ILF 接口行提升为 EO
是否仍保留默认接口开发 ILF 行
计算依据归类如何选择 EO 判定原则
```

### AI prompt

`ui_api_mapping_up` 继续引用：

```text
${calculation_explanation_rules}
```

由于 `profiles.ui_api_mapping.calculation_explanation_rules` 指向专属规则，AI 只会在 `ui_api_mapping` 下收到样例 Excel 风格要求。

## 实施切片

### 切片 1：配置落地

修改文件：

```text
config/fpa_config.yaml.example
```

修改内容：

1. 将 `profiles.ui_api_mapping.calculation_explanation_rules` 从 `ui_api_mapping_ce` 改为 `ui_api_mapping_workload_eval_ce`。
2. 保留 `ui_api_mapping_ce` 或让其继续作为通用规则存在，不删除，避免影响历史配置示例。
3. 新增 `calculation_explanation_rules.ui_api_mapping_workload_eval_ce`。
4. 在 `rule_sets.ui_api_mapping_rs` 下新增 `explanation_patterns`。

验收：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py::TestFpaConfigUtils::test_default_fpa_prompt_example_contains_calculation_explanation_rules
```

同时增加或更新断言：

```text
load_fpa_calculation_explanation_rules("ui_api_mapping").text 包含
"ui_api_mapping 计算依据说明生成规则"
```

### 切片 2：rule_set 解析

修改文件：

```text
ai_gen_reimbursement_docs/fpa_profiles.py
```

修改内容：

1. 新增 `FpaExplanationPattern`。
2. 扩展 `FpaRuleSetConfig`。
3. 新增 `_explanation_pattern_from_dict()`。
4. 新增 `_explanation_patterns_from_dict()`。
5. 修改 `_rule_set_from_dict()` 读取配置。
6. 修改 `_merge_rule_sets()` 支持继承合并。

验收测试建议放在：

```text
tests/test_fpa_profiles.py
```

新增用例：

```text
test_rule_set_parses_explanation_patterns
test_rule_set_extends_merges_explanation_patterns
test_rule_set_extends_replaces_explanation_patterns
```

核心断言：

```text
resolve_fpa_rule_set_config("ui_api_mapping_rs").explanation_patterns 非空
第一个 pattern.pattern_id == "ui_list_page"
type 被规范化为 "EI"
keywords / required_points 为 tuple 且去空
```

### 切片 3：ui_api_mapping fallback 应用 pattern

修改文件：

```text
ai_gen_reimbursement_docs/fpa_profiles.py
tests/test_fpa_profiles.py
tests/fpa_profiles/test_ui_api_mapping_harness.py
```

修改内容：

1. 在 `UiApiMappingProfile` 中新增 `_mapping_explanation()`。
2. 在默认 UI/API 行生成处替换直接 `explanation_template.format(...)`。
3. 在显式后端行生成处同样替换。
4. 保持 `_configured_mapping_explanation_template()` 的必填校验不变，未命中 pattern 时仍可回退。

新增测试：

```text
test_ui_api_mapping_fallback_uses_numbered_explanation_pattern_for_list_page
test_ui_api_mapping_fallback_uses_numbered_explanation_pattern_for_query_service
test_ui_api_mapping_fallback_uses_numbered_explanation_pattern_for_delete_service
test_ui_api_mapping_fallback_falls_back_to_configured_template_when_no_pattern_matches
```

示例 fixture：

```python
group = {
    "client_type": "业务端",
    "l1": "营销管理",
    "l2": "驿站管理",
    "l3": "驿站列表",
    "processes": [
        {
            "name": "驿站列表数据查询服务",
            "change_status": "新增",
            "desc": "查询条件为驿站名称，根据查询条件返回列表数据包含序号、驿站名称、添加时间、状态。",
        },
        {
            "name": "驿站列表数据删除服务",
            "change_status": "新增",
            "desc": "点击删除按钮传输数据 ID，新增数据删除接口，从数据表中匹配对应数据并删除。",
        },
    ],
}
```

核心断言：

```text
计算依据说明 startswith "{name}，具体如下："
查询服务行包含 "1、查询条件为驿站名称"
查询服务行包含 "返回字段"
删除服务行包含 "传输数据 ID"
删除服务行包含 "后端匹配并删除对应数据"
```

### 切片 4：非目标 profile 不受影响

修改文件：

```text
tests/test_fpa_profiles.py
```

新增或补充测试：

```text
test_strict_fpa_fallback_explanation_not_affected_by_ui_api_mapping_patterns
test_unified_ui_fallback_explanation_not_affected_by_ui_api_mapping_patterns
```

核心断言：

```text
strict_fpa fallback 仍包含 "来源场景：" / "业务数据：" / "业务规则：" / "计算说明："
unified_ui fallback 不包含 "ui_api_mapping 计算依据说明生成规则"
unified_ui fallback 不因 explanation_patterns 自动追加编号清单
```

### 切片 5：文档和回归

修改文件：

```text
docs/fpa/ui-api-mapping-explanation-rules.md
```

实施完成后在本文档增加“实施记录”小节，记录：

```text
提交哈希
实际修改文件
实际测试命令
是否支持 EO fallback
```

推荐回归命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fpa_profiles.py tests/fpa_profiles/test_ui_api_mapping_harness.py tests/test_config_utils.py
```

若只做最小回归：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fpa_profiles.py::test_ui_api_mapping_fallback_generates_default_and_explicit_backend_rows tests/test_fpa_profiles.py::test_ui_api_mapping_fallback_uses_configured_explanation_template
```

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
6. `ui_api_mapping` 未命中 pattern 时仍回退到 `row_planning_rules.process_rows.explanation_template`。
7. `strict_fpa` fallback 行仍保持四段式：

   ```text
   来源场景
   业务数据
   业务规则
   计算说明
   ```

8. `unified_ui` 和 `multi_uis` 仍使用各自现有 `explanation_template`，不自动套用 `ui_api_mapping` 的编号清单模板。
9. `export_service` pattern 只作为 prompt 和后续扩展预留；本轮不要求 fallback 自动生成 `EO` 导出行。

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

## 实施记录

- 实施状态：已实施。
- 本轮提交：见最终回复中的提交哈希。
- 实际修改文件：`ai_gen_reimbursement_docs/fpa_profiles.py`、`ai_gen_reimbursement_docs/config_utils.py`、`config/fpa_config.yaml.example`、`tests/test_fpa_profiles.py`、`tests/test_config_utils.py`、`docs/fpa/ui-api-mapping-explanation-rules.md`。
- 实际测试命令：`.\.venv\Scripts\python.exe -m pytest tests/test_fpa_profiles.py tests/fpa_profiles/test_ui_api_mapping_harness.py tests/test_config_utils.py`。
- EO fallback：本轮不支持自动生成 `EO` fallback 行；`export_service` pattern 仅作为 prompt 和后续扩展预留。
