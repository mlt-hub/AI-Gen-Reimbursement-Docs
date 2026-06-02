# Web 生成过程展示与 CLI 复用实施方案

## 背景

当前 Web UI 已经可以运行生成任务，并通过日志视图展示运行过程。后端并不是简单调用 CLI 子进程，而是通过 `web_app/services/task_runner.py` 进入共享的 Python 生成流程，再调用 `ai_gen_reimbursement_docs.pipeline`。

这说明项目已经具备复用基础：Web 与 CLI 可以共享同一套 pipeline、配置解析、模板处理、AI 调用和产物生成逻辑。后续改造的重点不应是重新实现 Web 专用生成流程，而是把“生成过程”从日志文本中抽象为结构化事件，再由 Web 和 CLI 分别渲染。

## 目标

本方案要解决两个问题：

1. Web UI 不再以日志作为主要生成过程展示方式，而是用更清晰的阶段化界面展示任务进展。
2. CLI 与 Web 最大化复用生成代码，避免出现两套业务编排、两套错误处理和两套产物生成逻辑。

目标行为：

- Web 主界面展示“阶段卡片 + 当前动作 + 产物列表”。
- 日志保留为折叠的“运行详情 / 排错信息”，不再作为主进度界面。
- CLI 与 Web 都消费同一套结构化生成事件。
- Web 不通过调用 CLI 子进程来实现复用。
- 第一版不做百分比进度，百分比进度列为后续待做。

## 当前实现判断

当前项目已有几个可复用基础：

- `ai_gen_reimbursement_docs.pipeline.run_pipeline` 是核心管道入口。
- `web_app/services/task_runner.py` 的 `execute_mode()` 已经是 Web 任务进入 pipeline 的应用服务层入口。
- `ai_gen_reimbursement_docs.pipeline_callbacks.PipelineCallbacks` 已经提供了 callback 扩展点。
- `pipeline._step()` 已经能通过 callback 向 Web 发送 `{ "type": "step", "key": key }` 形式的步骤事件。
- Web 前端已有 `StepsBar.vue`、`stores/steps.ts`、`LogViewer.vue`、`stores/log.ts` 等基础组件和状态。

因此，推荐方向是扩展现有 callback 和事件能力，而不是新增一套 Web-only 生成流程。

## 核心原则

### 复用点在应用服务层和 pipeline 核心层

Web 不应通过调用 CLI 子进程来实现复用。

原因：

- 子进程方式难以做结构化事件上报。
- 停止任务、等待用户确认、会话隔离会变复杂。
- 错误处理容易退化成解析标准输出。
- Web 需要的任务状态、产物状态、用户输入状态无法自然回传。
- CLI 输出格式变化可能意外破坏 Web。

推荐复用路径：

```text
CLI / Web
  -> 共享应用服务层 execute_mode
  -> run_pipeline_simple
  -> run_pipeline
  -> gen_fpa / gen_spec / gen_cosmic / gen_list
```

CLI 和 Web 的差异只应体现在入口参数收集、事件渲染、用户交互方式上。

### 日志不再承载主进度

日志定位调整为：

- 用于排错。
- 用于审计。
- 用于查看 AI prompt、异常栈、底层调用细节。
- 作为“运行详情”折叠展示。

主界面应展示业务用户能理解的生成阶段和产物状态。

## Web UI 目标形态

Web 主区域采用“阶段卡片 + 当前动作 + 产物列表”。

推荐阶段：

- 读取基础数据
- 生成 FPA
- 生成功能需求
- 生成 COSMIC
- 生成需求清单
- 生成需求说明书

每个阶段卡片展示：

- 阶段名称
- 阶段状态：等待中、运行中、已完成、失败、等待用户确认
- 当前动作：例如“正在调用 AI 生成 FPA 说明”“正在写入 Excel 模板”
- 耗时
- 产物列表：文件名、类型、是否临时文件、下载入口
- 错误摘要：失败时展示可读错误，完整日志进入详情

日志视图保留，但默认折叠到“运行详情”中。

## 结构化事件模型

第一版采用轻量事件模型，避免一次性设计过重。

建议事件类型：

```python
PipelineEvent = {
    "type": "step_started" | "activity" | "artifact" | "input_required" | "step_done" | "step_failed",
    "step": "basedata" | "fpa" | "spec" | "cosmic" | "list",
    "message": str,
    "payload": dict,
}
```

### 事件说明

`step_started`

表示某个阶段开始。

`activity`

表示当前阶段的动作变化，例如读取 Excel、调用 AI、写入模板、保存 Markdown。

`artifact`

表示生成了一个产物，例如 FPA Excel、需求说明书 Word、AI prompt 文件。

`input_required`

表示需要用户确认或输入，例如 FPA 核减后工作量、送审功能点数。

`step_done`

表示阶段成功完成。

`step_failed`

表示阶段失败，事件中应包含用户可读错误摘要。

## 为什么第一版不做百分比进度

百分比进度列为后续待做，不进入第一版。

原因：

- AI 调用耗时不可预测，无法提供真实百分比。
- Word / Excel 写入、模板填充、文件保存的耗时与输入规模有关，难以统一估算。
- 假百分比会制造误导，例如长时间卡在 90%。
- 当前用户最需要的是知道“正在做什么”“做到哪一步”“生成了什么”“是否需要我确认”。

后续如果要做百分比，应基于可度量的子任务数量或历史耗时估算，而不是在第一版硬编码。

## CLI 复用方案

CLI 也应消费同一套 `PipelineEvent`，但第一阶段只做最小渲染：

- 阶段开始
- 阶段完成
- 关键动作
- 产物路径
- 等待用户输入
- 失败摘要

CLI 不需要复刻 Web 的卡片界面，也不需要复杂进度条。CLI 的目标是让终端输出与 Web 语义一致，避免 pipeline 为 Web 和 CLI 分别写不同分支。

推荐方式：

- 保留 `PipelineCallbacks` 作为扩展点。
- 增加统一的 `emit_event` 事件约定。
- Web callback 将事件写入 session 状态。
- CLI callback 将事件渲染为终端文本。
- 底层生成函数只关心“发事件”，不关心事件展示方式。

## 分阶段实施计划

### 第一期：定义共享事件模型

目标：

- 明确 `PipelineEvent` 类型。
- 扩展 `PipelineCallbacks` 的事件发送接口。
- 为默认 CLI 行为保留兼容默认值。

涉及文件：

- `ai_gen_reimbursement_docs/pipeline_callbacks.py`
- `ai_gen_reimbursement_docs/runtime_context.py`
- `tests/test_pipeline_callbacks.py`

验证：

- 默认 callback 不影响现有 CLI。
- 自定义 callback 能收到结构化事件。

### 第二期：改造 pipeline 关键节点

目标：

- 在 pipeline 阶段开始、阶段结束、产物生成、等待用户输入时发出结构化事件。
- 逐步替换当前单一 `{ "type": "step", "key": key }` 事件。

涉及文件：

- `ai_gen_reimbursement_docs/pipeline.py`
- `ai_gen_reimbursement_docs/gen_fpa.py`
- `ai_gen_reimbursement_docs/gen_spec.py`
- `ai_gen_reimbursement_docs/gen_cosmic.py`
- `ai_gen_reimbursement_docs/gen_list.py`
- 相关测试

验证：

- `gen-fpa`、`gen-all` 能产生完整事件序列。
- 失败时能产生 `step_failed`。
- 用户输入节点能产生 `input_required`。

### 第三期：改造 Web UI 展示

目标：

- 新增或改造前端状态 store，保存结构化生成过程。
- 用阶段卡片展示任务进展。
- 将日志折叠为“运行详情 / 排错信息”。

涉及文件：

- `web_app/services/pipeline_runtime.py`
- `web_app/services/task_runner.py`
- `web_app/routes/tasks.py`
- `web_app/src/stores/steps.ts`
- `web_app/src/components/StepsBar.vue`
- `web_app/src/components/LogViewer.vue`
- 新增 `web_app/src/components/GenerationProgress.vue`

验证：

- Web 运行任务时，主区域显示阶段卡片。
- 当前动作随事件更新。
- 产物生成后能出现在对应阶段卡片中。
- 日志仍可展开查看。

### 第四期：CLI 消费同一事件

目标：

- CLI 入口复用同一套事件语义。
- CLI 输出阶段开始、关键动作、完成、产物和失败摘要。
- 避免 CLI 与 Web 生成逻辑分叉。

涉及文件：

- `ai_gen_reimbursement_docs/cli/main.py`
- `ai_gen_reimbursement_docs/cli/logging.py`
- `web_app/services/task_runner.py` 或共享应用服务层
- 相关 CLI 测试

验证：

- CLI 运行 `gen-fpa`、`gen-all` 输出结构化阶段信息。
- CLI 与 Web 调用同一套 pipeline。
- CLI 不依赖 Web session。

## 验收标准

- Web 运行任务时，主界面不再以日志作为生成过程展示。
- Web 主界面展示阶段卡片、当前动作、阶段状态、耗时和产物列表。
- 日志入口仍可查看完整运行日志。
- Web 不通过 CLI 子进程运行生成任务。
- CLI 与 Web 不分叉生成逻辑。
- CLI 能消费同一套结构化事件并做轻量终端展示。
- 结构化事件有单元测试覆盖。
- 失败、取消、等待用户输入都有明确状态。
- 百分比进度明确列为后续待做，不进入第一版验收。

## 风险与应对

### 事件粒度过粗

风险：UI 只从日志换成步骤条，用户仍不知道当前在做什么。

应对：第一版至少覆盖阶段开始、当前动作、产物生成、用户输入、阶段结束。

### 事件粒度过细

风险：底层生成函数被前端展示细节绑死。

应对：事件表达业务语义，不表达具体 UI。前端自行决定如何渲染。

### CLI 和 Web 入口继续分叉

风险：后续修复只改一边，另一边行为漂移。

应对：把共享编排收敛到应用服务层和 pipeline，只在展示层分叉。

### 日志能力被削弱

风险：结构化展示替代日志后，排错信息不足。

应对：日志继续完整保留，只改变默认展示位置。

## 后续待做

- 基于历史耗时或可计数子任务设计真实进度估算。
- 支持阶段级重试。
- 支持更细的 AI 调用状态展示，例如排队、请求中、响应解析中。
- 支持按阶段查看 prompt 和中间 Markdown。
- 支持生成完成后的阶段级产物预览。
