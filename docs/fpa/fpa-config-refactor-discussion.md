# FPA 配置结构调整讨论记录

## 当前问题

当前 `fpa_config.yaml` 使用 `prompt_sets.<name>.system` 和 `prompt_sets.<name>.user` 保存同一组提示词中的 system/user 两段内容。

这个结构容易让人误解为 `custom_rules` 自身包含两类规则，而不是一次 LLM 调用中的两类消息。

## 已确认方向

1. 将 `prompt_sets` 拆分为两个顶层配置：
   - `system_prompt_sets`
   - `user_prompt_sets`
2. prompt set 与 FPA profile 的关联继续由 `profiles` 指定：
   - `profiles.<profile>.system_prompt` 指向 `system_prompt_sets.<name>`
   - `profiles.<profile>.user_prompt` 指向 `user_prompt_sets.<name>`
3. 在讨论完全敲定前，先维护本讨论记录；暂不直接修改正式文档、配置示例、代码和测试。

## 目标配置结构草案

```yaml
profile: custom_rules

profiles:
  custom_rules:
    strategy: rules_first
    rule_set: custom_rules_default
    system_prompt: custom_rules
    user_prompt: custom_rules

  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
    system_prompt: strict_fpa
    user_prompt: strict_fpa

system_prompt_sets:
  custom_rules: |-
    ...

  strict_fpa: |-
    ...

user_prompt_sets:
  custom_rules: |-
    ${core_rules}
    ${judgement_rules}
    ${payload_json}

  strict_fpa: |-
    ${core_rules}
    ${judgement_rules}
    ${payload_json}

rule_sets:
  custom_rules_default:
    keyword_rules:
      merge: append
      items: []
  strict_fpa_default:
    keyword_rules:
      merge: append
      items: []
```

## 决策记录

1. 保留 `profiles.<profile>.system_prompt` / `profiles.<profile>.user_prompt` 字段名。
   - 理由：它们表达的是当前 profile 绑定哪套 system/user prompt；虽然目标配置区改为 `system_prompt_sets` / `user_prompt_sets`，但 profile 内字段继续叫 `system_prompt` / `user_prompt` 足够直观。
   - 暂不改为 `system_prompt_set` / `user_prompt_set`，避免字段名过长。

2. 错误提示和来源标签使用新的顶层路径：
   - `system_prompt_sets.custom_rules`
   - `user_prompt_sets.custom_rules`
   - 示例：
     - `用户配置（配置目录/fpa_config.yaml: system_prompt_sets.custom_rules）`
     - `用户配置（配置目录/fpa_config.yaml: user_prompt_sets.custom_rules）`

3. 不做迁移脚本，直接替换旧结构。
   - 理由：系统尚未上线，仓库约束允许移除旧逻辑和旧分支；实施时同步更新配置示例、正式文档和测试即可。

4. 允许 system prompt 和 user prompt 使用不同名称。`system_prompt` 和 `user_prompt` 是引用名，不是内联 Prompt 文本。
   - 示例：
     ```yaml
     profiles:
       custom_rules:
         system_prompt: default_fpa
         user_prompt: custom_rules_v2
     ```
   - 理由：这正是拆成两个 prompt set 的价值之一，便于复用 system prompt 或单独迭代 user prompt。

## rule_sets 结构解析

`rule_sets` 可以理解为：给某个 FPA profile 使用的一组“规则补充包”。profile 决定口径，rule_set 决定这套口径下有哪些可配置规则参与判断、兜底、补齐和告警。

它和 `profiles` 的关系是：

```yaml
profiles:
  strict_fpa:
    strategy: ai_first
    rule_set: strict_fpa_default
```

含义是：`strict_fpa` 默认使用 `strict_fpa_default` 这套规则。也可以在 CLI/Web 显式选择别的 rule_set，例如 `strict_fpa_conservative` 或 `client_a_rules`。

### 整体结构

```yaml
rule_sets:
  custom_rules_default:
    keyword_rules:
      merge: append
      items: []
  strict_fpa_default:
    keyword_rules:
      merge: append
      items: []
  strict_fpa_conservative:
    extends: strict_fpa_default
    ...
  client_a_rules:
    extends: strict_fpa_default
    ...
```

每个一级 key 都是一套规则集名称：

- `custom_rules_default`：给 `custom_rules` profile 用的默认规则集。实施后显式写出关键词、类型映射和覆盖补齐等默认规则数据。
- `strict_fpa_default`：给 `strict_fpa` profile 用的默认规则集。实施后显式写出事务关键词、外部数据组识别和覆盖补齐等默认规则数据。
- `strict_fpa_conservative`：示例扩展规则集，继承 `strict_fpa_default`，再追加更保守、更项目化的规则。
- `client_a_rules`：客户 A 的项目级规则集，继承 `strict_fpa_default`，只追加客户 A 自己的外部数据组识别规则。

### extends

```yaml
strict_fpa_conservative:
  extends: strict_fpa_default
```

`extends` 表示继承父规则集。最终执行时会先解析 `strict_fpa_default`，再把 `strict_fpa_conservative` 里的规则合并进去。

如果父规则里已有某类规则，子规则可以通过 `merge` 决定是追加还是替换。

### merge

```yaml
keyword_rules:
  merge: append
  items:
    ...
```

- `merge: append`：继承父规则后，把当前 `items` 追加进去。
- `merge: replace`：不用父规则的这一段，直接用当前 `items` 替换。

如果不写，代码默认按 `append` 处理。

### keyword_rules

```yaml
keyword_rules:
  merge: append
  items:
    - type: EO
      keywords: ["打印清单", "打印报表"]
      reason: "打印清单或报表属于格式化输出，按 EO。"
```

这是事务功能关键词规则。命中关键词时，给出建议类型。

这个例子表示：如果功能过程或相关文本里出现“打印清单”“打印报表”，规则建议类型为 `EO`，因为打印清单/报表通常属于格式化输出。

适合配置：

```text
导出、打印、下载、生成报表 -> EO
查询、查看、检索 -> EQ
新增、提交、保存、导入 -> EI
```

### type_mapping_rules

```yaml
type_mapping_rules:
  merge: append
  items:
    - type: ILF
      keywords: ["本地报表快照"]
      reason: "本系统持久化报表快照，按 ILF。"
```

这是更通用的“关键词到 FPA 类型”的映射。它不只限 EI/EQ/EO，也支持 `ILF/EIF`。

这个例子表示：只要识别到“本地报表快照”这个业务对象，规则建议它是 `ILF`，因为本系统持久化维护这个数据组。

和 `keyword_rules` 的区别可以粗略理解为：

- `keyword_rules` 更偏事务动作，例如“打印报表”。
- `type_mapping_rules` 更偏业务对象或项目口径，例如“本地报表快照”。

### ai_type_conflict_rules

```yaml
ai_type_conflict_rules:
  merge: append
  items:
    - expected_type: ILF
      ai_type: EO
      keywords: ["本地报表快照"]
      conflict: false
      reason: "示例：已确认项目口径允许 AI 按格式化输出复核时，不提示类型冲突。"
```

这是 AI 类型冲突告警规则，不是直接改 AI 输出的主规则。

含义是：规则侧期望 `ILF`，AI 返回 `EO`，而且文本命中“本地报表快照”时，是否认为这是冲突。

- `conflict: false` 表示：这个差异已经被项目确认可以接受，不提示类型冲突 warning。
- `conflict: true` 表示：这是需要提示人工关注的冲突。

它适合处理“AI 和规则都说得通，但项目已经定了口径”的情况。

### internal_data_rules

```yaml
internal_data_rules:
  merge: append
  items:
    - keywords: ["认证授权关系", "角色授权关系"]
      data_name: "认证授权关系"
      reason: "本系统维护认证授权关系，按 ILF。"
```

这是内部数据组识别规则，用于识别 `ILF`。

含义是：如果文本里出现“认证授权关系”或“角色授权关系”，就识别出一个内部逻辑数据组，名称统一为“认证授权关系”。

因为“本系统维护”，所以按 `ILF`。

适合配置本系统自己维护的数据：

```text
客户档案
订单主数据
角色授权关系
报表快照
配置参数
```

### external_data_rules

```yaml
external_data_rules:
  merge: append
  items:
    - source_aliases: ["统一认证平台", "统一认证"]
      data_name: "统一认证账号"
      data_nouns: ["账号", "账户", "人员"]
```

这是外部数据组识别规则，用于识别 `EIF`。

含义是：如果文本里同时体现外部来源和被引用的数据对象，就把它识别成外部数据组。例如：

- 外部来源：`统一认证平台` / `统一认证`
- 数据名词：`账号` / `账户` / `人员`
- 识别结果：`统一认证账号`

因为这个数据由外部系统维护，本系统只是引用，所以按 `EIF`。

这个规则比简单关键词更严格，因为它区分“外部系统名称”和“被引用的数据对象”。例如“调用统一认证平台登录接口”不一定是 EIF；但“引用统一认证平台维护的人员账号”更像 EIF。

### coverage_rules

```yaml
coverage_rules:
  require_process_coverage: true
  require_data_function: true
```

这是 AI 结果的覆盖补齐策略。不配置时两个默认都是 `true`。

- `require_process_coverage: true`：如果 AI 没覆盖某些功能过程，就追加 rules_fallback 行补齐。
- `require_data_function: true`：在 `strict_fpa / ai_first` 下，如果 AI 没有识别出必要的 `ILF/EIF` 数据功能，规则会补齐数据功能行。

例如输入有“新增、编辑、删除、查询”，AI 只返回了“查询”，规则会补上缺失的过程。

例如 strict_fpa 下输入明显描述“本系统维护客户档案”，但 AI 只给了 EI/EQ，没有给 ILF，规则会补一条“客户档案：ILF”。

### client_a_rules

```yaml
client_a_rules:
  extends: strict_fpa_default
  external_data_rules:
    merge: append
    items:
      - source_aliases: ["供应商平台"]
        data_name: "供应商平台供应商档案"
        data_nouns: ["供应商", "档案", "信息"]
```

这是一个典型的客户级规则集。

它表示：客户 A 的项目里，如果文本提到引用“供应商平台”维护的供应商、档案、信息，就识别为外部数据组“供应商平台供应商档案”，按 `EIF`。

以后可以在 profile 或运行参数里选择：

```yaml
profiles:
  strict_fpa:
    rule_set: client_a_rules
```

这样 strict_fpa 就使用客户 A 的规则集。

一句话总结：`rule_sets` 不是 prompt，它是 FPA 规则引擎的项目级配置。`extends` 管继承，`merge` 管追加/替换，各段规则分别负责类型关键词、数据组识别、AI 冲突告警和 AI 结果补齐。

## 历史背景：默认 rule_set 曾为空

改造前默认配置中：

```yaml
rule_sets:
  custom_rules_default: {}
  strict_fpa_default: {}
```

这两个空对象不是表示“没有规则可用”，而是表示“没有额外配置规则”。真正的基础规则当时仍在代码里的 profile 默认逻辑中。

改造前执行含义大致是：

```text
profile = custom_rules
rule_set = custom_rules_default
=> 使用 custom_rules 代码内置基础逻辑
=> rule_set 里没有追加项目级规则
```

```text
profile = strict_fpa
rule_set = strict_fpa_default
=> 使用 strict_fpa 代码内置基础逻辑
=> rule_set 里没有追加项目级规则
```

保留两个空对象的作用：

1. 让 `profiles.<profile>.rule_set` 永远有明确引用目标。
2. 给扩展规则提供继承基线，例如 `strict_fpa_conservative.extends: strict_fpa_default`。
3. 区分“默认规则”和“客户/项目规则”。
4. 避免把代码内置基础规则全部塞进 YAML，导致配置过长或基础口径被误改。

因此，改造前的 `custom_rules_default: {}` 和 `strict_fpa_default: {}` 更像“默认规则集名称”，不是“空规则系统”。

实施后，这两个默认规则集已不再为空；可表达为规则数据的默认关键词、类型映射、外部数据组识别和覆盖补齐开关已写入 `config/fpa_config.yaml.example` 的 `rule_sets.<default>`。

## 默认规则配置化讨论

倾向上，把硬编码规则摘出来会更好，尤其本系统尚未上线，不需要保留旧版本兼容路径。

但建议分层摘取，而不是一次把所有 profile 行为都塞进 YAML。

### 建议迁移到 rule_sets 的规则数据

这些规则本来就像配置，适合迁移到 `rule_sets.<name>`：

1. `keyword_rules`
2. `type_mapping_rules`
3. `internal_data_rules`
4. `external_data_rules`
5. `ai_type_conflict_rules`
6. `coverage_rules`

迁移后，`custom_rules_default` 和 `strict_fpa_default` 可以从空对象变成显式默认规则包，例如：

```yaml
rule_sets:
  custom_rules_default:
    keyword_rules:
      merge: append
      items:
        - type: EQ
          keywords: ["查询", "查看", "检索"]
          reason: "查询类功能按 EQ。"
        - type: EO
          keywords: ["导出", "打印", "报表"]
          reason: "格式化输出按 EO。"
    coverage_rules:
      require_process_coverage: true
      require_data_function: true

  strict_fpa_default:
    keyword_rules:
      merge: append
      items:
        - type: EI
          keywords: ["新增", "修改", "删除", "保存", "提交", "导入"]
          reason: "维护系统数据的输入处理按 EI。"
        - type: EQ
          keywords: ["查询", "查看", "详情"]
          reason: "无派生计算的查询按 EQ。"
        - type: EO
          keywords: ["导出", "报表", "下载", "打印"]
          reason: "格式化输出或派生输出按 EO。"
    coverage_rules:
      require_process_coverage: true
      require_data_function: true
```

这样默认规则不再只存在于代码中，而是可读、可审、可改。

### 建议继续保留在代码中的执行机制

这些属于执行算法，不建议配置化：

1. `rules_first` / `ai_first` 的执行流程。
2. AI 失败、返回非法 JSON、返回非法类型时如何 fallback。
3. 行覆盖检查和补齐的具体算法。
4. Prompt 渲染、JSON 解析、输出合法性校验。
5. 规则集继承、合并、循环检测、配置结构校验。

边界建议：

```text
规则数据放进 YAML。
执行算法留在代码。
```

这样既能减少硬编码，又不会让 YAML 变成半个程序。

## 已确认决策：默认规则配置化

1. 将 profile 中可表达为规则表的硬编码默认规则迁移到 `rule_sets.<default>`。
   - 决策：是。
   - 影响：`custom_rules_default` 和 `strict_fpa_default` 不再为空对象，默认规则可读、可审、可改。

2. 默认规则配置化的范围限定为规则数据，不迁移执行算法。
   - 决策：是。
   - 影响：`strategy` 执行流程、AI fallback、覆盖补齐算法、解析和校验仍由代码负责。

3. `custom_rules_default` 也要显式写出默认规则。
   - 决策：是，但只写能清晰表达的规则数据。
   - 影响：继续保留 custom_rules 的模板友好表达，同时让关键词、类型映射等规则来源更透明。

4. `strict_fpa_default` 要显式写出默认规则。
   - 决策：是。
   - 影响：strict_fpa 的 EI / EQ / EO / ILF / EIF 默认判断规则更容易复核和调整。

5. 默认规则集配置化后，仍允许客户规则通过 `extends` 继承默认规则。
   - 决策：是。
   - 影响：`client_a_rules.extends: strict_fpa_default` 仍然成立，客户规则只需要追加差异。

6. 对于无法自然表达成配置项的 profile 特殊逻辑，允许暂时保留在代码中。
   - 决策：是。
   - 影响：先迁移清晰规则，避免为了“全配置化”引入难读、难测的复杂配置结构。

## 保留在代码中的 profile 特殊逻辑

实施后，关键词、类型映射、内外部数据组规则、AI 类型冲突特例和覆盖补齐开关已经配置化到 `rule_sets`。仍保留在代码中的部分主要是算法、行生成结构、文本抽取和边界推理。

### custom_rules

1. 三级模块默认生成一条“界面开发”行。
   - 这不是关键词规则，而是行生成策略：同一三级模块先合并页面能力，再按功能过程生成逻辑行。

2. 逻辑行命名规则。
   - 命中 `EQ` 时生成 `-查询处理开发`。
   - 命中 `EO` 时生成 `-导出处理开发`。
   - 其余默认生成 `-逻辑处理开发`。
   - 这是输出结构转换，不只是类型映射。

3. 类型判断优先级。
   - 当前顺序是先看非 ILF 的 `type_mapping_rules`，再看 `keyword_rules`，最后再看 ILF 映射。
   - 这样可以避免“导入客户名单”被描述里的“保存”抢成 ILF。
   - 这类优先级算法不适合直接塞进 YAML。

4. AI 明显冲突判断。
   - 例如出现“外部接口”且规则期望 ILF 时，AI 给 EIF 才算明显冲突。
   - 这是判断矩阵和保护逻辑，不是单条规则。

### strict_fpa

1. 先识别数据功能，再识别事务功能。
   - `fallback_rows_for_l3()` 会先生成 ILF/EIF 数据功能，再给每个功能过程生成 EI/EQ/EO。
   - 这是 FPA 行规划算法。

2. 外部数据组识别的组合判断。
   - 不是只命中外部系统名称就生成 EIF，还要结合数据名词、外部维护提示、否定提示等。

3. 普通外部服务不等于 EIF。
   - 短信平台、支付网关、OCR、文件存储等普通服务调用，默认按事务功能处理，不直接算外部数据组。
   - `external_data_rules` 如果把普通服务配置成 EIF，系统会加载但记录 warning。

4. 同步外部数据后本系统继续维护。
   - 如果文本描述“同步”后写入、保存或继续维护本系统数据，应识别为 ILF，而不是 EIF。

5. 从文本抽取外部数据组名称。
   - 例如从“外部征信平台维护的企业信用记录”中抽出“企业信用记录”。
   - 这依赖正则匹配和名称清洗逻辑。

6. 识别额外内部关联数据。
   - 例如管理员关系、匹配关系、映射关系、绑定关系，会从功能过程描述中推导额外 ILF。

7. AI 数据功能复核 warning。
   - AI 给了 ILF/EIF，但当前规则无法确认边界时，提示人工复核。
   - 这是审核保护逻辑。

### 边界总结

```text
适合配置化：
关键词、类型映射、内外部数据组表、AI 冲突特例、覆盖补齐开关。

继续留在代码：
行怎么生成、先后顺序、文本抽取、边界推理、fallback/补齐算法、审核保护逻辑。
```

## 迁移影响范围

预计需要同步调整：

1. `config/fpa_config.yaml.example`
2. `ai_gen_reimbursement_docs/config_utils.py`
3. FPA 配置、Prompt 加载、Web 任务相关测试
4. `docs/fpa/fpa-prompt-configuration.md`
5. `docs/fpa/fpa-profiles.md`
6. `docs/fpa/gen-fpa-implementation-notes.md`
7. README 中引用 FPA Prompt 配置结构的内容

## 后续实施计划

讨论敲定后再一次性更新正式文档、配置示例、代码和测试，并运行相关 Python 测试验证。
