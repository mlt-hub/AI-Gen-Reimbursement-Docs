# 源代码上下文辅助 gen-fpa 设计说明

## 背景

当项目已有源代码时，源代码可以为 `gen-fpa` 提供更可靠的系统边界、数据归属、外部依赖和功能动作线索。

但源代码结构不能直接替代 FPA 计量口径。数据库表不等于 ILF，接口不等于功能点，页面或按钮也不一定单独计量。源码信息应先被提炼成项目级领域上下文，再参与 `gen-fpa` 的 AI prompt、规则兜底和人工审阅。

## 目标

建立一条可解释、可审阅的辅助路径：

```text
项目源代码
→ 源码分析摘要
→ 人工确认的数据边界和外部依赖
→ domain_context.json 或后续独立源码上下文配置
→ gen-fpa 生成与审阅
```

目标不是让 `gen-fpa` 按代码结构直接拆功能点，而是提高以下判断的稳定性：

- 本系统维护的数据组，辅助 ILF 判断。
- 外部系统维护、本系统引用的数据组，辅助 EIF 判断。
- 普通外部服务调用，避免误判为 EIF。
- 新增、修改、删除、提交、导入、查询、导出等事务动作，辅助 EI/EQ/EO 判断。
- 功能点名称和计算依据说明中的业务对象命名一致性。

## 源代码能提供的有效信息

### 系统边界

可从项目结构、模块名、服务名、包名、部署配置等信息识别：

- 哪些模块属于本系统。
- 哪些模块只是外部 SDK、外部 client 或适配器。
- 哪些服务是本系统内部服务，哪些是跨系统依赖。

这些信息适合沉淀到 `domain_context.json` 的 `system_boundary`。

### 数据归属

可从 ORM model、实体类、数据库 migration、Repository、DAO、Mapper、聚合根等信息识别：

- 本系统创建、修改、保存和维护的数据对象。
- 只读引用的数据对象。
- 同步进入本系统并继续维护的数据对象。
- 来自外部系统且仍由外部维护的数据对象。

这些信息适合沉淀到：

- `internal_data_groups`：本系统维护的数据组，辅助 ILF。
- `external_data_groups`：外部维护、本系统引用的数据组，辅助 EIF。

注意：物理表数量不能直接等同于 ILF 数量。应按逻辑数据组归并。

### 外部依赖

可从 HTTP client、RPC client、SDK、消息队列 producer/consumer、第三方库封装等信息识别：

- 普通外部服务调用。
- 外部系统维护的数据组查询。
- 外部系统的数据同步。
- 通知、支付、签章、短信、文件、OCR 等能力型服务。

这些信息适合区分：

- `external_data_groups`：外部维护的数据组。
- `external_services`：普通外部服务调用，不应直接判为 EIF。

### 事务动作

可从 controller、router、API path、service 方法、页面路由和前端 action 中识别：

- 新增、修改、删除、保存、提交、审批、导入、同步等 EI 候选。
- 查询、查看、详情、列表、检索等 EQ 候选。
- 导出、报表、下载、生成文件、打印清单等 EO 候选。

这些信息可以辅助 AI 理解功能清单中描述不完整的功能过程，但不应机械地“一接口一功能点”。

### 命名校准

源码中的实体名、服务名、路由名、页面名可以帮助统一：

- 功能点名称中的业务对象。
- `domain_context.json` 中的数据组名称和别名。
- 计算依据说明中的系统元素。

## 不应该直接使用源码做的事情

不要把源码扫描结果直接作为 FPA 行输出。

不建议：

- 一张数据库表生成一条 ILF。
- 一个接口生成一条 EI/EQ/EO。
- 一个页面、按钮、弹窗生成一条功能点。
- 只因为调用了外部 API 就生成 EIF。
- 把技术类对象、DTO、VO、缓存表、日志表、字典表都直接计为数据功能。

FPA 仍应按业务能力、逻辑数据组和事务功能计量。

## 推荐工作流

### 1. 扫描源代码

扫描目标：

- 实体、表、Repository、Mapper、DAO、ORM model。
- Controller、Router、API path、Service 方法。
- 外部 client、SDK、HTTP/RPC 调用、消息队列调用。
- 前端页面路由、主要 action、导入导出入口。

### 2. 形成源码分析摘要

摘要应按 FPA 有用的信息分类，而不是按文件树分类。

建议输出结构：

```json
{
  "system_boundary_candidates": [],
  "internal_data_group_candidates": [],
  "external_data_group_candidates": [],
  "external_service_candidates": [],
  "transaction_action_candidates": []
}
```

### 3. 人工确认边界

源码只能提供线索，最终仍需要人工确认：

- 该数据组是否由本系统维护。
- 外部数据是否只是同步副本，还是仍由外部系统维护。
- 外部调用是普通服务，还是引用外部维护的数据组。
- 功能清单中的业务语义是否和源码命名一致。

### 4. 写入 domain_context.json

确认后的稳定信息写入：

```text
配置目录/domain_context.json
```

建议只写稳定事实：

- `system_boundary`
- `internal_data_groups`
- `external_data_groups`
- `external_services`

不要把所有接口和表原样塞进 `domain_context.json`。

### 5. 运行 gen-fpa 并审阅

运行 FPA 预览或正式生成后，重点审阅：

- ILF/EIF 是否符合数据归属。
- 普通外部服务是否未被误判为 EIF。
- EI/EQ/EO 是否和事务动作一致。
- 计算依据说明是否引用了真实系统元素，且没有把表或接口机械等同为功能点。

## Agent 协作流程

当用户把项目源代码提供给 agent 时，推荐按“先分析、再确认、后落配置”的方式执行。

### 输入要求

用户提供源码路径即可，例如：

```text
F:\mlt\some-project-source
```

如果项目包含多个代码仓库，建议同时说明每个仓库的职责，例如：

```text
backend: F:\project\backend
frontend: F:\project\frontend
batch: F:\project\batch-jobs
```

可选补充：

- 技术栈，例如 Java Spring、Python FastAPI、Vue、React。
- 哪个仓库属于本系统边界内。
- 哪些外部系统名称已知。
- 是否允许读取数据库脚本、配置文件、接口文档和部署配置。

### Agent 执行步骤

1. 扫描源码结构，识别后端、前端、配置、数据库脚本和外部依赖入口。
2. 提取候选信息：
   - 本系统维护的数据组候选。
   - 外部系统维护、本系统引用的数据组候选。
   - 普通外部服务调用候选。
   - EI/EQ/EO 事务动作候选。
   - 系统边界线索。
3. 为每个候选项保留来源证据，例如文件路径、类名、方法名、接口路径或配置键。
4. 形成源码上下文分析报告。
5. 形成 `domain_context.json` 建议稿。
6. 等用户确认后，再更新实际配置文件。

### 输出产物

第一轮分析建议输出两类文件：

```text
docs/fpa/todo/source-context-analysis-<project>.md
docs/fpa/todo/domain-context-suggestion-<project>.json
```

其中：

- `source-context-analysis-<project>.md`：解释分析范围、候选项、来源证据、判断理由和风险。
- `domain-context-suggestion-<project>.json`：只放适合进入 `domain_context.json` 的建议稿，不直接作为最终配置写入。

### 人工确认点

进入 `domain_context.json` 前，用户或业务负责人至少确认：

- 哪些数据组确实由本系统维护。
- 哪些数据组确实由外部系统维护、本系统只是引用。
- 哪些外部调用只是能力型服务，不应计为 EIF。
- 源码中的技术名是否需要改成业务名。
- 是否存在源码未覆盖但业务上必须纳入的系统边界。

### 修改边界

agent 默认不应直接把源码扫描结果写入正式 `domain_context.json`。

默认流程是：

```text
源码扫描
→ 候选分析报告
→ domain_context 建议稿
→ 用户确认
→ 更新正式配置
```

只有用户明确发出“按建议更新配置”“写入 domain_context.json”等指令后，才修改正式配置。

## 与 domain_context.json 的关系

当前最合适的落点是 `domain_context.json`。

示例：

```json
{
  "system_boundary": "本系统负责报账申请、审批流转和本地报账单据维护；财务系统负责凭证和核算结果维护；统一用户中心负责账号和组织主数据维护。",
  "internal_data_groups": [
    {
      "name": "报账单据",
      "aliases": ["报账申请", "报销单"],
      "description": "源码中由本系统的报账实体、Repository 和保存流程维护。"
    }
  ],
  "external_data_groups": [
    {
      "name": "统一用户中心账号",
      "source": "统一用户中心",
      "aliases": ["用户账号", "人员信息"],
      "description": "源码中通过用户中心 client 查询，本系统不维护账号主数据。"
    }
  ],
  "external_services": [
    {
      "name": "短信发送服务",
      "aliases": ["短信网关"],
      "description": "源码中仅调用短信发送接口，不引用短信平台维护的数据组。"
    }
  ]
}
```

## 实现难度与分期

整体判断：MVP 好实现，中高级自动分析不算简单。

现有 `gen-fpa` 已经有合适的扩展点：prompt payload 中包含 `domain_context`，并且合并后的 `domain_context` 已进入 AI cache key。因此第一版不需要重写生成流程，只需要把源码分析结果整理成领域上下文，再进入现有 `domain_context` 路径。

### 第一阶段：MVP

难度：低。

目标：

- 不做复杂源码解析。
- 允许用户或简单脚本生成 `source_context.json`。
- 人工确认后，把稳定信息写入 `domain_context.json`。
- `gen-fpa` 继续使用现有 prompt 注入和 cache key 逻辑。

适合先验证价值：

- 源码信息是否能减少 ILF/EIF 误判。
- 外部服务是否能和外部数据组区分开。
- 计算依据说明是否更贴近真实系统元素。

这一阶段主要新增文档、示例和少量辅助脚本，不触碰核心 FPA 判定算法。

### 第二阶段：实用版

难度：中等。

目标：

- 新增源码扫描命令，输出候选上下文。
- 按 FPA 有用信息分类，而不是按文件树输出。
- 每个候选项带来源证据，例如文件路径、类名、方法名、路由。
- 用户确认后再合并到 `domain_context.json`。

候选输出包括：

- `internal_data_group_candidates`
- `external_data_group_candidates`
- `external_service_candidates`
- `transaction_action_candidates`
- `system_boundary_candidates`

这一阶段的关键不是“扫描到更多”，而是“候选项可审阅、可解释、可舍弃”。

### 第三阶段：自动辅助版

难度：中高到高。

目标：

- 支持多语言或多框架源码。
- 识别 ORM、Controller、Service、外部 Client、前端路由。
- 在 FPA 预览中显示命中的源码证据。
- 辅助判断 ILF/EIF/EI/EQ/EO，但不直接替代 profile 和 rule_set。

主要难点：

- 不能把数据库表机械等同为 ILF。
- 不能把接口机械等同为 EI/EQ/EO。
- 不能把普通外部 API 调用机械等同为 EIF。
- 源码命名和业务语言可能不一致，需要保留人工确认环节。
- 多语言、多框架项目的结构差异较大，自动识别规则需要逐步扩展。

### 难度拆解

```text
把源码摘要接入 gen-fpa prompt：低
新增 source_context.json 配置和读取：低到中
生成候选项并带来源证据：中
扫描 Java/Python/前端等多类源码：中到中高
自动判 ILF/EIF/EI/EQ/EO：中高
做到可审计、低误判：高
```

推荐优先实现第一阶段和第二阶段。这样能获得主要收益，同时避免让源码结构直接污染 FPA 计量口径。

## 后续可实施能力

### 源码上下文生成命令

可考虑新增一个辅助命令，例如：

```powershell
ard analyze-source-context --source-dir <path> --output source_context.json
```

该命令只生成候选摘要，不直接修改 FPA 配置。

### domain_context 合并建议

可考虑新增审阅命令：

```powershell
ard suggest-domain-context --source-context source_context.json
```

输出建议修改项，由用户确认后再写入 `domain_context.json`。

### Web 预览辅助

可在 FPA 预览页展示：

- 当前使用的 `domain_context` 摘要。
- 哪些功能点命中了源码上下文。
- 哪些 ILF/EIF 判断依赖人工确认。

## 风险与控制

- 源码可能不完整，尤其缺少外部系统、数据库 migration 或前端代码时，不能据此作最终判断。
- 老代码命名可能和业务语言不一致，需要业务人员确认。
- 技术表、缓存表、日志表、临时表不应直接计为 ILF。
- 普通外部接口调用不应直接计为 EIF。
- 自动分析结果必须保留来源证据，便于审阅和回退。

## 验收标准

后续若实现源码上下文辅助，应满足：

1. 源码分析只输出候选上下文，不直接改 FPA 结果。
2. 生成的候选项带来源证据，例如文件路径、类名、方法名或路由。
3. 人工确认后再进入 `domain_context.json`。
4. `gen-fpa` 仍按 profile、rule_set、judgement_rules 和 domain_context 统一生成。
5. AI cache key 包含最终 domain_context，源码上下文变化导致配置变化时能触发缓存失效。
