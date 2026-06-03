# FPA Domain Context 配置说明

## 配置位置

FPA 的 `domain_context` 配置在用户配置目录下的独立 JSON 文件中：

```text
配置目录/domain_context.json
```

默认示例文件位于：

```text
config/domain_context.json.example
```

初始化配置时，系统会把 `config/domain_context.json.example` 复制为用户配置目录中的 `domain_context.json`。

## 当前示例结构

```json
{
  "system_boundary": "",
  "internal_data_groups": [],
  "external_data_groups": [],
  "external_services": []
}
```

这个文件用于给 FPA 生成提供项目级背景。它不会直接生成 FPA 行，而是帮助 AI 和规则判断：

- 什么属于本系统边界内。
- 哪些数据组由本系统维护，通常是 ILF 候选。
- 哪些数据组由外部系统维护、本系统引用，通常是 EIF 候选。
- 哪些只是普通外部服务调用，不应因为出现“外部”字样就误判为 EIF。

## 字段含义

### system_boundary

字符串。用于描述本系统的边界、职责范围和计量口径中的系统边界。

示例：

```json
"system_boundary": "本系统负责报账申请、审批流转、单据归档和本地报账数据维护；外部财务系统仅提供核算结果查询。"
```

使用建议：

- 写清楚本系统负责维护哪些业务数据。
- 写清楚外部系统负责维护哪些数据，本系统只是引用或查询。
- 写清楚容易混淆的边界，例如“调用外部服务”和“引用外部数据组”的区别。

示例：

```json
"system_boundary": "本系统负责报账申请、审批流转、报账单据保存和本地报账状态维护；财务核算系统负责凭证生成和核算结果维护，本系统仅引用核算结果。"
```

### internal_data_groups

对象列表。用于声明本系统维护的逻辑数据组，通常辅助 strict_fpa 识别 ILF。

每项至少包含：

```json
{
  "name": "报账单据",
  "aliases": ["报账申请", "报账记录"],
  "description": "本系统创建、保存并维护的报账业务数据。"
}
```

字段要求：

- `name`：必填，非空字符串。
- `aliases`：可选，字符串列表。
- `description`：可选，字符串。

使用场景：

- 功能清单中经常出现某个业务对象，但描述没有明确写“本系统维护”。
- 需要让 strict_fpa 更稳定地把本系统维护的数据组识别为 ILF。
- 多个模块共用同一逻辑数据组，需要给 AI 一个统一名称。

示例：

```json
"internal_data_groups": [
  {
    "name": "报账单据",
    "aliases": ["报账申请", "报账记录", "报销单"],
    "description": "由本系统创建、保存、修改和维护的报账业务数据。"
  },
  {
    "name": "审批流转记录",
    "aliases": ["审批记录", "流转记录"],
    "description": "由本系统记录并维护的审批过程数据。"
  }
]
```

### external_data_groups

对象列表。用于声明外部系统维护、本系统引用的逻辑数据组，通常辅助 strict_fpa 识别 EIF。

每项至少包含：

```json
{
  "name": "财务系统单据",
  "source": "财务系统",
  "aliases": ["核算单据", "财务凭证"],
  "description": "由财务系统维护，本系统仅查询或引用。"
}
```

字段要求：

- `name`：必填，非空字符串。
- `source`：必填，非空字符串。
- `aliases`：可选，字符串列表。
- `description`：可选，字符串。

使用场景：

- 某个数据组明确由外部系统维护，本系统只读取、校验、引用或展示。
- 需要把真实外部维护数据组和普通外部接口调用区分开。
- 功能清单中只写了简称，需要通过 `aliases` 识别外部数据组。

示例：

```json
"external_data_groups": [
  {
    "name": "财务系统凭证",
    "source": "财务核算系统",
    "aliases": ["财务凭证", "核算凭证"],
    "description": "由财务核算系统维护，本系统仅查询或引用。"
  },
  {
    "name": "统一用户中心账号",
    "source": "统一用户中心",
    "aliases": ["用户账号", "人员账号", "组织人员"],
    "description": "由统一用户中心维护，本系统引用账号和组织人员信息。"
  }
]
```

注意：`external_data_groups` 表示外部系统维护的数据组，不表示“调用了一个外部接口”。只有本系统引用外部维护的数据组时，才是 EIF 候选。

### external_services

对象列表。用于声明普通外部服务调用。它用于帮助区分“调用外部服务”和“引用外部维护的数据组”，避免把普通服务调用误判为 EIF。

每项至少包含：

```json
{
  "name": "短信发送服务",
  "aliases": ["短信网关"],
  "description": "本系统调用该服务发送通知，不引用其维护的数据组。"
}
```

字段要求：

- `name`：必填，非空字符串。
- `aliases`：可选，字符串列表。
- `description`：可选，字符串。

使用场景：

- 功能清单中出现“短信网关”“电子签章”“支付接口”等外部服务。
- 这些外部服务只是被调用完成动作，不是本系统引用其维护的数据组。
- 需要防止 AI 或规则把普通外部服务调用误判为 EIF。

示例：

```json
"external_services": [
  {
    "name": "短信发送服务",
    "aliases": ["短信网关"],
    "description": "本系统调用该服务发送通知，不引用其维护的数据组。"
  },
  {
    "name": "电子签章服务",
    "aliases": ["签章平台"],
    "description": "本系统调用该服务完成签章动作，不把签章平台数据作为外部数据组计量。"
  }
]
```

如果功能描述为“调用短信网关发送审批通知”，通常不应生成 EIF。它更可能是事务功能中的一部分，例如 EI 或相关处理动作。

## 完整配置示例

```json
{
  "system_boundary": "本系统负责报账申请、审批流转、单据归档和本地状态维护；财务核算系统负责凭证和核算结果维护；统一用户中心负责账号和组织人员主数据维护。",
  "internal_data_groups": [
    {
      "name": "报账单据",
      "aliases": ["报账申请", "报销单", "报账记录"],
      "description": "由本系统创建、保存、修改和维护的报账业务数据。"
    },
    {
      "name": "审批流转记录",
      "aliases": ["审批记录", "流转记录"],
      "description": "由本系统维护的审批过程、处理意见和状态变化记录。"
    }
  ],
  "external_data_groups": [
    {
      "name": "财务系统凭证",
      "source": "财务核算系统",
      "aliases": ["财务凭证", "核算凭证"],
      "description": "由财务核算系统维护，本系统仅查询或引用。"
    },
    {
      "name": "统一用户中心账号",
      "source": "统一用户中心",
      "aliases": ["用户账号", "人员信息", "组织人员"],
      "description": "由统一用户中心维护，本系统引用账号、人员和组织信息。"
    }
  ],
  "external_services": [
    {
      "name": "短信发送服务",
      "aliases": ["短信网关"],
      "description": "本系统调用该服务发送通知，不引用其维护的数据组。"
    }
  ]
}
```

## 使用方法

1. 先确认系统边界，写入 `system_boundary`。
2. 梳理本系统真正维护的核心业务对象，写入 `internal_data_groups`。
3. 梳理外部系统维护、本系统只引用的数据组，写入 `external_data_groups`，并填写 `source`。
4. 梳理容易被误判为 EIF 的普通外部服务，写入 `external_services`。
5. 运行 FPA 预览或正式生成，检查 AI prompt、预览结果或审计 trace 中的判断是否符合预期。

最小可用配置可以只写 `system_boundary` 和少量关键数据组。不要为了完整而把每个接口、按钮、数据库表字段都写进去。

## 读取与校验逻辑

配置读取入口：

```text
ai_gen_reimbursement_docs/config_utils.py
```

核心函数：

- `load_fpa_domain_context()`：严格读取 `domain_context.json`。文件缺失、JSON 解析失败或结构非法时抛出 `FpaConfigError`。
- `load_optional_fpa_domain_context()`：可选读取。文件不存在时返回空对象；文件存在但内容非法时仍抛出错误。
- `validate_fpa_domain_context()`：校验字段结构。

当前 `gen-fpa` 使用的是可选读取入口，因此已有配置目录中如果没有 `domain_context.json`，仍可继续生成；但如果文件存在且格式错误，会明确失败。

## Prompt 注入方式

`domain_context` 不是 `fpa_config.yaml` 用户提示词模板中的独立占位符。

`fpa_config.yaml` 的 `user_prompt_sets` 只支持以下三个占位符：

```text
${core_rules}
${judgement_rules}
${payload_json}
```

`domain_context` 会被放入 `${payload_json}` 内部，作为 JSON 字段传给 AI。

生成时的上下文合并逻辑：

1. 先从元数据 MD 中提取项目上下文字段，例如：
   - `子系统（模块）`
   - `资产标识`
   - `新增/修改功能点前缀生成规则`
   - `功能用户-接收者判定`
2. 再读取 `domain_context.json`。
3. 使用 `domain_context.json` 的内容覆盖或补充元数据上下文。
4. 合并后的对象写入 prompt payload：

```json
{
  "module": {},
  "processes": [],
  "domain_context": {}
}
```

## 与 FPA 判定的关系

`domain_context` 主要影响 AI 和 strict_fpa 的语义判断：

- 辅助识别本系统维护的数据组，减少 ILF 漏判。
- 辅助识别外部系统维护的数据组，减少 EIF 漏判。
- 区分外部数据组和普通外部服务调用，减少把服务调用误判为 EIF。
- 进入 AI cache key，配置变化后会使旧 AI 缓存失效。

## 配置建议

优先记录稳定的项目边界和跨模块共用数据组，不建议把每个页面、按钮、接口都写入 `domain_context.json`。

推荐维护内容：

- 本系统负责维护的核心业务对象。
- 明确由外部系统维护、本系统引用的数据组。
- 容易被误判为 EIF 的普通外部服务。
- 客户或项目明确指定的系统边界口径。

不推荐维护内容：

- 单个功能过程的临时描述。
- 数据库物理表字段清单。
- 普通接口清单，除非它们用于说明外部服务不是外部数据组。

## 后续待办

1. 在 FPA 配置文档中补充 `domain_context.json` 的完整示例。
2. 在 Web 配置页中展示当前 `domain_context` 是否已配置。
3. 在 FPA 预览 debug 中展示合并后的 `domain_context` 摘要，方便审查 AI 输入。
4. 结合后续 `judgement_rules_source: config` 改造，统一说明 FPA 独立配置文件清单。
