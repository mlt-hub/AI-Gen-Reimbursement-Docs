# FPA AI 稳定性收敛 Agent 分工决策

决策日期：2026-06-08

## 结论

分工，但轻量分工，不开太多 agent。

采用 `2 + 1` agent 分工：2 个专项分析 agent，1 个主控实施 agent。当前问题已经从“真实 API Key 是否能跑通”进入“如何降低 FPA AI 稳定性重试和质量问题”，适合小规模并行诊断，但不适合拆得过细。

## 背景

第七轮真实 API Key 验收已跑通：

| 指标 | 第七轮基线 |
|---|---:|
| 三级模块总数 | 19 |
| AI 来源模块数 | 19 |
| `retry_count` | 5 |
| `quality_issue_count` | 2 |
| `retryable_quality_issue_count` | 2 |
| 人工确认数 | 0 |

审计报告暴露的主要收敛方向：

| 方向 | 说明 |
|---|---|
| `type_judgement` | AI 类型判定与高置信规则建议存在冲突，需要强化判定依据引用。 |
| 合并边界 | 出现 `validator.split_query_eq`，需要强化维护/查询合并口径。 |
| validator 压力 | 部分基础类型边界仍依赖后置校验重试，适合前置到 prompt 或判定节点。 |

## 分工

| 角色 | 责任 | 产出 |
|---|---|---|
| 主控实施 agent | 统筹范围，最终修改代码和文档，执行测试、真实样例复跑和提交。 | 最小实现补丁、验证结果、提交记录。 |
| 诊断 agent | 深挖第七轮审计 trace、AI 对话日志、5 次 retry、2 个 quality issue。 | 问题归因清单，标明是 prompt、类型判定、合并边界还是 validator 后置兜底。 |
| 回归 agent | 设计复跑指标、对比口径和验收表。 | 基线对比表，覆盖 `retry_count`、`quality_issue_count`、warning、Excel 行数、AI 来源模块数。 |

暂不扩大到更多 agent。FPA prompt、`type_judgement`、合并边界和 validator 强耦合，过度拆分容易让改动分散，增加复跑成本。

## 下一轮目标

在保持同一真实业务样例、同一 Web UI 模式和同一 FPA 策略的前提下，降低可避免的 AI 稳定性重试和质量问题，并让审计报告中的问题归因更清晰。

建议实施范围：

| 范围 | 说明 |
|---|---|
| FPA AI prompt | 强化类型判定依据引用，降低 AI 与高置信规则建议冲突。 |
| 类型判定节点 | 聚焦 `quality.type_judgement_mismatch`，明确 EI/EQ/ILF/EIF 边界。 |
| 合并边界审查 | 聚焦 `validator.split_query_eq`，强化维护/查询合并口径。 |
| validator 反馈 | 保留后置校验，但尽量把高频边界前置到 prompt 或判定节点。 |
| 审计留档 | 继续记录重试来源、质量问题和复跑对比。 |

## 固定复跑配置

| 项 | 值 |
|---|---|
| 接口 | `POST /api/run-local` |
| 生成模式 | `from-excel-gen-fpa` |
| 输入目录 | `F:\mlt\mlt-tests\AI-Gen-Reimbursement-Docs\6` |
| FPA 方案 | `strict_fpa` |
| FPA 执行策略 | `ai_first` |
| FPA 规则集 | `strict_fpa_rs` |
| FPA 确认模式 | `auto` |
| 对比基线 | 第七轮输出目录 `web-ui-fpa-ai-first-20260608-164819` |

## 退出标准

| 标准 | 说明 |
|---|---|
| 功能完整 | 19 个三级模块仍应全部完成，主 FPA 工作簿和审核副本仍应生成。 |
| 来源稳定 | 审计轨迹中 AI 来源模块数不低于第七轮，即保持 19 个。 |
| 质量收敛 | `quality_issue_count` 不高于第七轮基线 2，优先目标为降低到 0 或 1。 |
| 重试收敛 | `retry_count` 不高于第七轮基线 5，优先目标为明显下降。 |
| 审计可解释 | 新增或残留 warning 必须能在审计报告中定位到模块、触发来源和建议动作。 |
| 回归通过 | FPA 相关单元测试通过，真实样例复跑完成并留档。 |

## 风险边界

- 真实模型输出存在随机性，下一轮不承诺永久 `0 retry`。
- 如果 prompt 收紧过度，可能降低召回或让 AI 过度贴合规则，需要用审核副本的 `AI原始返回`、`覆盖审核` 和 `稳定性报告` 交叉验证。
- 若复跑质量改善但 warning 数量上升，需要区分“真实问题增多”和“审计暴露更充分”两类情况。
