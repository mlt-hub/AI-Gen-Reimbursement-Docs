# unified_ui profile 口径调整方案

## 背景

`unified_ui` profile 用于生成报账模板友好的 FPA 工作量评估结果。当前口径已经支持三级模块级界面合并、非界面处理行补充、规则兜底和 AI prompt 约束，但部分类型映射与目标交付口径仍不一致：

- 查询类处理当前容易映射为 `EQ`。
- 导入类处理当前容易映射为 `EI`。
- 非界面行名称多使用“逻辑处理开发”“查询处理开发”等旧表达。
- 界面行虽然已有合并要求，但还需要更明确约束“不要把简单页面拆得过细”。

本方案记录新的 `unified_ui` profile 目标口径，作为后续配置、规则、测试和文档修改依据。

## 推进状态

截至本轮推进，配置结构、`unified_ui` 类型口径、fallback 命名、配置诊断、核心测试和 profile 文档已经完成落地：

1. `calculation_explanation_rules` 已提升为顶层配置段，默认 profile 已通过 `profiles.<profile>.calculation_explanation_rules` 显式绑定。
2. `unified_ui` 与 `multi_uis` 已使用统一界面口径的说明规则，`strict_fpa` 保留标准 FPA 结构化证据说明。
3. `unified_ui_rs` 已将查询/查看类能力按 `ILF` 输出为“逻辑接口开发”，导入按 `EQ` 输出为“导入处理开发”，导出按 `EO` 输出为“导出处理开发”，明确外部边界按 `EIF` 输出为“外部接口联调调用”。
4. fallback 行命名已从单纯按类型推后缀调整为优先按关键词/业务动作命中规则，再使用对应类型后缀。
5. 垂直行业管理 golden case 已收敛为单一“查询垂直行业-逻辑接口开发”能力行，避免继续按列表查询和条件查询拆成两条非界面行。

后续已有 `ui_api_mapping` 专项方案对计算依据说明做了差异化增强，因此当前默认配置保留 `ui_api_mapping_workload_eval_ce` 绑定，不再强行回退为与 `unified_ui_ce` 完全一致的 `ui_api_mapping_ce`。`ui_api_mapping_ce` 仍作为通用别名存在，便于自定义 profile 复用统一界面说明口径。

## 目标行为

`unified_ui` 输出应以三级模块为主要组织粒度，界面类能力合并，非界面能力按业务动作或数据处理能力拆分。

类型规则：

| 场景 | 类型 | 输出口径 |
|---|---|---|
| 界面类 | EI | 同一三级模块内的列表、条件查询组件、按钮、弹窗、状态组件、管理界面等默认合并为一条界面开发行。 |
| 逻辑接口/表 | ILF | 添加、编辑、查询、删除、状态更新、数据表新增修改等均按逻辑接口/表能力输出。 |
| 导入 | EQ | 导入类能力单独输出一行。 |
| 导出 | EO | 导出、下载、报表输出、生成文件等单独输出一行。 |
| 外部接口联调调用 | EIF | 外部接口联调、外部系统调用、外部数据引用等有明确外部边界证据时单独输出一行。 |

界面类不应拆得太细。对于简单管理页面，优先按三级模块整体输出一条界面开发行，覆盖页面内的列表、搜索、按钮、弹窗、状态组件和关联管理界面。

非界面类功能可以按照一个能力一行输出。新增表、修改表字段等数据表变更不单独造行，应归属到对应添加、编辑、导入或其他逻辑接口/表能力中；没有明确添加能力时，可归属到最相关的业务动作。

## 示例

以“垂直行业管理”为例，界面能力合并为一行：

```text
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-界面开发
```

计算依据说明可概括该界面做了什么：

```text
1、新增垂直行业列表，可以分页切换
2、新增条件查询组件，输入行业名称搜索、可重置搜索条件
3、添加/编辑/删除/管理员等按钮
4、添加垂直行业界面，输入垂直行业名称保存
5、编辑更新垂直行业界面
6、管理员界面，可展示/添加/删除管理员
7、更新垂直行业状态组件
```

对应 `unified_ui` 行建议为：

| 序号 | 新增/修改功能点 | 类型 |
|---|---|---|
| 1 | 垂直行业管理界面开发 | EI |
| 2 | 添加垂直行业-逻辑接口开发 | ILF |
| 3 | 编辑垂直行业-逻辑接口开发 | ILF |
| 4 | 查询垂直行业-逻辑接口开发 | ILF |
| 5 | 删除垂直行业-逻辑接口开发 | ILF |
| 6 | 新增垂直行业管理员-逻辑接口开发 | ILF |
| 7 | 删除垂直行业管理员-逻辑接口开发 | ILF |

## 计算依据说明规则

`计算依据说明` 应描述本次功能建设做了什么，而不是复述用户操作流程。

建议规则：

1. 涉及新增表、修改表字段或数据结构调整时，可归纳为一个小点。
2. 每个小点描述系统建设内容，例如“新增垂直行业列表”“新增条件查询组件”“新增管理员维护能力”。
3. 不要按用户点击路径、前后操作顺序、页面跳转流程来写说明。
4. 不编造输入中没有的表名、接口名、外部系统、权限规则或审批流程。
5. FPA 用户可见字段统一使用“新增/修改功能点”“类型”“计算依据归类”“计算依据说明”“生成方式”。

## 配置结构调整

`calculation_explanation_rules` 应从旧的 `prompt_fragments.calculation_explanation_rules.default` 结构中提升出来，成为与 `core_rules`、`system_prompt_sets`、`user_prompt_sets`、`rule_sets` 同级的顶层配置段。

每个 profile 在 `profiles.<profile_name>` 下显式绑定使用哪一份 `calculation_explanation_rules`，与 `strategy`、`rule_set`、`core_rules`、`system_prompt`、`user_prompt` 同级。

目标结构示例：

```yaml
profiles:
  strict_fpa:
    kind: strict_fpa
    strategy: ai_first
    rule_set: strict_fpa_rs
    core_rules: strict_fpa_cr
    system_prompt: strict_fpa_sp
    user_prompt: strict_fpa_up
    calculation_explanation_rules: strict_fpa_ce

  unified_ui:
    kind: unified_ui
    strategy: rules_first
    rule_set: unified_ui_rs
    core_rules: unified_ui_cr
    system_prompt: unified_ui_sp
    user_prompt: unified_ui_up
    calculation_explanation_rules: unified_ui_ce

  multi_uis:
    kind: unified_ui
    strategy: ai_first
    rule_set: multi_uis_rs
    core_rules: multi_uis_cr
    system_prompt: multi_uis_sp
    user_prompt: multi_uis_up
    calculation_explanation_rules: multi_uis_ce

  ui_api_mapping:
    kind: ui_api_mapping
    strategy: ai_first
    rule_set: ui_api_mapping_rs
    core_rules: ui_api_mapping_cr
    system_prompt: ui_api_mapping_sp
    user_prompt: ui_api_mapping_up
    calculation_explanation_rules: ui_api_mapping_ce

calculation_explanation_rules:
  strict_fpa_ce: |-
    计算依据说明生成规则：
    1. explanation 必须写成结构化证据说明...
  unified_ui_ce: |-
    统一界面口径计算依据说明生成规则：
    1. explanation 应描述本次功能建设做了什么...
  multi_uis_ce: |-
    # 内容同 unified_ui_ce
  ui_api_mapping_ce: |-
    # 内容同 unified_ui_ce
```

调整后，user prompt 仍继续通过 `${calculation_explanation_rules}` 引用规则文本；运行时渲染时先读取当前 profile 的 `calculation_explanation_rules` 绑定 key，再从顶层 `calculation_explanation_rules.<key>` 读取实际文本。

原 `default` calculation_explanation_rules 改名为 `strict_fpa_ce`，并绑定到 `strict_fpa` profile。`unified_ui` profile 新增并绑定 `unified_ui_ce`，用于承载统一界面口径下“按建设内容描述、界面合并、逻辑接口/表按能力拆分”的计算依据说明规则。

`multi_uis` profile 绑定 `multi_uis_ce`，`ui_api_mapping` profile 绑定 `ui_api_mapping_ce`。两者的规则内容与 `unified_ui_ce` 保持一致，先通过独立 key 保留 profile 级配置边界，后续如需针对多界面拆分或界面接口映射补充差异化说明规则，可以只调整对应 CE key 的文本。

`unified_ui_ce` 不应只是 `strict_fpa_ce` 的改名复用。`strict_fpa_ce` 保留标准 FPA 结构化证据说明，重点解释来源路径、业务数据、系统元素和当前 FPA 类型；`unified_ui_ce` 必须体现统一界面交付口径，`计算依据说明` 要按系统建设内容描述，不按用户点击路径或页面跳转顺序叙述。界面开发行应概括同一三级模块内的列表、条件查询组件、按钮、弹窗、状态组件和关联管理界面；逻辑接口/表能力行应说明添加、编辑、查询、删除、状态更新或数据结构调整归属的业务动作；导入、导出和外部接口联调调用行只描述输入中有证据的建设内容，不补写表名、接口名、外部系统、权限或审批流程。

由于本系统尚未上线，不建议保留旧 `prompt_fragments.calculation_explanation_rules` 兼容回退，也不建议继续保留 `default_calculation_explanation_rules` 这类泛化命名。配置校验应直接要求引用 `${calculation_explanation_rules}` 的 profile 显式配置 `profiles.<profile>.calculation_explanation_rules`，且绑定 key 必须存在于顶层 `calculation_explanation_rules`。

## 拟修改范围

后续实施时建议修改以下范围：

| 文件 | 修改内容 |
|---|---|
| `config/fpa_config.yaml.example` | 更新 `unified_ui_cr`、`unified_ui_sp`、`unified_ui_up` 和 `unified_ui_rs`，同步新类型规则、行命名和计算依据说明约束；将 `calculation_explanation_rules` 提升为顶层配置段，并在各 profile 下显式绑定。 |
| `ai_gen_reimbursement_docs/config_utils.py` | 允许并校验 `profiles.<profile>.calculation_explanation_rules`；改为通过 profile 绑定 key 读取顶层 `calculation_explanation_rules`；更新 prompt diagnostics 的 source path。 |
| `ai_gen_reimbursement_docs/fpa_profiles.py` | 调整 `unified_ui` fallback/规则兜底的后缀选择逻辑，避免只按类型决定“查询处理开发/导入处理开发”等旧后缀；保持 `${calculation_explanation_rules}` 渲染入口不变。 |
| `tests/test_config_utils.py`、`tests/test_fpa_profiles.py` | 更新旧 `prompt_fragments.calculation_explanation_rules.*` 断言；新增 profile 绑定 key、缺失绑定、绑定 key 不存在、未引用占位符 warning 等测试。 |
| `tests/fpa_profiles/test_unified_ui_harness.py` | 更新规则兜底测试，覆盖查询为 `ILF`、导入为 `EQ`、导出为 `EO`、外部接口联调调用为 `EIF`。 |
| `tests/fixtures/fpa_golden_cases/vertical_industry_management.json` | 更新垂直行业管理 golden case，补齐查询逻辑接口行，并将非界面行命名调整为“逻辑接口开发”。 |
| `docs/fpa/fpa-profiles.md`、`docs/fpa/calculation-basis-explanation-rules.md` | 同步 profile 文档和计算依据说明文档，移除旧 `prompt_fragments.calculation_explanation_rules` 路径说明，改为 profile 级绑定说明。 |

## 实施顺序

建议按以下顺序实施，降低配置结构调整和 profile 行为调整互相干扰的风险：

1. 调整 `config/fpa_config.yaml.example` 的配置结构：新增顶层 `calculation_explanation_rules`，将原 default 规则文本改名为 `strict_fpa_ce`，新增 `unified_ui_ce`、`multi_uis_ce`、`ui_api_mapping_ce`，并在四个 profile 下显式绑定。
2. 调整 `ai_gen_reimbursement_docs/config_utils.py`：允许 `profiles.<profile>.calculation_explanation_rules` 字段，校验绑定 key 存在，移除旧 `prompt_fragments.calculation_explanation_rules` 读取路径，并更新 diagnostics 的 source path。
3. 先更新配置结构相关测试：覆盖默认配置可加载、profile 绑定 key 可解析、缺失绑定报错、绑定不存在 key 报错、未引用占位符只 warning。
4. 调整 `unified_ui` profile 口径：更新 `unified_ui_cr`、`unified_ui_sp`、`unified_ui_up`、`unified_ui_rs`，落实界面合并、逻辑接口/表、导入、导出、外部接口联调调用的类型规则。
5. 调整 `ai_gen_reimbursement_docs/fpa_profiles.py` 的 fallback/规则兜底命名逻辑：从“按类型推后缀”改为“按业务动作或关键词优先推后缀”，确保查询为 `ILF` 时仍输出“逻辑接口开发”，导入为 `EQ` 时仍输出导入类行。
6. 更新 `unified_ui` 相关测试和 golden case：重点覆盖垂直行业管理、查询逻辑接口、导入、导出、外部接口联调调用，以及 `multi_uis`、`ui_api_mapping` 是否保持预期行为。
7. 同步文档：更新 `docs/fpa/fpa-profiles.md` 和 `docs/fpa/calculation-basis-explanation-rules.md` 中的配置路径、profile 绑定和新口径说明。
8. 运行完整验证命令，确认配置加载、prompt 渲染、fallback、AI 后处理和验收样例均通过。

## 验证方式

后续实施完成后，至少运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\fpa_profiles\test_unified_ui_harness.py
.\.venv\Scripts\python.exe -m pytest tests\test_gen_fpa_ai.py tests\test_fpa_profiles.py tests\test_fpa_acceptance.py
```

如修改 golden case，应补充运行相关 golden case 测试，确认 `unified_ui` 输出名称、类型、计算依据说明和 profile quality review 均符合预期。

配置结构调整还需要重点验证：

1. 默认配置四个官方 profile 都能解析并渲染 `${calculation_explanation_rules}`。
2. profile 绑定的 `calculation_explanation_rules` key 能正确读取顶层文本。
3. user prompt 引用了 `${calculation_explanation_rules}` 但 profile 未配置绑定时，应明确报错。
4. profile 绑定了不存在的 key 时，应明确报错。
5. user prompt 未引用 `${calculation_explanation_rules}` 时，仍只给 warning，不强制要求绑定。

## 验收清单

实施完成后，应满足以下验收项：

- 默认 `config/fpa_config.yaml.example` 不再包含 `prompt_fragments.calculation_explanation_rules`。
- 顶层存在 `calculation_explanation_rules.strict_fpa_ce`、`calculation_explanation_rules.unified_ui_ce`、`calculation_explanation_rules.multi_uis_ce`、`calculation_explanation_rules.ui_api_mapping_ce`。
- 原 `default` calculation_explanation_rules 文本迁移为 `strict_fpa_ce`。
- `profiles.strict_fpa.calculation_explanation_rules` 绑定 `strict_fpa_ce`。
- `profiles.unified_ui.calculation_explanation_rules` 绑定 `unified_ui_ce`。
- `profiles.multi_uis.calculation_explanation_rules` 绑定 `multi_uis_ce`。
- `profiles.ui_api_mapping.calculation_explanation_rules` 绑定 `ui_api_mapping_ce`。
- `multi_uis_ce` 和 `ui_api_mapping_ce` 的规则内容与 `unified_ui_ce` 保持一致。
- 默认四个官方 profile 的 user prompt 均能成功渲染 `${calculation_explanation_rules}`，最终 prompt 中不残留 `${...}`。
- 缺失 `profiles.<profile>.calculation_explanation_rules` 或绑定不存在 key 时，配置校验给出明确错误。
- `unified_ui` 界面类输出合并为三级模块级 `EI` 行，不按按钮、弹窗、列表、状态组件拆成多行。
- `unified_ui` 添加、编辑、查询、删除、状态更新、数据表新增修改等非界面能力输出为“逻辑接口开发”类行，类型为 `ILF`。
- `unified_ui` 导入类能力类型为 `EQ`。
- `unified_ui` 导出类能力类型为 `EO`。
- `unified_ui` 外部接口联调调用类型为 `EIF`。
- 垂直行业管理 golden case 至少包含“垂直行业管理界面开发 / EI”“添加垂直行业-逻辑接口开发 / ILF”“编辑垂直行业-逻辑接口开发 / ILF”“查询垂直行业-逻辑接口开发 / ILF”“删除垂直行业-逻辑接口开发 / ILF”。
- `计算依据说明` 按系统建设内容描述，不按用户操作流程描述；新增表、修改字段等可归纳为一个小点。
- Web 配置诊断和 prompt diagnostics 不再显示旧路径 `prompt_fragments.calculation_explanation_rules.default`。
- `git status` 只包含本轮相关变更；提交前测试命令有明确通过记录或说明未运行原因。

## 风险

主要风险是 `unified_ui` 现有规则使用类型反推行后缀，例如 `EQ -> 查询处理开发`、`EI -> 导入处理开发`。新口径中“查询 = ILF”“导入 = EQ”，同一类型无法再唯一决定行名称后缀，因此需要改为关键词或业务动作优先的后缀选择策略。

另一个风险是 `multi_uis` 当前复用 `unified_ui` kind。实施时应确认是否只改 `unified_ui_rs`，还是同步影响 `multi_uis_rs`。如只调整 `unified_ui`，需要避免共享逻辑导致 `multi_uis` 行名或类型被意外改变。

配置结构调整的风险是 Web 配置诊断页、测试和文档中仍可能显示旧 source path。实施时需要同步更新 diagnostics 输出，避免运行时已使用新结构，但页面或测试仍提示 `prompt_fragments.calculation_explanation_rules.default`。
