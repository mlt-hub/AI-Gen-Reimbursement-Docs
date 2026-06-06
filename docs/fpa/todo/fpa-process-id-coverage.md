# FPA 功能过程 process_id 覆盖判断方案

## 背景

当前 `ai_first` 策略下，系统会在 AI 输出后执行覆盖检查：

- AI 未覆盖功能过程时，追加 `rules_fallback` 行。
- strict_fpa 要求的数据功能行缺失时，追加 `rules_fallback` 行。

现有覆盖检查主要依赖 `source_processes` 的中文名称匹配。真实业务输入中出现过规则侧为 `搜索卡劵订单`、AI 返回为 `搜索卡券订单` 的情况。两者语义相同，但字符串不完全一致，系统会误判 AI 未覆盖功能过程，从而追加重复的 `rules_fallback` 行。

## 目标行为

覆盖判断应以稳定内部标识为准，不再依赖 AI 对中文功能过程名称的一字不差复述。

目标结构：

```json
{
  "process_id": "m10_p1",
  "process_name": "搜索卡劵订单"
}
```

AI 返回：

```json
{
  "name": "【地市后台】垂直行业营销-订单管理-卡券订单-搜索卡券订单",
  "type": "EQ",
  "source_process_ids": ["m10_p1"],
  "source_processes": ["搜索卡券订单"]
}
```

系统行为：

- 覆盖审核使用 `source_process_ids` 判断功能过程是否已覆盖。
- `source_processes` 继续作为人工审阅展示字段，不作为主判断依据。
- `源功能过程` 优先用 `process_id` 反查出的原始功能过程名称。
- `新增/修改功能点` 保留 AI 生成的完整名称结构，但可用 `process_id` 对应名称校正末尾功能过程名。

## 名称展示规范

对于 AI 行，`新增/修改功能点` 不应无条件替换为源功能过程名称。AI 名称可能包含完整模块路径或 FPA 表达，直接替换会丢失信息。

推荐规则：

1. AI 行必须保留完整功能点结构。
2. 如果 AI 名称末尾对应某个 `source_process_id`，则只把末尾功能过程名替换为该 ID 对应的原始功能过程名。
3. 如果 AI 名称不是可识别的“模块路径 + 功能过程名”结构，则保留 AI 名称。
4. `源功能过程` 使用 `source_process_id` 反查出的原始功能过程名。

示例：

```text
AI name:
【地市后台】垂直行业营销-订单管理-卡券订单-搜索卡券订单

process_id 对应源功能过程:
搜索卡劵订单

新增/修改功能点:
【地市后台】垂直行业营销-订单管理-卡券订单-搜索卡劵订单

源功能过程:
搜索卡劵订单
```

这样既保留 AI 的完整功能点路径，又让关键业务名称与原始功能清单一致。

## 覆盖补齐规则

`ai_first` 下覆盖补齐应调整为：

```text
expected_process_ids = 当前三级模块的全部功能过程 ID
covered_process_ids = AI 行 source_process_ids 中的合法 ID
missing_process_ids = expected_process_ids - covered_process_ids
```

补齐逻辑：

- `missing_process_ids` 非空时，按规则补齐缺失功能过程，生成方式为 `rules_fallback`。
- strict_fpa 下 AI 行不包含 `ILF` / `EIF` 时，仍按 `coverage_rules.require_data_function` 补齐数据功能行。
- 数据功能补齐不是名称匹配问题，应继续保留。
- rules 不覆盖 AI 已给出的合法类型判断，只追加缺失行或记录 warning。

## Prompt 与 AI 输出要求

Prompt 中应给 AI 明确的功能过程候选列表：

```json
[
  {
    "process_id": "m10_p1",
    "process_name": "搜索卡劵订单",
    "description": "..."
  }
]
```

AI 输出 schema 应新增：

```json
{
  "source_process_ids": ["m10_p1"],
  "source_processes": ["搜索卡劵订单"]
}
```

约束：

- `source_process_ids` 必须来自候选列表。
- 一个 FPA 行允许覆盖多个功能过程时，返回多个 ID。
- 数据功能行可记录识别来源功能过程 ID；如果数据组来自模块整体而非单一功能过程，允许为空，并通过规则命中详情说明来源。

## 审核与 check.xlsx

正式 FPA Excel 不新增列。

check.xlsx 建议：

- `FPA结果` 保留现有用户可见列：`新增/修改功能点`、`源功能过程`、`生成方式`、`后处理警告` 等。
- `源功能过程` 展示 `process_id` 反查后的原始功能过程名称。
- 可在审核 Sheet 或调试字段中保留 `source_process_ids`，用于排查覆盖判断。
- `覆盖审核` 仍展示功能过程名称、已覆盖数、未覆盖数；内部统计使用 ID。
- `Warnings` 中区分：
  - AI 未返回合法 `source_process_ids`。
  - AI 返回了未知 `source_process_ids`。
  - AI 缺少数据功能行。
  - AI 真正未覆盖功能过程。

## 已确认决策

1. `process_id` 格式

   使用模块内稳定短 ID，例如 `m10_p1`。ID 只需要在当前运行上下文中唯一，不把客户端类型、一级模块、二级模块、三级模块写入 ID 本身；这些业务路径继续由模块上下文和审核字段承载。

2. AI 未返回 `source_process_ids` 时的处理

   记录 warning，并降级使用 `source_processes` 名称匹配作为兜底；如果仍无法匹配，再触发 `rules_fallback`。

3. AI 返回未知 `source_process_ids` 时的处理

   忽略未知 ID，记录 warning，合法 ID 仍参与覆盖统计。未知 ID 本身进入审核提示，但不阻断该 AI 行中其它合法 ID 的覆盖判断。

4. `新增/修改功能点` 的名称校正规则

   只校正末尾功能过程名，不替换整条 AI 名称。末尾功能过程名与 `process_id` 对应原始名称只有近形字、错别字或标点差异时，以原始功能过程名为准。

5. 数据功能行的 `source_process_ids`

   数据功能行可以记录识别来源功能过程 ID；如果数据组来自模块整体，则允许为空，并通过规则命中详情说明来源。不要求所有 ILF / EIF 行必须绑定至少一个功能过程 ID。

6. check.xlsx 是否展示 `source_process_ids`

   不放入主表可见列，只在审核/调试 Sheet 中保留。`FPA结果` 不新增隐藏列，避免主结果表结构继续膨胀。

7. 历史 AI cache 处理

   系统尚未上线，不保留旧结构兼容；cache key 或 schema 变更后旧缓存自然失效。不需要专门迁移旧缓存；如实施时发现旧缓存仍可能命中，应通过 cache key/schema 变化使其失效。

## 验收标准

- 规则侧 `搜索卡劵订单`、AI 返回 `搜索卡券订单` 且 `source_process_ids` 正确时，不追加重复 `rules_fallback`。
- `新增/修改功能点` 可规范化为 `【地市后台】垂直行业营销-订单管理-卡券订单-搜索卡劵订单`。
- `源功能过程` 展示 `搜索卡劵订单`。
- strict_fpa 下 AI 只返回 EQ、未返回 ILF / EIF 时，仍补齐数据功能行。
- 覆盖审核、Warnings、规则命中详情和 AI原始返回能说明补齐原因。
- 预览与正式 check.xlsx 的覆盖统计一致。

## 建议测试

```text
tests/test_gen_fpa_ai.py
  覆盖 process_id 正确但 source_processes 名称存在近形字差异时，不补 rules_fallback。
  覆盖 AI 未返回 source_process_ids 时的 warning / 兜底行为。
  覆盖未知 source_process_ids 的 warning 行为。
  覆盖 strict_fpa 缺数据功能行仍补 ILF / EIF。

tests/test_fpa_acceptance.py
  覆盖预览与正式 check.xlsx 的覆盖统计一致。
  覆盖 D 列名称末尾按 process_id 对应源功能过程名校正。
```

## 实施记录

状态：已实施。

本次实现要点：

- `_group_rows_by_l3` 为当前运行上下文中的每个功能过程生成 `process_id`，格式为 `m{模块序号}_p{过程序号}`。
- Prompt payload 中的 `processes` 改为显式提供 `process_id`、`process_name`、`description` 和 `type`。
- AI 行规范化时校验 `source_process_ids`，合法 ID 用于反查并展示原始 `源功能过程`；未知 ID 会被忽略并记录 warning。
- AI 未返回合法 `source_process_ids` 但返回 `source_processes` 时，记录 warning 并降级使用名称精确匹配。
- `ai_first` 覆盖补齐和审核覆盖统计优先使用合法 `source_process_ids`，缺失 ID 时保留旧的名称兜底。
- AI 行 `新增/修改功能点` 保留完整路径，仅在单个合法 `source_process_id`、事务功能行且末尾名称与源功能过程高度相似时校正末尾功能过程名。
- strict_fpa 数据功能补齐逻辑继续保留，不受功能过程覆盖 ID 化影响。

验证结果：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gen_fpa_ai.py
.\.venv\Scripts\python.exe -m pytest tests/test_fpa_profiles.py tests/test_gen_fpa_preview.py tests/test_fpa_acceptance.py tests/test_config_utils.py
```
