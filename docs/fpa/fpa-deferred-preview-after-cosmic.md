# gen-cosmic 重构后的预览抽象状态

本文档记录从 FPA 当前收口队列中转出的多预览页面扩展事项，以及 `gen-cosmic` 结构化重构后已恢复推进的状态。

`/preview/cosmic` 已完成最小结构化 JSON 审阅页，不再属于“等待 gen-cosmic 重构后再做”的事项。生成任务和历史记录中已有 COSMIC 会话预览入口；剩余工作集中在确认后导出策略和跨预览抽象边界，仍不并入 FPA 收口主线。

## 当前触发条件状态

原恢复条件当前状态：

```text
1. 已满足：gen-cosmic 已形成结构化 JSON 草稿、review_items、confirmation 和 export_policy。
2. 已满足：COSMIC 预览所需的中间结果、审核信息和错误模型已经进入 JSON 契约。
3. 部分满足：FPA / COSMIC 已分别有预览页；SPEC 和跨预览组件抽象边界仍待评估。
```

## 事项状态

```text
I1. 已恢复并完成最小页：/preview/cosmic 可加载 COSMIC JSON 草稿，展示功能过程、数据移动、审阅项、确认状态，并导出确认 JSON。会话页 /sessions/:sessionId/cosmic/preview 会自动读取任务输出目录内的 COSMIC JSON 草稿，并可保存/读取 cosmic-confirmation.json；任务页和历史页已提供 COSMIC 会话预览入口。
I2. 仍暂缓：/preview/spec 仍等 SPEC 数据契约和预览抽象边界稳定后再评估。
I3. 部分暂缓：COSMIC 已有独立最小页；COSMIC / SPEC 预览组件是否抽象共用仍待设计，避免在 SPEC 未明确前过早抽象。
I4. 仍暂缓：如后续需要 Golden Case 对比，可增加 /preview/golden-cases；是否做成 FPA 专属入口或跨生成器入口，应等预览抽象边界确定后再决策。
```

## 后续推进建议

继续推进时建议先收口 COSMIC 预览闭环，再评估跨生成器抽象：

```text
读取 docs/fpa/fpa-deferred-preview-after-cosmic.md，结合当前 /preview/cosmic、会话预览接口、COSMIC JSON 草稿和确认 JSON，实现下一步 COSMIC 预览闭环。先给方案，不直接修改代码。
```

如果确认继续实施，建议拆成小步：

```text
1. 先定义确认后正式导出执行策略，明确 export_policy 如何驱动草稿/正式输出。
2. 再评估人工编辑功能过程和数据移动是否进入当前预览页。
3. 最后判断 FPA / COSMIC / SPEC 预览组件是否需要抽象共用，以及 /preview/golden-cases 是 FPA 专属能力还是跨生成器验收能力。
```
