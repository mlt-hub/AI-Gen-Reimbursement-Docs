# gen-cosmic 当前逻辑

## 目标

`gen-cosmic` 用于根据功能清单模块树生成 COSMIC 项目功能点拆分表。当前实现是批处理生成链路：

1. 读取模块树和元数据。
2. 生成空白 COSMIC Markdown 模板。
3. 调用 AI 为三级模块生成功能过程的数据移动链。
4. 将 AI 结果写回 Markdown。
5. 从 Markdown 解析结构化数据。
6. 写入 COSMIC Excel 输出模板。
7. 汇总 CFP 总和，供后续 `gen-list` 使用。

当前还不是稳定的预览或人工审阅链路，`/preview/cosmic` 仍是占位页。

## 流水线入口

主入口是 `ai_gen_reimbursement_docs.pipeline._generate_cosmic`。

执行步骤：

1. 检查 COSMIC Excel 模板是否存在。
2. 读取项目名称和 FPA 核减后工作量。
3. 写入 `md/3.1.gen-cosmic-FPA核减后的工作量-总和.md`。
4. 调用 `init_cosmic_template_md` 生成 `md/3.2.gen-cosmic-COSMIC-模板.md`。
5. 如果存在 API Key，复制模板为 `md/3.3.gen-cosmic-AI填充-COSMIC.md`，再调用 `ai_fill_cosmic_md`。
6. 读取元数据中的 `CFP计算公式`。
7. 调用 `generate_cosmic_xlsx_from_md` 写入 Excel。
8. 从 `md/3.5.gen-cosmic-CFP-总和.md` 读取 CFP 总和到 `result.cfp_total`。

如果没有 API Key，当前逻辑只记录 warning，不调用 AI，也不会生成真实 COSMIC 内容；但 `result.cosmic_xlsx` 仍会被设置为目标输出路径。

## 核心模块

| 模块 | 职责 |
| --- | --- |
| `pipeline.py` | 编排 `gen-cosmic` 阶段和全流程顺序。 |
| `gen_cosmic.py` | COSMIC 高层入口，连接模块树、Markdown、Excel 写入。 |
| `cosmic_md.py` | 导出空 Markdown、写入 AI 结果、从 Markdown 解析 `CosmicItem`。 |
| `cosmic_ai.py` | 构造 prompt、调用 LLM、解析 JSON、生成质量 warning。 |
| `cosmic_models.py` | 定义 `DataMovement` 和 `CosmicItem`。 |
| `cosmic_writer.py` | 将 `CosmicItem` 扁平化后写入 Excel 模板。 |

## 数据模型

`DataMovement` 表示一次 COSMIC 数据移动：

- `order`：序号。
- `sub_process`：子过程描述。
- `move_type`：移动类型，标准值为 `E/X/R/W`。
- `data_group`：数据组。
- `data_attrs`：数据属性。
- `reuse`：复用度，默认 `新增`。
- `move_type_flagged`：移动类型是否由模糊匹配得出。

`CosmicItem` 表示一个功能过程：

- `project`：项目名称。
- `module_l1/module_l2/module_l3`：模块路径。
- `user`：功能用户，格式为 `发起者：xxx|接收者：xxx`。
- `trigger`：触发事件。
- `process`：功能过程名称。
- `movements`：数据移动列表。
- `warnings`：质量检查提示。

`CosmicItem.total_cfp()` 当前计算规则：

- `复用`：每次数据移动按 `1/3` CFP。
- 其他值：每次数据移动按 `1` CFP。

## AI 生成逻辑

核心函数是 `cosmic_ai.generate_cosmic_items`。

当前只处理 `level == 3` 的模块。每个三级模块会构造一个 prompt，包含模块路径、功能描述和功能过程列表，要求 AI 为每个功能过程生成数据移动链。

用户和触发事件的默认逻辑：

- 功能用户由元数据中的 `功能用户-发起者判定`、`功能用户-接收者判定` 解析得到。
- 规则格式类似 `默认：操作员`、`分销：分销员`。
- 触发事件中，模块名包含 `同步` 或描述包含 `定时` 时使用 `定时触发`，否则使用 `用户触发`。

AI 调用限制：

- `load_flow_max_ai("gen_cosmic")` 限制调用 AI 的三级模块数量。
- `load_gen_cosmic_ai_limit()` 限制调用 AI 的功能过程数量。

超过限制的模块不会被丢弃，而是生成空 `CosmicItem` 占位，保留功能过程骨架。

失败处理：

- 非交互环境下，AI 调用或解析失败后跳过该模块，并记录到 `error_modules`。
- 交互环境下，可选择重试、调整 `max_tokens`、跳过或结束。
- 失败模块不会中断整轮生成。

质量 warning：

- 移动类型不是标准 `E/X/R/W` 时尝试模糊匹配，并标记 warning。
- 数据属性为空或少于 3 个时标记 warning。
- 数据移动少于 2 步时标记 warning。
- 首步不是 `E` 时标记 warning。
- 末步不是 `W` 或 `X` 时标记 warning。
- 功能过程名称为空时标记 warning。

## Markdown 中间层

`cosmic_md.export_empty_md` 根据模块树生成空白模板。结构依赖以下格式：

- `## 一级模块 > 二级模块 > 三级模块`
- `### 功能过程名称`
- `发起者： | 接收者：`
- `触发事件：`
- 固定列 Markdown 表格：`序号 / 子过程描述 / 移动类型 / 数据组 / 数据属性 / 复用度 / CFP`

`cosmic_md.fill_md_with_ai` 当前不是在原 Markdown 中局部填空，而是：

1. 调用 `generate_cosmic_items` 重新生成全部 `CosmicItem`。
2. 调用 `export_filled_md` 整体重写已填充 Markdown。

`cosmic_md.parse_md_to_items` 再从填充后的 Markdown 解析回结构化对象。该解析对标题层级和表格格式较敏感。

## Excel 写入逻辑

核心函数是 `cosmic_writer.write_cosmic_xlsx`。

写入规则：

1. 打开模板中的 `2、功能点拆分表` sheet。
2. 保留模板前 5 行。
3. 删除第 6 行之后的旧数据区。
4. 将 `CosmicItem.to_rows()` 的结果扁平化为 Excel 行。
5. 使用模板第 6 行样式写入数据。
6. 如果配置了 `CFP计算公式`，将 `{row}` 替换为实际行号后写入 CFP 公式。
7. 合并项目名、一级模块、二级模块、三级模块、用户、触发事件、功能过程等重复单元格。
8. 给 `复用度` 列添加下拉：`新增,复用,利旧`。
9. 将模板页脚备注搬移到新数据之后。
10. 根据 warning 添加黄色标记和 Excel 批注。

写入过程中还会保存一份扁平源数据到日志目录 `source_data`，用于排查 Excel 写入问题。

## 主要产物

| 路径 | 内容 |
| --- | --- |
| `md/3.1.gen-cosmic-FPA核减后的工作量-总和.md` | FPA 核减后工作量。 |
| `md/3.2.gen-cosmic-COSMIC-模板.md` | 空白 COSMIC Markdown 模板。 |
| `md/3.3.gen-cosmic-AI填充-COSMIC.md` | AI 填充后的 COSMIC Markdown。 |
| `md/3.5.gen-cosmic-CFP-总和.md` | CFP 总和。 |
| `cosmic文档/*.xlsx` | 项目功能点拆分表。 |
| `log/ai_prompts/*generate_cosmic_prompt.md` | AI prompt 日志。 |
| `log/ai_responses/*` | AI response 日志。 |
| `log/source_data/*excel_source.json` | Excel 写入源数据快照。 |

## 当前风险和重构关注点

1. 数据契约绕行 Markdown：AI 结果先写 Markdown，再解析回对象，容易受格式变更影响。
2. 失败不阻断：AI 失败或超过限制时会产生空占位，最终 Excel 可能包含没有数据移动的功能过程。
3. 质量问题只提示：warning 主要进入日志、Markdown 和 Excel 批注，不作为硬性校验。
4. CFP 依赖公式和重算：如果公式缺失、写入失败或 Excel 未重算，下游读取到的 CFP 可能不准确。
5. 预览模型缺失：目前没有稳定的 COSMIC 预览、人工审阅、确认、错误边界数据结构。
6. 解析格式敏感：`parse_md_to_items` 依赖固定标题和表格结构，不适合承载复杂人工编辑。

后续如果要实现 COSMIC 预览或审阅页，应先稳定核心输入/输出模型，再决定是否复用 FPA 的审阅抽象。
