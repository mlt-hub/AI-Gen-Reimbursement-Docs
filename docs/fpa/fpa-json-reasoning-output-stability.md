# FPA JSON 输出与推理调试稳定性方案

## 实施记录

2026-06-09 已落地 P0-P2：

- 重试调用或解析失败时，保留上一版可解析 AI rows，并写入 warning。
- FPA 主响应在代码侧追加 JSON-only 输出约束，禁止外显长 reasoning，允许短 `debug_summary`。
- `strict_fpa` 的 `fallback` / `rules_fallback` 行会按模板判定原则补齐 `计算依据归类`。

## 背景

在测试目录 `F:\mlt\mlt-tests\AI-Gen-Reimbursement-Docs\5` 的“关于构建垂直行业场景化营销的需求”生成结果中，正式 FPA 工作簿出现 `F29:F32` 的 `计算依据归类` 为空。

排查对应文件：

```text
F:\mlt\mlt-tests\AI-Gen-Reimbursement-Docs\5\关于构建垂直行业场景化营销的需求\闽市移需【202501】17658 号-关于构建垂直行业场景化营销的需求（和乐业）-FPA工作量评估.xlsx
```

现象集中在 `FPA功能点估算` sheet：

- `F29`：签到奖品配置，类型 `ILF`，计算依据归类为空。
- `F30`：签到列表数据查询，类型 `EQ`，计算依据归类为空。
- `F31`：添加签到奖品数据，类型 `EI`，计算依据归类为空。
- `F32`：查询奖品数据，类型 `EQ`，计算依据归类为空。

对应 check 工作簿显示，签到奖品配置模块来源为 `rules_fallback`，不是正常 AI rows。

`Warnings` 中有明确错误：

```text
模块序号 8，签到奖品配置：
AI 调用或解析失败: Expecting ',' delimiter: line 32 column 6 (char 1272)
```

稳定性报告中也显示：

```text
模块：签到奖品配置
来源：rules_fallback
Warning数：1
Quality Issue数：1
可重试Quality Issue数：1
```

## 实际链路

该问题不是 Excel 写入丢失列，而是生成链路中出现了两层问题：

```text
AI 重试响应被截断
  -> JSON 解析失败
  -> 模块走 rules_fallback
  -> fallback 行历史上默认不填“计算依据归类”
  -> 正式 Excel F 列为空
```

进一步查看日志，签到奖品配置模块有两次 AI response：

```text
日志\ai_responses\20260609_070519_fpa_l3_签到奖品配置_response.md
日志\ai_responses\20260609_070608_fpa_l3_签到奖品配置_response.md
```

第一次 response 去掉日志头后 JSON 可解析，包含 7 行 rows，并且每行都有 `classification_basis_index`：

```text
[11, 11, 7, 7, 1, 1, 5]
```

第二次 response 前面输出了很长 `[reasoning]`，JSON 写到中途被截断：

```text
{
  "name": "【地市后台】垂直行业营销-
```

因此，更精确的判断是：

```text
第一次 AI 返回可用
  -> 质量审核触发重试
  -> 第二次重试输出大量 reasoning
  -> JSON 部分被截断
  -> 重试解析失败
  -> 当前模块最终走 rules_fallback
```

## 是否是 max_tokens 问题

该现象高度符合输出 token 预算不足或响应中断：

- response 中存在大量 `[reasoning]`。
- 最终 JSON 停在字符串中间。
- 解析错误是典型半截 JSON 错误。
- `config/system_config.yaml.example` 中默认 `max_tokens: 6000`，并明确注释“如果 AI response 数据被截断，增大 max_tokens”。

但它不一定只是简单的 `max_tokens` 打满，也可能是：

- 模型/网关侧输出限制。
- 流式响应中断。
- 请求超时或连接中断。
- reasoning 部分占用大量输出预算，导致 JSON 没写完。

无论哪种情况，工程上都应避免把长推理和最终 JSON 放在同一个必须完整解析的响应里。

## 压制 reasoning 会不会影响判断

会有一点影响，但对 `gen-fpa` 这种任务，压制“外显长 reasoning”通常利大于弊。

关键区别是：

```text
不让模型长篇输出 reasoning
不等于不让模型思考
```

系统真正需要压制的是模型把推理过程写进 response，占用输出 token，导致 JSON 被截断。模型仍然可以在内部完成判断，只是最终响应必须给结构化 JSON。

当前问题中，第二次响应不是“不知道怎么判断”，而是把大量判断过程写到了 `[reasoning]`，最后 JSON 没写完。这说明外显长 reasoning 已经直接伤害了交付结果。

不建议压掉以下字段：

```text
type_reason
explanation
split_reason
complexity_reason
```

这些字段是正式 rows 的结构化判断依据，应该保留。

建议压制的是：

```text
[reasoning]
分析如下：
我先判断...
综合考虑...
最终输出...
```

推荐 prompt 约束：

```text
不要输出 reasoning、分析过程、Markdown 或解释。
只输出 JSON。
所有判断理由必须写入 rows[].type_reason、rows[].explanation、rows[].split_reason、rows[].complexity_reason。
```

这样模型仍然给出依据，但依据进入可解析字段，而不是以自由文本消耗 token。

## 会不会影响调试

会少一点“看模型自言自语”的信息，但不会损害工程调试。相反，结构化调试会更可靠。

外显 reasoning 的调试价值是能看到模型“怎么想”，但它的问题也明显：

- 占用 token。
- 污染 JSON。
- 容易截断。
- 不稳定。
- 不便于结构化比较。
- 不一定忠实反映模型真实判断过程。

`gen-fpa` 更适合依赖以下结构化调试材料：

```text
prompt
raw_response
parsed_rows
final_rows
process_facts
type_judgement
merge_review
quality_review
agent_review
validator issues
rule_hits
warnings
retry_trigger_source
stability_report
```

这些材料能定位：

- 模型是否收到正确输入。
- 前置规则建议是什么。
- AI 输出了哪些 rows。
- 哪些字段被后处理改写。
- 哪个 validator 或 quality_review issue 触发重试。
- 最终为什么 fallback。
- 哪条规则命中。

因此，调试应依赖结构化 trace，而不是依赖一大段可能截断最终 JSON 的自由 reasoning。

## 两全方案

两全方案是把“可调试的推理痕迹”和“可交付的 JSON”拆开，但仍在同一条审计链里关联。

### 方案 A：保留短 `debug_summary`

默认禁止长 reasoning，但允许模型输出短调试摘要：

```json
{
  "debug_summary": [
    "m8_p2/m8_p4/m8_p5 合并为签到奖品配置维护 EI",
    "m8_p1/m8_p3 合并为签到奖品配置查询 EQ",
    "未生成 EIF：输入未明确外部维护数据组"
  ],
  "rows": []
}
```

系统只把 `rows` 写入正式结果，把 `debug_summary` 写入 check/debug。

优点：

- 改动小。
- 成本低。
- 调试信息仍可见。
- 不容易挤断 JSON。

缺点：

- 调试信息是摘要，不是完整 reasoning。

### 方案 B：两阶段调用

第一阶段只产短结构化判断：

```json
{
  "decisions": [
    {
      "id": "merge_prize_maintenance",
      "decision": "merge",
      "source_process_ids": ["m8_p2", "m8_p4", "m8_p5"],
      "reason": "同一业务对象的新增、编辑、删除维护动作"
    }
  ]
}
```

第二阶段只根据 decisions 输出 rows：

```json
{
  "rows": []
}
```

优点：

- 最稳。
- 调试也清楚。
- 决策链可以被 validator、golden case 和稳定性报告检查。

缺点：

- 多一次调用。
- 成本和延迟增加。
- 需要更完整的中间契约设计。

当前已有的 `process_facts`、`type_judgement`、`merge_review`、`quality_review` 和 `agent_review` 已经是在为这种方向铺路。

### 方案 C：失败时才请求 reasoning

正常生成时：

```text
只输出 JSON rows。
```

如果 validator 或 quality_review 失败，再追加一个轻量诊断请求：

```text
请解释为什么上一版 rows 违反以下质量问题，输出不超过 5 条 debug_notes。
```

优点：

- 大多数正常模块不花调试 token。
- 只有失败时才要解释。
- 不会让主响应被 reasoning 挤断。

缺点：

- 事后解释不一定完全等于当时推理，但工程上通常够用。

### 方案 D：允许 reasoning 但设置硬预算

允许短 debug notes，但强限制：

```text
可以输出 debug_summary，最多 5 条，每条不超过 40 字。
禁止输出长篇 reasoning。
rows 必须完整。
```

优点：

- 改动小。
- 可以保留少量模型判断痕迹。

缺点：

- 模型偶尔仍可能不遵守，需要后处理校验。

## 推荐组合

当前 `gen-fpa` 推荐采用组合方案：

```text
生产默认：方案 A
重试路径：方案 C
未来复杂 profile / 高风险样例：方案 B
```

具体建议：

1. prompt 强制禁止 `[reasoning]`、Markdown、长分析。
2. 允许可选 `debug_summary`，限制为短列表。
3. `rows` 是唯一正式输出来源。
4. `debug_summary` 只进入 check/debug/audit，不进入正式 FPA 表。
5. 如果 `rows` 解析失败但能提取 `debug_summary`，仍不能交付，走 fallback 或保留上一版可解析结果。
6. 如果第一次 rows 可解析、重试 rows 截断，应保留第一次可解析 rows，并把重试失败写 warning。
7. 对特别复杂模块，后续再做“两阶段 decisions -> rows”。

## 重试路径的关键修复

当前案例暴露出一个重要工程问题：第一次 AI 返回可解析，第二次重试被截断后，最终模块走了 `rules_fallback`。

更稳的策略应是：

```text
第一次 AI rows 可解析
  -> 质量审核触发重试
  -> 重试 rows 解析失败
  -> 保留第一次可解析 rows
  -> 写入 warning：重试解析失败，已保留上一版可解析 AI 输出
```

这样可以避免因为一次失败的重试把可用结果全部丢掉。

该策略适用于：

- 重试响应 JSON 截断。
- 重试响应空。
- 重试响应无法解析。
- 重试响应格式合法但 rows 为空。

保留上一版结果时仍应保留原始质量 warning，不应假装完全通过。

## fallback 行的计算依据归类补全

当前 F29:F32 空白的直接原因不是 AI rows 缺字段，而是 fallback 行进入正式结果后 `计算依据归类` 仍为空。

历史上测试中曾明确写过：

```text
F 列（计算依据归类）初始为空，待 AI 填充。
```

这在“规则只生成骨架，AI 后续补充”的旧口径下合理。但现在 `strict_fpa` 的 `fallback` / `rules_fallback` 行会进入正式结果，继续留空会影响交付质量。

建议给 `strict_fpa` 规则兜底行补一层 `计算依据归类` 推断：

```text
ILF -> 后台数据库变更/内部逻辑数据组相关原则
EIF -> 外部应用维护数据组/外部接口文件相关原则
EI  -> 修改或增加界面的个数，或进入/改变系统边界数据的事务原则
EQ  -> 提供查询界面输入并展示返回结果
EO  -> 输出票据、报表、统计、文件等
```

原则：

- 优先基于配置中的 `judgement_rules` 匹配，不硬写完整中文文案。
- 先收 `strict_fpa`，避免误改 `unified_ui` / `ui_api_mapping` 历史口径。
- check/debug 中保留该归类来自规则兜底的审计痕迹。

## max_tokens 配置建议

短期缓解可以提高 `max_tokens`：

```yaml
max_tokens: 16K
```

或在复杂模块、真实模型抽样、严格确认模式下使用更高值：

```yaml
max_tokens: 32K
```

但只提高 `max_tokens` 不是根治。

如果 prompt 允许长 reasoning，模型仍可能把更多预算花在分析文本上，最终 JSON 依然可能被截断。真正稳定的做法是：

```text
提高输出预算
+ 禁止外显长 reasoning
+ 保留短 debug_summary
+ 重试失败保留上一版可解析 rows
+ fallback 行补齐正式必填字段
```

## 推荐落地顺序

### P0：修复重试失败丢弃可用结果

当重试解析失败时，保留上一版可解析 AI rows，并写 warning。

验收：

- 第一次 AI rows 可解析。
- 重试响应截断。
- 最终结果仍使用第一次 rows。
- warning 明确记录重试解析失败。

### P1：压制 FPA 主响应外显 reasoning

更新 strict_fpa / unified_ui / multi_ui / ui_api_mapping 的 system prompt 或 user prompt：

```text
不要输出 reasoning、分析过程、Markdown 或 JSON 外文本。
只输出 JSON。
如需说明判断依据，必须写入 rows[].type_reason、rows[].explanation、rows[].split_reason、rows[].complexity_reason。
```

可选增加：

```text
debug_summary 最多 5 条，每条不超过 40 字；没有必要时省略。
```

验收：

- response 不再出现 `[reasoning]`。
- JSON 可解析率提升。
- debug_summary 如出现，可进入 check/debug。

### P2：fallback 行补齐 `计算依据归类`

给 `strict_fpa` fallback/rules_fallback 行补齐正式 F 列。

验收：

- 规则兜底行 `计算依据归类` 不为空。
- F29:F32 这类场景不再空白。
- 旧测试更新为新口径。

### P3：失败后轻量诊断

当 validator/quality_review 仍失败时，新增可选轻量诊断请求，只返回短 `debug_notes`，不影响主 rows。

验收：

- 正常路径不增加调用。
- 失败路径可得到结构化 debug_notes。
- debug_notes 不进入正式 FPA 表。

### P4：复杂模块两阶段 decisions -> rows

对高风险或复杂 profile，引入两阶段生成：

```text
decisions
  -> rows
```

验收：

- decisions 可被 validator/golden case 检查。
- rows 只负责格式化最终结果。
- 稳定性报告能关联 decisions 和 rows。

## 结论

当前案例不是单纯“AI 不会生成”，而是：

```text
重试阶段 reasoning 过长 / 输出截断
+ 重试失败后未保留上一版可解析 AI rows
+ fallback 行正式字段补全不足
```

两全方案不是保留无限 reasoning，也不是完全牺牲调试信息，而是：

```text
主响应只承载可交付 JSON
调试信息变成短 debug_summary / debug_notes / agent_review / quality_review
复杂判断逐步沉淀为 decisions 和 profile contract
```

这样可以同时提高：

- JSON 可解析率。
- 正式结果完整性。
- 调试可追踪性。
- 后续 harness 和稳定性报告的可比较性。
