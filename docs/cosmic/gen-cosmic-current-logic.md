# gen-cosmic 当前逻辑

## 文档定位

本文同时承担两类用途：

1. 说明当前 `gen-cosmic` 的真实实现逻辑、产物和风险。
2. 记录第一阶段已实施的结构化校验基线，作为后续修改代码、文档和测试的验收依据。

更完整的中长期改造路线见 [`gen-cosmic-improvement-plan.md`](gen-cosmic-improvement-plan.md)。本文中的“第一阶段实施状态”描述当前已落地行为；未纳入第一阶段的内容只作为风险和后续方向，不应在后续实现时隐含扩大范围。

## 目标

`gen-cosmic` 用于根据功能清单模块树生成 COSMIC 项目功能点拆分表。当前实现是批处理生成链路：

1. 读取模块树和元数据。
2. 生成空白 COSMIC Markdown 模板。
3. 调用 AI 为三级模块生成功能过程的数据移动链，得到结构化 `CosmicItem`。
4. 对结构化草稿执行确定性规则校验。
5. 写入 JSON 草稿、Markdown 审阅稿和 Markdown 校验报告。
6. 根据 `passed/review_required/blocked` 决定是否写正式 Excel 或草稿 Excel。
7. 只有正式 Excel 写入成功时，才写入 CFP 总和，供后续 `gen-list` 使用。

当前还不是稳定的预览或人工审阅链路，`/preview/cosmic` 仍是占位页；但批处理阶段不再用“目标 Excel 路径已设置”表示 COSMIC 成功。

## 流水线入口

主入口是 `ai_gen_reimbursement_docs.pipeline._generate_cosmic`。

执行步骤：

1. 检查 COSMIC Excel 模板是否存在。
2. 读取项目名称和 FPA 核减后工作量。
3. 写入 `md/3.1.gen-cosmic-FPA核减后的工作量-总和.md`。
4. 调用 `init_cosmic_template_md` 生成 `md/3.2.gen-cosmic-COSMIC-模板.md`。
5. 如果存在 API Key，直接调用 `generate_cosmic_items` 生成结构化 `CosmicItem`；如果没有 API Key，则以空列表进入校验。
6. 读取元数据中的 `CFP计算公式`。
7. 调用 `generate_cosmic_artifacts` 写 JSON 草稿、Markdown 审阅稿、校验报告，并按校验状态决定 Excel 输出。
8. 如果正式 Excel 写入成功，将 CFP 总和写入 `md/3.5.gen-cosmic-CFP-总和.md` 并同步到 `result.cfp_total`。

如果没有 API Key，当前逻辑会生成 COSMIC 模板、JSON 草稿和校验报告，报告状态为 `blocked`，包含 `NO_API_KEY`、`NO_COSMIC_ITEMS` 等结构化问题；不会写正式 COSMIC Excel，也不会更新正式 CFP 总和。

如果 AI 生成过程抛出异常，管线会把异常转成全局 `AI_GENERATION_FAILED` issue，并继续写出 JSON 草稿和校验报告。若 AI 返回空列表，还会记录 `AI_GENERATION_EMPTY` 和最终 `NO_COSMIC_ITEMS`，避免只从日志中推断失败原因。模块树没有三级模块时会记录 `NO_L3_MODULES`；配置限制导致全部跳过时会记录 `AI_LIMIT_SKIPPED_ALL`；配置限制导致部分跳过时会记录 `AI_L3_LIMIT_PARTIAL_SKIP` 或 `AI_PROCESS_LIMIT_PARTIAL_SKIP`；交互模式下用户主动终止时会记录 `USER_ABORTED_GENERATION`；部分模块失败但仍有结果时会记录 `PARTIAL_AI_FAILURE`。

## 核心模块

| 模块 | 职责 |
| --- | --- |
| `pipeline.py` | 编排 `gen-cosmic` 阶段和全流程顺序。 |
| `gen_cosmic.py` | COSMIC 高层入口，连接模块树、Markdown、Excel 写入。 |
| `cosmic_md.py` | 导出空 Markdown、写入 AI 结果、从 Markdown 解析 `CosmicItem`。 |
| `cosmic_ai.py` | 构造 prompt、调用 LLM、解析 JSON、生成质量 warning。 |
| `cosmic_models.py` | 定义 `DataMovement` 和 `CosmicItem`。 |
| `cosmic_validator.py` | 定义结构化校验结果、确定性规则、JSON 草稿和 Markdown 校验报告写出。 |
| `cosmic_writer.py` | 将校验后的 `CosmicValidationReport` 扁平化后写入 Excel 模板。 |

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
- `warnings`：旧 AI 解析路径留下的兼容字段；正式 Excel 标记以 `CosmicIssue` 为准。

`CosmicItem.total_cfp()` 当前计算规则：

- `复用`：每次数据移动按 `1/3` CFP。
- 其他值：每次数据移动按 `1` CFP。

第一阶段新链路不再依赖 `CosmicItem.total_cfp()` 计算正式 CFP。正式 Excel 中的 CFP 仍以模板公式为准；Python 侧只在正式 Excel 写入成功时写入 CFP 总和。JSON 草稿会在顶层 `cfp_basis` 中记录 CFP 来源：有公式时为 `template_formula`，缺公式时为 `unconfirmed`。

## AI 生成逻辑

核心函数是 `cosmic_ai.generate_cosmic_items`。

当前只处理 `level == 3` 的模块。每个三级模块会构造一个 prompt，包含模块路径、功能描述、COSMIC 送审口径硬约束和功能过程列表，要求 AI 为每个功能过程生成数据移动链。

当前 prompt 已包含以下硬约束：

- 功能用户的发起者或接收者之一必须对应三级模块或最小颗粒度模块。
- 前端/后端、前台/后台交互不识别为 COSMIC 边界。
- 上一页、下一页、排序、展示或隐藏菜单、点击确认等控制命令不计列为数据移动。
- 校验、分析、统计、格式化、连接数据库、连接服务器、建立容器等通常不单独作为数据移动。
- 非功能内容不得拆成 COSMIC 功能过程。
- 每个功能过程必须由触发事件启动，且至少包含两个数据移动。

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

`cosmic_md.fill_md_with_ai` 仍保留给旧调用或排查使用，不再是正式批处理管线的结构化入口。正式管线直接使用 AI 返回的 `CosmicItem` 列表，并将 Markdown 作为人类可读审阅稿。

`cosmic_md.fill_md_with_ai` 不是在原 Markdown 中局部填空，而是：

1. 调用 `generate_cosmic_items` 重新生成全部 `CosmicItem`。
2. 调用 `export_filled_md` 整体重写已填充 Markdown。

`cosmic_md.parse_md_to_items` 仅保留给临时排查或兼容场景；正式管线不再从填充后的 Markdown 解析结构化对象。该解析对标题层级和表格格式较敏感，不应作为新链路事实源。

## Excel 写入逻辑

核心函数是 `cosmic_writer.write_cosmic_xlsx`，其输入是 `CosmicValidationReport`，不是裸 `CosmicItem` 列表。

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
10. 根据结构化 `CosmicIssue` 添加黄色标记和 Excel 批注。

写入过程中还会保存一份扁平源数据到日志目录 `source_data`，用于排查 Excel 写入问题。

## 主要产物

| 路径 | 内容 |
| --- | --- |
| `md/3.1.gen-cosmic-FPA核减后的工作量-总和.md` | FPA 核减后工作量。 |
| `md/3.2.gen-cosmic-COSMIC-模板.md` | 空白 COSMIC Markdown 模板。 |
| `md/3.3.gen-cosmic-AI填充-COSMIC.md` | AI 结果导出的 COSMIC Markdown 审阅稿。 |
| `md/3.3.gen-cosmic-AI填充-COSMIC.json` | 结构化 COSMIC 草稿、状态和 issue。 |
| `md/3.4.gen-cosmic-校验报告.md` | 人工可读校验报告和 Excel 输出策略说明。 |
| `md/3.5.gen-cosmic-CFP-总和.md` | CFP 总和，仅正式 Excel 写入成功时更新。 |
| `cosmic文档/*.xlsx` | 正式项目功能点拆分表，仅 `passed` 时默认写入。 |
| `cosmic文档/*-草稿.xlsx` | 草稿项目功能点拆分表，仅 `review_required` 且开启草稿输出时写入。 |
| `log/ai_prompts/*generate_cosmic_prompt.md` | AI prompt 日志。 |
| `log/ai_responses/*` | AI response 日志。 |
| `log/source_data/*excel_source.json` | Excel 写入源数据快照。 |

## 与软评填报参考手册2024的差距

参考文档：`F:\mlt\mlt-docs\AI-Gen-Reimbursement-Docs\02.亚伟需求沟通\软评填报参考手册2024.pdf`。

该手册要求的核心口径是：需求说明书、软件功能清单、COSMIC 工作量拆分共同支撑送审；需求说明书的详细功能说明要按系统功能架构图层级下钻，并能对应拆分表的一、二、三级模块；COSMIC 拆分表要按功能用户需求、触发事件、功能过程、数据组、数据移动和 CFP 规则填报。

当前 `gen-cosmic` 和手册存在以下差距。

### 功能用户口径不足

手册要求：功能过程的数据发送者或预期接收者之一必须对应功能架构图上的最小颗粒度模块，用于区分功能过程所属模块，并且功能用户与功能过程是一对一关系。

当前实现：`cosmic_ai._build_user` 主要依赖元数据中的默认值和关键词规则生成 `发起者/接收者`。校验器已经把功能用户拆分和模块匹配结果写入 `items[].basis.function_user`：匹配三级模块时通过；仅匹配一/二级模块、只出现泛化角色或完全无法匹配时进入 `GENERIC_FUNCTION_USER` 待审；但仍未自动修复功能用户，也不验证功能用户与功能过程的一对一关系。

影响：可能生成泛化用户，如 `操作员`、`管理模块`，但无法满足送审材料中“绑定最小颗粒度模块”的要求。

### 必填规则仅作为 warning

手册要求：

1. 一个功能过程必须完全属于某一层、某一个软件块的度量范围。
2. 功能过程不能对应多个模块。
3. 功能过程必须由触发事件启动。
4. 第一个子过程必须为输入 `E`。
5. 最后一个子过程必须为写 `W` 或输出 `X`。
6. 一个功能过程至少包含两个子过程及相应的数据移动。

当前实现：首步 `E`、末步 `W/X`、至少两步、缺少模块路径、缺少功能过程名称、缺少触发事件等规则已经进入结构化校验。存在 `error` 时报告状态为 `blocked`，默认不会写正式 Excel；存在 `warning` 且没有 `error` 时报告状态为 `review_required`，默认也不会写正式 Excel。

影响：当前批处理输出已经能阻断明显不符合送审规则的结果；但跨模块归属、功能用户一对一关系等更复杂规则仍需要后续阶段继续工程化。

### CFP 和复用口径待确认

手册说明：每个子过程对应一个功能点，CFP 默认 1；优化功能需要填写完整子过程，不涉及修改的子过程 CFP 填 0；设计院会根据材料和评估规则更正为新增、复用、利旧。

当前实现：

1. `CosmicItem.total_cfp()` 中仍保留旧兼容逻辑，但第一阶段新链路不再依赖它计算正式 CFP。
2. Excel 写入时 CFP 列依赖模板或元数据中的 `CFP计算公式`；未配置公式时产生 `MISSING_CFP_FORMULA` error，并阻断正式输出。
3. `利旧`、优化未改子过程填 `0` 的规则没有进入模型层。

影响：缺公式不再静默生成正式结果，但 `复用`、`利旧`、`0` 的完整送审口径仍待后续确认和配置化。

### 边界识别规则缺失

手册说明：前端/后端、前台/后台交互不识别为边界；跨越边界的数据移动通常体现在功能用户、外部系统、持久存储等之间。

当前实现：AI prompt 已明确提示前端/后端、前台/后台交互不识别为 COSMIC 边界。校验器会对命中前端/后端、前台/后台、内部接口、临时接口、微服务等关键词的数据移动产生 `INTERNAL_TECHNICAL_BOUNDARY` warning，并把命中依据写入 `items[].basis.movement_semantics`；当前只进入待审，不自动判定接口是否跨有效边界。

影响：AI 可能把内部技术交互、微服务交互、临时开发接口误计为 COSMIC 数据移动，导致过度拆分。

### 数据运算和无数据移动子过程过滤不足

手册说明：数据格式化、操作提交、校验、分析、统计等通常归入相关数据移动的数据运算，不单独识别为数据移动；连接数据库、连接服务器、建立容器等不应作为数据移动子过程。

当前实现：校验器会对命中格式化、校验、统计、连接数据库等关键词的子过程产生 `DATA_OPERATION_ONLY_MOVEMENT` warning，并把命中依据写入 `items[].basis.movement_semantics`；当前只进入待审，不自动删除数据移动。

影响：AI 可能把运算步骤或技术准备步骤写成独立子过程，导致 CFP 虚高。

### 控制命令过滤缺失

手册说明：上一页、下一页、排序、展示/隐藏菜单、点击 `OK` 确认前一操作等控制命令不移动兴趣对象数据，应被忽略。

当前实现：校验器会对命中上一页、下一页、排序、展示/隐藏菜单、点击确认等关键词的子过程产生 `CONTROL_COMMAND_MOVEMENT` warning，并把命中依据写入 `items[].basis.movement_semantics`；当前只进入待审，不自动删除数据移动。

影响：页面交互类需求容易被拆出不应计列的数据移动。

### 错误和确认消息规则未细化

手册说明：错误/确认消息通常可归为一个输出；但因持久数据读或写而接收到的错误提示不单独识别；操作系统发布的错误消息等不应识别。

当前实现：校验器会对命中错误提示、确认消息、成功/失败提示等关键词的数据移动产生 `ERROR_CONFIRMATION_MESSAGE` warning，并把命中依据写入 `items[].basis.movement_semantics`；当前只进入待审，不自动合并或删除。

影响：AI 仍可能多计或漏计错误/确认类输出，但结构化草稿会提示人工确认是否重复计列。

### 非功能部分边界不足

手册说明：非功能部分 COSMIC 无法评估，只检查是否包含于 COSMIC 开发里，对工作量不进行确认。多系统联调、系统迁移、前端适配、软硬件环境扩容、架构及组件改造等应与 COSMIC 功能规模区分。

当前实现：校验器会对命中系统迁移、前端适配、环境扩容、架构/组件改造等关键词的模块路径或功能过程产生 `NON_FUNCTIONAL_SCOPE` warning，并把命中依据写入 `items[].basis.process_semantics`；当前只进入待审，不自动剔除。

影响：如果模块树中混入非功能或技术改造事项，AI 可能将其误拆为功能过程。

## 当前风险和重构关注点

1. 边界识别不足：prompt 已加入送审口径硬约束，内部技术交互、控制命令、部分纯数据运算、错误/确认消息和部分非功能事项已有待审 warning；但复杂边界和复杂非功能事项仍主要依赖 AI 自觉和后续人工确认。
2. 功能用户口径仍偏弱：当前已经记录功能用户匹配依据并要求三级模块匹配；但尚未自动修复到最小颗粒度模块，也未接入业务角色映射表。
3. CFP 口径仍需配置化：缺公式已阻断，但 `复用`、`利旧`、优化未改子过程填 `0` 仍未完整工程化。
4. 预览模型缺失：目前没有稳定的 COSMIC 预览、人工审阅、确认、错误边界数据结构。
5. 解析格式敏感：`parse_md_to_items` 仍保留给兼容或排查场景，不适合承载复杂人工编辑。
6. 送审规则未完整工程化：软评填报参考手册中的启发式规则尚未完整进入 prompt、结构化校验和结果状态。

后续如果要实现 COSMIC 预览或审阅页，应先稳定核心输入/输出模型，再决定是否复用 FPA 的审阅抽象。

## 第一阶段实施状态

第一阶段已完成。当前链路已经把“生成草稿后直接写 Excel”改造成“先生成结构化草稿，再执行确定性规则校验，再决定是否允许正式输出”的链路。

本阶段没有实现 `/preview/cosmic` 审阅页，没有重写整套 AI 生成策略，也没有一次性覆盖所有《软评填报参考手册2024》启发式规则。页面审阅、人工编辑、内部接口边界自动判定、非功能内容自动剔除等内容仍属于后续阶段；内部技术交互、控制命令、纯数据运算、错误/确认消息和部分非功能事项当前只做待审提示。

本节后续内容保留为第一阶段实现记录和验收基线；其中“必须”“建议”等措辞按已实现规格理解，不再表示新的待办。

### 目标行为

生成 COSMIC 结果后，系统必须为每个功能过程给出校验状态：

| 状态 | 含义 | 行为 |
| --- | --- | --- |
| `passed` | 没有 `error` 和 `warning`。 | 可进入正式 Excel 写入。 |
| `review_required` | 没有 `error`，但存在 `warning`。 | 可写草稿和校验报告，正式输出需明确允许。 |
| `blocked` | 存在至少一个 `error`。 | 默认不写正式 Excel，输出校验报告。 |

本阶段必须保持当前批处理入口可运行。没有 API Key、AI 失败或超过 AI 限制时，不能静默产出看似正式的 COSMIC Excel；应在结构化校验结果中体现空占位、缺少数据移动或缺少触发事件等问题。

### 修改范围

第一阶段建议修改以下文件：

| 文件 | 修改内容 |
| --- | --- |
| `ai_gen_reimbursement_docs/cosmic_models.py` | 补充结构化校验相关模型，或为现有模型增加可承载校验结果的字段。 |
| `ai_gen_reimbursement_docs/cosmic_validator.py` | 新增 COSMIC 确定性规则校验器。 |
| `ai_gen_reimbursement_docs/gen_cosmic.py` | 以结构化 `CosmicItem` 或 `CosmicDraft` 为输入调用校验器，生成 JSON 草稿和校验报告。 |
| `ai_gen_reimbursement_docs/pipeline.py` | 根据校验状态决定是否写正式 Excel、草稿 Excel 或仅输出报告。 |
| `ai_gen_reimbursement_docs/cosmic_writer.py` | 接收结构化校验结果，继续把 warning/error 写入批注或标记。 |
| `tests/test_cosmic_validator.py` | 覆盖确定性规则和状态归并。 |
| 既有 COSMIC 生成测试 | 调整期望产物，验证 JSON 草稿和校验报告。 |

如果实现时发现 `cosmic_models.py` 与现有调用耦合过重，可以新增独立模型模块；但最终对外数据契约必须稳定，不应继续让 Markdown 成为唯一结构化来源。

### 具体实现方案

第一阶段采用直接替换式改造。本系统尚未上线，不需要保留旧版本路径；可以删除旧函数、修改函数签名、重写调用方和测试。目标是让结构化校验结果成为唯一事实源，不再用“返回 Excel 路径”表示 COSMIC 阶段成功。

新增模块 `ai_gen_reimbursement_docs/cosmic_validator.py`：

```python
from dataclasses import dataclass, field
from typing import Literal

from ai_gen_reimbursement_docs.cosmic_models import CosmicItem

IssueSeverity = Literal["error", "warning", "info"]
ValidationStatus = Literal["passed", "review_required", "blocked"]


@dataclass
class CosmicIssue:
    severity: IssueSeverity
    code: str
    message: str
    field: str = ""
    module_path: str = ""
    process: str = ""
    movement_order: int | None = None
    scope: str = "item"


@dataclass
class CosmicValidationResult:
    item: CosmicItem
    status: ValidationStatus
    issues: list[CosmicIssue] = field(default_factory=list)


@dataclass
class CosmicValidationReport:
    project: str
    status: ValidationStatus
    results: list[CosmicValidationResult]
    summary: dict[str, int]
    issues: list[CosmicIssue] = field(default_factory=list)
```

新增函数：

```python
def validate_cosmic_item(item: CosmicItem) -> CosmicValidationResult: ...

def validate_cosmic_items(
    items: list[CosmicItem],
    *,
    project_name: str = "",
    cfp_formula: str = "",
) -> CosmicValidationReport: ...

def cosmic_report_to_dict(report: CosmicValidationReport) -> dict: ...

def write_cosmic_validation_json(
    report: CosmicValidationReport,
    output_path: str,
) -> str: ...

def write_cosmic_validation_report_md(
    report: CosmicValidationReport,
    output_path: str,
    *,
    formal_excel_written: bool,
    draft_excel_written: bool,
    excel_reason: str,
) -> str: ...
```

`gen_cosmic.py` 用新的结果对象和主入口替换旧 Excel 生成入口：

```python
@dataclass
class CosmicGenerationResult:
    formal_excel_path: str
    formal_excel_written: bool
    draft_excel_path: str
    draft_excel_written: bool
    validation_json_path: str
    validation_report_path: str
    status: str
    cfp_total: float | None
    item_count: int
    blocked_count: int
    warning_count: int


def generate_cosmic_artifacts(
    items: list[CosmicItem],
    template_path: str,
    formal_output_path: str,
    meta_md_path: str = "",
    *,
    md_dir: str = "",
    project_name: str = "",
    cfp_formula: str = "",
    allow_draft_excel_output: bool = False,
) -> CosmicGenerationResult: ...
```

`generate_cosmic_xlsx_from_md(...) -> str` 应删除。所有调用方必须改为读取 `CosmicGenerationResult.formal_excel_written/draft_excel_written/status/cfp_total`，不得再通过目标 Excel 路径判断成功。

`PipelineResult` 建议新增字段：

```python
cosmic_validation_json: str = ""
cosmic_validation_report: str = ""
cosmic_status: str = ""
cosmic_formal_xlsx: str = ""
cosmic_formal_excel_written: bool = False
cosmic_draft_xlsx: str = ""
cosmic_draft_excel_written: bool = False
```

这些字段用于区分“阶段执行完成”“正式 COSMIC Excel 已生成”和“草稿 COSMIC Excel 已生成”。只有 `cosmic_formal_excel_written=True` 且正式文件存在时，才登记为正式 artifact；草稿 Excel 只能登记为草稿 artifact 或仅写入报告。

### 替换策略

本阶段必须遵守以下替换策略：

1. 可以重命名、移动或删除旧函数，只要同步更新调用方、测试和文档。
2. `CosmicItem.warnings` 应删除或停止写入；结构化 `CosmicIssue` 是唯一问题事实源。
3. `write_cosmic_xlsx` 应直接接收校验后的结构化报告或结果列表，避免 Excel 写入绕过校验状态。
4. 推荐签名：

```python
def write_cosmic_xlsx(
    template_path: str,
    output_path: str,
    report: CosmicValidationReport,
    *,
    meta: dict[str, str] | None = None,
    cfp_formula: str = "",
) -> str: ...
```

5. `pipeline._generate_cosmic` 必须使用新入口，不能再调用旧的 `generate_cosmic_xlsx_from_md`。
6. 如果 `blocked`，本轮不得登记正式 artifact；若目标目录存在上一轮残留文件，可以覆盖为草稿、移动到草稿路径，或在报告中明确“本轮未写入正式 Excel”。实现时选择一种清晰策略并补测试。

### 调用流程

`pipeline._generate_cosmic` 第一阶段应调整为以下顺序：

```text
1. 检查 COSMIC Excel 模板。
2. 读取项目名称、FPA 核减后工作量，并写 3.1 MD。
3. 生成 3.2 空白 COSMIC Markdown 模板。
4. 如果有 API Key：
   4.1 调用 AI 生成结构化 `list[CosmicItem]` 或 `CosmicDraft`。
   4.2 由结构化数据导出 3.3 Markdown 审阅稿。
   4.3 调用 generate_cosmic_artifacts。
   4.4 写入 result.cosmic_validation_json / result.cosmic_validation_report / result.cosmic_status。
   4.5 仅当 formal_excel_written=True 时登记正式 cosmic_xlsx artifact，并读取 3.5 CFP 总和。
5. 如果没有 API Key：
   5.1 不调用 AI。
   5.2 基于空 items 生成校验报告，报告必须包含全局 error `NO_COSMIC_ITEMS`。
   5.3 result.cosmic_status=blocked。
   5.4 不登记正式 cosmic_xlsx artifact，不更新 result.cfp_total。
```

`generate_cosmic_artifacts` 内部顺序：

```text
1. 接收结构化 items，不从 Markdown 解析。
2. validate_cosmic_items(items, project_name=project_name, cfp_formula=cfp_formula)。
3. 写 3.3 JSON 草稿。
4. 根据 report.status 和 allow_draft_excel_output 决定是否调用 write_cosmic_xlsx。
5. 如果写正式或草稿 Excel，再按现有逻辑写环境图 sheet。
6. 只有正式写 Excel 且可计算 CFP 时，写 3.5 CFP 总和。
7. 写 3.4 校验报告，说明 Excel 是否写入和原因。
8. 返回 CosmicGenerationResult。
```

Markdown 在新链路中只作为人类可读审阅稿和日志产物。不得再把 Markdown 作为结构化数据主入口；`parse_md_to_items` 可删除，或仅保留给临时排查脚本使用，不能被正式管线调用。

### 数据契约

新增结构化 issue：

```python
CosmicIssue(
    severity="error|warning|info",
    code="FIRST_MOVE_NOT_ENTRY",
    message="第一个子过程必须为输入 E",
    field="movements[0].move_type",
)
```

新增校验结果：

```python
CosmicValidationResult(
    item=cosmic_item,
    status="passed|review_required|blocked",
    issues=[...],
)
```

新增 JSON 草稿产物，路径为：

```text
md/3.3.gen-cosmic-AI填充-COSMIC.json
```

建议顶层结构：

```json
{
  "project": "...",
  "status": "blocked",
  "cfp_basis": {
    "source": "unconfirmed",
    "formula_configured": false,
    "description": "未配置 CFP计算公式，正式 CFP 来源未确认"
  },
  "issues": [],
  "issue_codes": {
    "GENERIC_FUNCTION_USER": 1,
    "MISSING_CFP_FORMULA": 1
  },
  "review_items": [
    {
      "review_id": "global::global::MISSING_CFP_FORMULA::cfp_formula::",
      "scope": "global",
      "item_index": null,
      "code": "MISSING_CFP_FORMULA",
      "severity": "error",
      "message": "未配置 CFP计算公式，不能生成正式 CFP 总和",
      "details": {},
      "confirmation": {
        "status": "unconfirmed",
        "decision": "",
        "note": "",
        "confirmed_by": "",
        "confirmed_at": ""
      }
    }
  ],
  "export_policy": {
    "manual_confirmation_required": true,
    "unconfirmed_review_item_count": 2,
    "formal_excel": {
      "status": "blocked",
      "reason": "存在阻断问题，未写正式 Excel"
    },
    "draft_excel": {
      "status": "blocked",
      "reason": "存在阻断问题，不能写草稿 Excel",
      "requires_config": false,
      "config_key": "gen_cosmic.allow_draft_excel_output"
    }
  },
  "preview_rows": [
    {
      "item_index": 0,
      "module_path": "一级模块 > 二级模块 > 三级模块",
      "module_l1": "一级模块",
      "module_l2": "二级模块",
      "module_l3": "三级模块",
      "process": "提交注册",
      "user": "发起者：用户|接收者：系统",
      "trigger": "用户触发",
      "movement_count": 2,
      "movement_types": ["E", "X"],
      "status": "review_required",
      "issue_count": 1,
      "review_item_ids": ["item::0::GENERIC_FUNCTION_USER::user::"]
    }
  ],
  "items": [
    {
      "module_l1": "...",
      "module_l2": "...",
      "module_l3": "...",
      "user": "...",
      "trigger": "...",
      "process": "...",
      "movements": [],
      "status": "blocked",
      "issues": [],
      "basis": {
        "function_user": {
          "parts": ["操作员", "系统"],
          "matched": false,
          "match_source": "generic_only",
          "matched_term": "",
          "requires_review": true,
          "description": "功能用户仅为泛化角色，未能对应三级模块或最小颗粒度模块"
        },
        "process_semantics": [
          {
            "code": "NON_FUNCTIONAL_SCOPE",
            "matched_terms": ["系统迁移"],
            "description": "功能过程或模块路径疑似非功能内容或技术改造事项，通常不应拆成 COSMIC 功能规模"
          }
        ],
        "movement_semantics": [
          {
            "code": "CONTROL_COMMAND_MOVEMENT",
            "movement_order": 3,
            "matched_terms": ["下一页", "排序"],
            "description": "子过程疑似控制命令，通常不单独计为 COSMIC 数据移动"
          },
          {
            "code": "ERROR_CONFIRMATION_MESSAGE",
            "movement_order": 4,
            "matched_terms": ["错误提示", "确认消息"],
            "description": "子过程疑似错误或确认消息输出，通常需要按手册规则合并识别"
          },
          {
            "code": "INTERNAL_TECHNICAL_BOUNDARY",
            "movement_order": 5,
            "matched_terms": ["后端", "内部接口"],
            "description": "子过程疑似内部技术交互或无效软件边界，需确认是否跨有效 COSMIC 边界"
          }
        ]
      }
    }
  ],
  "summary": {
    "passed": 0,
    "review_required": 0,
    "blocked": 0,
    "errors": 0,
    "warnings": 0,
    "global_errors": 0,
    "global_warnings": 0
  }
}
```

字段约束：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project` | `string` | 是 | 项目名称。 |
| `status` | `string` | 是 | 报告总状态，`passed/review_required/blocked`。 |
| `cfp_basis` | `object` | 是 | CFP 来源说明，`source` 当前为 `template_formula/unconfirmed`。 |
| `issues` | `array` | 是 | 全局 issue，例如无 AI 输出、无功能过程、缺 CFP 公式。 |
| `issue_codes` | `object` | 是 | 报告级 issue code 计数，包含全局 issue 和所有功能过程 issue。 |
| `review_items` | `array` | 是 | 扁平审阅 issue 列表，包含全局 issue 和功能过程 issue；供预览页、筛选、人工确认列表直接消费。 |
| `review_items[].review_id` | `string` | 是 | 稳定审阅项 ID，由 scope、item_index、code、field、movement_order 组成，用于前端保存人工确认状态；组成段内的 `:` 和 `\` 会转义。 |
| `review_items[].item_index` | `number|null` | 是 | 对应 `items` 的 0 基序号；全局 issue 为 `null`。 |
| `review_items[].confirmation` | `object` | 是 | 人工确认状态占位，默认 `status=unconfirmed`。COSMIC 预览页会按 `review_id` 在浏览器本地恢复确认状态，并可导出带确认结果的 JSON；Web session 也提供确认 JSON 保存/读取接口。 |
| `review_items[].confirmation.status` | `string` | 是 | 默认 `unconfirmed`；预览页当前支持 `confirmed/rejected/waived`。 |
| `review_items[].confirmation.decision` | `string` | 是 | 人工确认决定，默认空字符串。 |
| `review_items[].confirmation.note` | `string` | 是 | 人工备注，默认空字符串。 |
| `review_items[].confirmation.confirmed_by` | `string` | 是 | 确认人，默认空字符串。 |
| `review_items[].confirmation.confirmed_at` | `string` | 是 | 确认时间，默认空字符串；后续建议使用 ISO 8601 字符串。 |
| `export_policy` | `object` | 是 | 基于校验状态推导的预览页导出策略；不表示实际 Excel 是否已经写入。 |
| `export_policy.manual_confirmation_required` | `boolean` | 是 | 是否存在需要人工处理的审阅项。 |
| `export_policy.unconfirmed_review_item_count` | `number` | 是 | 默认未确认审阅项数量，等于当前 `review_items` 数量。 |
| `export_policy.formal_excel.status` | `string` | 是 | 正式 Excel 导出策略，当前为 `allowed/blocked`。 |
| `export_policy.formal_excel.reason` | `string` | 是 | 正式 Excel 导出策略原因。 |
| `export_policy.draft_excel.status` | `string` | 是 | 草稿 Excel 导出策略，当前为 `not_needed/eligible/blocked`。 |
| `export_policy.draft_excel.reason` | `string` | 是 | 草稿 Excel 导出策略原因。 |
| `export_policy.draft_excel.requires_config` | `boolean` | 是 | 草稿导出是否依赖 `gen_cosmic.allow_draft_excel_output`。 |
| `export_policy.draft_excel.config_key` | `string` | 是 | 草稿导出配置键，固定为 `gen_cosmic.allow_draft_excel_output`。 |
| `preview_rows` | `array` | 是 | 面向 `/preview/cosmic` 列表页的轻量行模型，由 `items` 和 `review_items` 派生，不作为新的事实源。 |
| `preview_rows[].item_index` | `number` | 是 | 对应 `items` 的 0 基序号。 |
| `preview_rows[].module_path` | `string` | 是 | 由一、二、三级模块拼接得到的模块路径。 |
| `preview_rows[].module_l1/module_l2/module_l3` | `string` | 是 | 模块路径分段，便于前端筛选。 |
| `preview_rows[].process` | `string` | 是 | 新增/修改功能过程。 |
| `preview_rows[].user` | `string` | 是 | 功能用户。 |
| `preview_rows[].trigger` | `string` | 是 | 触发事件。 |
| `preview_rows[].movement_count` | `number` | 是 | 数据移动数量。 |
| `preview_rows[].movement_types` | `array` | 是 | 数据移动类型序列。 |
| `preview_rows[].status` | `string` | 是 | 当前功能过程校验状态。 |
| `preview_rows[].issue_count` | `number` | 是 | 当前功能过程关联 issue 数量。 |
| `preview_rows[].review_item_ids` | `array` | 是 | 当前功能过程关联的 `review_items[].review_id` 列表。 |
| `items` | `array` | 是 | COSMIC 功能过程列表。 |
| `items[].module_l1` | `string` | 是 | 一级模块，允许为空但会触发 `MISSING_MODULE_PATH`。 |
| `items[].module_l2` | `string` | 是 | 二级模块，允许为空但会触发 `MISSING_MODULE_PATH`。 |
| `items[].module_l3` | `string` | 是 | 三级模块，允许为空但会触发 `MISSING_MODULE_PATH`。 |
| `items[].user` | `string` | 是 | 当前阶段使用 `发起者：xxx|接收者：xxx` 格式。 |
| `items[].trigger` | `string` | 是 | 触发事件，允许为空但会触发 `MISSING_TRIGGER`。 |
| `items[].process` | `string` | 是 | 功能过程名称，允许为空但会触发 `MISSING_PROCESS_NAME`。 |
| `items[].movements` | `array` | 是 | 数据移动列表。 |
| `items[].movements[].order` | `number` | 是 | 数据移动序号。 |
| `items[].movements[].sub_process` | `string` | 是 | 子过程描述。 |
| `items[].movements[].move_type` | `string` | 是 | 数据移动类型，标准值为 `E/X/R/W`。 |
| `items[].movements[].data_group` | `string` | 是 | 数据组。 |
| `items[].movements[].data_attrs` | `string` | 是 | 数据属性。 |
| `items[].movements[].reuse` | `string` | 是 | 复用度，标准值先限定为 `新增/复用/利旧`。 |
| `items[].status` | `string` | 是 | `passed/review_required/blocked`。 |
| `items[].issues` | `array` | 是 | 当前功能过程的结构化问题列表。 |
| `items[].basis` | `object` | 是 | 当前功能过程的结构化判定依据。 |
| `items[].basis.function_user` | `object` | 是 | 功能用户匹配依据，记录拆分后的用户、匹配来源、匹配项和是否需要人工确认。 |
| `items[].basis.process_semantics` | `array` | 是 | 疑似非功能内容或技术改造事项的功能过程级语义命中记录。 |
| `items[].basis.movement_semantics` | `array` | 是 | 疑似内部技术交互、控制命令、纯数据运算、技术操作、错误或确认消息的数据移动语义命中记录。 |
| `items[].issues[].severity` | `string` | 是 | `error/warning/info`。 |
| `items[].issues[].code` | `string` | 是 | 稳定问题编码。 |
| `items[].issues[].message` | `string` | 是 | 面向人的说明。 |
| `items[].issues[].field` | `string` | 否 | 字段路径，例如 `movements[0].move_type`。 |
| `items[].issues[].movement_order` | `number|null` | 否 | 问题关联的数据移动序号。 |
| `items[].issues[].details` | `object` | 是 | 结构化依据。语义 warning 当前包含 `matched_terms` 和 `basis_description`；功能用户 warning 当前包含 `function_user_parts`、`match_source`、`matched_term` 和 `basis_description`。 |
| `summary` | `object` | 是 | 汇总数量。 |

JSON 写入必须使用 `ensure_ascii=False` 和稳定缩进，便于人工排查和测试断言。

本阶段可以继续生成 Markdown 审阅稿，但 Excel 写入和 CFP 汇总应优先使用结构化对象和校验结果，不应依赖人工可读 Markdown 作为唯一事实源。

### 确定性校验规则

第一阶段必须实现以下规则：

| code | 级别 | 条件 | 说明 |
| --- | --- | --- | --- |
| `MISSING_TRIGGER` | `error` | `trigger` 为空。 | 功能过程必须由触发事件启动。 |
| `FIRST_MOVE_NOT_ENTRY` | `error` | 存在数据移动，但第一步不是 `E`。 | 首个子过程必须为输入。 |
| `LAST_MOVE_NOT_WRITE_OR_EXIT` | `error` | 存在数据移动，但最后一步不是 `W` 或 `X`。 | 末个子过程必须写入或输出。 |
| `TOO_FEW_MOVEMENTS` | `error` | 数据移动少于 2 个。 | 一个功能过程至少包含两个子过程及相应数据移动。 |
| `MISSING_MODULE_PATH` | `error` | 一级、二级或三级模块任一为空。 | 功能过程必须完全归属到单一模块路径。 |
| `MISSING_PROCESS_NAME` | `error` | 功能过程名称为空。 | 功能过程必须可识别。 |
| `EMPTY_DATA_GROUP` | `warning` | 任一数据移动的数据组为空。 | 需要人工补充或确认兴趣对象数据组。 |
| `EMPTY_DATA_ATTRS` | `warning` | 任一数据移动的数据属性为空。 | 需要人工补充或确认数据属性。 |
| `NON_STANDARD_MOVE_TYPE` | `warning` | 移动类型不是 `E/X/R/W`。 | 可以复用现有模糊匹配逻辑，但必须保留提示。 |
| `NO_API_KEY` | `error` | 未设置 API Key，未调用 AI。 | 生成期原因，说明为什么没有调用 AI。 |
| `AI_GENERATION_FAILED` | `error` | AI 生成过程抛出异常。 | 生成期原因，异常信息会写入 message。 |
| `AI_GENERATION_EMPTY` | `error` | AI 调用结束但返回空功能过程列表。 | 生成期原因，常见于 AI 全部失败、全部跳过或解析为空。 |
| `AI_LIMIT_SKIPPED_ALL` | `error` | 配置限制导致 AI 未处理任何三级模块。 | 生成期原因，常见于 AI 数量限制配置过小。 |
| `AI_L3_LIMIT_PARTIAL_SKIP` | `warning` | 三级模块数量限制导致部分模块跳过。 | 生成期原因，默认进入待审状态。 |
| `AI_PROCESS_LIMIT_PARTIAL_SKIP` | `warning` | 功能过程数量限制导致部分模块跳过。 | 生成期原因，默认进入待审状态。 |
| `NO_L3_MODULES` | `error` | 模块树没有三级模块。 | 生成期原因，说明没有可生成 COSMIC 的最小模块。 |
| `USER_ABORTED_GENERATION` | `warning/error` | 交互模式下用户主动终止生成。 | 有可校验结果时为 warning；没有结果时为 error。 |
| `PARTIAL_AI_FAILURE` | `warning` | 部分模块 AI 生成失败但仍有可校验结果。 | 生成期原因，默认进入待审状态。 |
| `NO_COSMIC_ITEMS` | `error` | `items` 为空。 | 最终结果没有可送审的 COSMIC 功能过程。 |
| `MISSING_CFP_FORMULA` | `error` | 模板或元数据中未取得 `CFP计算公式`。 | 无法可靠写入正式 CFP 和下游 `gen-list` 所需 CFP 总和。 |
| `GENERIC_FUNCTION_USER` | `warning` | 功能用户无法匹配三级模块、最小颗粒度模块或元数据规则结果；或只匹配到一/二级模块。 | 第一阶段不自动修复，但必须在 `items[].basis.function_user` 和 `items[].issues[].details` 中提示人工确认功能用户口径。 |
| `NON_FUNCTIONAL_SCOPE` | `warning` | 模块路径或功能过程命中系统迁移、前端适配、环境扩容、架构/组件改造等非功能或技术改造事项。 | 非功能内容通常不确认 COSMIC 功能规模，进入待审。 |
| `CONTROL_COMMAND_MOVEMENT` | `warning` | 子过程命中上一页、下一页、排序、展示/隐藏菜单、点击确认等控制命令。 | 控制命令通常不移动兴趣对象数据，进入待审。 |
| `DATA_OPERATION_ONLY_MOVEMENT` | `warning` | 子过程命中格式化、校验、统计、连接数据库等数据运算或技术操作。 | 通常应归入相关数据移动或不单独计列，进入待审。 |
| `ERROR_CONFIRMATION_MESSAGE` | `warning` | 子过程命中错误提示、确认消息、成功/失败提示等消息输出。 | 错误或确认消息通常需要按手册规则合并识别，进入待审。 |
| `INTERNAL_TECHNICAL_BOUNDARY` | `warning` | 子过程命中前端/后端、前台/后台、内部接口、临时接口、微服务等内部技术交互。 | 内部技术交互通常不构成 COSMIC 有效边界，进入待审。 |

状态归并规则：

1. 任一 item issue 为 `error` 时，该功能过程状态为 `blocked`。
2. item 没有 `error` 但有 `warning` 时，该功能过程状态为 `review_required`。
3. item 没有 `error` 和 `warning` 时，该功能过程状态为 `passed`。
4. 任一全局 issue 为 `error` 时，报告总状态为 `blocked`。
5. 没有全局 `error`、没有 blocked item，但存在任一全局 `warning` 或 review_required item 时，报告总状态为 `review_required`。
6. 没有全局 issue 且所有 item 为 `passed` 时，报告总状态为 `passed`。

校验器实现顺序应保持确定性，便于测试和报告阅读：

```python
def validate_cosmic_item(item: CosmicItem) -> CosmicValidationResult:
    issues = []
    module_path = " > ".join(
        part for part in [item.module_l1, item.module_l2, item.module_l3] if part
    )

    if not item.module_l1 or not item.module_l2 or not item.module_l3:
        issues.append(error("MISSING_MODULE_PATH", "功能过程必须归属到完整的一、二、三级模块路径", "module_path"))

    if not item.process:
        issues.append(error("MISSING_PROCESS_NAME", "功能过程名称不能为空", "process"))

    if not item.trigger:
        issues.append(error("MISSING_TRIGGER", "功能过程必须由触发事件启动", "trigger"))

    if basis.function_user.requires_review:
        issues.append(warning("GENERIC_FUNCTION_USER", "功能用户未能对应三级模块、最小颗粒度模块或元数据规则结果", "user"))

    if len(item.movements) < 2:
        issues.append(error("TOO_FEW_MOVEMENTS", "一个功能过程至少包含两个子过程及相应数据移动", "movements"))

    if item.movements:
        first = item.movements[0]
        last = item.movements[-1]
        if first.move_type != "E":
            issues.append(error("FIRST_MOVE_NOT_ENTRY", "第一个子过程必须为输入 E", "movements[0].move_type", first.order))
        if last.move_type not in {"W", "X"}:
            issues.append(error("LAST_MOVE_NOT_WRITE_OR_EXIT", "最后一个子过程必须为写 W 或输出 X", f"movements[{len(item.movements)-1}].move_type", last.order))

    for index, movement in enumerate(item.movements):
        if movement.move_type not in {"E", "X", "R", "W"}:
            issues.append(warning("NON_STANDARD_MOVE_TYPE", "移动类型不是标准 E/X/R/W", f"movements[{index}].move_type", movement.order))
        if not movement.data_group:
            issues.append(warning("EMPTY_DATA_GROUP", "数据组不能为空", f"movements[{index}].data_group", movement.order))
        if not movement.data_attrs:
            issues.append(warning("EMPTY_DATA_ATTRS", "数据属性不能为空", f"movements[{index}].data_attrs", movement.order))

    return CosmicValidationResult(item=item, status=merge_status(issues), issues=issues)
```

实现时可以不逐字复制该伪代码，但必须保持 issue code、severity 和状态归并规则一致。

`validate_cosmic_items` 必须先执行全局校验：

```python
def validate_cosmic_items(items: list[CosmicItem], *, project_name: str = "", cfp_formula: str = "") -> CosmicValidationReport:
    issues = []
    if not items:
        issues.append(error("NO_COSMIC_ITEMS", "没有可送审的 COSMIC 功能过程", "items", scope="global"))
    if not cfp_formula:
        issues.append(error("MISSING_CFP_FORMULA", "未配置 CFP计算公式，不能生成正式 CFP 总和", "cfp_formula", scope="global"))
    results = [validate_cosmic_item(item) for item in items]
    return build_report(project_name, results, issues)
```

### 输出策略

第一阶段输出策略如下：

| 场景 | 输出行为 |
| --- | --- |
| 全部 `passed` | 生成 JSON 草稿、Markdown 审阅稿、正式 COSMIC Excel 和 CFP 总和。 |
| 存在 `review_required`，无 `blocked` | 生成 JSON 草稿、Markdown 审阅稿和校验报告；只有 `allow_draft_excel_output=true` 时写草稿 Excel，不写正式 Excel。 |
| 存在 `blocked` | 生成 JSON 草稿和校验报告；默认不写正式 COSMIC Excel，不更新可被下游误用的 CFP 总和。 |
| 无 API Key 或 AI 全部失败 | 生成模板、JSON 草稿或校验报告，状态应反映缺少可送审数据；不得伪装为成功正式输出。 |

如需允许存在待审问题时写出草稿 Excel，可新增配置项，例如：

```yaml
gen_cosmic:
  allow_draft_excel_output: false
```

当 `allow_draft_excel_output=true` 时，可以写入带批注和黄色标记的草稿 Excel；但日志、报告和返回结果必须明确标识其不是正式送审结果。草稿路径建议使用正式路径同目录的独立文件名，例如 `项目功能点拆分表-草稿.xlsx`，不得覆盖正式路径。

配置读取规则：

1. 默认值必须为 `false`。
2. 配置缺失时按 `false` 处理，不应改变当前生产安全策略。
3. 配置读取只保留一种标准结构，建议实现为 `load_gen_cosmic_allow_draft_excel_output() -> bool`：

```yaml
gen_cosmic:
  allow_draft_excel_output: false
```

4. 不再新增扁平 key 兜底。
5. 文档、日志和校验报告中应统一称为“草稿 Excel 输出”，不要称为“正式 Excel”。

### 校验报告

新增人工可读校验报告，路径为：

```text
md/3.4.gen-cosmic-校验报告.md
```

报告至少包含：

1. 项目名称。
2. 总体状态汇总。
3. 按模块路径和功能过程列出的 issue。
4. 每个 issue 的 `severity`、`code`、字段位置、说明和结构化依据。
5. 对 Excel 输出策略的说明，例如“存在阻断问题，未写正式 Excel”。

建议报告格式：

```markdown
# gen-cosmic 校验报告

## 汇总

- 项目：xxx
- 总状态：blocked
- 功能过程数：10
- 通过：6
- 待审：2
- 阻断：2
- error：3
- warning：5
- issue code：FIRST_MOVE_NOT_ENTRY=1、GENERIC_FUNCTION_USER=2
- 正式 Excel 输出：未写入
- 草稿 Excel 输出：未写入
- 原因：存在阻断问题

## 问题明细

### 系统管理 > 用户管理 > 用户新增 / 新增用户

| 级别 | code | 字段 | 数据移动序号 | 说明 | 依据 |
| --- | --- | --- | --- | --- | --- |
| error | `FIRST_MOVE_NOT_ENTRY` | `movements[0].move_type` | 1 | 第一个子过程必须为输入 E |  |
```

报告中不使用“功能点类型”“说明详情”等 FPA 禁用同义词。`/preview/cosmic` 已提供基于结构化 JSON 的最小审阅页，用户可加载 COSMIC JSON 草稿、查看功能过程/数据移动/审阅项、编辑人工确认状态和备注，并导出带确认结果的 JSON。浏览器会按当前项目和 `review_id` 集合本地恢复确认状态；后端 session 接口 `GET/PUT /api/sessions/{session_id}/cosmic/confirmation` 可保存和读取 `cosmic-confirmation.json`。页面用户可见文案必须遵循 [`docs/fpa/result-review-terminology.md`](../fpa/result-review-terminology.md) 中的 COSMIC 审阅术语映射。

### CFP 处理

第一阶段不重新定义全部 CFP 业务口径，但必须消除静默不一致：

1. 如果存在 `blocked`，不得更新供 `gen-list` 使用的正式 CFP 总和。
2. 如果模板未配置 `CFP计算公式`，必须记录 `MISSING_CFP_FORMULA` error，报告总状态为 `blocked`，不能静默留空后继续汇总。
3. `CosmicItem.total_cfp()` 中 `复用 = 1/3` 的逻辑不得继续扩散到新链路；新链路已经在 JSON 草稿和校验报告中记录 CFP 来源为模板公式或未确认。
4. 正式 Excel 中的 CFP 仍以模板公式为准，Python 侧只负责结构化记录和异常提示。

### 验收标准

第一阶段完成后，应满足以下验收标准：

1. 对首步非 `E`、末步非 `W/X`、少于两个数据移动、缺少触发事件、缺少模块路径、缺少功能过程名称的样例，校验器能产生 `error`。
2. 对缺少数据组、缺少数据属性、非标准移动类型的样例，校验器能产生 `warning`。
3. 状态归并结果符合 `passed/review_required/blocked` 规则。
4. 生成链路会产出 `md/3.3.gen-cosmic-AI填充-COSMIC.json`。
5. 存在 `blocked` 时默认不写正式 COSMIC Excel，且不更新正式 CFP 总和。
6. 校验报告能说明阻断原因和对应字段。
7. 既有无阻断样例仍能生成 COSMIC Excel。
8. `review_required` 且 `allow_draft_excel_output=true` 时，只写草稿 Excel，不登记正式 artifact。
9. `items=[]` 时产生全局 `NO_COSMIC_ITEMS` error，报告总状态为 `blocked`。
10. 缺少 `CFP计算公式` 时产生全局 `MISSING_CFP_FORMULA` error，报告总状态为 `blocked`。
11. Python 测试使用项目虚拟环境运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cosmic_validator.py
.\.venv\Scripts\python.exe -m pytest
```

### 测试矩阵

新增 `tests/test_cosmic_validator.py`，建议至少包含以下用例：

| 测试名 | 输入构造 | 断言 |
| --- | --- | --- |
| `test_passed_item_has_no_issues` | 完整模块路径、触发事件、两步数据移动 `E -> X`，数据组和属性齐全。 | 状态为 `passed`，issues 为空。 |
| `test_missing_trigger_is_error` | `trigger=""`。 | 包含 `MISSING_TRIGGER`，状态为 `blocked`。 |
| `test_first_move_must_be_entry` | 第一条 movement 为 `R`。 | 包含 `FIRST_MOVE_NOT_ENTRY`，字段为 `movements[0].move_type`。 |
| `test_last_move_must_be_write_or_exit` | 最后一条 movement 为 `R`。 | 包含 `LAST_MOVE_NOT_WRITE_OR_EXIT`。 |
| `test_too_few_movements_is_error` | movement 数量为 0 或 1。 | 包含 `TOO_FEW_MOVEMENTS`。 |
| `test_missing_module_path_is_error` | `module_l3=""`。 | 包含 `MISSING_MODULE_PATH`。 |
| `test_missing_process_name_is_error` | `process=""`。 | 包含 `MISSING_PROCESS_NAME`。 |
| `test_empty_data_group_is_warning` | 任一 movement 的 `data_group=""`。 | 包含 `EMPTY_DATA_GROUP`，状态为 `review_required`。 |
| `test_empty_data_attrs_is_warning` | 任一 movement 的 `data_attrs=""`。 | 包含 `EMPTY_DATA_ATTRS`，状态为 `review_required`。 |
| `test_non_standard_move_type_is_warning` | movement 的 `move_type="输入"`。 | 包含 `NON_STANDARD_MOVE_TYPE`。 |
| `test_control_command_movement_requires_review` | 子过程命中下一页、排序等控制命令。 | 包含 `CONTROL_COMMAND_MOVEMENT`，状态为 `review_required`，写入 `basis.movement_semantics`。 |
| `test_data_operation_only_movement_requires_review` | 子过程命中格式化、校验等数据运算。 | 包含 `DATA_OPERATION_ONLY_MOVEMENT`，状态为 `review_required`，写入 `basis.movement_semantics`。 |
| `test_error_confirmation_message_requires_review` | 子过程命中错误提示、确认消息。 | 包含 `ERROR_CONFIRMATION_MESSAGE`，状态为 `review_required`，写入 `basis.movement_semantics`。 |
| `test_internal_technical_boundary_requires_review` | 子过程命中后端、内部接口、微服务等内部技术交互。 | 包含 `INTERNAL_TECHNICAL_BOUNDARY`，状态为 `review_required`，写入 `basis.movement_semantics`。 |
| `test_non_functional_scope_requires_review` | 模块或功能过程命中系统迁移、扩容、架构改造等非功能/技术事项。 | 包含 `NON_FUNCTIONAL_SCOPE`，状态为 `review_required`，写入 `basis.process_semantics`。 |
| `test_error_wins_over_warning` | 同时缺触发事件和缺数据属性。 | 状态为 `blocked`。 |
| `test_report_summary_counts_status_and_severity` | 三个 item 分别为 passed/review_required/blocked。 | summary 和 `issue_codes` 数量正确。 |
| `test_report_json_is_stable_and_chinese_readable` | 写 JSON 到临时目录。 | 文件为 UTF-8，包含未转义中文、`summary` 和 `issue_codes`。 |
| `test_report_json_includes_flat_review_items` | 同时存在全局 issue 和功能过程 issue。 | `review_items` 扁平列出全部 issue，包含 `review_id`、`scope`、`item_index` 和 `details`。 |
| `test_empty_items_is_global_error` | `items=[]`。 | report 包含 `NO_COSMIC_ITEMS`，总状态为 `blocked`。 |
| `test_missing_cfp_formula_is_global_error` | `cfp_formula=""`。 | report 包含 `MISSING_CFP_FORMULA`，总状态为 `blocked`。 |
| `test_generic_function_user_is_warning` | 功能用户只包含泛化角色。 | 包含 `GENERIC_FUNCTION_USER`，状态为 `review_required`，`basis.function_user.match_source=generic_only`，issue details 包含功能用户拆分和匹配来源。 |
| `test_module_context_without_l3_user_requires_review` | 功能用户只匹配一级或二级模块，不匹配三级模块。 | 包含 `GENERIC_FUNCTION_USER`，状态为 `review_required`，`basis.function_user.match_source=module_context_only`。 |

调整或新增集成测试：

| 文件 | 用例 | 断言 |
| --- | --- | --- |
| `tests/test_pipeline.py` | `gen-cosmic` 在 AI 返回有效数据且无 warning/error 时。 | 生成 JSON 草稿、校验报告、正式 Excel，`result.cosmic_formal_excel_written is True`。 |
| `tests/test_pipeline.py` | `gen-cosmic` 无 API Key 时。 | `result.cosmic_status == "blocked"`，不登记正式 cosmic artifact，不更新 `cfp_total`。 |
| `tests/test_pipeline.py` | AI 返回空 movement 时。 | 写校验报告，默认不写正式 Excel。 |
| `tests/test_pipeline.py` | 仅存在 warning 且开启 `allow_draft_excel_output`。 | `result.cosmic_draft_excel_written is True`，`result.cosmic_formal_excel_written is False`。 |
| `tests/test_cosmic_md.py` | 结构化 items 导出 Markdown 审阅稿。 | Markdown 只作为审阅产物，不参与正式管线输入。 |
| `tests/test_models.py` | 按新模型调整 `CosmicItem.to_rows()` 或移除已失效断言。 | 模型测试表达当前目标行为。 |

如现有 `mock_ai` 无法稳定构造 COSMIC 数据，应新增专用 fixture，直接 mock `generate_cosmic_items` 返回结构化 items，避免集成测试依赖大模型文本格式。

### 实施步骤拆分

建议按以下顺序提交代码，任一步失败都能单独回滚：

1. 新增 `cosmic_validator.py` 和 `tests/test_cosmic_validator.py`，只依赖现有 `CosmicItem/DataMovement`，不接入管线。
2. 新增 JSON 和 Markdown 报告写出函数，补充文件写入测试。
3. 在 `gen_cosmic.py` 新增 `CosmicGenerationResult` 和 `generate_cosmic_artifacts`，删除旧 `generate_cosmic_xlsx_from_md`。
4. 修改 `pipeline._generate_cosmic` 使用新入口，补充 `PipelineResult` 字段。
5. 调整 Excel 写入策略：`blocked` 默认不写正式 Excel，`review_required` 受 `allow_draft_excel_output` 控制。
6. 调整 CFP 写入策略：只有正式 Excel 写入成功时才写 `3.5.gen-cosmic-CFP-总和.md`。
7. 更新集成测试和相关文档。

每一步完成后至少运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cosmic_validator.py
```

第 4 步之后还应运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py
```

最终运行：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### 完成定义

第一阶段只有同时满足以下条件，才视为实施完成：

1. 校验器、JSON 草稿、Markdown 校验报告均已落地。
2. 管线能区分 `passed/review_required/blocked`，并把状态写入 `PipelineResult`。
3. `blocked` 默认不会写正式 Excel，也不会更新正式 CFP 总和。
4. `review_required` 默认不会写正式 Excel；开启 `allow_draft_excel_output` 后只写草稿 Excel。
5. 既有可通过样例仍能生成正式 Excel。
6. 单元测试和集成测试覆盖主要状态分支。
7. 本文档和 [`gen-cosmic-improvement-plan.md`](gen-cosmic-improvement-plan.md) 未出现互相矛盾的目标行为。

### 后续阶段边界

以下内容不属于第一阶段验收范围：

1. `/preview/cosmic` 页面实现。
2. 人工编辑和确认状态流转。
3. 控制命令、数据运算、内部技术步骤、非功能事项的自动过滤。
4. 功能用户和三级模块的一对一强绑定自动修复；第一阶段必须先产生 `GENERIC_FUNCTION_USER` warning。
5. `复用`、`利旧`、优化未改子过程 CFP 为 `0` 的完整配置化。

这些内容应在结构化草稿和校验器稳定后，再按 [`gen-cosmic-improvement-plan.md`](gen-cosmic-improvement-plan.md) 分阶段实施。
