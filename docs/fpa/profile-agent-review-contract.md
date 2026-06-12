# Profile Agent Review 契约复用方案

## 当前实施状态

截至 2026-06-12，本文中的最小落地路线已推进到 profile-aware Agent Review 和 `multi_uis` 独立 kind 阶段：

- `agent_review` 已增加 `profile`、`profile_kind`、`contract`、`applicability`、`contract_outputs` 和 `categories`。
- `strict_fpa` 使用 `strict_fpa_contract`，`applicability: primary`，继续以 `type_judgement`、`merge_review`、`quality_review` 作为主审计契约。
- `unified_ui` 使用 `unified_ui_contract`，`applicability: debug_only`，已输出只读的 `workload_judgement`、`unified_merge_review`、`unified_quality_review`。
- `multi_uis` 使用独立 `kind: multi_uis` 和 `multi_uis_contract`，生成规则仍复用统一界面兜底能力，继续输出只读的 `workload_judgement`、`unified_merge_review`、`unified_quality_review`。
- `ui_api_mapping` 使用 `ui_api_mapping_contract`，`applicability: debug_only`，已输出只读的 `mapping_judgement`、`mapping_merge_review`、`mapping_quality_review`。
- profile 专属 quality review 进入 `agent_review` 和稳定性报告；prompt 已明确读取 profile 专属 judgement，但 warning 仍不阻断、不自动重试、不直接改写 rows。
- `tests/fpa_profiles/` 已补充 `unified_ui`、`multi_uis`、`ui_api_mapping` 的分层 harness、自定义 profile 继承式 harness、prompt payload contract 覆盖，以及 profile 级 golden fixture contract 覆盖。
- 稳定性报告已新增独立指标 `profile_quality_issue_count` 和 `profile_issue_code_counts`，不混入原 `quality_issue_count`。
- 真实模型抽样记录模板已新增到 `docs/fpa/validation-runs/multi-profile-run-template.md`，首轮多 profile 基线与 hardening 后归零记录已归档。

持续治理事项：

- profile 专属 warning 仍保持只读质量门，不阻断生成；如需升级为阻断或自动重试，需要先补更大样本的误报评估。
- 新增 profile 或 rule_set 时继续采用 `contract + fixture + 稳定性抽样`，不要复制 Python 流程。
- 真实模型抽样应继续按日期归档，尤其要覆盖 `multi-profile-real-model` 之外的真实项目样本，避免只保留单次通过记录。
- 当前最小落地路线没有剩余必做切片；后续推进只由新增真实项目样本、profile 口径调整或质量门升级触发。

## 背景

当前 `gen-fpa` 已经为 `strict_fpa` 建立了第一版多 Agent 分工骨架。这里的 Agent 不是多个独立 LLM 调用，而是“角色化的确定性中间节点”：

```text
business_fact_extractor -> process_facts
fpa_type_judge -> type_judgement
merge_boundary_reviewer -> merge_review
quality_reviewer -> quality_review
```

这些节点被统一收束到 `agent_review`，并进入 prompt payload、预览 debug、正式生成 audit trace 和稳定性报告。

这套做法的价值是：先把多 Agent 的岗位、输入输出、审计链路和替换边界工程化。未来如果某个确定性节点确实不够用，可以只替换该节点的实现，而不需要重做整条生成流程。

## 当前骨架状态

当前骨架已经具备两类能力。

### 接口形态

系统已经把潜在 Agent 的职责拆成结构化输出：

- `process_facts`：抽取业务事实，例如操作类型、目标数据组、是否查询、是否维护内部数据、是否普通外部服务。
- `type_judgement`：给出 FPA 类型建议，例如 `EI`、`EQ`、`EO`、`ILF`、`EIF` 或不生成数据功能。
- `merge_review`：审查合并边界，例如同一业务对象维护动作合并为一个维护类 `EI`，同一列表查询合并为一个查询类 `EQ`。
- `quality_review`：检查最终 rows 是否偏离 validator、类型建议或合并建议。
- `agent_review`：登记各角色的实现、状态、输出 key 和汇总信息。

这意味着未来可以把某个角色从确定性代码替换为 AI Agent，只要保持相同 JSON 契约，后续 prompt、validator、audit trace、稳定性报告不需要大改。

### 审计形态

当前链路不只输出最终 FPA rows，还可以追踪中间判断：

```text
原始 processes
  -> process_facts
  -> type_judgement
  -> merge_review
  -> AI rows
  -> quality_review
  -> agent_review / audit trace / stability report
```

当结果异常时，可以定位问题发生在哪一层：

- 业务事实是否抽错。
- 类型建议是否错误。
- 合并边界是否遗漏。
- AI 是否没有遵循高置信建议。
- validator 或 quality review 是否没有拦住。
- prompt 是否没有清楚传递约束。

## 当前实现是不是硬编码

当前实现主要是确定性规则代码，其中包含一部分硬编码口径。

硬编码内容包括：

- 操作关键词，例如查询、搜索、列表、新增、添加、编辑、删除、导出、统计。
- 普通外部服务提示词，例如校验、认证、短信、支付、OCR、消息推送。
- 外部数据组证据短语，例如外部系统维护、本系统不维护、维护的主数据。
- `strict_fpa` 合并口径，例如同一业务对象 CRUD 合并为维护类 `EI`，同一列表查询合并为查询类 `EQ`。
- `strict_fpa` 质量审核口径，例如查询不得判为 `EI`，普通服务不得生成 `EIF`。

但它不是针对单一样例写死。它仍然基于输入中的模块路径、`processes`、流程名称、流程描述、AI rows、validator 结果、确认结果和 profile/rule_set 后处理进行判断。

更准确的描述是：

```text
硬编码规则骨架 + 输入驱动判断 + profile/validator/audit 联动
```

对于已经明确的项目口径，例如普通校验不生成 `EIF`、同一管理场景 CRUD 合并，这种确定性编码是合理的。它能减少模型自由发挥带来的波动。

## 其他 profile 能否复用

技术上，其他 profile 也能拿到这些中间结构。通用 prompt payload 会构造：

```text
process_facts
merge_review
type_judgement
agent_review
```

只要某个 profile 的 prompt 模板包含 `${payload_json}`，理论上就能读取这些字段。

但语义上，当前中间层主要按 `strict_fpa` 口径设计，不适合所有 profile 直接作为硬约束。

| profile | 能否读取当前中间结构 | 是否适合作为硬约束 |
|---|---:|---:|
| `strict_fpa` | 是 | 是 |
| `unified_ui` | 是 | 不建议直接使用 |
| `ui_api_mapping` | 是 | 不建议直接使用 |
| 继承 `strict_fpa_rs` 的自定义 profile | 是 | 可用，但需抽样验证 |
| 完全不同计量口径 profile | 是 | 需要单独契约适配 |

原因是当前 `type_judgement`、`merge_review`、`quality_review` 关注的是 FPA 逻辑事务：

```text
EI / EQ / EO / ILF / EIF
维护类 EI 合并
查询类 EQ 合并
普通服务不生成 EIF
```

而 `unified_ui` 更关注统一界面交付口径下的界面和非界面能力，例如：

```text
界面开发
逻辑接口开发
导入处理开发
导出处理开发
外部接口联调调用
```

因此，当前骨架对 `unified_ui` 可以作为审计和调试信息，但不应直接驱动生成约束。

## 非 strict Profile 的 Harness 现状

`strict_fpa` 外的 harness 已经补充分层覆盖，但成熟度仍低于 `strict_fpa` 的真实模型基线。

当前非 strict profile 的覆盖重点主要是配置、规则兜底和少量验收行为：

| profile | 当前 harness | 当前成熟度 |
|---|---|---|
| `unified_ui` | 配置校验、prompt 渲染、三级模块界面行、非界面过程行、同名非界面行合并、prompt payload contract、profile golden fixture、`workload_judgement` / `unified_quality_review` 只读审计。 | supported，已有真实模型归零记录；更多项目样本属于持续治理。 |
| `multi_uis` | 独立 `kind: multi_uis`、独立 `multi_uis_contract`、多界面同名行保留、拆分理由进入 review/check 元数据、profile golden fixture、非界面业务动作沿用 `unified_ui` harness。 | supported，已有真实模型归零记录；更多项目样本属于持续治理。 |
| `ui_api_mapping` | 默认界面 EI、默认接口 ILF、明确后端调用 ILF、多接口行、重复默认行、prompt payload contract、profile golden fixture、`mapping_judgement` / `mapping_quality_review` 只读审计。 | supported，已有真实模型归零记录；更多项目样本属于持续治理。 |
| 自定义 profile | 主要依赖所复用 kind 和 rule_set 的配置校验与基础规则。 | 需要自行补 profile 级 fixture。 |

这些 profile 目前仍没有达到 `strict_fpa` 的 harness 水平：

- profile 专属 golden fixture 已覆盖 `unified_ui`、`multi_uis`、`ui_api_mapping` 的核心 contract；真实项目出现新边界时再增量扩展。
- 已有真实模型 preset 和归零记录；后续真实模型复跑继续按日期归档。
- 已有 `profile_quality_issue_count` 质量门；是否升级为阻断或自动重试仍未决定。
- profile 专属 review 仍是只读 warning，prompt 会读取 judgement，但 warning 本身不直接阻断或改写 rows。
- `type_judgement`、`merge_review`、`quality_review` 仍保留为 `strict_fpa` 语义的调试信息。

因此，非 strict profile 可以作为 supported 组合使用，但还不能按 `strict_fpa` 的 certified 级稳定性结论直接背书。持续治理重点是随真实项目样本扩充 profile 级 golden fixtures、真实模型归档和 warning 误报评估，再决定是否把只读 warning 升级为阻断或自动重试。

## Profile 组合 Harness 分层

由于实际运行组合由以下维度共同决定：

```text
profile × kind × strategy × rule_set × prompt × model
```

所以 4 种 strategy 与不同 rule_set 混搭时，harness 仍然有用，但不能把所有组合都当成同等级保证。

推荐把组合分为四类：

| 等级 | 目标 | 典型检查 |
|---|---|---|
| `certified` | 推荐组合，承诺业务口径稳定。 | golden fixtures、行为断言、真实模型抽样、质量门。 |
| `supported` | 允许使用，有基础规则和审计闭环。 | 配置校验、规则/AI smoke、schema 校验、source_process_ids 校验。 |
| `experimental` | 技术上可运行，但不承诺业务口径。 | 防崩溃、warning、audit trace、清晰生成来源。 |
| `invalid` | 语义明显不兼容或配置错误。 | 直接报错，不回退默认 profile。 |

当前建议状态：

| 组合 | 等级 | 说明 |
|---|---|---|
| `strict_fpa + ai_first + strict_fpa_rs` | `certified` | 当前最成熟，已完成真实模型 recommended 连续复测归零。 |
| `unified_ui + rules_first + unified_ui_rs` | `supported` | 规则和配置路径可用，已有 profile review 与真实模型归零记录；扩大样本属于持续治理。 |
| `multi_uis + rules_first + multi_uis_rs` | `supported` | 已提升为独立 kind，已有多界面同名/拆分理由 harness 和真实模型归零记录。 |
| `ui_api_mapping + rules_first + ui_api_mapping_rs` | `supported` | 默认映射规则清楚，已有 profile review 与真实模型归零记录；扩大样本属于持续治理。 |
| `strict_fpa + rules_first + unified_ui_rs` 等跨口径混搭 | `experimental / invalid` | 只保证可追踪或明确报错，不承诺业务正确。 |

规则集扩展建议采用继承式 harness：

```text
base harness + extension assertions
```

例如 `client_a_rules extends strict_fpa_rs` 时，复用 `strict_fpa` 基础断言，只为客户 A 的新增规则补充增量 fixture。这样新增 rule_set 不需要复制整套 harness。

稳定性报告必须记录组合指纹，至少包括：

```text
profile
kind
strategy
rule_set
prompt ids
model
fixture suite
run_id
```

否则同一个 warning 无法判断是 profile 问题、rule_set 问题、prompt 问题还是模型问题。

## 不推荐的复用方式

不建议为每个 profile 复制一套独立 Python 流程：

```text
build_strict_fpa_agent_review()
build_unified_ui_agent_review()
build_ui_api_mapping_agent_review()
build_xxx_agent_review()
```

这样会导致 profile 越多，代码分叉越多。每新增一个 profile，都可能要新增事实抽取、类型判定、合并审查、质量审核、稳定性报告适配和测试，维护成本会快速上升。

这种方式的问题是：

- 公共审计链路被重复实现。
- profile 差异混在 Python 分支中，不利于业务口径审阅。
- prompt、validator、稳定性报告容易出现不同步。
- 新 profile 需要改大量代码，而不是只补规则和样例。

## 推荐方向：Profile Contract 驱动

推荐把 Agent Review 做成一个通用引擎，profile 差异通过 contract 描述。

通用引擎尽量不随 profile 增长：

```text
extract_process_facts
build_agent_review
build_judgements
build_merge_review
build_quality_review
audit/stability/report glue
```

profile contract 随 profile 增长：

```text
categories
judgement_rules
merge_rules
quality_checks
prompt_exposure
naming_policy
```

也就是从：

```python
build_fpa_agent_review(group, rows)
```

演进为：

```python
build_agent_review(profile_contract, group, rows)
```

## Contract 示例

`strict_fpa` contract 可以描述为：

```yaml
agent_contracts:
  strict_fpa_contract:
    categories: [EI, EQ, EO, ILF, EIF]
    judgement_rules:
      - id: query_eq
        when: operation == query and produces_external_output == false
        suggest: EQ
      - id: maintenance_ei
        when: operation in [create, update, delete, maintain]
        suggest: EI
      - id: external_data_function
        when: external_data_group_evidence exists
        suggest: EIF
      - id: ordinary_service_not_eif
        when: ordinary_external_service == true
        suggest: NONE
    merge_rules:
      - id: crud_same_object
        when: same(target_data_group) and operation in [create, update, delete, maintain]
        recommendation: merge
      - id: query_same_object
        when: same(target_data_group) and query_only == true
        recommendation: merge
    quality_checks:
      - query_as_ei
      - ordinary_service_as_eif
      - merge_review_not_applied
      - source_process_ids_out_of_scope
```

`unified_ui` contract 可以描述为：

```yaml
agent_contracts:
  unified_ui_contract:
    categories:
      - 界面开发
      - 逻辑接口开发
      - 导入处理开发
      - 导出处理开发
      - 外部接口联调调用
    judgement_rules:
      - id: ui_change
        when: operation in [query, create, update, delete, maintain]
        suggest: 界面开发
      - id: api_change
        when: operation in [query, create, update, delete, output]
        suggest: 逻辑接口开发
      - id: import_change
        when: operation == import
        suggest: 导入处理开发
      - id: export_change
        when: operation == export
        suggest: 导出处理开发
      - id: external_integration
        when: ordinary_external_service == true or external_data_group_evidence exists
        suggest: 外部接口联调调用
    merge_rules:
      - id: same_module_ui
        when: same(module_path) and category == 界面开发
        recommendation: merge
      - id: same_target_logic
        when: same(target_data_group) and category == 逻辑接口开发
        recommendation: merge
      - id: same_target_external
        when: same(target_data_group) and category == 外部接口联调调用
        recommendation: merge
    quality_checks:
      - ui_flow_missing_ui_row
      - action_missing_logic_interface_row
      - import_or_export_missing_processing_row
      - duplicate_same_category_same_target
      - source_process_ids_out_of_scope
      - explanation_structure_missing
```

上面的 YAML 只是方向示例，不代表当前配置已经支持这些表达式。

## 对 `unified_ui` 的复用方式

`unified_ui` 应复用外壳，不复用 `strict_fpa` 的 EI/EQ/ILF 语义。

推荐目标结构：

```text
agent_review
  profile: unified_ui
  mode: deterministic_contract
  roles:
    business_fact_extractor -> process_facts
    workload_judge -> workload_judgement
    merge_boundary_reviewer -> ui_api_merge_review
    quality_reviewer -> unified_quality_review
```

其中：

- `process_facts` 可复用一部分字段。
- `workload_judgement` 替代 `type_judgement`，输出界面、接口、数据库、外部对接等工作量建议。
- `ui_api_merge_review` 替代 strict 的 CRUD/EQ 合并审查。
- `unified_quality_review` 检查漏界面、漏接口、漏数据库变更、重复计数和来源流程越界等问题。

## 通用事实层

`process_facts` 应尽量保持 profile 无关，作为所有 contract 的共同输入。

当前已有字段：

```text
process_id
process_name
input_type
operation
target_data_group
query_only
changes_internal_data
produces_external_output
ordinary_external_service
external_data_group_evidence
confidence
evidence
```

可为 `unified_ui` 补充但仍保持通用的字段：

```text
ui_change_evidence
api_change_evidence
database_change_evidence
external_integration_evidence
permission_or_config_evidence
```

这些字段仍然描述事实，不直接等同最终计量结果。

## 最小落地路线

不建议一开始就重构全部 profile。推荐分阶段推进。

### 第一步：标注适用范围（已完成）

在 `agent_review` 增加 profile/applicability 信息：

```json
{
  "profile": "strict_fpa",
  "applicability": "primary"
}
```

对非 strict profile，可以返回：

```json
{
  "profile": "unified_ui",
  "applicability": "debug_only"
}
```

这样可以避免其它 profile 把 strict 口径误认为硬约束。

### 第二步：抽出 contract 概念（已完成）

新增 profile contract 数据结构，但先不追求 YAML 表达式完整通用。

第一版已用 Python dataclass 表达：

```text
contract.name
contract.categories
contract.judgement_rules
contract.merge_rules
contract.quality_checks
contract.prompt_exposure
```

### 第三步：为 `unified_ui` 增加 workload judgement（已完成，只读）

先只做非破坏式建议，不直接改写 rows：

```text
workload_judgement
  -> 界面开发
  -> 逻辑接口开发
  -> 导入处理开发
  -> 导出处理开发
  -> 外部接口联调调用
```

### 第四步：为 `unified_ui` 增加 quality review（已完成，只读）

先只做 warning 和 audit trace，不参与自动重试：

```text
有界面流程但漏界面开发
有动作流程但漏逻辑接口开发
有导入或导出流程但漏对应处理开发行
有内部数据变更但漏对应逻辑接口开发行
同一类别同一目标重复计数
source_process_ids 越界
```

### 第五步：补 profile harness / fixture（已完成基础分层、自定义 profile 继承示例、profile golden fixtures 和真实模型归零记录）

已补充 `tests/fpa_profiles/` 分层 harness，覆盖 `unified_ui`、`multi_uis`、`ui_api_mapping` 的基础行为，并通过配置解析路径覆盖自定义 `kind: unified_ui` / `kind: ui_api_mapping` profile 的继承式 harness。`multi_uis` 已提升为独立 `kind: multi_uis`，profile 级 golden fixture 已覆盖 `unified_ui` 复合业务动作、`multi_uis` 多界面拆分和 `ui_api_mapping` 默认 UI/API + 显式后端行，真实模型抽样基线和 hardening 后归零记录已归档到 `docs/fpa/validation-runs/`。

后续 fixture 扩展应跟随真实项目样本增量补充，而不是在当前样例集上复制相近场景；当前最小 contract 覆盖不再有必须补齐的基础缺口。

### 第六步：prompt 硬约束与只读 warning 分层（已完成 prompt 消费，warning 仍只读）

`unified_ui` / `multi_uis` prompt 已明确消费 `workload_judgement`，`ui_api_mapping` prompt 已明确消费 `mapping_judgement`。profile 专属 warning 仍保持只读质量门，不直接阻断生成、不自动重试、不改写 rows；只有在更大样本证明误报可控后，才考虑升级为阻断或自动重试。

## 判断原则

新增 profile 时，应优先新增 contract，而不是新增一整套 Python 流程。

只有出现以下情况，才考虑扩展通用引擎代码：

- 现有 facts 无法表达该 profile 需要的业务事实。
- contract 需要新的规则谓词，例如跨模块聚合、流程前后依赖、复杂字段比较。
- quality check 需要新的通用检查能力。
- 稳定性报告需要新增通用指标维度。

否则，新 profile 的成本应控制在：

```text
增加 contract
补关键词或分类映射
补 prompt exposure
补 golden fixture
跑稳定性抽样
```

## 结论

当前多 Agent 分工骨架已经适合继续复用，但不应按 profile 复制代码分支。

推荐方向是：

```text
一个通用 Agent Review 引擎
+ 多个 profile contract
+ 少量可扩展事实字段
+ profile 级 golden fixtures
+ 稳定性报告按 contract 聚合
```

这样 `strict_fpa` 可以继续使用现有稳定口径，`unified_ui` 可以逐步接入自己的工作量判断，而新增 profile 也不需要每次大改代码。
