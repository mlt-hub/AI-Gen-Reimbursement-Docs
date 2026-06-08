# gen-fpa 输出稳定性方案

## 背景问题

本轮讨论围绕 `gen-fpa` 在同一模块输入下产生明显不同的 AI 输出展开。代表样例是“地市后台-垂直行业营销-垂直行业管理-垂直行业管理”：

- 模块描述支持搜索、添加、编辑、删除垂直行业。
- 功能过程包含添加垂直行业、垂直行业列表数据查询、编辑垂直行业、查询垂直行业数据、删除垂直行业、新增垂直行业管理员、删除垂直行业管理员。
- 输入中的部分 `processes.type` 与实际业务动作不一致，例如查询过程被标成“新增”。

同一类输入下，AI 可能输出两种差异很大的结果：

- 按 FPA 逻辑事务合并：同一数据组的新增、修改、删除合并为维护类 EI；同一列表界面的默认查询和条件搜索合并为查询类 EQ；普通手机号校验不生成 EIF。
- 按 `processes` 逐条输出：每个功能过程生成一个事务功能点，并把“系统用户校验”识别为 EIF。

本方案目标是让 `gen-fpa` 输出更稳定，减少模型在可解释空间内摇摆。

## 两个版本的差异对比

上一个提示词版本更适合作为通用提示词基础，原因是它把项目口径写得更清楚：

- 明确要求不盲信 `processes.type`，必须按流程名称、描述、输入输出重新判断类型。
- 明确要求同一 ILF 的新增、修改、删除，在同一管理界面或同一业务对象下合并为一个 EI。
- 明确要求同一列表界面的默认查询、条件搜索、按名称查询，在读取同一数据组并展示同类结果时合并为一个 EQ。
- 明确禁止把普通外部服务调用、手机号校验、权限校验、认证校验直接识别为 EIF。
- 要求 `计算依据说明` 使用结构化内容，包含来源场景、业务数据、业务规则和计算说明。

另一个版本的主要风险是：

- 容易把添加、编辑、删除分别生成为多个 EI，导致维护类事务功能点多算。
- 容易把默认列表查询和条件搜索拆成多个 EQ，导致查询类事务功能点多算。
- 容易把“校验手机号必须为系统用户”直接识别为系统用户 EIF。
- `计算依据说明` 过薄，不利于结果审阅和质量检查。

## 推荐采用的 FPA 口径

当前建议 `strict_fpa/gen-fpa` 采用以下决策口径。

### 类型判断

`processes.type` 只能作为参考，不作为最终判定依据。优先级建议固定为：

```text
流程描述 > 流程名称 > 输入 type
```

常见判断规则：

- 名称或描述包含查询、搜索、列表、查看，且只读取数据并展示，优先判为 EQ。
- 名称或描述包含新增、添加、编辑、修改、删除、保存，且改变本系统维护的数据组，优先判为 EI。
- 存在派生计算、统计、汇总、报表、导出、通知输出等外部输出时，才考虑 EO。
- 本系统维护的逻辑数据组判为 ILF。
- 只有明确说明外部系统维护某数据组，且本系统引用该数据组作为业务数据时，才判为 EIF。

### 维护类合并

如果多个功能过程满足以下条件，应合并为一个维护类 EI：

- 针对同一个 ILF。
- 属于同一业务对象。
- 出现在同一管理界面、同一组操作入口或同一业务维护场景。
- 动作是新增、修改、删除、启停、保存等维护动作。

示例：

```text
添加垂直行业 + 编辑垂直行业 + 删除垂直行业
= 垂直行业维护：EI
```

### 查询类合并

如果多个功能过程满足以下条件，应合并为一个查询类 EQ：

- 读取同一个 ILF 或 EIF。
- 属于同一列表、搜索或查看界面。
- 输出同一类业务结果。
- 只是默认加载、条件筛选、按名称搜索等同类查询变化。

示例：

```text
垂直行业列表数据查询 + 查询垂直行业数据
= 垂直行业查询：EQ
```

### EIF 边界

普通校验、认证、权限判断、手机号是否存在检查、短信发送、支付调用、OCR 调用、消息推送等外部服务调用，不自动生成 EIF。

只有输入明确表达“外部系统维护的数据组被本系统读取或引用”，才生成 EIF。例如：

```text
本系统读取主数据平台维护的组织主数据，用于选择所属组织。
```

仅有以下描述时，不应直接生成 EIF：

```text
校验手机号必须为系统用户。
调用外部服务校验账号是否合法。
```

### 命名口径

`strict_fpa` 建议通过名称后缀区分数据功能和事务功能，减少审阅时的混淆：

```text
ILF/EIF 数据功能：xxx数据组
EI 维护类事务：xxx维护
EQ 查询类事务：xxx查询
EO 输出类事务：xxx输出 / xxx导出 / xxx报表
```

示例：

```text
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业数据组：ILF
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业管理员数据组：ILF
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业维护：EI
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-垂直行业查询：EQ
```

## 为什么同一提示词会产生巨大差异

AI 输出不稳定的根本原因是提示词只是约束，不是程序。FPA 规则和项目口径存在解释空间时，模型会在多个看似合理的路径之间摇摆。

主要原因包括：

- FPA 实践中对 CRUD 是否合并、查询是否合并、校验是否构成 EIF 存在不同口径。
- 输入里列出多个 `processes`，模型容易机械地按“一个 process 一个功能点”输出。
- “严格 FPA”这个表述不够具体，不同模型可能理解为“逐个用户动作计数”或“按逻辑事务计数”。
- 输入字段之间存在冲突时，如果没有写清优先级，模型有时信 `type`，有时信描述。
- 缺少禁止项时，模型可能把普通外部服务调用扩展成外部数据功能。

因此，仅靠提示词无法彻底保证稳定性。需要把项目口径写成决策树，并在 harness 和后处理阶段增加约束。

## 提示词层方案

提示词需要从“原则描述”升级为“决策树 + 禁止项 + 输出结构”。

关键约束建议：

```text
1. processes 只是候选业务步骤，不是功能点计数单位。
2. 多个流程维护同一 ILF、属于同一业务对象、同一管理界面时，必须合并为一个 EI。
3. 多个查询读取同一数据组、展示同一类结果、属于同一列表或搜索界面时，必须合并为一个 EQ。
4. 只有输入明确说明外部系统维护某数据组，且本系统读取该数据组作为业务数据时，才能生成 EIF。
5. 普通校验、认证、权限判断、手机号是否存在检查，不生成 EIF。
6. 查询类流程不得因为 processes.type 写“新增”而判为 EI。
```

输出中应继续保留以下字段：

- `name`
- `type`
- `type_reason`
- `classification_basis_index`
- `explanation`
- `source_process_ids`
- `source_processes`
- `split_reason`

其中 `explanation` 对应用户可见的`计算依据说明`，必须结构化：

```text
来源场景：...
业务数据：...
业务规则：...
计算说明：...
```

有明确系统元素时才输出系统元素，不得编造表、接口、服务、外部系统或字段。

## Harness 层方案

Harness 可以作为提示词之外的稳定器，负责让生成结果通过固定验收口径。

### Harness 定义

本文中的 harness 不是某一个前端页面，也不是单纯的 prompt，而是围绕 `gen-fpa` 生成流程的一套测试、校验、回归、评估和兜底机制，用来约束 AI/规则输出是否符合预期口径。

可以把它理解为“生成系统的验收框架”：

```text
prompt：告诉 AI 应该怎么做。
harness：检查 AI 有没有真的做到。
agent：参与生成流程，负责理解、抽取、判定或审核。
生产系统：给用户生成结果。
```

Harness 通常包含：

- 输入样例：典型模块输入，例如 `tests/fixtures/fpa_golden_cases/*.json`。
- 期望结果或行为断言：例如查询不得判为 EI、普通校验不得生成 EIF、`source_process_ids` 必须来自当前模块候选列表。
- 测试代码：例如 `tests/test_fpa_golden_fixture_reports.py`、`tests/test_gen_fpa_golden_cases.py`、`tests/test_gen_fpa_strict_profile.py`。
- validator 或后处理检查：AI 返回 JSON 后检查类型、来源、说明结构、EIF 误判、查询误判等问题。
- 真实模型评估脚本：用真实 LLM 跑样例，观察 warning、误判率、确认率、重试率和输出稳定性。
- 确认流测试：如果系统支持 `needs_confirmation`，则测试模糊输入、用户确认、确认作用域和二次生成稳定性。

其中部分能力，例如 validator 和 warning，也可以进入生产系统作为兜底；但 golden cases 和回归测试主要用于开发、测试、CI/CD 和发布前验收。

### 当前口径对齐点

当前仓库已经有 FPA golden cases 和 strict profile 相关测试，例如：

- `tests/fixtures/fpa_golden_cases/`
- `tests/test_fpa_golden_fixture_reports.py`
- `tests/test_gen_fpa_golden_cases.py`
- `tests/test_gen_fpa_strict_profile.py`

`strict_fpa` 已切换为逻辑事务合并口径。代表例是 `vertical_industry_management.json`：同一数据组、同一管理场景下的添加垂直行业、编辑垂直行业、删除垂直行业合并为“垂直行业维护”EI；新增垂直行业管理员、删除垂直行业管理员合并为“垂直行业管理员维护”EI；默认列表查询和条件搜索合并为“垂直行业查询”EQ。

后续 harness 增强的重点，是让 prompt、golden fixtures、规则兜底、AI 后处理和确认流测试持续保持同一口径，避免某一层回退到逐 process 计数。

### 实施记录

2026-06-06 已将 `strict_fpa` 切换为逻辑事务合并口径，提交为 `7ae01cc6e842858a3ed91b00432b946fc33299b8`。

本次实施范围：

- `ai_gen_reimbursement_docs/fpa_profiles.py`：`StrictFpaProfile` 规则兜底支持同一业务对象的维护类 EI、查询类 EQ 合并。
- `ai_gen_reimbursement_docs/gen_fpa.py`：AI 数据功能人工复核 warning 独立保留，不被其它类型冲突 warning 覆盖。
- `config/fpa_config.yaml.example`：`strict_fpa` prompt 增加功能过程类型参考规则、processes 非计数单位、维护类 EI 合并、查询类 EQ 合并、普通外部服务不生成 EIF、合并行来源说明规则。
- `tests/fixtures/fpa_golden_cases/vertical_industry_management.json`：垂直行业管理 strict 期望调整为逻辑事务合并结果。
- `tests/test_gen_fpa_strict_profile.py`、`tests/test_fpa_profiles.py`、`tests/test_fpa_acceptance.py`、`tests/test_config_utils.py`：同步锁定新口径和工作量汇总期望。

当前代表行为：

```text
垂直行业列表数据查询 + 查询垂直行业数据
= 垂直行业查询：EQ

添加垂直行业 + 编辑垂直行业 + 删除垂直行业
= 垂直行业维护：EI

新增垂直行业管理员 + 删除垂直行业管理员
= 垂直行业管理员维护：EI
```

验证结果：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

最近一次结果：

```text
449 passed, 2 skipped
```

2026-06-06 已按推荐路线完成第一轮输出稳定性增强，提交为：

```text
c9967f2 stabilize gen-fpa ai output validation
efeb82a add fpa confirmation contract
188228c expose fpa confirmation mode in web ui
```

本轮实施范围：

- `ai_gen_reimbursement_docs/fpa_validator.py`：新增非破坏式结构化 validator，检查查询误判 EI、普通服务误判 EIF、`source_process_ids` 越界、同一对象 CRUD 拆分、同一查询场景拆分、`计算依据说明` 结构缺失等问题。
- `ai_gen_reimbursement_docs/gen_fpa.py`：AI 输出规范化和规则补齐后接入 validator；`ai_first` 对高置信稳定性问题自动重试一次，重试后仍有问题则保留结果并写入 warning，不阻断最终结果。
- `tests/test_fpa_validator.py`、`tests/test_gen_fpa_ai.py`：覆盖 validator 高置信误判、`ai_first` 一次重试、预览确认问题返回、确认结果进入 prompt 并抑制同一问题重复确认。
- `tests/test_fpa_golden_fixture_reports.py`、`tests/fixtures/fpa_golden_cases/vertical_industry_management.json`：golden case 支持“固定期望 + 行为断言”两层，锁定垂直行业管理 strict 口径下查询合并、维护合并和来源流程合并。
- `ai_gen_reimbursement_docs/fpa_confirmation.py`：新增确认流后端契约，支持 `auto`、`cautious`、`strict` 三种模式；将 validator issue 转换为结构化确认问题；将 `confirmed_decisions` 渲染为下一轮 AI prompt 的硬约束。
- `web_app/routes/tasks.py`：`/api/fpa/options` 返回确认模式枚举；`/api/fpa/preview-module` 接收 `fpa_confirmation_mode` 和 `confirmed_decisions`，并可返回 `status=needs_confirmation`、`confirmation_questions`、`confirmed_decision_count`。
- `web_app/src/components/AdvancedOptions.vue`、`web_app/src/stores/config.ts`、`web_app/src/composables/useFpaOptions.ts`、`web_app/src/components/FpaPreview.vue`、`web_app/src/views/Home.vue`：Web 高级选项新增 `FPA 生成模式`，默认审慎模式；FPA 预览和正式运行请求携带该模式；FPA 预览页已支持展示确认卡片、选择口径并带 `confirmed_decisions` 继续生成。

当前新增代表行为：

```text
AI 将“查询客户”判为 EI
=> validator 标记 validator.query_as_ei
=> ai_first 自动带校验反馈重试一次
=> 重试仍失败则保留结果并进入 warning/check/debug

AI 将“调用短信平台发送测试短信”判为 EIF
=> validator 标记 validator.ordinary_service_as_eif
=> 审慎/严格确认模式可生成“EIF 识别”确认项

用户带 confirmed_decisions 再次预览
=> 确认结果进入 prompt 硬约束
=> 同一确认项不再重复返回
```

最新验证结果：

```powershell
.\.venv\Scripts\python.exe -m pytest
npm run build
```

最近一次结果：

```text
463 passed, 2 skipped
vue-tsc -b && vite build passed
```

### Golden Case 回归集

准备 5 到 10 个典型 FPA 输入案例，每个案例配期望结果或关键断言。重点覆盖：

- 同一对象 CRUD 合并为一个维护类 EI。
- 默认列表查询和条件搜索合并为一个查询类 EQ。
- 普通手机号校验不生成 EIF。
- `processes.type` 写错时必须按描述纠正。
- 普通外部服务调用不生成 EIF。
- 明确外部系统维护的数据组可以生成 EIF。

Golden Cases 不是生产用户直接使用的功能，而是开发、测试、CI/CD 和发布前的质量闸门。

### Golden Case 分层

建议把 golden cases 从单一的 `name + type` 全量比对，拆成两层：

- 固定期望：用于稳定检查关键输出形态，例如必须生成哪些数据功能、事务功能。
- 行为断言：用于检查项目口径是否成立，例如是否合并、是否禁止 EIF 误判、是否纠正错误 type。

行为断言示例：

```text
source_process_ids 是否被正确合并。
查询流程不得判为 EI。
普通校验不得生成 EIF。
同一数据组 CRUD 只能生成一个维护类 EI。
同一列表查询和搜索只能生成一个查询类 EQ。
所有 source_process_ids 必须来自输入 processes.process_id，source_processes 只作为人工审阅展示字段。
```

这样可以避免 AI 文案或名称轻微变化导致测试失败，同时仍能锁住关键计量口径。

当前已在 `tests/test_fpa_golden_fixture_reports.py` 中支持 fixture 级 `assertions` 字段。`vertical_industry_management.json` 已添加 strict_fpa 行为断言，要求：

- 必须包含 `垂直行业查询：EQ`、`垂直行业维护：EI`、`垂直行业管理员维护：EI`。
- `垂直行业查询` 必须合并来源流程 `垂直行业列表数据查询、查询垂直行业数据`。
- `垂直行业维护` 必须合并来源流程 `添加垂直行业、编辑垂直行业、删除垂直行业`。
- 不得出现逐 process 输出的短名称，例如 `添加垂直行业`、`编辑垂直行业`、`删除垂直行业`。

### 结构化断言

不建议用全文比对 AI 输出。更稳定的做法是断言关键行为：

```text
rows 中不得出现“系统用户数据 EIF”，除非输入明确系统用户是外部维护数据组。
添加、编辑、删除同一业务对象时，必须合并到同一个维护类 EI。
默认列表查询和条件搜索读取同一数据组时，必须合并到同一个查询类 EQ。
所有 source_process_ids 必须来自输入 processes.process_id。
查询类流程不得判为 EI。
计算依据说明必须包含来源场景、业务数据、业务规则、计算说明。
```

### 结果校验器

AI 返回 JSON 后，harness 可执行 validator：

- JSON schema 校验。
- 类型合法性校验。
- `classification_basis_index` 合法性校验。
- `source_process_ids` 来源校验；`source_processes` 仅作展示字段和缺失 ID 时的兜底线索。
- 合并规则校验。
- EIF 禁止项校验。
- `计算依据说明` 结构校验。

校验失败时，可以打回模型重试，并附带明确错误，例如：

```text
你错误地将“系统用户校验”识别为 EIF。普通校验服务不得生成 EIF，请修正。
```

当前已实现 `ai_gen_reimbursement_docs/fpa_validator.py`。它只产生 `FpaValidationIssue`，不直接改写 AI rows。这样可以保留审阅透明度，并避免在 `ai_first/ai_only` 策略下悄悄覆盖模型输出。

当前 validator 行为：

- 高置信问题标记为 `retryable=True`，例如查询判 EI、普通服务判 EIF、`source_process_ids` 越界、同一对象 CRUD 拆成多个 EI。
- `ai_first` 首次命中 retryable issue 时自动重试一次。
- 重试后仍命中问题时，不阻断交付物生成，将问题写入 warning、`后处理警告` 和规则命中详情。
- `ai_only` 和预览路径保留 warning，不自动兜底覆盖类型。

### 确认流测试

如果引入 `needs_confirmation` 和 `confirmed_decisions`，harness 也需要覆盖确认流程：

```text
模糊输入在审慎模式下返回 needs_confirmation。
自动模式不返回确认，直接按默认口径生成。
严格确认模式返回所有合并、拆分、EIF、EO 争议点。
带 confirmed_decisions 二次调用后不再在同一问题上摇摆。
scope: current_run 不影响下一次生成。
scope: project_profile 才影响后续生成。
用户修改输入后，旧 confirmed_decisions 被清除或重新校验。
```

确认流测试的重点是保证“用户确认的项目口径”真正进入下一轮生成，并且确认作用域不会意外污染后续交互。

当前已实现后端确认契约和预览路径测试：

- `fpa_confirmation_mode=auto`：不返回确认项。
- `fpa_confirmation_mode=cautious`：只把高风险 validator issue 转换为确认项。
- `fpa_confirmation_mode=strict`：除高风险问题外，也可返回说明结构等审阅项。
- `confirmed_decisions` 支持 `{id: {value, scope}}` 格式，默认作用域为 `current_run`。
- `confirmed_decisions` 会进入下一轮 prompt，作为硬约束文本。
- 已确认的问题不会在同一轮预览中重复返回。
- `scope=project_profile` 会持久化为项目默认口径；后续 FPA 预览和批量正式生成会自动加载，当前请求中的确认结果仍可覆盖已保存口径。

2026-06-08 已完成批量正式生成中的 `needs_confirmation` 暂停/继续流程。正式 Web 生成会将 `fpa_confirmation_mode` 传入 FPA 批量规划；当单个三级模块产生确认项时，FPA 阶段会进入 `waiting_input`，前端展示“确认计量口径”卡片，用户提交 `confirmed_decisions` 后，后端会把确认结果作为硬约束重新生成当前模块，再继续后续批量流程。`auto` 模式仍不暂停。

2026-06-08 已完成 `scope=project_profile` 项目口径持久化。前端确认区提供“仅本次使用 / 保存为项目默认口径”显式选择，默认仍为“仅本次使用”。只有 `scope=project_profile` 的确认结果会写入配置作用域下的 `fpa_project_profile.json`；本地模式使用全局配置目录，远程模式使用当前用户配置目录。`scope=current_run` 不落盘。

### 两阶段生成

稳定性要求更高时，可将 AI 任务拆成两阶段。

第一阶段只抽取业务事实：

```json
{
  "process": "添加垂直行业",
  "operation": "create",
  "target_data_group": "垂直行业",
  "is_query": false,
  "is_data_maintenance": true
}
```

第二阶段由规则引擎或受约束的 AI 根据中间结构合并为最终 FPA rows。

这能把 AI 的自由判断从“直接生成最终结果”降低为“标注业务事实”，再由程序化规则完成合并和纠偏。

当前已完成第一版规则化业务事实中间结构，提交后 `prompt payload` 会同时包含原始 `processes` 和新增 `process_facts`。该层由 `ai_gen_reimbursement_docs/fpa_facts.py` 生成，不依赖 AI，不直接决定最终 FPA rows。

当前 `process_facts` 字段包括：

```json
{
  "process_id": "m1_p1",
  "process_name": "查询客户",
  "input_type": "新增",
  "operation": "query",
  "target_data_group": "客户",
  "query_only": true,
  "changes_internal_data": false,
  "produces_external_output": false,
  "ordinary_external_service": false,
  "external_data_group_evidence": "",
  "confidence": "high",
  "evidence": ["命中关键词：查询", "input_type=新增"]
}
```

这一步先解决“中间结构可见、可测试、可进 prompt”的问题。后续多 Agent 工作流可以让“业务事实抽取 Agent”替换或复核这层输出，但最终仍应保留同样的 JSON 契约，便于 validator 和 golden cases 检查。

当前也已完成第一版规则化合并审查中间结构，`prompt payload` 会新增 `merge_review`。该层由 `ai_gen_reimbursement_docs/fpa_merge_review.py` 基于 `process_facts` 生成，只提出合并边界建议，不直接改写最终 FPA rows。

当前 `merge_review` 字段示例：

```json
{
  "groups": [
    {
      "kind": "maintenance_ei",
      "target_data_group": "垂直行业",
      "process_ids": ["m1_p3", "m1_p4", "m1_p5"],
      "process_names": ["添加垂直行业", "编辑垂直行业", "删除垂直行业"],
      "recommendation": "merge",
      "reason": "同一业务对象的数据维护动作按一个维护类 EI 合并。",
      "needs_confirmation": false
    },
    {
      "kind": "query_eq",
      "target_data_group": "垂直行业",
      "process_ids": ["m1_p1", "m1_p2"],
      "recommendation": "merge",
      "reason": "同一业务对象的默认查询、条件搜索或查看动作按一个查询类 EQ 合并。",
      "needs_confirmation": false
    }
  ],
  "questions": []
}
```

当前还已完成第一版规则化质量审核输出，预览接口和 AI 审计信息会新增 `quality_review`。该层由 `ai_gen_reimbursement_docs/fpa_quality_review.py` 基于最终 rows、validator 和 `merge_review` 生成，只暴露风险和建议动作，不直接改写最终 FPA rows。

当前 `quality_review` 字段示例：

```json
{
  "issues": [
    {
      "code": "quality.merge_review_not_applied",
      "severity": "warning",
      "message": "合并审查建议合并同一数据组的维护动作，但结果仍按多个功能点拆分。",
      "suggested_action": "retry_or_confirm",
      "retryable": true,
      "source_process_ids": ["m1_p3", "m1_p4"]
    }
  ],
  "summary": {
    "issue_count": 1,
    "retryable_count": 1,
    "confirmed_decision_count": 0
  }
}
```

这一步先把“审核 Agent”的职责落成可测试契约：审核节点可以发现 validator 误判和合并建议未应用，但不越权修改 AI 输出。后续如拆成独立 AI Agent，应继续沿用同样的 `quality_review` 结构，便于预览页、审计日志和真实模型稳定性报告复用。

当前已继续推进第一版统一 Agent 分工契约，新增 `ai_gen_reimbursement_docs/fpa_agent_review.py`。该层把已有规则化节点收束为一个 `agent_review`，并进入 prompt payload、预览 debug、正式生成 audit trace 和稳定性报告：

```json
{
  "version": 1,
  "mode": "deterministic_contract",
  "roles": [
    {
      "name": "business_fact_extractor",
      "label": "业务事实抽取 Agent",
      "implementation": "deterministic:fpa_facts.extract_fpa_process_facts",
      "status": "completed",
      "output_key": "process_facts"
    },
    {
      "name": "fpa_type_judge",
      "label": "FPA 类型判定 Agent",
      "implementation": "deterministic:fpa_type_judgement.build_fpa_type_judgement",
      "status": "completed",
      "output_key": "type_judgement"
    },
    {
      "name": "merge_boundary_reviewer",
      "label": "合并边界审查 Agent",
      "implementation": "deterministic:fpa_merge_review.build_fpa_merge_review",
      "status": "completed",
      "output_key": "merge_review"
    },
    {
      "name": "quality_reviewer",
      "label": "质量审核 Agent",
      "implementation": "deterministic:fpa_quality_review.build_fpa_quality_review",
      "status": "completed",
      "output_key": "quality_review"
    }
  ]
}
```

这一步仍不新增额外 AI 调用，也不改变最终功能点计数。它解决的是“Agent 分工可追踪、可测试、可替换”的问题：后续如果要把某个确定性节点替换成独立 AI Agent，只需要保持同样的 `agent_review.roles[*]`、`process_facts`、`type_judgement`、`merge_review`、`quality_review` 契约，稳定性报告也能继续统计 `pending_agent_roles`。

当前已继续完成第一版规则化 FPA 类型判定节点，新增 `ai_gen_reimbursement_docs/fpa_type_judgement.py`。该节点基于 `process_facts` 和 `merge_review` 输出 `type_judgement`，作为生成前的类型建议和质量审核证据链：

```json
{
  "judgements": [
    {
      "id": "type_query_eq_垂直行业",
      "candidate_name": "垂直行业查询",
      "suggested_type": "EQ",
      "judgement_kind": "query_eq",
      "target_data_group": "垂直行业",
      "source_process_ids": ["m1_p1", "m1_p2"],
      "confidence": "high",
      "rationale": "同一列表、搜索或查看场景只读取并展示同类数据，按查询类 EQ 判断。"
    },
    {
      "id": "type_maintenance_ei_垂直行业",
      "candidate_name": "垂直行业维护",
      "suggested_type": "EI",
      "judgement_kind": "maintenance_ei",
      "source_process_ids": ["m1_p3", "m1_p4", "m1_p5"],
      "confidence": "high",
      "rationale": "同一业务对象的新增、修改、删除或维护动作改变本系统内部数据，按维护类 EI 判断。"
    }
  ]
}
```

当前覆盖的确定性建议包括：

- 同一业务对象维护动作合并后建议 EI。
- 同一查询或列表场景合并后建议 EQ。
- 导出、统计、汇总、报表或文件输出建议 EO。
- 明确外部系统维护或本系统不维护的数据组建议 EIF。
- 普通校验、认证、短信、支付、消息调用等没有外部维护数据组证据时建议 `NONE`，即不生成 EIF。

`quality_review` 已接入 `type_judgement`：当最终 rows 的来源流程命中高置信类型建议但类型不一致时，会产生 `quality.type_judgement_mismatch`。该检查仍是非破坏式 warning/retry 信号，不直接改写 AI 输出。

当前已继续将 `quality_review` 的高置信可重试问题接入 `ai_first` 稳定性重试链路：

- validator 反馈优先，用于查询判 EI、普通服务判 EIF、来源流程越界等已有项目口径问题。
- 如果 validator 没有触发重试，但 `quality_review` 发现 `type_judgement` 或 `merge_review` 高置信冲突，则同样只触发一次 AI 重试。
- 重试反馈会明确要求模型遵循 `type_judgement`、`merge_review`，只修正 rows JSON。
- 重试后仍存在质量审核问题时，结果仍保留并写入 warning、audit trace 和稳定性报告，不阻断交付。
- AI audit trace 会写入 `retry_trigger_source`，取值为 `validator` 或 `quality_review`。
- 稳定性报告会汇总 `retry_trigger_source_counts`，Markdown 对比报告会新增 `Retry Triggers` 分布段。
- 稳定性报告会基于 issue code、重试来源和生成来源给出 `recommendations`，Markdown 对比报告会新增 `Recommendations` 段，提示下一步应优先修 prompt、规则、validator、合并口径、说明结构，还是推进真实模型抽样。

这样类型判定节点不只是审计展示，也能在 AI 首次输出偏离高置信建议时参与自动纠偏。

当前已继续修复 rules_only 基线中的确定性质量问题：

- 规则兜底生成的 `计算依据说明` 会统一补齐 `来源场景`、`业务数据`、`业务规则`、`计算说明` 四段结构。
- AI rows 仍保持透明策略，不由该规则静默改写；缺结构时继续进入 warning/quality review。
- `validator.split_crud_ei` 改为按维护对象分桶判断，避免把“垂直行业维护”和“垂直行业管理员维护”误判为同一对象拆分。

最新本地 rules_only standard 抽样结果：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py --preset "" --suite standard --profiles strict_fpa --strategies rules_only --rule-sets strict_fpa_rs --output-dir tmp_fpa_stability_ci_rules --max-retries 0 --max-quality-issues 0 --max-retryable-issues 0
```

```text
Runs: 5
Quality Issues: 0
Retryable Issues: 0
Retries: 0
Quality Gate: PASS
Recommendation: 当前质量信号稳定，可推进真实模型批量抽样。
```

当前已继续增强真实模型抽样入口的安全性：

- `scripts/run_fpa_stability_ci.py` 默认不再隐式启用 `strict-real-model` preset。
- 仅传 `--suite standard` 时，默认按 `strict_fpa + rules_only + strict_fpa_rs` 运行。
- 真实模型抽样必须显式传 `--preset strict-real-model`。
- 新增 `--dry-run`，只打印解析后的 fixture、profile、strategy、rule_set、threshold、output_dir 和 `will_call_model`，不调用模型。

推荐真实模型运行前先执行：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py --dry-run --preset strict-real-model
```

当前继续收敛 agent 分工契约：

- `业务事实抽取 Agent` 会把三级模块整体描述纳入外部维护数据组证据，避免只看单个功能过程时漏掉“本系统不维护”“外部系统维护”的边界信息。
- `FPA 类型判定 Agent` 支持同一功能过程同时产生数据功能建议和事务功能建议，例如“引用外部主数据并保存到当前业务对象”应前置给出 `EIF + EI`，而不是二选一。
- `质量审核 Agent` 对 `external_data_function` 改为检查“是否存在对应 EIF 数据功能行”，不会因为同源 EI 事务行存在而误判；同时支持按 `source_process_ids` 和规则兜底行中的源功能过程名称匹配。
- `strict_fpa` 默认提示词已把 `agent_review.type_judgement`、`merge_review` 和 `process_facts` 写成硬约束：`external_data_function(EIF)` 必须生成 EIF 数据功能行，同源 EI 事务行可以并存但不能替代 EIF。
- 后处理类型冲突检查已消费 `type_judgement` 高置信建议；当 AI 的 EIF 数据功能行被 `external_data_function` 支持时，不再误报 `postprocess.ai_first_type_conflict`。
- rules-only 稳定性基线已重新通过 `quality_issue_count=0`、`retryable_quality_issue_count=0`、`retry_count=0`，真实模型抽样下一步重点转为验证模型是否按前置 agent judgement 主动输出 EIF 数据功能行。

当前 fresh 真实模型标准套件已阶段性通过：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset strict-real-model `
  --output-dir tmp_fpa_stability_ci_real_standard_fresh_20260607 `
  --max-quality-issues 0 `
  --max-retryable-issues 0 `
  --max-retries 0
```

结果：

```text
Status: PASS
Sources: ai=5
Warnings: 6
Quality Issues: 0
Retryable Issues: 0
Retries: 0
```

剩余 warning 均为非阻断后处理提示，集中在三类：计算依据说明仍夹带数据库表个数口径、少数 EIF/ILF 与事务类型规则冲突、以及外部数据组边界需人工复核。下一步应优先收敛 warning，而不是继续扩大抽样。

当前已继续收敛 fresh 真实模型标准套件暴露的 warning：

- `计算依据说明` 中一句归类式短语（例如“符合 ILF 定义，按后台数据库变更的表个数计量”）不再视为详细计量解释错误；只有出现“数据库表个数=...”“表数量...”等把表数量作为明细依据的表达时，才触发 `postprocess.explanation_quality`。
- `strict_fpa` 后处理在判断 AI 数据功能是否需要人工复核时，会消费 `type_judgement` 的高置信建议；当 `external_data_function` 已支持组织主数据等 EIF 行时，不再额外提示“AI 数据功能需人工复核”。
- `strict_fpa` 数据功能名称判断优先识别显式 `数据组`，避免“OA审批流程单据数据组”被名称中的“审批”动作词误判为 EI。
- `strict_fpa` 事务名称判断不再把“短信模板维护”这类维护类事务误吸到 ILF；同源 `ordinary_external_service` 的 `NONE` 判断只表示“不生成 EIF”，不会压过被 AI 正确识别为 EI 的事务行。

本轮目标是让下一次 fresh real-model 标准套件的 warning 更接近真实人工复核点，而不是把可由后处理确定解释的误报继续留在报告中。

2026-06-07 复测 fresh real-model 标准套件后，warning 从 6 条降至 4 条，且 `mixed_internal_external_data_functions` 已归零；剩余 warning 集中在 `sms_notification_service` 的“计算说明未明确当前 FPA 类型”和 `master_data_org_reference` 的来源场景完整路径检查。

当前继续收敛第二轮 warning：`计算说明`在未直接写 `EI/EQ/EO/ILF/EIF` 时，如果已明确使用“外部输入”“外部查询”“外部输出”“内部逻辑数据”“外部逻辑数据/外部数据组”等业务术语，也视为明确当前 FPA 类型，避免将真实模型的自然中文类型说明误报为缺失。

第二轮复测后 `sms_notification_service` 和 `master_data_org_reference` 已归零，但 `mixed_internal_external_data_functions` 暴露了新的类型冲突误报：本系统维护的“供应商准入申请数据组”说明中包含 `关联CRM客户档案ID`、`关联OA审批单ID` 时，后处理规则曾因外部数据规则优先而建议 EIF。当前已调整 strict_fpa 判断优先级：数据功能名称明确且说明有“本系统维护/内部维护/本系统保存”等内部维护证据时，优先保留 ILF；外部引用字段只作为该 ILF 的关联数据，不把本系统维护的数据组改判为 EIF。

2026-06-07 已完成 warning 收敛后的 fresh real-model 标准套件复测：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset strict-real-model `
  --output-dir tmp_fpa_stability_ci_real_standard_fresh_after_internal_data_evidence_20260607 `
  --max-quality-issues 0 `
  --max-retryable-issues 0 `
  --max-retries 0
```

结果：

```text
Status: PASS
Sources: ai=5
Warnings: 0
Quality Issues: 0
Retryable Issues: 0
Retries: 0
```

五个标准样例 `vertical_industry_management`、`mixed_internal_external_data_functions`、`sms_notification_service`、`external_user_center_reference`、`master_data_org_reference` 均为 `warning_count=0`。当前 strict-real-model standard fresh 基线已完成 warning 收敛，可进入更大范围抽样或多次采样趋势对比。

当前已将抽样范围从 standard 5 例扩展到 11 个 golden fixtures。首轮扩展 fresh real-model 抽样暴露 `payment_gateway_refund` 的质量门失败：输入明确说明“支付网关为普通外部服务，不作为外部维护数据组计量”，但事实抽取层曾把否定句中的 `外部维护` 误识别为 EIF 正向证据，导致 `quality.external_data_function_missing` 和一次质量审核重试。

本轮已补充支付网关反例的三层回归测试：

- `process_facts`：普通外部服务否定口径不产生 `external_data_group_evidence`。
- `type_judgement`：支付网关退款结果不生成 `external_data_function`，查看退款结果仍可按查询类 EQ 判断。
- `quality_review`：ILF + EI + EQ 的结果不要求额外补 EIF 行。

实现层已新增外部数据组否定短语识别，并调整 `type_judgement` 顺序：`ordinary_external_service` 只作为“不生成 EIF”的非行级约束，不再吞掉后续查询类 EQ 建议。

2026-06-07 扩展 fresh real-model 11 fixtures 复测结果：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --profiles strict_fpa `
  --strategies ai_first `
  --rule-sets strict_fpa_rs `
  --fixture tests\fixtures\fpa_golden_cases\crm_customer_archive_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\customer_list_import.json `
  --fixture tests\fixtures\fpa_golden_cases\erp_order_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\external_user_center_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\internal_vs_external_org_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\master_data_org_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\mixed_internal_external_data_functions.json `
  --fixture tests\fixtures\fpa_golden_cases\oa_approval_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\payment_gateway_refund.json `
  --fixture tests\fixtures\fpa_golden_cases\sms_notification_service.json `
  --fixture tests\fixtures\fpa_golden_cases\vertical_industry_management.json `
  --output-dir tmp_fpa_stability_ci_real_all_fixtures_fresh_after_payment_gateway_service_20260607 `
  --max-quality-issues 0 `
  --max-retryable-issues 0 `
  --max-retries 0
```

```text
Status: PASS
Runs: 11
Modules: 12
Warnings: 7
Quality Issues: 0
Retryable Issues: 0
Retries: 0
Sources: ai=11, rules_fallback=1
```

其中 `payment_gateway_refund` 已归零。`crm_customer_archive_reference` 本轮真实模型输出发生一次 JSON 解析失败并由规则兜底生成，但质量门仍通过；下一步扩展抽样可优先看剩余 7 条 warning 的来源分布，区分真实复核点、解析失败兜底和可继续收敛的后处理误报。

当前继续收敛扩展集 warning 的确定性误报：

- `计算依据说明` 的来源场景检查不再只接受完整路径；当说明明确引用“模块描述”“业务场景”或源功能过程名时，也视为有可审阅来源锚点，避免用户中心、短信模板、外部组织等自然语言说明被误报。
- 数据组识别改为优先看功能点尾部，避免完整路径中的三级模块动作词（例如“内部组织维护”）污染 `xxx数据组` 的 ILF/EIF 判断。
- 内部数据组证据收窄，避免“外部维护本系统引用的数据组”中的 `维护本系统` 子串被误判为本系统内部维护。
- AI 名称后处理先固定前缀变更，再做 source_process_id 尾部规范化，避免同一名称调整同时产生“末尾规范化”和“前缀规范化”两条 warning。

2026-06-07 扩展 fresh real-model 11 fixtures 最新复测结果：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --profiles strict_fpa `
  --strategies ai_first `
  --rule-sets strict_fpa_rs `
  --fixture tests\fixtures\fpa_golden_cases\crm_customer_archive_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\customer_list_import.json `
  --fixture tests\fixtures\fpa_golden_cases\erp_order_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\external_user_center_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\internal_vs_external_org_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\master_data_org_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\mixed_internal_external_data_functions.json `
  --fixture tests\fixtures\fpa_golden_cases\oa_approval_reference.json `
  --fixture tests\fixtures\fpa_golden_cases\payment_gateway_refund.json `
  --fixture tests\fixtures\fpa_golden_cases\sms_notification_service.json `
  --fixture tests\fixtures\fpa_golden_cases\vertical_industry_management.json `
  --output-dir tmp_fpa_stability_ci_real_all_fixtures_fresh_after_external_reference_text_20260607 `
  --max-quality-issues 0 `
  --max-retryable-issues 0 `
  --max-retries 0
```

```text
Status: PASS
Runs: 11
Modules: 12
Warnings: 6
Quality Issues: 0
Retryable Issues: 0
Retries: 0
Sources: ai=12
```

本轮复测中 `external_user_center_reference`、`internal_vs_external_org_reference`、`mixed_internal_external_data_functions`、`oa_approval_reference` 均已归零。剩余 warning 主要是 AI 行名称末尾按 `source_process_id` 规范化，以及 `sms_notification_service` 一次覆盖补齐；下一步可考虑把确定性名称规范化从稳定性 warning 中降级为 rule hit 信息，或继续从 prompt 侧要求模型直接使用源功能过程名作为事务行尾部。

### 多次采样与择优

对于模型波动较大的场景，可以同一输入生成多次，由 harness 选择通过校验最多、风险最少的一版。该方案成本较高，适合真实模型抽样验收或高风险任务，不建议作为默认生产路径。

### 真实模型稳定性报告

真实模型验收不应只看是否能生成，还应记录稳定性指标：

```text
warning 数量。
needs_confirmation 数量。
确认后重试成功率。
AI 输出被 validator 打回次数。
同一数据组 CRUD 拆分误判率。
普通校验生成 EIF 误判率。
查询判 EI 误判率。
source_processes 越界率。
计算依据说明结构缺失率。
```

这些指标可以进入 check/debug 输出或真实模型验证报告，用于观察 prompt、规则和模型版本变更后的稳定性变化。

当前已完成第一版稳定性指标汇总，由 `ai_gen_reimbursement_docs/fpa_stability_report.py` 从 audit trace 聚合：

- 模块数和生成来源统计：`ai`、`ai_cache`、`rules`、`rules_fallback` 等。
- warning 总数。
- `quality_review` issue 总数和可重试 issue 总数。
- 用户确认数。
- 稳定性校验触发重试次数。
- issue code 分布，例如 `validator.query_as_ei`、`validator.ordinary_service_as_eif`、`quality.merge_review_not_applied`。

正式生成会将汇总写入 `fpa_audit_trace.json` 的 `stability_report` 字段；生成 FPA 审核副本时，会同步生成“稳定性报告”sheet。该 sheet 先提供本次运行的 summary 和模块级明细，后续真实模型抽样可以基于这些字段做跨模型、跨 prompt、跨 rule_set 的趋势对比。

当前也已完成第一版多运行对比能力。多个模型、prompt 或 rule_set 运行完成后，可以用 CLI 汇总多份 trace：

```powershell
ard --fpa-stability-report .\run-a\fpa_audit_trace.json .\run-b\fpa_audit_trace.json --fpa-stability-output .\fpa-stability-report.md
```

输出 Markdown 会包含：

- 总体 Runs/Modules/Warnings/Quality Issues/Confirmations/Retries。
- 每次运行的 case_id、run_id、profile、strategy、rule_set 和稳定性指标。
- `Issue Details` 明细，按 run/case/module 展示 issue code、是否可重试和问题说明，便于直接定位到触发样例。
- issue code 分布。
- warning 来源分布，例如 `validator`、`quality_review`、`postprocess_normalization`、`fallback`、`manual_review`、`config`。
- `ai`、`ai_cache`、`rules`、`rules_fallback` 等生成来源分布。

当前还已完成第一版自动批量抽样执行器。可以直接基于现有 FPA golden fixture 生成多组 trace 和汇总报告：

```powershell
ard --fpa-stability-sample-suite standard `
  --fpa-stability-sample-profiles strict_fpa `
  --fpa-stability-sample-strategies rules_only `
  --fpa-stability-sample-rule-sets strict_fpa_rs `
  --output-dir .\fpa-stability-samples
```

输出目录会包含：

- 每个 fixture/config 组合的 `module_tree.md`、`meta.md`、`fpa.md`、`summary.md`、`fpa_audit_trace.json`。
- `fpa-stability-sampling-manifest.json`。
- `fpa-stability-sampling-report.md`。

采样器会把 `case_id`、`run_id`、`run_dir` 和 `fixture_path` 写回每个 `fpa_audit_trace.json`。后续即使只拿 trace 重新生成对比报告，也能保留样例和运行配置定位信息。

第一版默认可用 `rules_only` 做无模型基线；传入 `--api-key`、`--model`、`--base-url` 并选择 `ai_first`/`ai_only` 后，可复用同一入口做真实模型抽样。

当前 `standard` 推荐样例集包含 5 类高风险口径：

- 垂直行业管理：同一业务对象维护和查询合并。
- 内外部数据功能混合：ILF/EIF 边界。
- 短信通知服务：普通外部服务不生成 EIF。
- 外部用户中心引用：明确外部维护数据组可生成 EIF。
- 主数据组织引用：组织主数据 EIF 识别。

当前还提供 `real-model-recommended` 扩展推荐样例集，面向真实模型抽样，覆盖 10 个已有 golden fixture：

- `vertical_industry_management.json`
- `mixed_internal_external_data_functions.json`
- `sms_notification_service.json`
- `external_user_center_reference.json`
- `master_data_org_reference.json`
- `internal_vs_external_org_reference.json`
- `oa_approval_reference.json`
- `payment_gateway_refund.json`
- `crm_customer_archive_reference.json`
- `customer_list_import.json`

该扩展集用于区分真实复核点、AI 解析失败后的规则兜底、确定性后处理规范化和可继续收敛的 prompt/validator 问题。报告中的 `Warning Sources` 分类口径如下：

- `validator`：高置信规则校验或 validator 重试来源。
- `quality_review`：AI 与 `type_judgement`、`merge_review` 等中间判断不一致。
- `postprocess_normalization`：名称、归类、`source_process_id` 等确定性规范化提示。
- `fallback`：AI 调用/解析失败、缺少 API Key 或规则兜底相关提示。
- `manual_review`：外部数据组边界等需要人工确认的复核点。
- `config`：FPA 配置 warning。
- `other`：暂未归入上述类别的普通 warning。

真实模型抽样可使用预设命令：

```powershell
ard --fpa-stability-sample-preset strict-real-model `
  --api-key <API_KEY> `
  --model <MODEL_NAME> `
  --output-dir .\fpa-stability-real-model-samples
```

`strict-real-model` 会展开为：

- `suite=standard`
- `profile=strict_fpa`
- `strategy=ai_first`
- `rule_set=strict_fpa_rs`
- `max_retryable_issues=0`
- `max_retries=0`

如果同时传入 `--fpa-stability-sample-profiles`、`--fpa-stability-sample-strategies`、`--fpa-stability-sample-rule-sets` 或质量门参数，显式参数会覆盖 preset 中的默认值。

扩展推荐样例集可使用：

```powershell
ard --fpa-stability-sample-preset strict-real-model-recommended `
  --api-key <API_KEY> `
  --model <MODEL_NAME> `
  --output-dir .\fpa-stability-real-model-recommended-samples
```

`strict-real-model-recommended` 会展开为：

- `suite=real-model-recommended`
- `profile=strict_fpa`
- `strategy=ai_first`
- `rule_set=strict_fpa_rs`
- `max_retryable_issues=0`
- `max_retries=0`

如果只是本地确认抽样计划、不调用模型，可以使用：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --dry-run `
  --preset strict-real-model-recommended
```

阅读扩展集报告时，建议先看 `Quality Gate`，再看 `Warning Sources`。如果 warning 主要集中在 `postprocess_normalization`，优先考虑是否降级为 rule hit；如果集中在 `manual_review`，优先沉淀为 `project_profile`、领域上下文或明确的外部数据组规则；如果集中在 `fallback`，优先定位模型响应解析、API 可用性和规则兜底路径。

当前还已补充第一版稳定性质量门。多 trace 对比或 fixture 采样时，可以增加阈值参数：

```powershell
ard --fpa-stability-sample-fixtures .\tests\fixtures\fpa_golden_cases\vertical_industry_management.json `
  --fpa-stability-sample-profiles strict_fpa `
  --fpa-stability-sample-strategies rules_only `
  --fpa-stability-max-retryable-issues 0 `
  --fpa-stability-max-retries 0 `
  --output-dir .\fpa-stability-samples
```

当前支持的阈值包括：

- `--fpa-stability-max-warnings`
- `--fpa-stability-max-quality-issues`
- `--fpa-stability-max-retryable-issues`
- `--fpa-stability-max-retries`

未传入阈值时只生成报告，不判定通过/失败；传入阈值后，Markdown 报告会增加 `Quality Gate` 区块，manifest/comparison 中会写入 `evaluation.status=pass|fail` 和每项检查结果。若质量门失败，CLI 会返回退出码 `2`，便于接入 CI 或自动验收。

阅读报告时建议先看 `Quality Gate` 是否失败，再看 `Issue Details`。例如规则基线只配置 `max_retries=0` 时，报告可能因为未发生重试而 PASS，但仍会列出 `validator.explanation_structure` 等非阻断质量提示；如果出现 `retryable=yes` 的 `validator.split_crud_ei`、`validator.query_as_ei` 或 `validator.ordinary_service_as_eif`，应优先回到对应 `case_id/run_id` 检查输入和生成结果。

2026-06-08 已将 `AI 行名称末尾已按 source_process_id 规范化` 从模块级 warning 降级为 `postprocess.ai_name_process_suffix` 规则命中。该类信息仍会进入 audit trace 和 check Excel 的规则命中详情，用于追溯 AI 原始名称与源功能过程名称的差异，但不再计入稳定性报告的 `warning_count`。`AI 行名称前缀已按源功能清单规范化` 仍保留为 warning，因为它代表 AI 输出跨模块或路径前缀不一致，仍需要显式暴露。

2026-06-08 已将 `ai_first` 下确定性追加的 `rules_fallback` 覆盖补齐从稳定性报告 warning 统计中排除。`AI 结果未覆盖...已追加 rules_fallback 行` 和 `AI 结果未包含数据功能行...已追加 rules_fallback 行` 仍保留在 audit trace、check Excel 和 `coverage.rules_fallback` 规则命中详情中，用于审阅 AI 覆盖缺口；但真实模型趋势报告不再把已被规则集补齐且质量审核通过的补齐动作计为模型 warning。

2026-06-08 已将可确定的 `计算依据说明` 来源场景路径规范化为后处理规则命中。AI 返回结构化说明但 `来源场景` 未使用当前 FPA 行完整路径时，后处理会把该行改为 `来源场景：<完整新增/修改功能点>`，并记录 `postprocess.explanation_source_path`；缺少结构化项、类型未说明、表个数计量描述等真实说明质量问题仍保留为 warning。

2026-06-08 已收口 OA 审批单关联口径：OA 系统维护的审批流程单据按 `EIF`，本系统保存的业务对象与审批单关联关系按 `ILF`，用户选择审批单并保存关联关系按 `EI`，查看审批进度按 `EQ`。`ai_first` 下如果 AI 已输出内部 `ILF` 但漏掉外部 `EIF`，规则补齐会按数据功能类型补齐缺失的 `EIF`，并继续通过 `coverage.rules_fallback` 追溯。

2026-06-08 已补充真实模型质量门的 `blocking_retry_count` 口径：`retry_count` 继续记录真实发生过的稳定性重试，`blocking_retry_count` 只统计重试后最终仍存在质量审核问题的阻断性重试。`strict-real-model` 和 `strict-real-model-recommended` preset 的质量门改为检查 `retryable_quality_issue_count=0` 与 `blocking_retry_count=0`，避免把已经自愈且最终质量审核通过的真实模型波动当作失败。

2026-06-08 完成 `strict-real-model-recommended` 推荐集最终复测：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset strict-real-model-recommended `
  --output-dir tmp_fpa_stability_ci_real_recommended_final_20260608
```

复测结果：Quality Gate PASS；`run_count=10`，`module_count=11`，`quality_issue_count=0`，`retryable_quality_issue_count=0`，`retry_count=1`，`blocking_retry_count=0`。剩余 `warning_count=7` 均非阻断，来源分布为 `postprocess_normalization=4`、`quality_review=1`、`other=2`。当前 recommended 集合已完成 OA 审批单关联口径、组织维护 EI 口径和真实模型质量门收口。

也可以直接使用 CI 友好的脚本入口：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset strict-real-model `
  --output-dir .\tmp_fpa_stability_ci
```

该脚本会打印 JSON 摘要，包含 `status`、`report_path` 和 `run_count`；当质量门失败时返回退出码 `2`，其它异常仍按普通错误返回非 0。无真实模型 API 时，可以用规则基线模式做本地烟测：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_fpa_stability_ci.py `
  --preset "" `
  --suite standard `
  --profiles strict_fpa `
  --strategies rules_only `
  --rule-sets strict_fpa_rs `
  --max-retries 0 `
  --output-dir .\tmp_fpa_stability_ci
```

CI 接入说明和 GitHub Actions 示例见 [`docs/fpa/fpa-stability-ci.md`](fpa-stability-ci.md)。

### 增强优先级

推荐按以下优先级增强 harness：

```text
P0：持续锁定 strict_fpa 逻辑事务合并口径，确保 golden fixtures、prompt、后处理规则和测试断言一致。
P1：新增结构化 validator，抓查询误判、EIF 误判、source_processes 越界、说明结构缺失等典型问题。
P2：补充确认流测试，覆盖 needs_confirmation、confirmed_decisions 和确认作用域。
P3：把 golden cases 拆成“固定期望 + 行为断言”两层。
P4：增加真实模型稳定性报告，持续跟踪 warning、确认率、重试率和误判率。
```

当前状态：

```text
P0：已完成。strict_fpa 逻辑事务合并口径已有 profile、prompt、fixture、测试锁定。
P1：已完成第一版。validator 已进入 AI 后处理和预览路径。
P2：已完成后端契约、预览测试、FPA 预览页确认卡片、批量正式生成中的暂停/继续流程，以及 `scope=project_profile` 项目口径持久化。
P3：已完成第一版。fixture 支持固定期望 + 行为断言，垂直行业样例已落地。
两阶段生成：已完成第一版规则化 `process_facts`、`type_judgement`、`merge_review` 和 `quality_review` 中间结构，并已新增统一 `agent_review` 分工契约；当前仍未引入额外 AI Agent 调用。
P4：已完成第一版指标沉淀、多 trace Markdown 对比报告、fixture 批量抽样执行器、稳定性质量门、真实模型推荐样例集和 warning 来源分类。后续可用真实 API Key 跑 `strict-real-model-recommended` 做 fresh 抽样。
```

## Agent 工作流方案

采用 Agent 对 `gen-fpa` 输出稳定性有帮助，但前提是 Agent 不是简单“换一个 AI 再问一遍”，也不是只把提示词拆细后多次调用模型。

### Agent 定义

本文中的 Agent 是参与生成流程的 AI 工作单元，有明确职责、固定输入输出、判断边界，并能被规则或工具约束。它更像流程里的一个岗位，而不是一个万能聊天窗口。

可以把 Agent 理解为“被工程流程约束住的专职 AI 节点”：

```text
prompt：一次调用里告诉 AI 怎么做。
agent：流程里的一个 AI 节点，负责某一类任务。
harness：验收生成结果是否符合预期口径。
规则引擎：执行确定性约束。
```

Agent 的关键特征是：

- 职责单一：只负责抽取、判定、合并审查或质量审核中的一种任务。
- 输入输出结构化：优先输出 JSON 等可被程序消费的中间结果。
- 判断范围受限：不越权生成最终结果，不编造数据组、接口、表或系统。
- 可被校验：输出可以被 validator、golden cases 或行为断言检查。
- 可接规则和工具：可以读取领域文档、规则配置、历史确认或后处理结果。

如果只是把一个大 prompt 拆成多个 prompt 连续询问，但每一步没有结构化输出、没有判断边界、没有校验机制，那么它只能算多轮 LLM 调用，不足以支撑稳定性。

落到 `gen-fpa` 时，Agent 通常包含：

- 角色职责：只做一个窄任务，例如抽取业务事实、判断类型、审查合并、检查误判。
- 固定输入输出：优先输出可被程序消费的 JSON，而不是自由长文。
- 独立判断边界：每个 Agent 只能处理自己的判断范围，不越权生成最终结果或编造数据。
- 规则和工具约束：可以接入 validator、golden cases、领域文档、后处理规则和人工复核机制。

因此，Agent 的最小实现可以是“细化 prompt + 多次调用 AI”，但更完整的实现应是：

```text
细化 prompt
+ 多次调用 AI
+ 每次调用职责单一
+ 中间结果结构化
+ 程序规则校验
+ 失败重试或人工复核
```

### 推荐角色拆分

对于 `gen-fpa`，可按以下职责拆分 Agent：

- 业务事实抽取 Agent：只从模块输入和 `processes` 中抽取业务动作、目标数据组、输入输出、是否查询、是否维护数据。
- FPA 类型判定 Agent：只基于业务事实判断 EI、EQ、EO、ILF、EIF，不决定最终合并数量。
- 合并审查 Agent：只判断同一 ILF 的维护动作是否合并、同一列表查询是否合并。
- 质量审核 Agent：只检查结果是否违反项目口径，不直接重写结果。

业务事实抽取 Agent 的输出示例：

```json
{
  "process": "编辑垂直行业",
  "operation": "update",
  "target_data_group": "垂直行业",
  "changes_internal_data": true,
  "query_only": false,
  "external_data_group_evidence": null
}
```

### 推荐编排方式

建议采用以下流程：

```text
业务事实抽取 Agent
        ↓
规则引擎合并/纠偏
        ↓
FPA 结果生成 Agent
        ↓
审核 Agent + validator
        ↓
最终 rows / warning / 人工复核点
```

当前实现中，`quality_review` 已先作为规则化审核节点接入预览 debug 和 AI audit metadata。它对应上图的“审核 Agent + validator”位置，但仍是确定性程序，不额外调用 AI。

其中真正提升稳定性的不是“调用 AI 多次”，而是让每次 AI 只做小判断，并让中间结果可以被规则和测试检查。

### Agent 的适用边界

Agent 适合处理理解、解释、证据组织和争议点标注。例如：

```text
争议点：新增垂直行业管理员时校验手机号是否构成 EIF。
建议：不生成 EIF。
原因：输入只体现校验服务，没有明确外部维护数据组。
```

但 Agent 不应替代硬规则。以下事项仍建议由规则引擎或 validator 兜底：

- `source_processes` 必须来自输入。
- 查询类流程不得判为 EI。
- 普通校验服务不得直接生成 EIF。
- 同一 ILF 的同一管理界面 CRUD 不应被拆成多个 EI。
- 同一列表界面的默认查询和条件搜索不应被拆成多个 EQ。

结论是：Agent 可以提升稳定性，但要和中间结构、规则引擎、harness、golden cases 一起使用。单纯把一次生成改成多次 AI 对话，收益有限。

## 用户确认机制

当 LLM 在调用过程中遇到模糊点时，可以暂停最终生成，返回结构化确认项让用户选择。对 FPA 这种“规则 + 业务口径 + 输入不完整”的任务，这比让模型硬猜更稳定。

该机制不应设计成自由聊天式追问，而应设计成争议点确认流程：模型只在高风险模糊点上提问，并给出推荐选项、原因和可追踪的确认 ID。

### 适合返回确认的场景

建议在以下场景触发用户确认：

- 同一数据组的新增、修改、删除是否合并为一个维护类 EI，输入没有明确界面关系。
- 默认列表查询和条件搜索是否合并为一个查询类 EQ，输入没有明确是否同一列表界面。
- 外部校验、权限校验、手机号校验是否构成 EIF，输入没有明确外部维护数据组。
- 某个输出是否属于普通查询展示还是派生输出，EO 边界不清。
- 一个功能过程可能同时涉及多个业务对象或多个数据组，拆分边界不清。

### 推荐模式

可以提供三种运行模式：

- 自动模式：不询问用户，按默认项目口径处理，适合批量生成。
- 审慎模式：只在高风险模糊点上返回确认，适合真实业务生成，建议作为默认交互模式。
- 严格确认模式：所有合并、拆分、EIF、EO 等争议点都列出给用户确认，适合验收、审计和关键项目。

### 确认项格式

确认项应结构化返回，便于前端展示和下一轮调用复用。

```json
{
  "status": "needs_confirmation",
  "questions": [
    {
      "id": "merge_vertical_industry_crud",
      "topic": "维护类 EI 合并",
      "question": "是否将添加、编辑、删除垂直行业合并为一个“垂直行业维护”EI？",
      "recommendation": "yes",
      "reason": "三个操作针对同一数据组，且属于同一管理界面或同一业务维护场景。",
      "options": [
        {
          "value": "yes",
          "label": "合并为一个 EI"
        },
        {
          "value": "no",
          "label": "分别计为多个 EI"
        }
      ]
    }
  ]
}
```

用户确认后，下一轮调用应携带确认结果：

```json
{
  "confirmed_decisions": {
    "merge_vertical_industry_crud": "yes"
  }
}
```

确认结果进入下一轮生成时，应作为硬约束使用。模型不得在同一问题上重新摇摆，除非用户修改输入或清除确认。

### 流程位置

推荐将用户确认机制放在业务事实抽取和最终生成之间：

```text
输入模块
  ↓
AI 抽取业务事实
  ↓
规则/AI 识别争议点
  ↓
如果无争议：直接生成
如果有争议：返回用户确认
  ↓
带 confirmed_decisions 重新生成
  ↓
validator 校验
```

这层机制的价值是把“模型猜测”变成“用户确认的项目口径”。确认结果还可以沉淀为后续 prompt、golden cases 或规则引擎的输入。

## 交互实现方案

用户确认机制在交互上建议做成“生成前/生成中确认争议点”的流程，不建议做成聊天式问答。这样更容易被前端组件承载，也更便于后端复用确认结果。

### 主流程

推荐流程如下：

```text
用户点击生成 FPA
  ↓
后端/AI 先做业务事实抽取和争议点识别
  ↓
如果没有争议点：直接生成结果
  ↓
如果有争议点：前端展示“确认计量口径”
  ↓
用户选择后点击“继续生成”
  ↓
带 confirmed_decisions 再次调用生成
  ↓
展示最终 FPA 结果
```

前端可以用弹窗或中间页承载确认项。推荐标题：

```text
确认计量口径
```

弹窗适合少量确认项；中间页适合严格确认模式或确认项较多的场景。

### 高级选项入口

在生成参数或高级选项中增加运行模式配置：

```text
生成模式：
[自动模式] [审慎模式] [严格确认模式]
```

建议默认使用审慎模式：

- 自动模式：不展示确认，按默认规则生成，适合批量生成。
- 审慎模式：只对高风险争议点展示确认，适合日常业务生成。
- 严格确认模式：所有合并、拆分、EIF、EO 争议都展示确认，适合验收和审计。

当前 Web 已在高级选项中增加 `FPA 生成模式` 下拉框，选项来自 `/api/fpa/options`：

```json
[
  {"name": "auto", "label": "自动模式"},
  {"name": "cautious", "label": "审慎模式"},
  {"name": "strict", "label": "严格确认模式"}
]
```

默认值为 `cautious`。FPA 预览请求会携带 `fpa_confirmation_mode`；正式运行请求也会携带该字段。当前批量生成已支持在高风险确认项上暂停，前端提交 `confirmed_decisions` 后继续生成；`auto` 模式仍按非阻断 warning/重试路径执行。

### 确认卡片

每个争议点展示为一张确认卡片，包含主题、问题、推荐选项、原因和用户选择。

维护类 EI 合并示例：

```text
维护类 EI 合并

是否将“添加垂直行业、编辑垂直行业、删除垂直行业”
合并为一个“垂直行业维护”EI？

推荐：合并为一个 EI
原因：三个操作针对同一数据组，且属于同一管理界面或同一业务维护场景。

[合并为一个 EI] [分别计为多个 EI]
```

EIF 识别示例：

```text
EIF 识别

“校验手机号必须为系统用户”是否生成系统用户 EIF？

推荐：不生成 EIF
原因：输入只体现校验动作，没有明确外部系统维护的数据组。

[不生成 EIF] [生成 EIF]
```

### 前后端契约

第一次生成如果需要确认，后端返回：

```json
{
  "status": "needs_confirmation",
  "questions": [
    {
      "id": "merge_vertical_industry_crud",
      "topic": "维护类 EI 合并",
      "question": "是否将添加、编辑、删除垂直行业合并为一个“垂直行业维护”EI？",
      "recommendation": "yes",
      "reason": "三个操作针对同一数据组，且属于同一管理界面。",
      "options": [
        {
          "value": "yes",
          "label": "合并为一个 EI"
        },
        {
          "value": "no",
          "label": "分别计为多个 EI"
        }
      ]
    }
  ]
}
```

用户确认后，前端再次提交：

```json
{
  "confirmed_decisions": {
    "merge_vertical_industry_crud": {
      "value": "yes",
      "scope": "current_run"
    }
  }
}
```

后端生成最终结果时，应将 `confirmed_decisions` 写入 prompt、规则上下文或后处理上下文，并作为硬约束执行。

当前预览接口实际返回字段为：

```json
{
  "status": "needs_confirmation",
  "confirmation_mode": "cautious",
  "confirmation_questions": [],
  "confirmed_decision_count": 0,
  "rows": [],
  "warnings": []
}
```

其中 `confirmation_questions` 中的确认项包含：

- `id`
- `topic`
- `question`
- `recommendation`
- `reason`
- `options`
- `source_issue`

### 确认作用域

本次交互中的确认结果默认只影响本次生成，不应自动影响以后所有交互。

确认可以分为两类：

- 本次输入相关确认：只和当前模块、当前 `processes` 有关，例如是否将添加、编辑、删除垂直行业合并为一个 EI。
- 项目口径确认：可以沉淀为当前项目的默认计量口径，例如普通手机号校验不生成 EIF、同一列表的默认查询和条件搜索合并为一个 EQ。

推荐交互提供两个明确动作：

```text
[仅本次使用] [保存为项目默认口径]
```

默认选择“仅本次使用”。只有用户显式选择“保存为项目默认口径”时，才影响后续生成。

本次有效的确认示例：

```json
{
  "confirmed_decisions": {
    "merge_vertical_industry_crud": {
      "value": "yes",
      "scope": "current_run"
    }
  }
}
```

保存为项目口径的确认示例：

```json
{
  "confirmed_decisions": {
    "crud_same_ilf_same_ui_merge": {
      "value": "yes",
      "scope": "project_profile"
    }
  }
}
```

更高权限的全局规则、prompt 更新或 golden cases 更新，不应由一次普通确认自动触发，应通过单独的配置入口、文档变更或开发流程完成。

### 结果页追溯

最终 FPA 结果页建议展示一条轻量提示：

```text
已应用 3 项计量口径确认
```

用户展开后可以看到确认记录：

```text
维护类 EI 合并：合并为一个 EI
EIF 识别：不生成 EIF
查询类 EQ 合并：合并为一个 EQ
```

这些确认记录应进入 check/debug 输出，便于人工审阅和问题复盘。

### 交互原则

- 默认不打扰用户，只在影响新增/修改功能点数量或类型的高风险问题上确认。
- 每个确认项必须给出推荐选项和原因，不让用户从零判断。
- 用户确认后，同一轮生成不得在同一问题上重新摇摆。
- 本次确认默认仅本次生成有效，不自动污染后续交互。
- 保存为项目口径必须由用户显式选择，并记录作用域。
- 用户修改输入后，应清除或重新校验已有确认项。
- 批量生成时可使用自动模式，并将争议点写入 warning。

## 生产系统可复用的校验机制

Golden Cases 主要用于开发、测试和 CI/CD，不直接在生产系统中给用户运行。

生产系统更适合复用以下机制：

- JSON schema 校验。
- `source_processes` 来源校验。
- 类型与流程名称的冲突检查。
- 同一数据组 CRUD 被拆成多个 EI 的 warning。
- 同一列表查询和搜索被拆成多个 EQ 的 warning。
- 普通校验服务生成 EIF 的 warning 或阻断。
- `计算依据说明` 结构缺失 warning。

生产路径可以采用非阻断策略：将问题写入 check/debug 输出，供人工审阅；对于高置信误判，例如查询流程被判为 EI、普通校验生成 EIF，也可以触发自动重试。

如果生产系统采用审慎模式，也可以在 validator 或争议点识别阶段返回 `needs_confirmation`，由用户确认后再生成最终结果。该路径适合低频但高要求的 FPA 评估，不适合完全无人值守的批量生成。

## 推荐落地路径

建议按以下顺序推进：

1. 先固化提示词决策树，明确合并、拆分和 EIF 边界。
2. 补充 5 到 10 个 Golden Cases，覆盖常见误判场景。
3. 在 harness 中增加结构化断言，不做全文比对。
4. 增加结果校验器，将高风险误判写入 warning 或触发重试。
5. 评估是否需要两阶段生成，把业务事实抽取和 FPA 合并分离。
6. 增加用户确认机制，在高风险模糊点上返回 `needs_confirmation`。
7. 如果模型波动仍然明显，再引入 Agent 工作流，把抽取、判定、合并、审核拆成独立节点。
8. 在真实模型上抽样验证，观察 warning、重试率、确认率和人工修改率。

最低成本的可落地组合是：

```text
提示词决策树 + Golden Cases + 结构化断言 + 结果校验器
```

更稳的长期方案是：

```text
提示词负责业务口径，用户确认负责模糊口径，Agent 负责理解和解释，harness 负责验收口径，后处理规则负责稳定归并。
```

## 附：通用 gen-fpa 提示词草案

```text
你是 FPA 功能点分析专家。请基于输入的模块信息、模块描述、业务流程 processes，生成 FPA 功能点识别结果。

必须严格遵循以下规则：

1. 不盲信 processes 中的 type 字段
- processes.type 只能作为参考，不作为最终判定依据。
- 必须根据流程名称、操作描述、输入输出、是否维护数据、是否查询数据来重新判断类型。
- 例如：名称包含“查询”“列表”“搜索”“查看”，且只读取数据并展示，通常判定为 EQ，而不是 EI。

2. 先识别数据功能
- 识别本系统内部维护的逻辑数据组，计为 ILF。
- 只有当数据组由外部系统维护，且本系统仅引用或读取该外部数据组时，才计为 EIF。
- 普通外部服务调用、校验接口、手机号校验、权限校验、认证校验，不自动生成 EIF。
- 不得编造输入中没有明确出现的数据组、表、接口、系统或字段。

3. 再识别事务功能
- EI：用户输入或触发操作，导致系统内部 ILF 被新增、修改、删除。
- EQ：用户查询、搜索、查看列表、详情展示，系统读取 ILF/EIF 并展示结果，且没有派生计算或复杂加工输出。
- EO：系统产生派生数据、统计结果、计算结果、报表、导出、汇总、通知输出等外部输出。
- 如果只是读取数据并原样展示，不得判为 EO，应判为 EQ。

4. 相同数据组的维护操作要合并
- 对同一个 ILF 的新增、修改、删除，如果发生在同一管理界面、同一业务对象、同一组操作入口中，应合并为一个 EI。
- 合并后的功能点名称应使用“xxx维护”。
- source_processes 必须列出被合并的原始流程。
- split_reason 必须说明为什么合并。

5. 相同数据组的查询操作要合并
- 默认列表查询、条件搜索、按名称查询，如果读取同一个数据组，并在同一查询或列表界面展示相同类型结果，应合并为一个 EQ。
- 合并后的功能点名称应使用“xxx查询”。
- source_processes 必须列出被合并的查询流程。
- split_reason 必须说明为什么合并。

6. 不因流程数量直接等于功能点数量
- 输入中有多个 processes，不代表必须输出相同数量的功能点。
- 必须按 FPA 逻辑事务和逻辑数据组进行合并、拆分。
- 如果多个流程属于同一逻辑事务，应合并。
- 如果一个流程中实际包含多个独立逻辑数据组或独立事务，应拆分。

7. 功能点名称格式
name 必须使用以下格式：

【客户端类型】一级模块-二级模块-三级模块-功能点名称

其中：
- 客户端类型、一级模块、二级模块、三级模块必须来自输入。
- 功能点名称可以根据 FPA 合并结果重新命名。
- ILF/EIF 数据功能建议命名为“xxx数据组”。
- 维护类 EI 建议命名为“xxx维护”。
- 查询类 EQ 建议命名为“xxx查询”。
- 输出类 EO 建议命名为“xxx输出 / xxx导出 / xxx报表”。

8. 计算依据归类
classification_basis_index 必须选择最贴近的归类编号：
- EI 有界面操作时，优先选择“修改或增加界面的个数”对应编号。
- EQ 查询界面输入并展示返回结果时，选择“提供查询界面输入并展示返回结果”对应编号。
- ILF 识别内部维护数据组时，选择“后台数据库变更的表个数”对应编号。
- 不得随意选择不匹配的归类编号。

9. 计算依据说明必须结构化
每个功能点的 explanation 必须包含：
- 来源场景：说明来自哪个客户端/模块/流程。
- 业务数据：列出输入中明确出现的数据对象和字段，不得编造。
- 业务规则：说明用户动作、系统处理和业务限制。
- 计算说明：说明为什么纳入 FPA 计量、为什么判为 EI/EQ/EO/ILF/EIF。

10. type_reason 必须说明判定原因
type_reason 不能只写“属于 EI”。
必须说明：
- 是否维护 ILF；
- 是否只是查询展示；
- 是否有派生输出；
- 是否由本系统维护数据组；
- 为什么不是其他类型。

11. source_process_ids / source_processes
- 事务功能必须在 source_process_ids 中列出对应的原始 processes.process_id。
- 合并功能点必须列出所有被合并流程的 process_id。
- source_processes 继续列出对应流程名称，用于人工审阅展示。
- 数据功能可以列出识别该数据组所依据的相关流程 ID；如果数据组来自模块整体而非单一流程，允许为空。
- 不得写不存在的 process_id；流程名称不作为主覆盖判断依据。

12. split_reason
- 如果功能点由多个流程合并而来，必须说明合并原因。
- 如果没有合并，split_reason 可为空字符串。
- 合并说明必须明确：
  - 是否针对同一 ILF/EIF；
  - 是否属于同一界面或同一业务对象；
  - 为什么按 FPA 规则合并为一个功能点。

13. 严禁行为
- 不得因为输入 type 写“新增”就直接判 EI。
- 不得把查询流程判为 EI。
- 不得把普通校验服务判为 EIF。
- 不得编造外部系统、数据库表、接口、字段。
- 不得把同一界面的同一数据组 CRUD 拆成多个 EI。
- 不得把同一列表的默认查询和条件搜索拆成多个 EQ，除非输入明确显示它们是不同业务对象、不同输出结构或不同用户目标。

输出格式必须为 JSON：

{
  "rows": [
    {
      "name": "【客户端类型】一级模块-二级模块-三级模块-功能点名称",
      "type": "EI | EQ | EO | ILF | EIF",
      "type_reason": "类型判定原因",
      "classification_basis_index": 数字,
      "explanation": "来源场景：...\n业务数据：...\n业务规则：...\n计算说明：...",
      "source_process_ids": ["m1_p1", "m1_p2"],
      "source_processes": ["原始流程名称1", "原始流程名称2"],
      "split_reason": "合并或拆分原因；无则为空字符串"
    }
  ]
}
```
