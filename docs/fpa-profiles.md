# FPA 方案选择说明

日期：2026-05-30

## 可选方案

系统当前提供两套 FPA 生成口径。`profile` 只描述方法学/业务口径，AI 与规则谁优先由 `strategy` 决定：

```text
custom_rules：用户自定义规则口径，默认 rules_first
strict_fpa：严格 FPA 口径，默认 ai_first
```

两套方案只影响 FPA 行规划、类型判断、AI prompt 和兜底规则，不改变 Excel 模板列结构。

## 如何选择

### 推荐使用 custom_rules 的场景

```text
目标是生成当前报账模板更容易接受的 FPA 工作量评估。
希望保留“界面开发 / 逻辑处理开发 / 查询处理开发 / 导出处理开发”等表达。
希望减少按钮、弹窗、查询条件、状态组件被拆得过细。
评审关注的是当前交付物格式和可解释性，而不是严格 FPA 方法学。
```

`custom_rules` 是默认方案。

### 推荐使用 strict_fpa 的场景

```text
目标是尽量贴近标准 FPA 方法。
希望按数据功能和事务功能拆分。
希望避免“界面开发”“接口开发”“逻辑处理开发”等开发工作项表达。
需要区分 ILF / EIF / EI / EQ / EO 的方法学含义。
```

`strict_fpa` 更适合方法学校准、内部复核、与标准 FPA 口径对齐。

## 输出差异

### 输入示例

```text
三级模块：垂直行业管理
三级模块描述：维护垂直行业基础信息、状态和管理员。

功能过程：
1. 查询垂直行业：按行业名称查询垂直行业列表。
2. 添加垂直行业：输入垂直行业名称并保存。
3. 编辑垂直行业：修改垂直行业名称并保存。
4. 删除垂直行业：删除指定垂直行业。
```

### custom_rules 输出形态

```text
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-界面开发：EI
查询垂直行业-查询处理开发：EQ
添加垂直行业-逻辑处理开发：ILF
编辑垂直行业-逻辑处理开发：ILF
删除垂直行业-逻辑处理开发：ILF
```

特点：

```text
同一三级模块默认合并 1 条界面开发行。
查询、导出、导入会用更模板友好的命名。
新增、编辑、删除等内部维护动作通常按 ILF 兜底。
```

### strict_fpa 输出形态

```text
垂直行业信息：ILF
垂直行业管理员关系：ILF
查询垂直行业：EQ
添加垂直行业：EI
编辑垂直行业：EI
删除垂直行业：EI
```

特点：

```text
不生成界面开发行。
先识别本系统维护的数据组为 ILF，可包含主数据和关系数据。
再按事务功能识别 EI / EQ / EO。
新增、编辑、删除等改变系统数据的动作按 EI。
```

## profile / strategy / rule_set

当前 FPA 执行已经拆成三层：

```text
profile  = FPA 方法学 / 业务口径
strategy = AI 与 rules 的执行优先级
rule_set = 具体用户可配置规则集
```

默认组合：

```text
custom_rules = rules_first + custom_rules_default
strict_fpa   = ai_first    + strict_fpa_default
```

策略含义：

```text
rules_first：规则优先。当前 custom_rules 内置规则可覆盖现有场景，因此直接按规则生成；后续会细化“规则无法判定再交 AI”。
ai_first：AI 优先。AI 输出合法且覆盖充分时采用 AI；AI 不完整时由 rules 补漏。
rules_only：仅规则。不调用 AI。
ai_only：仅 AI。不使用 rules 补行，AI 失败或被配置限制跳过时直接报错。
```

当前 rule_set 已作为配置入口透传到正式生成、预览和 AI 缓存；真正的外部规则文件、rule_set_version、extends 继承仍在后续任务中。

### strict_fpa 的 AI 与规则边界

`strict_fpa` 默认 `ai_first`，以 AI 规划结果为主。rules 不是第二套主判断器，不会覆盖 AI 已给出的合法 `type`。

当前边界：

```text
无 API Key：不生成，提示需要 API Key。
AI 返回非法 type：使用规则推断出的合法 type 兜底。
AI 返回 JSON 非法、结构非法或无有效行：按 rules fallback 生成。
AI 有效但未覆盖部分功能过程：追加 rules_fallback 行。
AI 合法 type 与 rules 判断冲突：保留 AI type，只记录 warning。
```

例如：

```text
功能点名称：添加垂直行业
AI type：EI
说明：保存后刷新列表，并展示查询结果。

结果：保留 EI。
```

虽然说明中包含“列表”“查询结果”，但 `ai_first` 不再因为 rules 关键词去覆盖 AI 的合法 `EI`。

## 使用方式

### Web UI

在高级选项中选择：

```text
FPA 方案 -> 用户自定义规则口径 / 严格 FPA 口径
FPA 执行策略 -> 跟随方案默认 / 规则优先 / AI 优先 / 仅规则 / 仅 AI
FPA 规则集 -> 留空使用方案默认规则集
```

FPA 预览页面也提供 profile 和 strategy 选择，预览结果标题会显示当前口径和策略。

独立预览入口：

```text
/preview/fpa
```

如果通过 FastAPI 生产静态目录访问，也支持：

```text
/static/dist/
/static/dist/preview/fpa
```

这些地址都应返回同一个前端 SPA 入口。生产环境下 `/static/dist/config`、`/static/dist/history`、`/static/dist/prompt-debug` 等前端路由也由服务端 fallback 到 `index.html`。若修改后端路由或重新构建前端，正在运行的 Web 服务需要重启后才会加载新路由。

### CLI

```powershell
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile custom_rules
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa --fpa-strategy ai_first
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile custom_rules --fpa-strategy rules_only --fpa-rule-set custom_rules_default
```

全流程同样支持：

```powershell
ard --from-excel 功能清单.xlsx --gen-all --fpa-profile strict_fpa
```

### 配置文件

`~/.ai-gen-reimbursement-docs/system_config.yaml`：

```yaml
fpa_profile: custom_rules
fpa_strategy: ""
fpa_rule_set: ""
```

可改为：

```yaml
fpa_profile: strict_fpa
```

`fpa_strategy` 和 `fpa_rule_set` 留空时使用 profile 默认值。

CLI 参数优先于配置文件。

## 用户提示词模板

FPA 用户提示词模板使用独立配置文件维护：

```text
~/.ai-gen-reimbursement-docs/fpa_user_prompts_config.yaml
```

模板示例：

```text
config/fpa_user_prompts_config.yaml.example
```

可分别配置：

```text
fpa_eval.user_templates.custom_rules
fpa_eval.user_templates.strict_fpa
```

如果未配置，系统会使用 `fpa_profiles.py` 中的内置模板兜底。

### 配置结构

```yaml
fpa_eval:
  user_templates:
    custom_rules: |-
      ${core_rules}
      ${judgement_rules}
      ${payload_json}
    strict_fpa: |-
      ${core_rules}
      ${judgement_rules}
      ${payload_json}
```

### 占位符

```text
${core_rules}
当前 profile 的核心规则。

${judgement_rules}
从 FPA 输出模板附录 Sheet 读取的“计算依据归类判定原则”。

${payload_json}
当前三级模块、功能过程和领域上下文 JSON。
```

### 维护建议

```text
custom_rules 和 strict_fpa 是两套不同口径，建议分别维护模板。
修改提示词后，先通过 `/preview/fpa` 检查 1 到 3 个典型三级模块。
建议保留三个核心占位符，否则 AI 可能缺少规则、判定依据或业务输入。
不要随意修改输出 JSON 字段结构；如确需修改，需要同步修改解析逻辑和测试。
独立配置文件缺失、读取失败或 profile 未配置模板时，系统会自动回退到内置模板。
```

## 预览建议

建议在正式生成前先使用 `/preview/fpa` 检查 1 到 3 个典型三级模块。生产静态路径下也可以使用 `/static/dist/preview/fpa`。

当前 FPA 预览页采用两段式流程：

```text
1. 选择功能清单输入来源。
2. 点击“生成基础数据”。
3. 从三级模块下拉框选择模块。
4. 点击“生成预览”。
```

“生成基础数据”只解析功能清单并返回三级模块列表，不调用 AI，不生成 FPA Excel，也不会写正式交付物。下拉框使用模块序号定位三级模块，避免手填名称时出现重名、错别字或空格差异。

API Key 输入框只显示灰色提示。留空时使用系统配置；`sk-...`、`here`、`****here` 等示例或占位文本不会作为真实 Key 提交。

建议优先检查：

```text
包含新增/编辑/删除的数据维护模块。
包含导入、导出、查询的模块。
包含外部用户中心、外部主数据或普通外部服务调用的模块。
```

重点看：

```text
是否选对了 profile。
是否出现不该出现的“界面开发 / 接口开发 / 逻辑处理开发”。
普通外部服务调用是否被误判为 EIF。
本系统维护的数据组是否识别为 ILF。
外部维护且本系统引用的数据组是否识别为 EIF。
```

## 当前边界

`strict_fpa` 目前是基础版严格口径：

```text
能覆盖常见 ILF / EIF / EI / EQ / EO 场景。
可从功能过程语义中识别主数据 + 管理员关系这类多个内部数据组。
外部数据组识别已形成代码内规则表，当前覆盖统一用户中心、CRM、客户中心、财务核算系统、ERP、OA、主数据平台等常见外部来源。
`system_config.yaml` 可通过 `fpa_external_data_rules` 扩展外部数据组规则；扩展规则只追加，不覆盖内置规则。
外部数据组规则表已有专门测试，正例覆盖已知外部来源，反例覆盖短信平台、支付网关、文件存储、地图服务、OCR 服务等普通外部服务。
ai_first 下 AI 合法 type 与 rules 判断冲突时只记录 warning，不覆盖 AI type；非法 type 仍会用规则兜底。
如果 AI 返回“界面开发 / 接口开发 / 逻辑处理开发”等开发项名称，后处理会尽量规范为严格 FPA 的事务/数据功能名称。
更复杂的数据组识别仍依赖模块名称、模块描述和功能过程描述中的语义。
普通外部服务调用不会自动判 EIF。
Excel 模板列结构暂不随 profile 改动。
pipeline 工作量汇总建议由代码中的业务计算规则统一产生。
Excel 继续保留模板原有公式；Excel/LibreOffice 复算只作为可选校验。
```

如果严格 FPA 结果用于正式方法学审计，建议结合人工复核。

## 后续路线

### 已实现的三层模型

FPA 已从单一 `fpa_profile` 扩展为三层模型：

```text
profile  = FPA 方法学 / 业务口径
strategy = AI 与 rules 的执行优先级
rule_set = 具体用户可配置规则集
```

当前默认组合：

```text
custom_rules = rules_first + custom_rules_default
strict_fpa   = ai_first    + strict_fpa_default
```

当前边界：

```text
custom_rules 已替代旧的 current_project 名称，表示“用户自定义规则主导”。
strict_fpa 以 AI 为主，rules 只做 warning、补漏和非法值处理。
系统尚未上线，不保留 current_project 兼容别名。
```

策略含义：

```text
rules_first:
  规则优先。当前 custom_rules 内置规则可覆盖现有场景，因此直接按规则生成；后续会细化“规则无法判定再交 AI”。

ai_first:
  AI 输出合法且覆盖充分时采用 AI；AI 不完整时由 rules 补漏。

rules_only:
  完全不调用 AI。

ai_only:
  完全依赖 AI，不用 rules 补行；AI 失败或被配置限制跳过时直接报错。
```

已确认 strict_fpa 边界：

```text
无 API Key 时默认不生成，只提示需要 API Key。
AI 不完整时，rules 补漏缺失行，并标记 generation=rules_fallback。
rules 不改 AI 已给出的合法 type；业务冲突只 warning。
只有 type 非法、JSON 非法、结构非法时才硬处理。
```

后续还会增加：

```text
rule_set 外部规则文件。
rule_set_version。
rule_set extends 继承。
rules_first 中“规则无法判定再交 AI”的细粒度判定。
UI 中的 rule_set 下拉选择。
FPA 审核工作簿 FPA工作量评估-check.xlsx。
预览页审核面板，展示覆盖情况、AI 原文、规则命中和 warnings。
```

详细设计见：

```text
docs/dev/gen-fpa-implementation-notes.md
```

对应章节：

```text
下一阶段设计决策：profile / strategy / rule_set
FPA 审核工作簿与预览审核面板
```

后续增强事项当前暂缓推进。详尽任务池和可复制的恢复指令见：

```text
docs/dev/gen-fpa-implementation-notes.md
```

对应章节：

```text
暂缓推进任务池
后续恢复指令
```

优先做 Golden Case 升级的原因：

```text
能保护 custom_rules 和 strict_fpa 两套口径不退化。
能把“看起来合理”的规则变成可重复验收的样例。
后续恢复推进时，每增加一个真实项目口径，都可以先固化成样例，再改规则。
```

不建议过早配置化：

```text
当前规则仍在探索期。
如果没有足够真实样例，过早配置化会把不稳定口径固化成复杂配置。
更稳妥的路径是先积累 Golden Case，再把稳定规则补充到内置规则或 `fpa_external_data_rules`。
补充规则前后，应保持规则表单元测试、strict_fpa 行为测试、Golden Case 差异报告三层测试同时通过。
普通外部服务调用不要配置为外部数据组，否则会把服务调用误判为 EIF。
```

当前已落地固定 fixture 集：

```text
tests/fixtures/fpa_golden_cases/vertical_industry_management.json
tests/fixtures/fpa_golden_cases/customer_list_import.json
tests/fixtures/fpa_golden_cases/external_user_center_reference.json
tests/fixtures/fpa_golden_cases/crm_customer_archive_reference.json
tests/fixtures/fpa_golden_cases/erp_order_reference.json
tests/fixtures/fpa_golden_cases/sms_notification_service.json
```

自动差异报告测试：

```text
tests/test_fpa_golden_fixture_reports.py
```
