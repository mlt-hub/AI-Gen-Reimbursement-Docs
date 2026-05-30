# FPA 暂缓推进任务与恢复指令

本文档记录当前暂不推进的 FPA 后续事项，以及后续让 Codex 继续处理这些事项时可直接使用的指令。

## 任务主入口

所有暂不推进事项统一记录在：

```text
docs/dev/gen-fpa-implementation-notes.md
```

对应章节：

```text
暂缓推进任务池
后续恢复指令
```

## 任务分组

当前暂缓事项按以下分组维护：

```text
A. 真实项目 Golden Case
B. strict_fpa 数据组识别
C. 类型冲突规则
D. 配置校验
E. 领域上下文
F. 验收
G. 可选增强
```

## 指令模板

### 继续全部任务

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，从 A1 开始按顺序继续推进。每完成一项更新文档并跑相关测试。
```

### 推进指定分组

示例：

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，推进 B 组 strict_fpa 数据组识别。每完成一项更新文档并跑相关测试。
```

### 推进指定事项

示例：

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，只推进 D5：普通外部服务被配置为数据组时记录 warning。完成后更新文档并跑相关测试。
```

### 只重新评估优先级，不修改代码

```text
读取 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，结合当前代码状态重新排序，先给出推荐，不修改代码。
```

## 文档引用关系说明

后续待办只在一份文档中详细维护，避免多份文档各写一套清单后逐渐不一致。

```text
docs/dev/gen-fpa-implementation-notes.md
  -> 暂缓推进任务池的详细主入口

docs/fpa-profiles.md
  -> 面向使用者的 FPA profile 说明，只引用任务池入口

docs/dev/gen-fpa-improvement-plan.md
  -> 原始改进规划，只引用任务池入口
```

可以理解为：

```text
gen-fpa-implementation-notes.md = 待办清单主入口
fpa-profiles.md = 使用者说明，放跳转提示
gen-fpa-improvement-plan.md = 改进规划，放跳转提示
```

以后如果需要继续推进，只需引用“暂缓推进任务池”，Codex 就应从统一清单接着处理。
