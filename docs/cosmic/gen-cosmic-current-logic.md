# gen-cosmic 当前逻辑

## 文档定位

本文同时承担两类用途：

1. 说明当前 `gen-cosmic` 的真实实现逻辑、产物和风险。
2. 明确第一阶段可实施范围，作为后续修改代码、文档和测试的验收依据。

更完整的中长期改造路线见 [`gen-cosmic-improvement-plan.md`](gen-cosmic-improvement-plan.md)。本文中的“第一阶段实施规格”优先约束下一轮实现；未纳入第一阶段的内容只作为风险和后续方向，不应在实现时隐含扩大范围。

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

## 与软评填报参考手册2024的差距

参考文档：`F:\mlt\mlt-docs\AI-Gen-Reimbursement-Docs\02.亚伟需求沟通\软评填报参考手册2024.pdf`。

该手册要求的核心口径是：需求说明书、软件功能清单、COSMIC 工作量拆分共同支撑送审；需求说明书的详细功能说明要按系统功能架构图层级下钻，并能对应拆分表的一、二、三级模块；COSMIC 拆分表要按功能用户需求、触发事件、功能过程、数据组、数据移动和 CFP 规则填报。

当前 `gen-cosmic` 和手册存在以下差距。

### 功能用户口径不足

手册要求：功能过程的数据发送者或预期接收者之一必须对应功能架构图上的最小颗粒度模块，用于区分功能过程所属模块，并且功能用户与功能过程是一对一关系。

当前实现：`cosmic_ai._build_user` 主要依赖元数据中的默认值和关键词规则生成 `发起者/接收者`，不保证其中一端一定对应三级模块，也不验证功能用户与功能过程的一对一关系。

影响：可能生成泛化用户，如 `操作员`、`管理模块`，但无法满足送审材料中“绑定最小颗粒度模块”的要求。

### 必填规则仅作为 warning

手册要求：

1. 一个功能过程必须完全属于某一层、某一个软件块的度量范围。
2. 功能过程不能对应多个模块。
3. 功能过程必须由触发事件启动。
4. 第一个子过程必须为输入 `E`。
5. 最后一个子过程必须为写 `W` 或输出 `X`。
6. 一个功能过程至少包含两个子过程及相应的数据移动。

当前实现：首步 `E`、末步 `W/X`、至少两步等规则只进入 `warnings`，仍会继续写入 Markdown 和 Excel；跨模块归属没有明确校验；缺少触发事件时也没有阻断。

影响：当前输出更适合作为草稿，不足以作为已满足送审规则的结果。

### CFP 和复用口径待确认

手册说明：每个子过程对应一个功能点，CFP 默认 1；优化功能需要填写完整子过程，不涉及修改的子过程 CFP 填 0；设计院会根据材料和评估规则更正为新增、复用、利旧。

当前实现：

1. `CosmicItem.total_cfp()` 中 `复用` 按 `1/3` 计，其他按 `1` 计。
2. Excel 写入时 CFP 列主要依赖模板中的 `CFP计算公式`，未配置公式时 CFP 留空。
3. `利旧`、优化未改子过程填 `0` 的规则没有进入模型层。

影响：代码内 CFP 汇总、Excel 公式、手册送审口径之间可能不一致，尤其是 `复用`、`利旧`、`0` 的处理。

### 边界识别规则缺失

手册说明：前端/后端、前台/后台交互不识别为边界；跨越边界的数据移动通常体现在功能用户、外部系统、持久存储等之间。

当前实现：AI prompt 和后置校验没有明确阻止模型把前端/后端、前台/后台交互拆成数据移动，也没有检查“内部接口是否为已开发接口”。

影响：AI 可能把内部技术交互、微服务交互、临时开发接口误计为 COSMIC 数据移动，导致过度拆分。

### 数据运算和无数据移动子过程过滤不足

手册说明：数据格式化、操作提交、校验、分析、统计等通常归入相关数据移动的数据运算，不单独识别为数据移动；连接数据库、连接服务器、建立容器等不应作为数据移动子过程。

当前实现：只做数据属性数量、移动类型、首尾步骤等基础检查，没有专门过滤“校验/统计/分析/连接数据库”等无数据移动子过程。

影响：AI 可能把运算步骤或技术准备步骤写成独立子过程，导致 CFP 虚高。

### 控制命令过滤缺失

手册说明：上一页、下一页、排序、展示/隐藏菜单、点击 `OK` 确认前一操作等控制命令不移动兴趣对象数据，应被忽略。

当前实现：没有针对控制命令的 prompt 约束或后置过滤。

影响：页面交互类需求容易被拆出不应计列的数据移动。

### 错误和确认消息规则未细化

手册说明：错误/确认消息通常可归为一个输出；但因持久数据读或写而接收到的错误提示不单独识别；操作系统发布的错误消息等不应识别。

当前实现：没有区分业务错误/确认输出、持久化读写错误、系统错误消息。

影响：AI 可能多计或漏计错误/确认类输出。

### 非功能部分边界不足

手册说明：非功能部分 COSMIC 无法评估，只检查是否包含于 COSMIC 开发里，对工作量不进行确认。多系统联调、系统迁移、前端适配、软硬件环境扩容、架构及组件改造等应与 COSMIC 功能规模区分。

当前实现：`gen-cosmic` 基于模块树直接生成，缺少非功能内容识别和剔除机制。

影响：如果模块树中混入非功能或技术改造事项，AI 可能将其误拆为功能过程。

## 当前风险和重构关注点

1. 数据契约绕行 Markdown：AI 结果先写 Markdown，再解析回对象，容易受格式变更影响。
2. 失败不阻断：AI 失败或超过限制时会产生空占位，最终 Excel 可能包含没有数据移动的功能过程。
3. 质量问题只提示：warning 主要进入日志、Markdown 和 Excel 批注，不作为硬性校验。
4. CFP 依赖公式和重算：如果公式缺失、写入失败或 Excel 未重算，下游读取到的 CFP 可能不准确。
5. 预览模型缺失：目前没有稳定的 COSMIC 预览、人工审阅、确认、错误边界数据结构。
6. 解析格式敏感：`parse_md_to_items` 依赖固定标题和表格结构，不适合承载复杂人工编辑。
7. 送审规则未工程化：软评填报参考手册中的硬性口径尚未完整进入 prompt、结构化校验和结果状态。

后续如果要实现 COSMIC 预览或审阅页，应先稳定核心输入/输出模型，再决定是否复用 FPA 的审阅抽象。

## 第一阶段实施规格

第一阶段目标是把当前“生成草稿后直接写 Excel”的链路，改造成“先生成结构化草稿，再执行确定性规则校验，再决定是否允许正式输出”的链路。

本阶段不实现 `/preview/cosmic` 审阅页，不重写整套 AI 生成策略，不一次性覆盖所有《软评填报参考手册2024》启发式规则。页面审阅、人工编辑、内部接口边界识别、非功能内容自动剔除、控制命令语义过滤等内容进入后续阶段。

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
| `ai_gen_reimbursement_docs/gen_cosmic.py` | 在 Markdown 解析为 `CosmicItem` 后调用校验器，生成 JSON 草稿和校验报告。 |
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
```

新增函数：

```python
def validate_cosmic_item(item: CosmicItem) -> CosmicValidationResult: ...

def validate_cosmic_items(
    items: list[CosmicItem],
    *,
    project_name: str = "",
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
    excel_written: bool,
    excel_reason: str,
) -> str: ...
```

`gen_cosmic.py` 用新的结果对象和主入口替换旧 Excel 生成入口：

```python
@dataclass
class CosmicGenerationResult:
    output_path: str
    excel_written: bool
    validation_json_path: str
    validation_report_path: str
    status: str
    cfp_total: float | None
    item_count: int
    blocked_count: int
    warning_count: int


def generate_cosmic_artifacts_from_md(
    md_path: str,
    template_path: str,
    output_path: str,
    meta_md_path: str = "",
    *,
    md_dir: str = "",
    project_name: str = "",
    cfp_formula: str = "",
    allow_draft_excel_output: bool = False,
) -> CosmicGenerationResult: ...
```

`generate_cosmic_xlsx_from_md(...) -> str` 应删除，或直接改为上述新签名和返回对象。所有调用方必须改为读取 `CosmicGenerationResult.excel_written/status/cfp_total`，不得再通过目标 Excel 路径判断成功。

`PipelineResult` 建议新增字段：

```python
cosmic_validation_json: str = ""
cosmic_validation_report: str = ""
cosmic_status: str = ""
cosmic_excel_written: bool = False
```

这些字段用于区分“阶段执行完成”和“正式 COSMIC Excel 已生成”。`result.cosmic_xlsx` 可以继续保存目标路径，但只有 `cosmic_excel_written=True` 且文件存在时，才登记为正式 artifact。

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
   4.1 复制模板为 3.3 Markdown。
   4.2 调用 AI 填充 3.3 Markdown。
   4.3 调用 generate_cosmic_artifacts_from_md。
   4.4 写入 result.cosmic_validation_json / result.cosmic_validation_report / result.cosmic_status。
   4.5 仅当 excel_written=True 时登记 cosmic_xlsx artifact，并读取 3.5 CFP 总和。
5. 如果没有 API Key：
   5.1 不调用 AI。
   5.2 基于空模板或空 items 生成校验报告。
   5.3 result.cosmic_status=blocked。
   5.4 不登记正式 cosmic_xlsx artifact，不更新 result.cfp_total。
```

`generate_cosmic_artifacts_from_md` 内部顺序：

```text
1. parse_md_to_items(md_path)。
2. validate_cosmic_items(items, project_name=project_name)。
3. 写 3.3 JSON 草稿。
4. 根据 report.status 和 allow_draft_excel_output 决定是否调用 write_cosmic_xlsx。
5. 如果写 Excel，再按现有逻辑写环境图 sheet。
6. 只有正式写 Excel 且可计算 CFP 时，写 3.5 CFP 总和。
7. 写 3.4 校验报告，说明 Excel 是否写入和原因。
8. 返回 CosmicGenerationResult。
```

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
      "issues": []
    }
  ],
  "summary": {
    "passed": 0,
    "review_required": 0,
    "blocked": 0,
    "errors": 0,
    "warnings": 0
  }
}
```

字段约束：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project` | `string` | 是 | 项目名称。 |
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
| `items[].issues[].severity` | `string` | 是 | `error/warning/info`。 |
| `items[].issues[].code` | `string` | 是 | 稳定问题编码。 |
| `items[].issues[].message` | `string` | 是 | 面向人的说明。 |
| `items[].issues[].field` | `string` | 否 | 字段路径，例如 `movements[0].move_type`。 |
| `items[].issues[].movement_order` | `number|null` | 否 | 问题关联的数据移动序号。 |
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

状态归并规则：

1. 任一 issue 为 `error` 时，功能过程状态为 `blocked`。
2. 没有 `error` 但有 `warning` 时，状态为 `review_required`。
3. 没有 `error` 和 `warning` 时，状态为 `passed`。

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

### 输出策略

第一阶段输出策略如下：

| 场景 | 输出行为 |
| --- | --- |
| 全部 `passed` | 生成 JSON 草稿、Markdown 审阅稿、正式 COSMIC Excel 和 CFP 总和。 |
| 存在 `review_required`，无 `blocked` | 生成 JSON 草稿、Markdown 审阅稿和校验报告；是否写 Excel 由显式配置控制。 |
| 存在 `blocked` | 生成 JSON 草稿和校验报告；默认不写正式 COSMIC Excel，不更新可被下游误用的 CFP 总和。 |
| 无 API Key 或 AI 全部失败 | 生成模板、JSON 草稿或校验报告，状态应反映缺少可送审数据；不得伪装为成功正式输出。 |

如需允许存在待审问题时写出草稿 Excel，可新增配置项，例如：

```yaml
gen_cosmic:
  allow_draft_excel_output: false
```

当 `allow_draft_excel_output=true` 时，可以写入带批注和黄色标记的草稿 Excel；但日志、报告和返回结果必须明确标识其不是正式送审结果。

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
4. 每个 issue 的 `severity`、`code`、字段位置和说明。
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
- Excel 输出：未写入正式 Excel
- 原因：存在阻断问题

## 问题明细

### 系统管理 > 用户管理 > 用户新增 / 新增用户

| 级别 | code | 字段 | 数据移动序号 | 说明 |
| --- | --- | --- | --- | --- |
| error | `FIRST_MOVE_NOT_ENTRY` | `movements[0].move_type` | 1 | 第一个子过程必须为输入 E |
```

报告中不使用“功能点类型”“说明详情”等 FPA 禁用同义词。COSMIC 审阅页尚未实现，本阶段报告里的业务对象统一称为“功能过程”“数据移动”“数据移动类型”“计算依据说明”。

### CFP 处理

第一阶段不重新定义全部 CFP 业务口径，但必须消除静默不一致：

1. 如果存在 `blocked`，不得更新供 `gen-list` 使用的正式 CFP 总和。
2. 如果模板未配置 `CFP计算公式`，必须记录 `warning` 或 `error`，不能静默留空后继续汇总。
3. `CosmicItem.total_cfp()` 中 `复用 = 1/3` 的逻辑不得继续扩散到新链路；新链路应记录 CFP 来源为模板公式、人工覆盖或未确认。
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
8. Python 测试使用项目虚拟环境运行：

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
| `test_error_wins_over_warning` | 同时缺触发事件和缺数据属性。 | 状态为 `blocked`。 |
| `test_report_summary_counts_status_and_severity` | 三个 item 分别为 passed/review_required/blocked。 | summary 数量正确。 |
| `test_report_json_is_stable_and_chinese_readable` | 写 JSON 到临时目录。 | 文件为 UTF-8，包含未转义中文和 `summary`。 |

调整或新增集成测试：

| 文件 | 用例 | 断言 |
| --- | --- | --- |
| `tests/test_pipeline.py` | `gen-cosmic` 在 AI 返回有效数据时。 | 生成 JSON 草稿、校验报告、Excel，`result.cosmic_excel_written is True`。 |
| `tests/test_pipeline.py` | `gen-cosmic` 无 API Key 时。 | `result.cosmic_status == "blocked"`，不登记正式 cosmic artifact，不更新 `cfp_total`。 |
| `tests/test_pipeline.py` | AI 返回空 movement 时。 | 写校验报告，默认不写正式 Excel。 |
| `tests/test_cosmic_md.py` | Markdown 解析后接校验器。 | 解析出的 item 可被校验器识别问题。 |
| `tests/test_models.py` | 按新模型调整 `CosmicItem.to_rows()` 或移除已失效断言。 | 模型测试表达当前目标行为。 |

如现有 `mock_ai` 无法稳定构造 COSMIC 数据，应新增专用 fixture，直接 mock `generate_cosmic_items` 或 `parse_md_to_items`，避免集成测试依赖大模型文本格式。

### 实施步骤拆分

建议按以下顺序提交代码，任一步失败都能单独回滚：

1. 新增 `cosmic_validator.py` 和 `tests/test_cosmic_validator.py`，只依赖现有 `CosmicItem/DataMovement`，不接入管线。
2. 新增 JSON 和 Markdown 报告写出函数，补充文件写入测试。
3. 在 `gen_cosmic.py` 新增 `CosmicGenerationResult` 和 `generate_cosmic_artifacts_from_md`，删除或改造旧 `generate_cosmic_xlsx_from_md`。
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
4. `review_required` 默认不会写正式 Excel；开启 `allow_draft_excel_output` 后才写草稿 Excel。
5. 既有可通过样例仍能生成正式 Excel。
6. 单元测试和集成测试覆盖主要状态分支。
7. 本文档和 [`gen-cosmic-improvement-plan.md`](gen-cosmic-improvement-plan.md) 未出现互相矛盾的目标行为。

### 后续阶段边界

以下内容不属于第一阶段验收范围：

1. `/preview/cosmic` 页面实现。
2. 人工编辑和确认状态流转。
3. 控制命令、数据运算、内部技术步骤、非功能事项的自动过滤。
4. 功能用户和三级模块的一对一强绑定自动修复。
5. `复用`、`利旧`、优化未改子过程 CFP 为 `0` 的完整配置化。

这些内容应在结构化草稿和校验器稳定后，再按 [`gen-cosmic-improvement-plan.md`](gen-cosmic-improvement-plan.md) 分阶段实施。
