# gen-cosmic 重构后的预览抽象暂缓项

本文档记录从 FPA 当前收口队列中转出的多预览页面扩展事项。

这些事项依赖 `gen-cosmic` 的核心输入/输出模型稳定。当前不在 FPA 重构主线中继续推进，避免把 COSMIC 当前临时数据流提前固化到 UI、API 和测试。

## 恢复触发条件

满足以下条件后再恢复评估：

```text
1. gen-cosmic 重构完成，核心输入/输出模型稳定。
2. COSMIC 预览所需的中间结果、审核信息和错误模型已经明确。
3. FPA / COSMIC / SPEC 预览是否需要共用抽象边界已有结论。
```

## 暂缓事项

```text
I1. 暂缓：/preview/cosmic 等 gen-cosmic 重构完成、核心输入/输出模型稳定后再做。
I2. 暂缓：/preview/spec 也等预览抽象边界稳定后再评估，避免跟 COSMIC 预览分叉。
I3. 暂缓：COSMIC / SPEC 预览组件拆分待 gen-cosmic 重构后统一设计。
I4. 暂缓：如后续需要 Golden Case 对比，可增加 /preview/golden-cases；是否做成 FPA 专属入口或跨生成器入口，应等预览抽象边界确定后再决策。
```

## 恢复推进建议

恢复时建议先做评估，不直接改代码：

```text
读取 docs/fpa/fpa-deferred-preview-after-cosmic.md，结合 gen-cosmic 重构后的输入/输出模型、当前 preview 路由和 FPA/COSMIC/SPEC 预览实现，重新评估 I1-I4 是否恢复推进。先给方案，不直接修改代码。
```

如果确认恢复实施，再拆成小步：

```text
1. 先定义 COSMIC 预览的数据契约和审核信息边界。
2. 再判断 FPA / COSMIC / SPEC 预览组件是否需要抽象共用。
3. 最后评估 /preview/golden-cases 是 FPA 专属能力，还是跨生成器验收能力。
```
