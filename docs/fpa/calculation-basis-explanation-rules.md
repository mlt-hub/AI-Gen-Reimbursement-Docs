# gen-fpa 计算依据说明生成规则

## 背景

`计算依据归类`和`计算依据说明`用于 gen-fpa 结果审阅，字段命名遵循 [`result-review-terminology.md`](result-review-terminology.md)。

这里的“计算”不是数学公式计算，而是指 FPA 功能点计量：判断需求内容为什么可以作为功能点纳入 FPA 评估，以及为什么按当前 FPA 类型识别。

## 字段边界

`计算依据归类`用于短标签或短依据，回答“该功能点按哪一类判定原则归类”。

`计算依据说明`用于详细证据说明，回答“该功能点基于哪些业务场景、业务数据、业务规则和系统要素纳入 FPA 功能点计量，并为什么按当前类型识别”。

两者应一短一长，避免把`计算依据归类`的短结论重复粘贴为`计算依据说明`。

## 已确认决策摘要

- 用户可见字段名继续使用`计算依据归类`和`计算依据说明`。
- “计算”统一解释为 FPA 功能点计量，不是数学公式计算。
- `计算依据归类`是短标签或短依据，可以保留模板判定原则原文。
- `计算依据说明`是结构化证据说明，不能把归类短依据扩写成详细计量解释。
- 正式输出固定使用`来源场景`、`业务数据`、`业务规则`、`计算说明`，有明确系统元素时才输出`系统元素`。
- check/debug 输出用于暴露缺失项和质量问题，可以出现“未识别到”等提示；正式输出尽量不出现缺失提示。
- `EI/EQ/EO` 事务功能的来源路径尾部是功能过程，`ILF/EIF` 数据功能的来源路径尾部是数据组名称。
- `ILF` 是内部逻辑文件或逻辑数据组，不等同于数据库表；数据库表只属于系统实现证据。
- “按后台数据库变更的表个数计量”等模板判定原则可以作为`计算依据归类`，但不应写入`计算依据说明`的`计算说明`。

## 执行进度

截至 2026-06-09，本规范已进入执行状态，且第一阶段 prompt fragment 抽取已落地。

已完成：

- 已更新默认 FPA prompt：`config/fpa_config.yaml.example` 中 `unified_ui` 和 `strict_fpa` 的用户提示词均已加入结构化`计算依据说明`生成规则。
- 已抽取公共 prompt fragment：`config/fpa_config.yaml.example` 中新增 `prompt_fragments.calculation_explanation_rules.default`，`strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping` 四个默认用户提示词均引用 `${calculation_explanation_rules}`。
- 已支持 profile override：运行时渲染按 `prompt_fragments.calculation_explanation_rules.<profile>` 优先、`default` 回退；自定义 prompt 不引用 `${calculation_explanation_rules}` 时仍可按旧的三个核心占位符渲染。
- 已实现后处理质量检查：`ai_gen_reimbursement_docs/gen_fpa.py` 中 `postprocess.explanation_quality` 会检查结构化项、来源场景完整路径、FPA 类型、正式输出缺失提示、以及“按后台数据库变更的表个数计量”等归类依据误入说明的问题。
- 已区分事务功能和数据功能来源路径：`EI/EQ/EO` 检查 `【客户端类型】一级模块-二级模块-三级模块-功能点名称`，`ILF/EIF` 检查 `【客户端类型】一级模块-二级模块-三级模块-数据组名称`。
- 已保持非阻断策略：质量问题只记录 warning，进入`后处理警告`、`Warnings` 和规则命中详情，不阻断 gen-fpa 生成。
- 已补充回归测试：覆盖结构化说明通过、非结构化说明告警、数据组路径、表个数归类依据误入说明、以及默认 prompt 规则存在性。

已提交：

- `a70f314`：实现结构化`计算依据说明` prompt 和后处理质量检查。
- `2dbe751`：修正数据功能来源路径 warning，区分`功能过程`和`数据组名称`。
- `9a6fbb3`：检查“按后台数据库变更的表个数计量”等归类依据误入`计算依据说明`。
- `13c5204`：补齐 prompt 和文档中的 `ILF/EIF` 数据功能来源路径规则。
- `41b4fc7`：补充决策摘要和`垂直行业数据组`示例。
- `17c104e`：抽取 FPA `calculation_explanation_rules` prompt fragment，补齐四个默认 profile 的引用、配置校验、渲染和测试。

已验证：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

最近一次全量结果：

```text
760 passed, 2 skipped
```

### 第二阶段实施方案：运行时配置校验与最终 prompt 预览

第二阶段目标是把 fragment 机制从“默认配置和仓库 harness 能正确渲染”推进到“用户在系统中修改 FPA prompt 时能看见、能校验、能定位问题”。本阶段不改变 `gen-fpa` 生成逻辑，不改变 `_explanation_quality_warnings` 质量门，只补运行时配置诊断和最终 prompt 展示能力。

#### 实施目标

本阶段实施：

- 在 Web 配置保存或预检时返回 FPA prompt 诊断信息。
- 对 `${calculation_explanation_rules}` 的引用状态给出明确诊断。
- 提供最终 prompt 预览，展示 fragment 展开后的完整 user prompt。
- 检查最终 prompt 是否仍有 `${...}` 未替换。
- 明确区分“配置错误”和“质量 warning”。
- 增加后端和前端测试，覆盖用户改 prompt 的主要风险。

本阶段不实施：

- 不为用户自定义 prompt 增加仓库 harness。
- 不强制用户 prompt 必须引用 `${calculation_explanation_rules}`。
- 不让 prompt 自定义 `_explanation_quality_warnings`。
- 不新增 fragment 版本字段。
- 不做真实模型样例试运行；样例试运行可作为后续阶段。

#### 后端诊断模型

建议新增一个轻量诊断结构，用于配置保存、配置页预览和调试接口复用：

```json
{
  "profile": "strict_fpa",
  "user_prompt_source": "用户配置（配置目录/fpa_config.yaml: user_prompt_sets.strict_fpa_up）",
  "fragments": [
    {
      "name": "calculation_explanation_rules",
      "referenced": true,
      "resolved": true,
      "source": "用户配置（配置目录/fpa_config.yaml: prompt_fragments.calculation_explanation_rules.default）"
    }
  ],
  "unresolved_placeholders": [],
  "warnings": [],
  "errors": [],
  "rendered_prompt": "..."
}
```

字段说明：

- `profile`：当前诊断的 FPA profile 名称。
- `user_prompt_source`：当前 user prompt 模板来源。
- `fragments[].name`：fragment 名称，第一阶段只有 `calculation_explanation_rules`。
- `fragments[].referenced`：user prompt 是否引用 `${calculation_explanation_rules}`。
- `fragments[].resolved`：引用后是否成功解析到 profile override 或 default。
- `fragments[].source`：实际使用的 fragment 来源；未引用或未解析时为空。
- `unresolved_placeholders`：最终 prompt 中残留的 `${...}`。
- `warnings`：非阻断提示，例如未引用推荐 fragment。
- `errors`：阻断错误，例如引用了 fragment 但缺失 default。
- `rendered_prompt`：最终展开后的 user prompt。若存在阻断错误，可为空或返回已知部分渲染结果。

#### 诊断规则

配置错误，必须阻断保存或运行：

- user prompt 包含非法模板变量语法。
- user prompt 使用未知占位符。
- user prompt 缺少强制占位符：`${core_rules}`、`${judgement_rules}`、`${payload_json}`。
- user prompt 引用了 `${calculation_explanation_rules}`，但 `prompt_fragments.calculation_explanation_rules.default` 缺失或为空。
- 最终 prompt 渲染失败。
- 最终 prompt 中仍有 `${...}` 残留。

配置 warning，不阻断保存：

- user prompt 未引用 `${calculation_explanation_rules}`。
- user prompt 引用了 `${calculation_explanation_rules}`，但当前 profile 没有 override，已回退 default。
- profile override 存在但为空白，已回退 default。

质量 warning，不在保存时判断：

- `计算依据说明` 缺少 `来源场景`、`业务数据`、`业务规则` 或 `计算说明`。
- 说明中出现“未识别到”“未明确说明”等缺失提示。
- 说明中混入表个数计量细节。

这些仍由 `gen-fpa` 运行后的 `_explanation_quality_warnings` 写入 check Excel。

#### 后端实现建议

建议在 `ai_gen_reimbursement_docs/config_utils.py` 中新增纯函数或 helper：

```python
def diagnose_fpa_user_prompt(profile_name: str) -> dict[str, object]:
    ...
```

该函数负责：

- 读取 profile 绑定的 user prompt template。
- 读取 core rules、judgement rules 占位符所需的最小展示值；若没有实际 judgement rules，可使用空列表或示例规则进行渲染预览。
- 解析模板 identifiers。
- 判断是否引用 `calculation_explanation_rules`。
- 如果引用，调用 `load_fpa_calculation_explanation_rules(profile_name)`。
- 渲染最终 prompt。
- 收集 unresolved placeholders、warnings、errors。

也可以把诊断拆成两个层次：

- `validate_fpa_prompt_template_config(profile_name)`：只做保存前校验，不需要真实 payload。
- `render_fpa_prompt_preview(profile_name, sample_group, sample_judgement_rules)`：生成完整预览 prompt。

如果现有 Web 配置服务已经有 FPA 配置读取/保存入口，优先在该服务层调用诊断 helper，避免把 Web 路由直接耦合到 YAML 细节。

#### Web/API 展示建议

配置页或调试页应展示：

- 当前 profile。
- 原始 user prompt template。
- fragment 引用状态。
- fragment 实际来源：profile override 或 default。
- warning 列表。
- error 列表。
- 最终渲染 prompt。

文案建议：

```text
当前 prompt 未引用 calculation_explanation_rules，计算依据说明可能不受统一规则约束。
```

```text
当前 prompt 引用了 calculation_explanation_rules，已使用 default 规则。
```

```text
当前 prompt 引用了 calculation_explanation_rules，但 prompt_fragments.calculation_explanation_rules.default 缺失或为空。
```

```text
最终 prompt 中仍存在未替换占位符：${xxx}
```

前端不需要理解 fragment 解析细节，只展示后端返回的 `warnings`、`errors`、`fragments` 和 `rendered_prompt`。

#### 测试建议

后端测试：

- 默认四个 profile 的诊断都返回 `referenced=true`、`resolved=true`、无 unresolved placeholders。
- 用户 prompt 不引用 `${calculation_explanation_rules}` 时，诊断返回 warning，不阻断。
- prompt 引用 `${calculation_explanation_rules}` 但缺少 fragment default 时，诊断返回 error。
- profile override 存在时，诊断 source 指向 profile override。
- profile override 为空白时，诊断 source 回退 default，并返回 warning。
- prompt 含未知占位符时，诊断返回 error。

Web/API 测试：

- 配置读取接口返回 prompt diagnostics。
- 保存非法 prompt 时返回 400 和明确错误。
- 保存未引用推荐 fragment 的 prompt 时允许保存，并返回 warning。
- prompt 预览接口返回展开后的 `rendered_prompt`，且无 `${...}` 残留。

前端测试或 smoke：

- 配置页面能展示 warning。
- 配置页面能展示最终 prompt 预览。
- error 状态下保存按钮或错误提示行为符合现有配置页模式。

#### 验收标准

第二阶段完成后应满足：

- 用户能在界面或调试接口看到最终展开后的 FPA user prompt。
- 用户能看到 `${calculation_explanation_rules}` 是否被引用、是否解析成功、使用 default 还是 profile override。
- 未引用 `${calculation_explanation_rules}` 只提示 warning，不阻断。
- 引用了 `${calculation_explanation_rules}` 但 fragment 缺失或为空时阻断，并给出明确错误。
- 最终 prompt 不允许残留 `${...}`。
- check Excel 质量 warning 逻辑不变。
- 仓库 harness 仍只覆盖默认配置和官方测试 fixture，不读取用户运行时配置。

建议验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py tests/test_web_config_service.py tests/test_web_config_routes.py tests/test_fpa_profiles.py
```

### 第三阶段实施方案：样例试运行与说明质量预检

第三阶段目标是在用户修改 FPA prompt 后，提供一个低风险的“样例试运行”能力，让用户在正式执行 `gen-fpa` 前看到模型输出是否能解析、是否包含结构化 `计算依据说明`，以及会触发哪些 `_explanation_quality_warnings`。本阶段只做预检，不写正式 Excel，不改变正式 `gen-fpa` 输出链路。

#### 实施目标

本阶段实施：

- 在第二阶段最终 prompt 预览基础上，增加“使用样例模块试运行”能力。
- 调用当前配置的 FPA profile、prompt fragment 和模型配置，生成一组样例 AI rows。
- 解析模型返回 JSON，并复用现有 FPA 行后处理和说明质量检查。
- 返回样例输出、解析状态、后处理 warnings、`计算依据说明` 质量 warnings。
- 明确标识本次试运行不会写入正式产物，不影响任务历史和正式 check Excel。

本阶段不实施：

- 不把样例试运行纳入仓库 harness。
- 不要求用户每次保存 prompt 都跑真实模型。
- 不自动修复用户 prompt。
- 不改变 `_explanation_quality_warnings` 的公共质量门。
- 不把样例结果写入正式 FPA Excel、check Excel 或任务历史。
- 不引入多模型对比、批量回归或稳定性评分；这些可作为后续模型评测能力。

#### 触发方式

样例试运行必须由用户显式触发，例如配置页按钮：

```text
试运行当前 prompt
```

不建议在保存 prompt 时自动调用模型，原因是：

- 会产生模型调用成本。
- 保存配置应保持快速、可预测。
- 用户可能只是在编辑草稿，不希望每次保存都触发 AI。
- 真实模型输出存在波动，不适合作为保存配置的硬阻断条件。

保存 prompt 时仍只执行第二阶段的配置 lint 和最终 prompt 预览；样例试运行用于额外质量确认。

#### 样例输入

第一版样例试运行建议使用内置固定样例模块，确保不同用户、不同环境下可以比较 prompt 行为。样例应覆盖事务功能和数据功能常见证据：

```json
{
  "client_type": "后台",
  "l1": "业务管理",
  "l2": "客户管理",
  "l3": "客户资料维护",
  "l3_desc": "维护客户基础资料，支持新增、编辑、查询和导出客户信息。",
  "processes": [
    {
      "id": "P1",
      "name": "新增客户",
      "desc": "录入客户名称、证件号码、联系电话并保存客户资料。"
    },
    {
      "id": "P2",
      "name": "查询客户",
      "desc": "按客户名称和证件号码查询客户列表。"
    },
    {
      "id": "P3",
      "name": "导出客户清单",
      "desc": "导出客户资料清单。"
    }
  ]
}
```

样例 judgement rules 使用当前配置来源。如果无法读取真实模板规则，可使用最小示例：

```text
1) 维护业务数据的外部输入，按 EI 识别。
2) 查询业务数据且无派生计算，按 EQ 识别。
3) 输出格式化清单或报表，按 EO 识别。
4) 本系统维护的逻辑数据组，按 ILF 识别。
5) 外部系统维护、本系统引用的数据组，按 EIF 识别。
```

后续可以允许用户选择“内置样例”或“从当前上传功能清单中选一个三级模块”，但第一版先做内置样例，降低实现复杂度。

#### 后端返回模型

建议新增试运行结果结构：

```json
{
  "profile": "strict_fpa",
  "prompt_diagnostics": {
    "errors": [],
    "warnings": [],
    "fragments": [],
    "unresolved_placeholders": [],
    "rendered_prompt": "..."
  },
  "sample_input": {},
  "ai_called": true,
  "parse_ok": true,
  "raw_response": "...",
  "parsed_rows": [],
  "normalized_rows": [],
  "warnings": [],
  "quality_warnings": [],
  "rule_hits": []
}
```

字段说明：

- `prompt_diagnostics`：复用第二阶段最终 prompt 诊断结果。
- `sample_input`：本次试运行使用的样例模块。
- `ai_called`：是否实际调用模型；如果 prompt 诊断有 error，则为 `false`。
- `parse_ok`：模型返回是否成功解析为 JSON rows。
- `raw_response`：模型原始响应，便于用户排查 prompt。
- `parsed_rows`：解析后的原始 rows。
- `normalized_rows`：经过现有后处理后的 FPA 行。
- `warnings`：解析、后处理、source_process_ids、classification_basis_index 等普通 warning。
- `quality_warnings`：`_explanation_quality_warnings` 产生的说明质量 warning。
- `rule_hits`：如现有后处理能返回规则命中详情，则同步暴露。

#### 后端实现建议

建议新增服务层函数，而不是把逻辑直接写在 Web route 中：

```python
def run_fpa_prompt_sample_preview(
    *,
    profile_name: str,
    task_config: dict[str, object],
) -> dict[str, object]:
    ...
```

执行顺序：

1. 调用第二阶段的 prompt diagnostics。
2. 如果存在配置 `errors`，直接返回，不调用模型。
3. 构建内置样例 group 和 judgement rules。
4. 使用当前 profile 的 `build_prompt` 生成最终 prompt。
5. 调用当前配置的 LLM。
6. 解析 JSON 响应。
7. 复用 `_normalize_ai_fpa_rows_for_l3` 或现有 preview/gen-fpa 后处理路径，将 AI rows 转成正式 FPA 行结构。
8. 收集普通 warnings、rule hits 和 `_explanation_quality_warnings`。
9. 返回试运行结果，不写文件。

实现时应优先复用已有 preview/debug 代码，避免创建第二套 AI rows 解析和后处理逻辑。如果现有函数耦合到 Excel 输出，应先抽一个无文件副作用的内部 helper。

#### Web/API 展示建议

配置页或调试页展示：

- 试运行按钮。
- 当前 profile 和模型配置摘要。
- 最终 prompt 折叠预览。
- 模型原始返回折叠区。
- 解析状态。
- 样例 FPA 行表格，至少展示：
  - `新增/修改功能点`
  - `类型`
  - `生成方式`
  - `计算依据归类`
  - `计算依据说明`
  - `后处理警告`
- quality warning 列表。

文案建议：

```text
样例试运行只用于检查当前 prompt 的输出形状，不会生成正式 Excel，也不会写入任务历史。
```

```text
当前样例输出存在计算依据说明 warning，正式 gen-fpa 运行时这些问题也会进入 check Excel。
```

```text
模型返回无法解析为 JSON，请检查 prompt 是否仍要求“只输出 JSON”。
```

#### 错误与 warning 边界

阻断试运行：

- prompt diagnostics 存在 `errors`。
- 当前运行配置没有可用 API Key。
- 当前 profile 不存在或配置无效。

试运行失败但不影响保存：

- 模型调用失败。
- 模型返回非 JSON。
- JSON 中没有 `rows`。
- rows 为空。

试运行成功但提示 warning：

- 存在 `_explanation_quality_warnings`。
- `classification_basis_index` 越界或缺失。
- `source_process_ids` 不合法。
- 输出行名称被后处理规范化。

#### 测试建议

后端单元测试：

- prompt diagnostics 有 error 时，不调用 LLM，直接返回 `ai_called=false`。
- mock LLM 返回合法 rows 时，`parse_ok=true`，返回 `normalized_rows`。
- mock LLM 返回非 JSON 时，`parse_ok=false`，返回明确错误。
- mock LLM 返回缺少结构化 `explanation` 时，返回 `quality_warnings`。
- mock LLM 返回 `${calculation_explanation_rules}` 未展开的 prompt 不应发生；如果发生，应由 diagnostics 阻断。

Web/API 测试：

- 试运行接口成功返回样例输入、raw response、parsed rows、normalized rows。
- 无 API Key 时返回 400 或现有配置错误格式。
- prompt 配置错误时返回 diagnostics errors，不调用模型。
- 非 JSON 响应时返回 parse error。

前端测试或 smoke：

- 试运行按钮能触发接口。
- loading、success、error 三种状态可见。
- quality warnings 能显示。
- raw response 和 rendered prompt 可折叠查看。

#### 验收标准

第三阶段完成后应满足：

- 用户可以在正式执行 `gen-fpa` 前，用内置样例试运行当前 profile prompt。
- 试运行会使用当前 prompt fragment 展开结果。
- 试运行不会写正式 Excel，不写任务历史。
- prompt 配置错误会阻断试运行并展示 diagnostics errors。
- 模型非 JSON 输出能被识别并展示 parse error。
- 结构化 `计算依据说明` 不合格时能展示 quality warnings。
- 成功试运行时能看到样例 FPA 行和每行 `计算依据说明`。

建议验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py tests/test_web_config_service.py tests/test_web_config_routes.py tests/test_gen_fpa_ai.py
```

后续待办：

- 用真实模型对典型模块进行抽样验证，观察 AI 是否稳定按结构输出`计算依据说明`。
- 根据真实模型输出，继续补充疑似编造表、服务、接口的检测规则。
- 如需在页面上单独展示 check/debug 信息，再评估是否增加更细的结构化质量报告字段。

## 正式输出规则

正式输出的`计算依据说明`固定采用结构化说明，基础结构如下：

```text
来源场景：...
业务数据：...
业务规则：...
系统元素：...
计算说明：...
```

其中`系统元素`为可选项：只有识别到明确的表、服务、接口、文件、外部系统等内容时才输出；如果没有任何明确系统元素，正式输出中省略该项。

正式输出尽量不出现“未明确说明”“未识别到”等缺失提示，缺失项由 check/debug 输出暴露。

### 来源场景

`来源场景`必须固定带完整路径。事务功能和数据功能的路径尾部不同：

```text
EI/EQ/EO：【客户端类型】一级模块-二级模块-三级模块-功能点名称
ILF/EIF：【客户端类型】一级模块-二级模块-三级模块-数据组名称
```

示例：

```text
来源场景：来自“【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-添加垂直行业”，后台用户点击添加按钮并提交创建垂直行业。
```

数据功能示例：

```text
来源场景：来自“【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业数据组”，该数据组从添加、编辑、删除、查询垂直行业等功能过程中识别。
```

`来源场景`必须保留用户动作或系统动作，例如点击、输入、提交、保存、查询、展示、删除、校验、返回列表等。

对于 `ILF` / `EIF` 数据功能，`来源场景`应保留数据组识别来源，例如“该数据组从添加、编辑、删除、查询垂直行业等功能过程中识别”。

### 业务数据

`业务数据`列出输入中明确出现或可由三级模块、功能过程、字段名合理归纳出的业务对象、数据组、字段或状态。

正式输出允许合理归纳业务对象。例如原文出现“垂直行业管理”和“ID、行业名称、添加时间、状态”时，可以归纳为“垂直行业数据”。

FPA 中的 `ILF` 是内部逻辑文件，表示本系统维护的一组逻辑相关业务数据，不等同于数据库表。`业务数据`中可以描述 ILF 候选或逻辑数据组，例如“垂直行业数据”“垂直行业管理员数据”；但不能仅因为存在某个数据库表，就直接认定该表等于一个 ILF。

### 业务规则

`业务规则`列出影响功能点识别、类型判断或处理边界的校验、状态流转、权限、分支规则等。

如果原文只写了动作，没有明确校验或状态规则，允许把动作本身表达为业务规则，例如：

```text
业务规则：系统根据用户删除操作移除对应垂直行业管理员记录。
```

不得补充原文没有的权限、审批、状态流、二次确认、软删除等规则。

### 系统元素

`系统元素`只列出输入中明确出现的表、服务、接口、文件或外部系统。

这里的“表”指系统实现层面的数据库表、设计表或持久化对象，是技术实现证据；它不是 FPA 类型中的 `ILF`。一个 ILF 可能由一张或多张表实现，一张表也不必然独立构成一个 ILF。

不得根据功能过程名称编造表名、接口名、服务名或外部系统。例如不能因为存在“添加垂直行业”就推断出“行业信息表”或“行业管理保存接口”。

正式输出中，如果没有明确系统元素，则省略`系统元素`项。

### 计算说明

`计算说明`说明两件事：

- 为什么该内容可以作为功能点纳入 FPA 功能点计量。
- 为什么按当前 FPA 类型识别。

正式输出优先在`计算说明`中明确出现 FPA 类型：`EI`、`ILF`、`EQ`、`EO`或`EIF`。

如果真实模型已经使用清晰业务术语说明类型，也可视为明确类型：

- `EI`：外部输入、输入事务、维护类事务。
- `EQ`：外部查询、查询类事务。
- `EO`：外部输出、输出类事务。
- `ILF`：内部逻辑数据、内部数据功能、内部数据组。
- `EIF`：外部逻辑数据、外部数据功能、外部数据组。

`计算依据归类`中的短依据可以保留模板判定原则原文，例如“按后台数据库变更的表个数计量”。但这类短依据不应改写进`计算依据说明`作为详细计量解释，避免误导为 `ILF` 按数据库表个数计量。

示例：

```text
计算说明：该功能过程体现后台用户提交行业名称并创建垂直行业数据，可支撑 FPA 功能点计量，并按 EI 识别。
```

## 篇幅控制

`计算依据说明`每项 1 句，总体建议 80-180 字；以证据充分为准，不要求写满。

生成时不得为了达到字数而补充输入中没有的信息。

## check/debug 输出规则

check/debug 输出用于暴露信息缺口和生成质量问题，可以比正式输出更严格、更显式。

check/debug 中：

- `系统元素`项永远保留。
- 如果未识别到明确表、服务、接口，应写：`系统元素：未识别到明确的表/服务/接口。`
- 对业务对象和数据项标记来源，区分原文明确出现与 AI 合理归纳。
- 对格式不完整、证据不足、疑似编造等问题记录 warning。
- warning 只提示质量问题，不阻断 gen-fpa 生成流程。

## AI 生成约束

AI 生成`计算依据说明`时必须遵循以下约束：

- 必须基于输入的三级模块、功能过程、功能过程描述、需求原文和结构化上下文。
- 不得编造不存在的页面、表、服务、接口、流程、字段、权限、审批、状态流或外部系统。
- 正式输出必须固定使用`来源场景`、`业务数据`、`业务规则`、`计算说明`，并在有明确系统元素时输出`系统元素`。
- `来源场景`必须使用完整路径：`EI/EQ/EO` 使用 `【客户端类型】一级模块-二级模块-三级模块-功能点名称`，`ILF/EIF` 使用 `【客户端类型】一级模块-二级模块-三级模块-数据组名称`。
- `计算说明`必须明确当前 FPA 类型。
- 信息不足时，正式输出只写已识别证据；缺失信息交由 check/debug 暴露。

## 示例

输入：

```text
客户端类型：地市后台
一级模块：垂直行业营销
二级模块：垂直行业管理
三级模块：垂直行业管理
功能过程：新增垂直行业管理员
功能过程描述：添加垂直行业管理员，输入手机号码保存；校验所添加的手机号码必须为系统用户，否则无法添加
类型：EI
```

正式输出：

```text
来源场景：来自“【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-新增垂直行业管理员”，后台用户输入手机号码并保存新增管理员。
业务数据：涉及垂直行业管理员数据，输入字段为手机号码。
业务规则：系统需校验所添加的手机号码必须为系统用户，否则无法添加。
计算说明：该功能过程体现后台用户提交管理员手机号并触发新增维护，可支撑 FPA 功能点计量，并按 EI 识别。
```

check/debug 输出可补充：

```text
系统元素：未识别到明确的表/服务/接口。
业务数据来源：垂直行业管理员为根据功能过程归纳；手机号码为原文明确字段。
```

### 数据功能说明示例

输入中识别出 `ILF` 数据组：

```text
客户端类型：地市后台
一级模块：垂直行业营销
二级模块：垂直行业管理
三级模块：垂直行业管理
数据组名称：垂直行业数据组
涉及功能过程：添加垂直行业、编辑垂直行业、删除垂直行业、查询垂直行业
字段：ID、行业名称、添加时间、状态
类型：ILF
计算依据归类：按后台数据库变更的表个数计量
```

推荐正式输出：

```text
来源场景：来自“【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业数据组”，该数据组从添加、编辑、删除、查询垂直行业等功能过程中识别。
业务数据：涉及垂直行业数据组，字段包括ID、行业名称、添加时间、状态。
业务规则：系统内部维护垂直行业数据，支持新增、编辑、删除和查询。
计算说明：该数据组由本系统内部维护，属于逻辑相关业务数据组，可支撑 FPA 功能点计量，并按 ILF 识别。
```

不推荐输出：

```text
来源场景：从添加、编辑、删除、查询垂直行业等过程中识别。
业务数据：垂直行业数据组（ID、行业名称、添加时间、状态）。
业务规则：系统内部维护，支持新增、编辑、删除、查询。
计算说明：系统内部维护的逻辑数据组，符合ILF定义，按后台数据库变更的表个数计量。
```

原因：

- `来源场景`缺少完整路径，应写到 `【客户端类型】一级模块-二级模块-三级模块-数据组名称`。
- “按后台数据库变更的表个数计量”属于`计算依据归类`，不应写进`计算依据说明`的`计算说明`。

### 数据表与 ILF 示例

如果输入明确出现数据库表：

```text
业务数据：涉及垂直行业数据，字段包括行业名称、添加时间和状态。
系统元素：涉及 vertical_industry 表，用于保存垂直行业基础信息。
计算说明：该功能点体现本系统维护的垂直行业逻辑数据组，可支撑 FPA 功能点计量，并按 ILF 识别。
```

如果输入只出现功能过程和字段，没有出现表名：

```text
业务数据：涉及垂直行业数据，字段包括行业名称、添加时间和状态。
计算说明：该功能过程体现后台用户查询垂直行业业务数据，可支撑 FPA 功能点计量，并按 EQ 识别。
```

上述第二种情况不得在正式输出中补写“涉及垂直行业表”。表名来源不明确时，只能在 check/debug 中提示未识别到明确表、服务、接口。

## 后处理 check 建议

后处理 check 可以检查以下问题，并记录 warning：

- 缺少`来源场景`、`业务数据`、`业务规则`或`计算说明`。
- `来源场景`未使用完整路径格式。
- `计算说明`未出现当前 FPA 类型。
- 正式输出中出现“未识别到”“未明确说明”等缺失提示。
- `计算依据说明`中出现“数据库表个数=...”“表数量...”等把表数量作为详细计量依据的表述。一句归类式短语可作为 FPA 类型判定说明保留，真正的短依据仍优先放在`计算依据归类`。
- `系统元素`中出现输入未明确提供的疑似表名、服务名、接口名或外部系统名。
- 文本明显过短，无法支撑人工审阅。

第一阶段仅记录 warning，不阻断生成。

## 当前 gen-fpa 实现与 profile prompt 抽取讨论

本节记录 2026-06-09 对 `gen-fpa` 中 `计算依据说明`当前实现、各 profile prompt 差异，以及后续抽取为独立 prompt 片段的讨论结论。

### 当前输出链路

`gen-fpa` 当前把内部字段 `explanation` 作为 `计算依据说明` 的主要来源。

AI 生成阶段要求模型在 `rows[].explanation` 中输出说明；后处理阶段在 `ai_gen_reimbursement_docs/gen_fpa.py` 的 `_normalize_ai_fpa_rows_for_l3` 中读取 `raw["explanation"]`，如果没有则尝试读取 `raw["计算依据说明"]`，最终写入输出行的中文列：

```python
"计算依据说明": explanation
```

如果 AI 行没有提供 `explanation`，后处理会生成一段简短兜底说明：

```text
<功能点名称>，具体为以下：
1、基于该三级模块功能过程完成对应业务能力。
```

同时记录 `postprocess.explanation_fallback` 警告。

后处理会做两类轻量规范化：

- 当 `来源场景` 需要完整路径时，替换为当前 FPA 行完整功能点路径。
- 当说明中混入“1 个表”“对应后台数据库变更的 1 个表”等数据库表个数细节时，将这类片段从正式 `计算依据说明` 中移除；这类短依据应保留在 `计算依据归类`，不应作为详细说明。

质量检查由 `_explanation_quality_warnings` 执行，只记录 warning，不阻断生成。当前检查项包括：

- 是否缺少 `来源场景`、`业务数据`、`业务规则`、`计算说明`。
- `来源场景` 是否使用完整路径。
- `计算说明` 是否明确当前 FPA 类型。
- 正式说明中是否出现“未识别到”“未明确说明”“需求未明确说明”等缺失提示。
- 是否疑似把数据库表个数作为详细计量解释。

规则兜底行的 `生成方式` 为 `fallback`。`fpa_profiles.py` 中 `_structure_fallback_explanations` 会检查 fallback 行的 `计算依据说明` 是否具备四段结构；如果缺失，则由 `_structured_fallback_explanation` 补成：

```text
来源场景：...
业务数据：...
业务规则：...
计算说明：...
```

因此当前实现可以概括为：AI 优先按 prompt 生成结构化 `explanation`，后端做路径规范化、表数量细节清理和质量告警；只有缺失或 fallback 规则行不完整时才兜底生成说明。

### 各 profile 的当前 prompt 差异

当前 `config/fpa_config.yaml.example` 中，`strict_fpa` 和 `unified_ui` 已经包含完整的 `计算依据说明生成规则`；`multi_uis` 和 `ui_api_mapping` 主要依赖 system prompt 中“判断理由必须写入 rows[].explanation”的约束，以及 JSON 示例中的四段式格式。

`strict_fpa` 的 system prompt 包含：

```text
计算依据说明必须基于输入业务内容，按用户提示词中的结构化证据说明规则生成；不要编造不存在的页面、表、服务、接口或流程。

不要输出 reasoning、分析过程、Markdown 或 JSON 外文本；所有判断理由必须写入 rows[].type_reason、rows[].explanation、rows[].split_reason、rows[].complexity_reason。
```

`strict_fpa` 的 user prompt 包含完整规则：

```text
计算依据说明生成规则：
1. explanation 必须写成结构化证据说明，固定包含「来源场景」「业务数据」「业务规则」「计算说明」；只有输入中明确出现表、服务、接口、文件、外部系统等系统元素时，才输出「系统元素」。
2. 来源场景必须使用完整路径；EI/EQ/EO 事务功能使用「【客户端类型】一级模块-二级模块-三级模块-功能点名称」，ILF/EIF 数据功能使用「【客户端类型】一级模块-二级模块-三级模块-数据组名称」，并保留用户动作、系统动作或数据组识别来源。
3. 业务数据描述业务对象、逻辑数据组、字段或状态；可以合理归纳业务对象，但不得把数据库表直接等同为 ILF。
4. 系统元素只列出输入中明确出现的表、服务、接口、文件或外部系统；未明确出现时，正式 explanation 中省略「系统元素」，不要写“未识别到”。
5. 计算说明必须说明为什么纳入 FPA 功能点计量，并明确当前类型 EI / EO / EQ / ILF / EIF。
6. 计算依据归类中的短依据可以是模板判定原则原文，但 explanation 不要把“按后台数据库变更的表个数计量”“按数据库表个数计量”等归类依据改写成详细计量解释。
7. 每项 1 句，总体建议 80-180 字；不要为凑字数补充输入中没有的权限、审批、状态流、表名、服务名或接口名。
```

`unified_ui` 的 system prompt 与 `strict_fpa` 同型，只是 profile 口径不同。它的 user prompt 中 `计算依据说明生成规则` 当前与 `strict_fpa` 完全一致。

`multi_uis` 的 system prompt 当前只有通用输出位置约束：

```text
不要输出 reasoning、分析过程、Markdown 或 JSON 外文本；只输出 JSON。所有判断理由必须写入 rows[].type_reason、rows[].explanation、rows[].split_reason、rows[].complexity_reason。如需额外调试摘要，可输出 debug_summary，最多 5 条，每条不超过 40 字；没有必要时省略。
```

`multi_uis` 的 user prompt 没有展开完整 7 条规则，只在 JSON 格式示例中要求：

```json
"explanation":"来源场景：...\n业务数据：...\n业务规则：...\n计算说明：..."
```

`ui_api_mapping` 的 system prompt 同样只有通用输出位置约束：

```text
不要输出 reasoning、分析过程、Markdown 或 JSON 外文本；只输出 JSON。所有判断理由必须写入 rows[].type_reason、rows[].explanation、rows[].split_reason、rows[].complexity_reason。如需额外调试摘要，可输出 debug_summary，最多 5 条，每条不超过 40 字；没有必要时省略。
```

`ui_api_mapping` 的 user prompt 也没有展开完整 7 条规则，只在 JSON 格式示例中要求：

```json
"explanation":"来源场景：...\n业务数据：...\n业务规则：...\n计算说明：..."
```

### 各 profile 的行为差异

各 profile 的 AI 行最终都走同一个 `_normalize_ai_fpa_rows_for_l3` 后处理函数，因此正式输出层面的 `计算依据说明` 字段和质量检查规则是一致的。profile 差异主要体现在 prompt 约束和 fallback 行生成。

`strict_fpa` 更强调读取 `agent_review.type_judgement`、`merge_review` 和 `process_facts`。fallback 会先识别数据功能行，再识别或合并事务功能行；fallback 原始说明可能是短句，随后由 `_structure_fallback_explanations` 补成四段式。

`unified_ui` 默认使用 `CustomRulesProfile`。fallback 通常生成三级模块级 `界面开发` 行，再按功能过程生成处理行。fallback 的说明来自配置中的 `explanation_template`，如果缺四段结构，会统一补齐。

`multi_uis` 会额外把 `split_reason` 记录进 check/review 元数据，但不直接改变 `计算依据说明`。如果 AI 输出多条界面开发行且缺少 `split_reason`，会合并为三级模块级界面行并记录 warning。

`ui_api_mapping` 固定将 `界面开发` 识别为 `EI`，将 `接口开发` 或明确接口/后端调用识别为 `ILF`。fallback 会为每个功能过程默认生成 `功能过程-界面开发` 和 `功能过程-接口开发`，明确接口/后端调用另补 ILF 行；这些 fallback 短说明也会进入结构化补齐流程。

### 抽取为独立 prompt 片段的建议

建议把各 profile 中关于 `计算依据说明` 的 prompt 抽成独立片段，例如：

```yaml
prompt_fragments:
  fpa_calculation_explanation_rules: |-
    计算依据说明生成规则：
    1. explanation 必须写成结构化证据说明，固定包含「来源场景」「业务数据」「业务规则」「计算说明」；只有输入中明确出现表、服务、接口、文件、外部系统等系统元素时，才输出「系统元素」。
    2. 来源场景必须使用完整路径；EI/EQ/EO 事务功能使用「【客户端类型】一级模块-二级模块-三级模块-功能点名称」，ILF/EIF 数据功能使用「【客户端类型】一级模块-二级模块-三级模块-数据组名称」，并保留用户动作、系统动作或数据组识别来源。
    3. 业务数据描述业务对象、逻辑数据组、字段或状态；可以合理归纳业务对象，但不得把数据库表直接等同为 ILF。
    4. 系统元素只列出输入中明确出现的表、服务、接口、文件或外部系统；未明确出现时，正式 explanation 中省略「系统元素」，不要写“未识别到”。
    5. 计算说明必须说明为什么纳入 FPA 功能点计量，并明确当前类型 EI / EO / EQ / ILF / EIF。
    6. 计算依据归类中的短依据可以是模板判定原则原文，但 explanation 不要把“按后台数据库变更的表个数计量”“按数据库表个数计量”等归类依据改写成详细计量解释。
    7. 每项 1 句，总体建议 80-180 字；不要为凑字数补充输入中没有的权限、审批、状态流、表名、服务名或接口名。
```

各 profile 的 user prompt 可以通过占位符复用：

```text
${calculation_explanation_rules}
```

实现时需要同步调整 prompt 构建逻辑。当前配置注释说明 user 模板只支持：

```text
${core_rules}
${judgement_rules}
${payload_json}
```

如果新增 `${calculation_explanation_rules}`，需要更新模板渲染、配置加载和相关测试，避免占位符未替换直接进入最终 prompt。

建议的复用策略：

- `strict_fpa` 和 `unified_ui` 复用同一份完整规则。
- `multi_uis` 和 `ui_api_mapping` 默认也复用同一份完整规则，补强当前仅靠 JSON 示例约束的问题。
- 如后续某个 profile 对说明有特殊口径，再增加 profile 专属片段，例如 `multi_uis_calculation_explanation_rules` 或 `ui_api_mapping_calculation_explanation_rules`。

### profile 专属 prompt 与输出差异

如果只抽取一个公共 `${calculation_explanation_rules}` 给所有 profile 复用，主要收益是统一 `计算依据说明` 的格式和质量要求。它会让所有 profile 更稳定地产生四段式说明，但不会单独保证“不同 profile 输出不同风格或不同重点的说明”。profile 差异仍主要来自行规划口径、类型规则、输入上下文和 fallback 行生成逻辑。

如果目标是让不同 profile 稳定输出不同侧重点的 `计算依据说明`，建议使用 `default + profile override` 结构：

```yaml
prompt_fragments:
  calculation_explanation_rules:
    default: |-
      通用计算依据说明生成规则...
    strict_fpa: |-
      strict_fpa 专属规则...
    unified_ui: |-
      unified_ui 专属规则...
    multi_uis: |-
      multi_uis 专属规则...
    ui_api_mapping: |-
      ui_api_mapping 专属规则...
```

构建 prompt 时按当前 profile 取专属片段；如果没有专属片段，则回退 `default`。

建议的 profile 差异重点：

- `strict_fpa`：突出标准 FPA 口径、数据功能和事务功能边界、合并依据，以及 `agent_review.type_judgement` 和 `merge_review` 的硬约束证据。
- `unified_ui`：突出三级模块级界面能力、非界面处理开发行覆盖，以及同一页面内列表、查询条件、按钮、弹窗和状态组件的合并依据。
- `multi_uis`：突出独立页面、独立业务对象、独立业务流程或独立用户端的拆分证据；`split_reason` 用于记录拆分理由，`explanation` 用于说明该行为什么纳入 FPA 计量。
- `ui_api_mapping`：突出界面开发固定 `EI`、接口开发和明确接口/后端调用固定 `ILF` 的映射依据，避免把普通保存、提交、审批等动作扩写成额外接口或后端调用。

因此，公共 prompt 用于统一质量；profile 专属 prompt 加默认回退，才用于稳定表达不同 profile 的说明重点。

### 其他可候选抽取的 prompt fragments

除 `calculation_explanation_rules` 外，后续还可以考虑抽取以下片段，但不建议第一阶段全部实施。

`json_output_contract`：抽取 JSON-only 输出约束，例如“不允许输出 JSON 外文本”“不要输出 reasoning、分析过程、Markdown”“所有判断理由必须写入 rows[].type_reason、rows[].explanation、rows[].split_reason、rows[].complexity_reason”。这类约束机械重复、语义稳定，适合作为第二优先级。

`classification_basis_selection_rules`：抽取 `classification_basis_index` 选择规则，例如“计算依据归类判定原则列表只能返回最匹配的序号，序号从 1 开始”。这类规则也较稳定，但与 user prompt 中的 `judgement_rules` 展示位置相关，抽取时要保证可读性。

`fpa_name_path_rules`：抽取完整路径命名规则，例如 `name` 必须使用 `【客户端类型】一级模块-二级模块-三级模块-功能点名称`，不得只返回功能过程名，不得用子系统（模块）替代客户端类型。该规则重复度较高，但也会与 profile 行规划语义交织。

`row_output_schema`：抽取 rows JSON 示例。多数 profile 的 schema 相似，但 `ui_api_mapping` 的类型范围和 `multi_uis` 的 `split_reason` 要求不同，适合做 `default + profile override`，不宜只做一个全局 schema。

`agent_review_rules`：抽取前置 agent review 读取约束。不同 profile 读取不同证据：`strict_fpa` 读取 `type_judgement`、`merge_review`、`process_facts`；`unified_ui` 和 `multi_uis` 读取 `workload_judgement`；`ui_api_mapping` 读取 `mapping_judgement`。这类片段接近 profile 业务语义，抽取前需要先定清楚命名和覆盖策略。

`row_planning_rules`：抽取 profile 行规划规则。例如 `strict_fpa` 不按开发工作项拆分，`unified_ui` 默认三级模块级界面开发行，`multi_uis` 可按独立页面或业务对象拆分，`ui_api_mapping` 每个功能过程默认界面开发 `EI` 和接口开发 `ILF`。这类规则是 profile 的核心，不建议过早抽取。

### 复杂度控制建议

prompt fragment 抽取有收益，也会引入模板系统复杂度。若一次抽取过多，配置会从“按 profile 读一段完整 prompt”变成“跨多个 fragment 拼装 prompt”，维护者需要在多个位置跳转，反而可能降低可读性。

第一阶段建议只抽取：

- `calculation_explanation_rules`

可选第二阶段再抽取：

- `json_output_contract`

暂不建议抽取：

- `row_planning_rules`
- `agent_review_rules`
- `row_output_schema`
- `fpa_name_path_rules`

阶段性原则是：先抽当前痛点最明确、重复最多、收益最高的 `计算依据说明` 规则，并支持 `default + profile override`。保留 profile 主 prompt 的完整上下文，避免把 profile 的业务语义拆得过碎。只有当后续真实维护中持续出现重复修改或不一致问题时，再抽第二块。

### harness 与用户运行时 prompt 的边界

如果只是修改 `calculation_explanation_rules` 的文案，而不引入新的占位符或配置结构，通常只需要同步更新现有 prompt 断言。当前测试中已有默认 prompt 内容断言，会检查 `计算依据说明生成规则`、`来源场景`、`业务数据`、`系统元素`、`不要写“未识别到”` 等关键文本；文案变化时这些断言需要随之调整。

如果引入 `${calculation_explanation_rules}` 新占位符，则必须同步修改 prompt 构建链路和 harness。当前 `config_utils.py` 中 FPA user prompt 占位符白名单只允许：

```python
{"core_rules", "judgement_rules", "payload_json"}
```

新增 fragment 后，至少需要调整：

- `FPA_USER_PROMPT_PLACEHOLDERS`：加入 `calculation_explanation_rules`，或设计为可选推荐占位符。
- `_validate_fpa_user_prompt_template`：更新未知占位符、必填占位符和错误提示逻辑。
- `_render_configured_fpa_prompt`：实际把 `${calculation_explanation_rules}` 替换为当前 profile 对应 fragment。
- 配置加载逻辑：读取 `prompt_fragments.calculation_explanation_rules`，支持 `default + profile override`。
- tests/harness：增加断言，确保新占位符能渲染、没有 `${...}` 残留、profile override 能生效、缺 fragment 或非法占位符时能给出清晰错误。

上线后的用户自定义 prompt 不应进入仓库 harness。仓库 harness 只验证产品默认配置、fragment 机制、官方内置 profile 和测试 fixture。用户在系统中修改 prompt 后，应走运行时配置校验、最终 prompt 预览和可选样例试运行，而不是为每个用户 prompt 增加 pytest 或项目级 harness。

因此边界应固定为：

```text
仓库 harness：验证产品默认能力和 fragment 机制。
用户 prompt 修改：通过运行时配置 lint、最终 prompt 预览和样例试运行检查。
```

如果用户修改后的 prompt 要被吸收为官方内置 profile、默认 prompt 或推荐模板，才需要把它纳入仓库 harness。

为了避免用户运行时配置影响仓库测试，harness 应使用测试 fixture 或复制仓库默认 `config/fpa_config.yaml.example` 到 `tmp_path`，并通过 monkeypatch 指向测试配置目录；不要直接读取用户 Web/本地运行时配置目录。

### 用户 prompt 修改后的运行时校验

系统上线后，如果用户修改 prompt，系统应尊重用户自定义 prompt，但保存或运行前应进行通用配置校验：

- 占位符是否合法。
- 必要占位符是否存在，至少应保证 `${payload_json}` 能进入最终 prompt。
- 如果 prompt 使用 `${calculation_explanation_rules}`，对应 fragment 必须存在并可解析。
- 模板变量没有未闭合或非法格式。
- 最终 prompt 能成功渲染。
- 最终 prompt 中没有未替换的 `${...}`。

这类检查属于配置 lint，不属于仓库 harness。它只回答“这个用户配置能不能安全渲染和运行”，不保证业务输出一定符合质量门。

用户修改 prompt 后，还应提供最终 prompt 预览或样例试运行能力，用于展示：

- 当前 profile。
- 原始 user prompt。
- 展开后的最终 prompt。
- 使用了哪些 fragments。
- 哪些推荐 fragments 没有被引用。
- 样例输出是否能解析为 JSON。
- 样例输出是否包含 `计算依据说明`。

### check Excel warning 与质量门

用户自定义 prompt 可能导致模型输出不再满足当前 `计算依据说明` 结构要求。此时不应让仓库 harness 报错，而应由运行后的 check Excel 暴露质量问题。

当前 `_explanation_quality_warnings` 是产品内置审阅质量门，不随用户 prompt 自动变化。它会把问题写入：

- FPA 结果行的 `后处理警告`。
- check Excel 的 `Warnings` sheet。
- `规则命中详情` 中的 `postprocess.explanation_quality`。

典型 warning 包括：

- `计算依据说明` 缺少 `来源场景`、`业务数据`、`业务规则` 或 `计算说明`。
- `来源场景` 没有完整路径。
- `计算说明` 没有明确当前类型，例如 `EI`、`EQ`、`EO`、`ILF`、`EIF`。
- 正式说明中出现“未识别到”“未明确说明”“需求未明确说明”等缺失提示。
- 把“1 个表”“按数据库表个数计量”等表数量或归类短依据写进详细说明。

因此，用户可以修改 prompt 的内容和措辞，但正式 `计算依据说明` 仍应满足系统的审阅结构契约。若用户 prompt 有意改变说明结构，check Excel 持续 warning 是预期行为，表示用户自定义 prompt 已偏离当前产品质量门。

### `_explanation_quality_warnings` 与 profile 差异

第一阶段不建议为每个 profile 复制一套完整 `_explanation_quality_warnings`。更稳的方式是保持公共质量门固定，所有 profile 都必须满足审阅底线：

- 有 `来源场景`。
- 有 `业务数据`。
- 有 `业务规则`。
- 有 `计算说明`。
- `计算说明` 明确 FPA 类型。
- 正式说明不出现缺失提示。
- 不把数据库表个数写成详细计量解释。

这些要求属于结果审阅契约，不应跟随用户 prompt 或 profile prompt 任意漂移。它们保证不同 profile 的输出都能被同一套审阅页、check Excel 和人工复核流程理解。

如果真实数据证明某些 profile 需要额外检查，建议在公共检查后追加少量 profile-specific checks，而不是整套复制：

```python
warnings = _common_explanation_quality_warnings(...)
warnings.extend(profile.explanation_quality_warnings(...))
```

可选的 profile 差异检查示例：

- `strict_fpa`：`ILF/EIF` 来源场景应更偏数据组名称；合并行说明应体现多个来源功能过程。
- `unified_ui`：三级模块级 `界面开发` 行说明应体现同一页面内能力覆盖，而不是单个按钮动作。
- `multi_uis`：多界面行说明应能呼应独立页面、独立业务对象、独立业务流程或独立用户端；`split_reason` 仍由独立规则检查。
- `ui_api_mapping`：`界面开发` 说明应体现 `EI`；`接口开发` 或明确后端调用说明应体现 `ILF` 映射口径；不应把普通保存、提交、审批扩写成明确接口调用。

阶段性建议仍是先保留 common quality gate。profile prompt 负责表达口径差异，公共 `_explanation_quality_warnings` 负责保证说明可审。只有当真实运行样本证明公共质量门太宽或太窄时，再增量添加 profile-specific checks。

### 第一阶段落地状态：抽取 `calculation_explanation_rules`

第一阶段已完成。`计算依据说明生成规则` 已从各 profile 的 user prompt 中抽成可复用 prompt fragment，并补齐 `multi_uis`、`ui_api_mapping` 原先缺少完整细则的问题。第一阶段只做这一件事，未抽取其它 prompt fragments。

#### 实施范围

本阶段已实施：

- 新增 `prompt_fragments.calculation_explanation_rules` 配置。
- 支持 `default + profile override`。
- 在四个默认 profile 的 user prompt 中引用 `${calculation_explanation_rules}`。
- 渲染最终 prompt 时将 `${calculation_explanation_rules}` 替换为当前 profile 对应规则。
- 保持 `_explanation_quality_warnings` 公共质量门不变。
- 更新默认配置、配置校验、prompt 渲染和测试。

本阶段未实施：

- 不抽取 `json_output_contract`、`row_planning_rules`、`agent_review_rules`、`row_output_schema`、`fpa_name_path_rules`。
- 不增加用户专属 harness。
- 不增加 fragment 版本字段。
- 不做历史用户配置迁移；当前系统尚未上线，不需要旧配置兼容路径。
- 不为每个 profile 复制一套完整 `_explanation_quality_warnings`。

#### 配置 schema

默认配置已新增：

```yaml
prompt_fragments:
  calculation_explanation_rules:
    default: |-
      计算依据说明生成规则：
      1. explanation 必须写成结构化证据说明，固定包含「来源场景」「业务数据」「业务规则」「计算说明」；只有输入中明确出现表、服务、接口、文件、外部系统等系统元素时，才输出「系统元素」。
      2. 来源场景必须使用完整路径；EI/EQ/EO 事务功能使用「【客户端类型】一级模块-二级模块-三级模块-功能点名称」，ILF/EIF 数据功能使用「【客户端类型】一级模块-二级模块-三级模块-数据组名称」，并保留用户动作、系统动作或数据组识别来源。
      3. 业务数据描述业务对象、逻辑数据组、字段或状态；可以合理归纳业务对象，但不得把数据库表直接等同为 ILF。
      4. 系统元素只列出输入中明确出现的表、服务、接口、文件或外部系统；未明确出现时，正式 explanation 中省略「系统元素」，不要写“未识别到”。
      5. 计算说明必须说明为什么纳入 FPA 功能点计量，并明确当前类型 EI / EO / EQ / ILF / EIF。
      6. 计算依据归类中的短依据可以是模板判定原则原文，但 explanation 不要把“按后台数据库变更的表个数计量”“按数据库表个数计量”等归类依据改写成详细计量解释。
      7. 每项 1 句，总体建议 80-180 字；不要为凑字数补充输入中没有的权限、审批、状态流、表名、服务名或接口名。
    strict_fpa: |-
      # 可选。缺省时回退 default。
    unified_ui: |-
      # 可选。缺省时回退 default。
    multi_uis: |-
      # 可选。缺省时回退 default。
    ui_api_mapping: |-
      # 可选。缺省时回退 default。
```

`default` 为必填非空字符串。profile override 为可选；为空、缺失或只包含空白时均回退 `default`。第一阶段默认配置只提供 `default`，等确有差异需要时再补 profile override。

#### user prompt 模板

四个默认 user prompt 已引用：

```text
${calculation_explanation_rules}
```

当前引用位置在行规划规则之后、`模块输入 JSON` 之前：

```text
...
name 必须使用完整模块路径前缀，格式为「【客户端类型】一级模块-二级模块-三级模块-功能点名称」。

${calculation_explanation_rules}

模块输入 JSON：
${payload_json}
```

最终渲染后的 prompt 不应出现 `${calculation_explanation_rules}` 或任何 `${...}` 残留。

#### 渲染规则

渲染 `${calculation_explanation_rules}` 时按以下顺序取值：

1. `prompt_fragments.calculation_explanation_rules.<profile_name>`
2. `prompt_fragments.calculation_explanation_rules.default`
3. 报错：`FPA 配置无效：prompt_fragments.calculation_explanation_rules.default 必须是非空字符串`

如果 user prompt 未引用 `${calculation_explanation_rules}`，渲染不强制追加 fragment。默认配置中的四个官方 profile 必须引用它；用户自定义 prompt 可不引用，但运行时配置检查可以提示“当前 prompt 未引用 calculation_explanation_rules，计算依据说明可能不受统一规则约束”。

#### 配置校验规则

`FPA_USER_PROMPT_PLACEHOLDERS` 已允许：

```python
{"core_rules", "judgement_rules", "payload_json", "calculation_explanation_rules"}
```

必填占位符已分为两类：

- 强制必填：`${core_rules}`、`${judgement_rules}`、`${payload_json}`。
- 推荐引用：`${calculation_explanation_rules}`。

如果继续沿用“所有允许占位符都必须出现”的旧逻辑，会导致用户自定义 prompt 必须引用 fragment，不符合运行时自定义边界。因此当前已把 `calculation_explanation_rules` 设计为允许但非强制；默认配置测试单独断言四个官方 profile 都引用并渲染该 fragment。

如果 prompt 引用了 `${calculation_explanation_rules}`，但 fragment 缺失或解析为空，应阻断并给出明确错误。

#### 代码修改点

已修改：

- `config/fpa_config.yaml.example`
  - 新增 `prompt_fragments.calculation_explanation_rules.default`。
  - `strict_fpa_up`、`unified_ui_up`、`multi_uis_up`、`ui_api_mapping_up` 引用 `${calculation_explanation_rules}`。
  - 移除 `strict_fpa_up`、`unified_ui_up` 中重复内联的完整 7 条规则。
  - 补齐 `multi_uis_up`、`ui_api_mapping_up` 的说明规则引用。

- `ai_gen_reimbursement_docs/config_utils.py`
  - 扩展 user prompt 占位符白名单。
  - 拆分强制必填占位符和允许占位符。
  - 新增加载 `prompt_fragments.calculation_explanation_rules` 的函数或内部 helper。
  - 校验 `default` 非空；profile override 可选。

- `ai_gen_reimbursement_docs/fpa_profiles.py`
  - `_render_configured_fpa_prompt` 注入 `calculation_explanation_rules`。
  - 按 `profile.name` 获取 override，缺省回退 default。
  - 保证最终 prompt 没有未替换占位符。

- `tests/test_config_utils.py`
  - 更新默认 prompt 断言：默认四个 profile 最终模板或渲染结果包含 `计算依据说明生成规则`。
  - 增加 fragment 缺失、default 为空、非法占位符、未替换占位符等测试。
  - 增加 `calculation_explanation_rules` 可选但被默认 profile 引用的断言。

- `tests/test_fpa_profiles.py`
  - 更新自定义最小配置 fixture；如其 user prompt 不引用 fragment，应仍可通过。
  - 增加 build_prompt 渲染后无 `${calculation_explanation_rules}` 残留的测试。
  - 增加 profile override 生效测试。

- `tests/fpa_profiles/test_profile_prompt_payload_contract.py` 和 `tests/fpa_profiles/test_custom_profile_harness.py`
  - 现有测试 fixture 不引用 `${calculation_explanation_rules}`，已通过聚焦测试确认最小配置仍能构建 payload，不被 fragment 机制强制阻断。

#### 验收标准

第一阶段已满足：

- 默认 `strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping` prompt 都能渲染成功。
- 四个默认 profile 的最终 prompt 都包含 `计算依据说明生成规则`。
- `multi_uis` 和 `ui_api_mapping` 不再只依赖 JSON 示例获得说明结构约束。
- `${calculation_explanation_rules}` 不会残留在最终 prompt 中。
- 其它 `${...}` 占位符也不会残留在最终 prompt 中。
- profile override 存在时优先使用 override。
- profile override 缺失时回退 default。
- prompt 未引用 `${calculation_explanation_rules}` 的自定义最小配置仍可通过基础 prompt 构建。
- prompt 引用了 `${calculation_explanation_rules}` 但 fragment 缺失或 default 为空时，给出明确配置错误。
- `_explanation_quality_warnings` 行为不变，check Excel warning 逻辑不受 prompt fragment 抽取影响。

已执行验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_utils.py tests/test_fpa_profiles.py tests/fpa_profiles/test_profile_prompt_payload_contract.py tests/fpa_profiles/test_custom_profile_harness.py tests/test_gen_fpa_ai.py
```

结果：

```text
207 passed
```

并已执行全量回归：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

结果：

```text
760 passed, 2 skipped
```
