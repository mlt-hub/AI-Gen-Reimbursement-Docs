# gen-fpa 三级模块规划改造实施记录

日期：2026-05-29

## 当前配置状态

FPA 配置当前统一使用：

```text
配置目录/fpa_config.yaml
config/fpa_config.yaml.example
```

该文件合并维护：

```text
profile
profiles
prompt_sets
rule_sets
```

旧拆分配置文件不再作为生产入口：

```text
fpa_system_prompts_config.yaml
fpa_user_prompts_config.yaml
fpa_rule_sets_config.yaml
```

系统尚未上线，不保留旧配置兼容路径。`system_config.yaml` 不再维护 `fpa_profile`、`fpa_strategy`、`fpa_rule_set`、`fpa_external_data_rules`。FPA 生成、预览、审核副本和 AI cache 不再暴露 `rule_set_version`；cache key 改为纳入 rule_set 的实际配置内容。

## 项目约束

根据 `AGENTS.md`：

```text
本系统尚未上线，开发时不需要保留旧版本兼容路径。
```

落实到 FPA 改造中：

```text
不保留旧版“每个功能过程固定生成界面开发 + 接口开发”的兼容路径。
不为旧版逐行 AI 填充流程保留兼容分支。
不为旧 10 列 FPA MD 保留读取兼容逻辑。
后续以 profile 化后的三级模块整体规划流程为准。
```

如果后续发现仍有旧兼容逻辑残留，应先记录到 `docs/fpa/fpa-todo.md` 的“旧兼容逻辑清理”分组，再单独推进删除和测试。

## 背景

本次修改基于 `docs/fpa/gen-fpa-improvement-plan.md` 推进第一阶段改造。由于系统尚未上线，本次实现不保留旧版兼容路径，`gen-fpa` 后续只采用“三级模块整体规划 FPA 行”的新流程。

旧流程为：

```text
功能过程
  -> 固定生成 1 条界面开发 EI
  -> 固定生成 1 条接口开发 ILF
  -> AI 逐行补充计算依据归类和计算依据说明
```

新流程为：

```text
功能清单模块树
  -> 按 客户端类型 + 一级模块 + 二级模块 + 三级模块 聚合
  -> 每个三级模块整体规划 FPA 行
  -> 界面能力默认合并为 1 条三级模块级界面开发行
  -> 非界面逻辑按功能动作拆分
  -> AI 输出经校验、规范化、类型兜底后写入 FPA MD
  -> 根据 FPA MD 生成 Excel
```

## 改动文件

### 核心代码

```text
ai_gen_reimbursement_docs/gen_fpa.py
ai_gen_reimbursement_docs/pipeline.py
ai_gen_reimbursement_docs/cli/main.py
```

### 测试代码

```text
tests/conftest.py
tests/test_gen_xlsx.py
tests/test_gen_fpa_ai.py
tests/test_gen_fpa_preview.py
```

## 核心行为变化

### 1. FPA 行生成粒度改变

旧行为：

```text
每个功能过程固定拆成：
1. 功能过程-界面开发
2. 功能过程-接口开发
```

新行为：

```text
每个三级模块默认生成：
1. 【客户端】一级模块-二级模块-三级模块-界面开发
2. 功能过程A-逻辑处理开发 / 查询处理开发 / 导出处理开发 / 导入处理开发
3. 功能过程B-...
```

界面类能力默认聚合到三级模块级界面行中，避免把列表、查询条件、按钮、弹窗、状态切换组件拆成多条界面开发工作量。

### 2. AI 调用粒度改变

旧行为：

```text
逐 FPA 行调用 AI。
AI 只能补充“计算依据归类”和“计算依据说明”。
```

新行为：

```text
逐三级模块调用 AI。
AI 负责返回该三级模块应生成的 FPA 行列表。
代码负责校验、规范化、类型兜底和最终落表。
```

新增函数：

```python
_ai_plan_fpa_rows_for_l3(...)
_plan_fpa_rows_with_ai(...)
plan_fpa_md_from_tree(...)
```

### 3. 旧逐行 AI 填充路径已删除

由于不需要兼容未上线版本，已移除旧函数：

```text
_ai_fill_fpa()
ai_fill_fpa_md()
```

`pipeline.py` 的 `gen-fpa` 分支现在只走：

```python
plan_fpa_md_from_tree(...)
```

旧 10 列 FPA MD 也不再作为兼容格式处理。当前生成和读取的 FPA MD 使用新 14 列格式。

## 新增核心函数

### `_group_rows_by_l3(rows)`

按以下维度聚合功能过程：

```text
客户端类型
一级模块
二级模块
三级模块
```

输出结构包含：

```text
client_type
l1
l2
l3
l3_desc
processes[]
```

每个 `processes[]` 项包含：

```text
name
type
desc
```

### `_fallback_fpa_rows_for_l3(group, meta, start_seq)`

AI 不可用、AI 调用失败、JSON 解析失败或 AI 输出无有效行时使用。

兜底策略：

```text
每个三级模块至少 1 条界面开发 EI。
每个功能过程至少 1 条逻辑处理/查询处理/导出处理/导入处理行。
```

兜底类型规则：

```text
界面开发 / 页面 -> EI
添加 / 新增 / 编辑 / 修改 / 删除 / 维护 / 保存 / 启用 / 停用 / 更新 -> ILF
查询 / 查看 / 详情 / 列表检索 / 检索 -> EQ
导出 / 报表输出 / 生成文件 -> EO
导入 -> EI
明确引用外部应用维护的数据组 / 统一用户中心 / 外部主数据 -> EIF
普通外部接口调用 -> 不机械判 EIF，默认 ILF
```

### `_normalize_ai_fpa_rows_for_l3(...)`

负责校验和规范化 AI 输出。

处理内容：

```text
校验 name 不能为空。
校验 type 必须属于 EI / ILF / EQ / EO / EIF。
AI type 非法时使用关键词规则兜底。
AI type 与关键词规则明显冲突时使用关键词规则兜底。
classification_basis_index 必须在模板判定原则范围内。
classification_basis 无法匹配模板规则时不乱填。
explanation 为空时使用兜底说明。
同一三级模块多条界面开发行缺少 split_reason 时合并为 1 条界面行。
```

### `_read_fpa_judgement_rules(template_path)`

判定原则读取范围从旧的固定 `C2:C14` 改为：

```python
for row_num in range(2, ws.max_row + 1):
```

这样模板附录后续新增规则时可以自动进入 prompt。

### `preview_fpa_module(...)`

新增单三级模块 FPA 预览函数。

用途：

```text
读取功能清单
生成临时基础 MD
按三级模块定位目标模块
调用 AI 规划或兜底规划
返回结构化预览结果
不生成 FPA Excel
不写正式交付物
```

返回结构包括：

```text
module
rows
warnings
used_ai
```

## Prompt 改造

新增固定 prompt 片段：

```python
FPA_CORE_RULES
```

核心约束：

```text
不按按钮、弹窗、数据库表、字段或技术实现拆分。
同一三级模块界面能力默认合并为 1 条。
多界面行必须有独立页面、独立业务对象、独立业务流程或独立用户端依据。
非界面逻辑按业务动作拆分。
不为数据库表或字段单独造 FPA 行。
EIF 仅用于引用其他应用维护的数据组。
计算依据归类只能从模板判定原则选择。
```

AI 输入中包含：

```text
模块上下文
三级模块整体描述
功能过程列表
功能过程类型
功能过程描述
领域上下文
模板判定原则列表
FPA 核心口径
```

AI 输出要求为 JSON：

```json
{
  "rows": [
    {
      "name": "功能点名称",
      "type": "EI/ILF/EQ/EO/EIF",
      "type_reason": "类型理由",
      "classification_basis_index": 1,
      "explanation": "计算依据说明",
      "source_processes": ["功能过程名称"],
      "split_reason": "多界面拆分理由，可空"
    }
  ]
}
```

## 提示词与规则来源

当前 `gen-fpa` 的 AI 输入由代码、配置文件、Excel 模板和业务数据共同组成。

| 内容 | 当前来源 | 维护方式 |
|---|---|---|
| 系统提示词 | `~/.ai-gen-reimbursement-docs/fpa_config.yaml` 中 `profiles.<profile>.system_prompt` 指向的 `prompt_sets.<name>.system` | FPA 专用配置文件；缺失时报错 |
| 用户提示词模板 | `~/.ai-gen-reimbursement-docs/fpa_config.yaml` 中 `profiles.<profile>.user_prompt` 指向的 `prompt_sets.<name>.user` | FPA 专用配置文件；缺失时报错 |
| 默认 profile / strategy / rule_set | `~/.ai-gen-reimbursement-docs/fpa_config.yaml` 中的 `profile` 与 `profiles` | FPA 专用配置文件 |
| 事务关键词扩展规则 | `~/.ai-gen-reimbursement-docs/fpa_config.yaml` 中的 `rule_sets.<name>.keyword_rules` | FPA 专用配置文件 |
| 内部数据组扩展规则 | `~/.ai-gen-reimbursement-docs/fpa_config.yaml` 中的 `rule_sets.<name>.internal_data_rules` | FPA 专用配置文件 |
| 外部数据组扩展规则 | `~/.ai-gen-reimbursement-docs/fpa_config.yaml` 中的 `rule_sets.<name>.external_data_rules` | FPA 专用配置文件 |
| FPA 核心规则 | `fpa_profiles.py` 中的 `CUSTOM_RULES_CORE_RULES` / `STRICT_FPA_CORE_RULES` | 代码 |
| 领域上下文 | `gen_fpa.py` 的 `_build_domain_context(meta)` 从元数据 MD 提取 | 代码 + Excel/MD 数据 |
| 功能过程上下文 | `parse_module_tree_md()` 读取模块树 MD 后按三级模块聚合 | Excel -> MD -> 代码 |
| 计算依据归类判定原则 | FPA 输出模板 Excel 的附录 Sheet | Excel 模板 |
| 类型兜底规则 | `fpa_profiles.py` 中各 profile 的 `infer_type()` | 代码 |
| AI 失败兜底拆分规则 | `fpa_profiles.py` 中各 profile 的 `fallback_rows_for_l3()` | 代码 |
| 多界面合并规则 | `gen_fpa.py` 的 `_normalize_ai_fpa_rows_for_l3()` | 代码 |

### 系统提示词

读取方式：

```python
load_fpa_system_prompt_config("custom_rules")
```

配置文件：

```text
~/.ai-gen-reimbursement-docs/fpa_config.yaml
```

配置结构：

```yaml
profiles:
  custom_rules:
    system_prompt: custom_rules

prompt_sets:
  custom_rules:
    system: |-
      ...
```

如果配置文件中没有对应的 `prompt_sets.<name>.system`，FPA AI 预览和正式生成都会直接报错。

### 用户提示词

用户提示词模板已从代码中分离到 FPA 专用配置文件：

```text
~/.ai-gen-reimbursement-docs/fpa_config.yaml
```

模板示例来自：

```text
config/fpa_config.yaml.example
```

当前支持按 profile 配置：

```yaml
profiles:
  custom_rules:
    user_prompt: custom_rules
  strict_fpa:
    user_prompt: strict_fpa

prompt_sets:
  custom_rules:
    user: |-
      ${core_rules}
      ${judgement_rules}
      ${payload_json}
  strict_fpa:
    user: |-
      ${core_rules}
      ${judgement_rules}
      ${payload_json}
```

可用占位符：

```text
${core_rules}
${judgement_rules}
${payload_json}
```

如果 `fpa_config.yaml` 不存在、profile 未配置模板或读取失败，FPA AI 预览和正式生成都会直接报错。

#### 配置结构

```yaml
prompt_sets:
  custom_rules:
    user: |-
      ${core_rules}

      计算依据归类判定原则列表：
      ${judgement_rules}

      模块输入 JSON：
      ${payload_json}

      请直接输出 JSON，不要输出其他内容。

  strict_fpa:
    user: |-
      ${core_rules}

      计算依据归类判定原则列表：
      ${judgement_rules}

      模块输入 JSON：
      ${payload_json}

      请直接输出 JSON，不要输出其他内容。
```

#### 占位符含义

```text
${core_rules}
当前 profile 的核心规则。custom_rules 与 strict_fpa 的规则不同。

${judgement_rules}
从 FPA 输出模板 Excel 附录 Sheet 读取的计算依据归类判定原则，按 1) 2) 3) 编号。

${payload_json}
当前三级模块输入 JSON，包含 module、processes、domain_context。
```

#### 兜底与风险边界

```text
fpa_config.yaml 不存在 -> 报错。
profile 未配置模板 -> 报错。
配置文件读取失败 -> 报错。
未知占位符 -> 原样保留，不中断任务。
```

用户提示词模板只影响 AI 规划阶段，不替代代码后处理：

```text
类型合法性校验仍在代码中。
strict_fpa 的 EI/EQ/EO/ILF/EIF 兜底仍以代码内置规则为默认行为。
`fpa_config.yaml` 的 rule_set 可追加 EI/EQ/EO 事务关键词、ILF 内部数据组和 EIF 外部数据组识别规则。
AI 失败时仍使用 profile fallback_rows_for_l3() 兜底。
```

#### 初始化与迁移

```text
ard --init-config 会复制 config/fpa_config.yaml.example 到用户配置目录。
exe 首次运行自动初始化配置时也会复制该文件。
migrate_config() 会对 fpa_config.yaml 做新增顶层键迁移。
```

#### 修改后建议验证

```powershell
.\scripts\test.ps1 tests/test_config_utils.py tests/test_fpa_profiles.py tests/test_gen_fpa_ai.py
```

如涉及正式生成或 Web 流程，继续执行：

```powershell
.\scripts\test.ps1 tests/test_web_tasks.py tests/test_pipeline.py
npm run build
```

当前用户提示词包含：

```text
FPA_CORE_RULES
计算依据归类判定原则列表
三级模块信息
三级模块整体功能描述
功能过程列表
功能过程类型
功能过程描述
领域上下文
拆分规则
类型规则
JSON 输出格式要求
```

### 领域上下文

当前领域上下文由元数据 MD 与配置目录/domain_context.json 合并得到。元数据 MD 主要字段包括：

```text
子系统（模块）
资产标识
新增/修改功能点前缀生成规则
功能用户-接收者判定
```

这些字段由功能清单 Excel 的元数据 Sheet 生成到 MD 后，再由代码读取；项目级 domain_context.json 额外补充系统边界、本系统维护数据组、外部引用数据组和普通外部服务。

### 计算依据归类判定原则

判定原则不写在 prompt 配置文件中，而是从 FPA 输出模板 Excel 读取：

```text
Sheet：system_config.yaml 中的 fpa_appendix_sheet
默认：附录1-FPA评估方法说明
列：C列
行：第2行到 ws.max_row
```

这些判定原则只用于让 AI 返回 `classification_basis_index`，不应反向决定拆分粒度。

### 当前边界

目前 FPA 系统提示词和用户提示词都放在配置文件中，后处理规则和兜底生成规则仍在代码中。

这样做的好处：

```text
兜底行为稳定。
AI 不听 prompt 或返回异常时，代码仍能保证基本输出。
测试可以覆盖真实后处理规则。
```

代价：

```text
如果要维护多套 FPA 方案，不能只改系统提示词。
FPA_CORE_RULES、用户提示词、类型兜底、失败兜底、配置选择项和 Golden Case 都需要跟着切换。
```

后续如要支持多套方案，建议抽象为 profile：

```text
custom_rules
strict_fpa
```

每个 profile 统一提供：

```text
core_rules
build_prompt()
fallback_rows_for_l3()
infer_type()
has_obvious_conflict()
golden_cases
```

## FPA 口径讨论记录

### 标准 FPA 是否区分“界面开发”和“接口开发”

严格来说，标准 FPA 不按“界面开发 / 接口开发”分类。

标准 FPA 关注的是用户可识别的功能，通常分为 5 类：

```text
EI  外部输入
EO  外部输出
EQ  外部查询
ILF 内部逻辑文件
EIF 外部接口文件
```

因此：

```text
“界面开发”不是 FPA 标准类型。
“接口开发”也不是 FPA 标准类型。
“接口开发”不能直接等同于 ILF、EIF 或 EI。
```

当前系统中出现的：

```text
界面开发
逻辑处理开发
查询处理开发
导出处理开发
导入处理开发
```

更准确地说，是报账模板中的“新增/修改功能点”命名口径，不是标准 FPA 的类型体系。真正的 FPA 类型仍由“类型”列承载：

```text
EI / EO / EQ / ILF / EIF
```

### 如果严格按照 FPA，当前业务应如何拆分

严格 FPA 应从“开发工作项”转向“数据功能 + 事务功能”。

关键区别：

```text
新增、编辑、删除、保存、审批、导入等操作通常是 EI。
查询、查看详情、列表检索通常是 EQ。
导出、报表、生成文件通常是 EO。
本系统维护的一组逻辑数据是 ILF。
本系统引用但由外部系统维护的一组逻辑数据是 EIF。
```

例如“垂直行业管理”，严格 FPA 形态更接近：

```text
数据功能：
1. 垂直行业信息：ILF
2. 垂直行业管理员关系：ILF

事务功能：
1. 查询垂直行业列表：EQ
2. 新增垂直行业：EI
3. 修改垂直行业：EI
4. 删除垂直行业：EI
5. 启用/停用垂直行业：EI
6. 新增垂直行业管理员：EI
7. 删除垂直行业管理员：EI
```

严格 FPA 下不应出现：

```text
垂直行业管理-界面开发：EI
添加垂直行业-逻辑接口开发：ILF
```

原因：

```text
“界面开发 / 接口开发”是实现视角。
FPA 需要的是用户视角下的业务事务和逻辑数据组。
维护动作不等于 ILF；维护动作通常是 EI。
ILF 是被维护的数据功能，不是“维护接口”本身。
```

### 当前项目口径与严格 FPA 的差异

当前实现仍保留“界面开发 / 逻辑处理开发”等命名，是为了适配现有 FPA 输出模板和报账材料表达习惯。

当前项目口径：

```text
以三级模块合并界面能力，避免拆碎。
非界面能力按功能动作生成处理行。
类型通过 AI 判断 + 代码兜底校验。
```

严格 FPA 口径：

```text
不按界面/接口命名。
按数据功能和事务功能拆分。
维护动作通常为 EI。
本系统维护的数据组才是 ILF。
外部维护的数据组才是 EIF。
```

结论：

```text
当前实现比旧版“每个功能过程固定界面+接口两行”更合理。
但如果追求严格 FPA，需要进一步调整 profile，而不是只改 prompt。
```

## 多套 FPA 方案讨论记录

### 只改提示词是否足够

不够。

原因是 `gen-fpa` 有三层决策：

```text
1. 拆分口径：生成哪些 FPA 行。
2. 类型规则：EI / EO / EQ / ILF / EIF 如何判定。
3. 后处理兜底：AI 失败、越界、冲突时如何修正。
```

只改系统提示词会出现的问题：

```text
AI 可能按新口径输出。
但代码兜底仍可能按旧口径生成行。
AI 失败时仍走旧兜底。
AI type 与关键词冲突时仍由旧冲突规则修正。
Golden Case 仍按旧预期测试。
缓存 key 虽会因 profile.core_rules 改变而失效，但如果 profile 不切换，缓存也可能复用旧口径输出。
```

因此，多套方案至少需要一起切换：

```text
系统提示词
用户提示词
profile.core_rules
代码兜底拆分规则
代码类型兜底规则
AI type 冲突规则
Golden Case 预期
输出命名规则
缓存 key 组成
```

### 多套方案是否会让代码变乱

会，如果直接在主流程里散落：

```python
if profile == "strict_fpa":
    ...
else:
    ...
```

不建议在 `gen_fpa.py` 中继续堆多个口径的条件分支。

更稳的做法是抽一个策略层：

```text
gen_fpa.py
  只负责编排流程：
  读取模块树 -> 分组 -> 调用 profile -> 写 MD -> 写 Excel

fpa_profiles.py
  放不同 FPA 方案：
  custom_rules
  strict_fpa
```

每套 profile 暴露同一组接口：

```python
class FpaProfile:
    name: str
    core_rules: str

    def build_prompt(...)
    def fallback_rows_for_l3(...)
    def infer_type(...)
    def has_obvious_conflict(...)
    def normalize_row_name(...)
```

主流程只依赖统一接口：

```python
profile = get_fpa_profile(config.fpa_profile)
prompt = profile.build_prompt(...)
fallback_rows = profile.fallback_rows_for_l3(...)
fpa_type = profile.infer_type(...)
```

这样新增第三套方案时，主要是新增 profile，而不是改主流程。

### 可选 profile 设想

短期如果需要保留两套口径，可以定义：

```text
custom_rules
strict_fpa
```

`custom_rules`：

```text
保留“界面开发 / 逻辑处理开发 / 查询处理开发”等模板友好命名。
同一三级模块界面能力默认合并为一条。
非界面逻辑按功能动作生成。
类型兜底保留当前项目口径。
```

`strict_fpa`：

```text
不生成“界面开发 / 接口开发”工作项。
生成事务功能 + 数据功能。
新增 / 修改 / 删除 / 保存 / 导入 / 审批 -> EI。
查询 / 查看 / 详情 -> EQ。
导出 / 报表 / 下载文件 -> EO。
本系统维护的数据组 -> ILF。
外部系统维护的数据组 -> EIF。
```

### 当前建议

短期：

```text
先明确最终业务口径。
如果只需要报账模板口径，就继续完善 custom_rules。
如果需要严格 FPA，就新增 strict_fpa，不要在 custom_rules 上硬改到半严格状态。
```

### 不要把 custom_rules 改成半严格状态

“半严格状态”指的是把严格 FPA 的部分规则零散混入当前报账模板口径，但又没有完整切换到严格 FPA。

例如：

```text
名称仍然叫“界面开发 / 逻辑处理开发 / 查询处理开发”。
但类型又部分按严格 FPA 改。
有些维护动作判 EI，有些维护动作仍判 ILF。
有些模块生成三级模块界面行，有些模块不生成界面行。
ILF 一会儿表示“逻辑接口开发”，一会儿表示“内部逻辑数据组”。
EIF 一会儿表示外部接口调用，一会儿表示外部维护的数据组。
```

这种状态的问题：

```text
业务口径不自洽，用户难以理解。
AI prompt 中的规则会互相牵扯。
代码兜底规则容易互相打架。
缓存命中结果和新规则可能语义不一致。
Golden Case 预期难以稳定。
同一类功能在不同模块中可能得到不同类型。
```

因此，`custom_rules` 和 `strict_fpa` 应保持清晰边界。

`custom_rules` 的边界：

```text
服务于当前报账模板表达。
允许保留“界面开发 / 逻辑处理开发 / 查询处理开发”等模板友好命名。
重点解决旧版界面拆碎、重复造工作量的问题。
规则目标是稳定、可解释、符合现有输出模板。
```

`strict_fpa` 的边界：

```text
服务于标准 FPA。
不按“界面开发 / 接口开发”命名。
按数据功能 + 事务功能拆分。
维护动作通常是 EI。
本系统维护的数据组才是 ILF。
外部系统维护的数据组才是 EIF。
```

结论：

```text
不是不能做严格 FPA。
而是不要把严格 FPA 的规则一点点混进 custom_rules。
如果要做严格 FPA，应新增 strict_fpa profile，让两套规则各自完整、自洽。
```

中期：

```text
抽 fpa_profiles.py。
把 FPA_CORE_RULES、prompt 构建、fallback、type infer、conflict check、Golden Case 预期都迁入 profile。
system_config.yaml 增加 fpa_profile。
缓存 key 纳入 profile.name 和 profile.version。
```

## 多套 FPA 方案细化设计

### 目标

支持在同一套系统中维护多种 FPA 生成口径，且不让主流程代码变乱。

第一批建议支持：

```text
custom_rules：当前报账模板口径。
strict_fpa：严格 FPA 口径。
```

设计目标：

```text
主流程不关心具体口径。
每套方案有完整、自洽的 prompt、兜底规则和测试预期。
新增方案时尽量只新增 profile，不改主流程。
缓存能区分不同 profile。
Web/CLI/正式生成/预览使用同一 profile 选择逻辑。
```

### 非目标

第一阶段不建议做成完全外部 YAML 规则引擎。

原因：

```text
FPA 拆分和类型冲突规则包含较多业务判断。
过早 YAML 化会让规则表达力不足，调试困难。
当前更适合先用 Python profile 固化边界。
待 profile 稳定后，再把关键词表、命名模板等低风险部分配置化。
```

### 建议文件结构

```text
ai_gen_reimbursement_docs/
  gen_fpa.py
  fpa_profiles.py
```

`gen_fpa.py` 保留流程编排：

```text
读取模块树
读取元数据
读取判定原则
按三级模块聚合
选择 profile
调用 profile 生成 prompt / 兜底行 / 类型判断
写 MD
写 Excel
```

`fpa_profiles.py` 承载方案差异：

```text
FpaProfile 基类或协议
CustomRulesProfile
StrictFpaProfile
get_fpa_profile(name)
```

### Profile 接口草案

```python
@dataclass(frozen=True)
class FpaProfile:
    name: str
    version: str
    description: str
    core_rules: str

    def build_prompt(
        self,
        group: dict[str, object],
        judgement_rules: list[str],
        domain_context: dict[str, object],
    ) -> str:
        ...

    def fallback_rows_for_l3(
        self,
        group: dict[str, object],
        meta: dict[str, str],
        start_seq: int = 1,
    ) -> list[dict[str, object]]:
        ...

    def infer_type(self, name: str, desc: str = "") -> tuple[str, str]:
        ...

    def has_obvious_conflict(self, name: str, desc: str, ai_type: str) -> bool:
        ...

    def normalize_ai_rows_for_l3(
        self,
        group: dict[str, object],
        meta: dict[str, str],
        ai_rows: list[object],
        judgement_rules: list[str],
        start_seq: int = 1,
    ) -> tuple[list[dict[str, object]], list[str]]:
        ...
```

说明：

```text
normalize_ai_rows_for_l3 可以先保留公共实现，但需要调用 profile.infer_type() 和 profile.has_obvious_conflict()。
custom_rules 和 strict_fpa 的差异主要集中在 core_rules、fallback_rows_for_l3、infer_type、命名规则。
```

### 配置项

当前在 `fpa_config.yaml` 配置默认 profile：

```yaml
profile: custom_rules
```

可选值：

```text
custom_rules
strict_fpa
```

读取函数：

```python
def load_fpa_profile(default: str = "custom_rules") -> str:
    ...
```

CLI 后续可选：

```powershell
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa
```

Web UI 后续可选：

```text
高级选项 -> FPA 方案：当前报账模板口径 / 严格 FPA 口径
```

第一步可以只支持配置文件，不急着加 CLI/Web 显式选择。

### custom_rules profile

定位：

```text
服务当前报账模板表达。
目标是减少界面拆碎和重复造工作量。
保留模板友好的“界面开发 / 逻辑处理开发 / 查询处理开发 / 导出处理开发”等名称。
```

拆分规则：

```text
同一三级模块默认 1 条界面开发行。
非界面逻辑按功能动作生成处理行。
多界面拆分需要 split_reason。
不为按钮、弹窗、字段、数据库表单独造行。
```

类型兜底：

```text
界面开发 / 页面 -> EI
查询 / 查看 / 详情 / 检索 -> EQ
导出 / 报表输出 / 生成文件 / 下载模板 -> EO
导入 -> EI
明确外部维护数据组 / 统一用户中心 / 外部主数据 -> EIF
添加 / 新增 / 编辑 / 修改 / 删除 / 维护 / 保存 / 启停 / 更新 -> ILF
普通外部服务调用 -> 不机械判 EIF
```

输出形态示例：

```text
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-界面开发：EI
查询垂直行业-查询处理开发：EQ
添加垂直行业-逻辑处理开发：ILF
导出申请列表-导出处理开发：EO
导入客户名单-导入处理开发：EI
引用统一用户中心账号-逻辑处理开发：EIF
```

### strict_fpa profile

定位：

```text
服务标准 FPA 口径。
不按开发工作项拆分。
按数据功能 + 事务功能拆分。
```

拆分规则：

```text
不生成“界面开发”行。
不生成“接口开发”行。
生成事务功能行：新增、修改、删除、查询、导出、导入、审批、提交等。
识别数据功能行：本系统维护的逻辑数据组为 ILF，外部维护且本系统引用的数据组为 EIF。
```

事务功能类型兜底：

```text
新增 / 修改 / 删除 / 保存 / 提交 / 审批 / 启用 / 停用 / 导入 -> EI
查询 / 查看 / 详情 / 检索 -> EQ
导出 / 报表 / 下载文件 / 生成文件 -> EO
```

数据功能类型兜底：

```text
本系统维护的数据组 -> ILF
外部系统维护、本系统引用的数据组 -> EIF
普通外部服务调用不生成 EIF 数据功能，除非明确存在外部维护的数据组。
```

输出形态示例：

```text
垂直行业信息：ILF
垂直行业管理员关系：ILF
查询垂直行业列表：EQ
新增垂直行业：EI
修改垂直行业：EI
删除垂直行业：EI
启用/停用垂直行业：EI
新增垂直行业管理员：EI
删除垂直行业管理员：EI
```

严格 FPA 中不应出现：

```text
垂直行业管理-界面开发
添加垂直行业-逻辑处理开发
接口开发
```

### 缓存策略

缓存 key 必须纳入：

```text
profile.name
profile.version
profile.core_rules
domain_context
group
judgement_rules
model
```

原因：

```text
同一三级模块在 custom_rules 和 strict_fpa 下可能生成完全不同的行。
profile version 变化意味着规则语义变化，应自动失效旧缓存。
```

缓存文件可以继续使用：

```text
md/fpa_ai_cache.json
```

缓存 entry 建议增加：

```json
{
  "profile": "custom_rules",
  "profile_version": "1",
  "model": "xxx",
  "rows": []
}
```

### 测试分层

建议按 profile 分层测试。

当前项目口径：

```text
tests/test_gen_fpa_ai.py
tests/test_gen_fpa_preview.py
tests/test_gen_fpa_golden_cases.py
```

新增严格 FPA 测试：

```text
tests/test_gen_fpa_strict_profile.py
```

覆盖：

```text
strict_fpa 不生成界面开发行。
strict_fpa 不生成接口开发行。
新增/修改/删除/保存为 EI。
查询为 EQ。
导出为 EO。
本系统维护数据组为 ILF。
统一用户中心账号为 EIF。
普通短信/支付/OCR 服务调用不自动生成 EIF。
```

共享测试：

```text
JSON code block 解析。
classification_basis_index 越界处理。
AI 空响应兜底。
缓存命中跳过 LLM。
Web 预览接口。
```

### 实施顺序

建议分 5 步推进。

#### 第 1 步：无行为变化抽 profile

状态：已完成。

目标：

```text
把当前逻辑迁入 CustomRulesProfile。
默认 profile = custom_rules。
测试结果不变。
```

改动：

```text
新增 fpa_profiles.py。
移动 FPA_CORE_RULES。
移动 _infer_fpa_type。
移动 _fallback_fpa_rows_for_l3。
移动 prompt 构建。
gen_fpa.py 只通过 profile 调用。
```

验收：

```text
现有目标测试全部通过。
生成结果与抽取前一致。
```

已落地：

```text
新增 ai_gen_reimbursement_docs/fpa_profiles.py。
CustomRulesProfile 承载 custom_rules 的核心规则、prompt、兜底拆分、类型推断、冲突判断和命名规则。
gen_fpa.py 主流程通过 FPA_PROFILE 调用 profile，不再保留规则副本。
缓存 key 和缓存条目已包含 profile.name 与 profile.version。
新增 tests/test_fpa_profiles.py，验证默认 profile、未知 profile 错误和 prompt 规则。
```

#### 第 2 步：配置 profile 选择

状态：已完成。

目标：

```text
system_config.yaml 支持 fpa_profile。
正式 gen-fpa、CLI 预览、Web 预览都使用同一 profile。
```

验收：

```text
默认配置下仍为 custom_rules。
非法 profile 给出明确错误。
缓存 key 包含 profile。
```

已落地：

```text
config/fpa_config.yaml.example 新增 profile: custom_rules。
config_utils.py 新增 load_fpa_profile()，并从 fpa_config.yaml 读取。
正式 gen-fpa、gen-all、run_pipeline_simple、CLI 预览和 Web 预览共用 profile 选择入口。
CLI 新增 --fpa-profile，可覆盖 fpa_config.yaml 默认值。
Web 预览接口接受 fpa_profile；未传时读取 fpa_config.yaml。
预览结果返回 profile 和 profile_version，便于人工确认当前口径。
非法 profile 会在正式生成和预览阶段给出明确错误。
```

#### 第 3 步：新增 strict_fpa profile

状态：已完成基础版。

目标：

```text
实现严格 FPA 的 prompt、fallback、type infer 和 Golden Case。
```

验收：

```text
strict_fpa Golden Case 通过。
custom_rules Golden Case 不受影响。
```

已落地：

```text
fpa_profiles.py 新增 StrictFpaProfile。
profile 注册表新增 strict_fpa。
strict_fpa 拥有独立 core_rules、prompt、fallback_rows_for_l3、infer_type 和冲突判断。
strict_fpa 兜底不生成“界面开发”“接口开发”“逻辑处理开发”行。
strict_fpa 按数据功能 + 事务功能生成行：ILF/EIF + EI/EQ/EO。
配置文件、CLI --fpa-profile、正式 gen-fpa/gen-all、CLI 预览、Web 预览均可选择 strict_fpa。
新增 tests/test_gen_fpa_strict_profile.py。
```

当前严格口径能力边界：

```text
本系统维护数据组通过三级模块名称、模块描述和功能过程描述中的维护/保存/新增/修改/删除/导入/配置等语义识别。
外部维护数据组通过统一用户中心、外部主数据、本系统不维护、外部维护等语义识别。
普通短信/支付/OCR 等外部服务调用不会自动生成 EIF。
更复杂的数据组识别后续可继续增强为规则表或 AI 辅助识别。
```

#### 第 4 步：CLI/Web 暴露可选项

状态：已完成。

目标：

```text
CLI 增加 --fpa-profile。
Web 高级选项增加 FPA 方案选择。
```

验收：

```text
正式生成和预览均可选择 profile。
界面默认 custom_rules。
```

已落地：

```text
CLI 已支持 --fpa-profile。
Web 高级选项新增 FPA 方案选择。
Web FPA 预览也显示同一 FPA 方案选择。
前端 config store 新增 fpaProfile，并持久化到 localStorage。
Web 正式运行 run-local / run-upload 会把 fpa_profile 传给 task_runner 和 pipeline。
Web 预览会把 fpa_profile 传给 /api/fpa/preview-module。
预览结果标题展示当前 profile 标签，方便人工确认口径。
```

#### 第 5 步：文档和样例

状态：已完成基础版。

目标：

```text
补充 custom_rules 和 strict_fpa 对比文档。
补充 Golden Case 输入样例。
补充用户选择建议。
```

已落地：

```text
新增 docs/fpa/fpa-profiles.md，面向用户说明 custom_rules / strict_fpa 的选择建议、使用方式和输出差异。
README.md 增加 FPA 方案章节和 --fpa-profile 参数说明。
docs/fpa/fpa-golden-cases.md 增加 strict_fpa 的典型期望输出形态。
```

### 风险与边界

主要风险：

```text
strict_fpa 需要识别 ILF/EIF 数据组，纯关键词可能不够，需要 AI 辅助。
现有 Excel 模板是否适合严格 FPA 的数据功能 + 事务功能混排，需要确认。
FPA 工作量汇总公式是否对严格 FPA 类型组合完全适配，需要验证。
用户可能混淆“报账模板口径”和“标准 FPA 口径”，需要 UI 和文档明确提示。
```

建议边界：

```text
profile 只决定 FPA 行规划和类型口径。
Excel 列结构暂不随 profile 改动。
汇总口径暂不随 profile 改动；第二阶段默认采用代码化业务计算规则，Excel/LibreOffice 复算只作为可选校验。
```

## FPA 汇总值一致性

状态：已完成基础版。

本轮已按第二阶段确认方向实现代码化汇总：

```text
calculate_fpa_row_workload(row)：按 调整值 × 要素数量 计算单行工作量。
calculate_fpa_total(rows)：汇总所有 FPA 行工作量。
write_fpa_summary_md(summary_md_path, total)：统一写入 1.2.gen-fpa-FPA工作量-总和.md。
```

生成 Excel 时继续保留模板原有公式逻辑：

```text
每行 L 列继续写入 FPA工作量公式，例如 =J3*K3。
第 1 行 L 列继续写入汇总公式，例如 =SUM(L3:L4)。
MD 汇总继续来自同一套 calculate_fpa_total(rows)。
pipeline result.fpa_reduced 读取 MD 汇总，因此默认流程不依赖 Excel 公式缓存。
```

边界：

```text
Excel 模板中的公式仍保留，不会被静态数值覆盖。
Excel COM / LibreOffice 复算未接入默认流程。
如果后续模板的真实业务公式不是 调整值 × 要素数量，应把该业务公式翻译为 Python 规则，而不是依赖 Excel 引擎。
```

## FPA MD 格式变化

新 FPA MD 表格列为 14 列：

```text
序号
子系统(模块)
资产标识
新增/修改功能点
类型
计算依据归类
计算依据说明
变更状态
调整值
要素数量
生成方式
类型理由
源功能过程
后处理警告
```

Excel 生成仍只写入模板需要的正式列，审计列不会写入最终 Excel。

当前不再兼容旧 10 列 FPA MD。

## Pipeline 流程变化

`_generate_fpa(...)` 当前流程：

```text
1. 检查 FPA 输出模板。
2. init_fpa_template_md(...) 生成三级模块兜底骨架 MD 和初始工作量汇总。
3. 有 API Key 时调用 plan_fpa_md_from_tree(...) 生成 AI 规划 MD，并更新工作量汇总。
4. 无 API Key 时直接使用兜底骨架 MD。
5. generate_fpa_xlsx_from_md(...) 生成 FPA Excel。
6. 从 1.2.gen-fpa-FPA工作量-总和.md 读取 FPA 工作量。
```

说明：

```text
无 API Key 时仍可生成 FPA Excel。
有 API Key 时不再复制模板 MD 后逐行填充，而是重新基于模块树整体规划。
```

## CLI 预览能力

新增参数：

```powershell
ard --from-excel 功能清单.xlsx --preview-fpa-module "垂直行业管理"
ard --from-excel 功能清单.xlsx --preview-fpa-module-index 1
ard --from-excel 功能清单.xlsx --preview-fpa-module "垂直行业管理" --preview-fpa-json
```

默认输出：

```text
三级模块
功能过程数
行列表：序号 / 类型 / 功能点名称 / 归类
Warnings
说明详情
```

JSON 输出用于自动化测试和排查。

## Web 预览能力

已新增 Web API：

```http
POST /api/fpa/preview-modules
POST /api/fpa/preview-module
```

请求使用 `multipart/form-data`，支持两种输入方式：

```text
本机模式：xlsx_path
远程模式：file
```

参数：

```text
POST /api/fpa/preview-modules:
  xlsx_path
  file

POST /api/fpa/preview-module:
  module_index
  api_key
  model
  base_url
  fpa_profile
```

行为：

```text
preview-modules 只解析功能清单，生成基础 MD，返回三级模块下拉列表。
preview-modules 不调用 AI，不生成 FPA Excel，不写正式交付物。
preview-module 只对选中的三级模块生成 FPA 行预览。
不创建任务 session。
不写运行历史。
不生成 FPA Excel。
远程上传文件只写入临时目录，预览结束后清理。
本机路径仅限本机访问。
API Key / model / base_url 为空时读取系统配置。
```

前端新增：

```text
web_app/src/components/PreviewLayout.vue
web_app/src/components/FpaPreview.vue
web_app/src/views/FpaPreviewPage.vue
```

入口位置：

```text
顶部导航 -> 预览 -> FPA
生成页任务设置 -> 打开 FPA 预览
路由：/preview/fpa
生产静态路径：/static/dist/preview/fpa
```

页面结构：

```text
PreviewLayout
  -> 顶部预览类型切换：FPA / COSMIC / SPEC
  -> 左侧输入设置：功能清单输入、高级选项、FPA 方案
  -> 右侧预览工具：生成基础数据、三级模块下拉框、生成预览、结果表格、warning、说明详情
```

FPA 预览交互：

```text
1. 用户先在左侧选择功能清单输入来源。
2. 点击“生成基础数据”。
3. 前端调用 /api/fpa/preview-modules。
4. 后端解析 Excel 并返回三级模块列表，每项包含 index、客户端类型、一二三级模块、功能过程数和 label。
5. 前端默认选中第 1 个三级模块。
6. 用户从下拉框选择三级模块。
7. 点击“生成预览”。
8. 前端调用 /api/fpa/preview-module，并传 module_index。
9. 后端只对选中的三级模块生成 FPA 行预览。
```

API Key 输入边界：

```text
API Key 输入框只使用灰色 placeholder 提示“留空使用系统配置”。
placeholder 或示例文本不能作为真实 api_key 提交。
前端统一通过 normalizeApiKeyInput() 清洗 API Key。
主生成、FPA 预览、Prompt Debug 均不会提交 sk-...、here、****here、your-api-key 等占位/示例值。
旧 localStorage 中残留的占位 API Key 会在页面加载时被清洗为空。
```

三级模块定位规则：

```text
前端主流程不再要求用户手填三级模块名称或序号。
下拉框使用 preview-modules 返回的 module_index 作为稳定定位方式。
module_name 仍可作为底层函数和 API 的调试能力存在，但界面不再作为主入口暴露。
这样可以避免名称重复、错别字、空格差异导致的定位错误。
```

设计边界：

```text
FPA 预览已从生成页折叠面板迁移为独立页面。
生成页只保留跳转入口，不再嵌入完整预览工具。
COSMIC / SPEC 预览暂未实现，但已在 PreviewLayout 中预留位置。
COSMIC 预览暂缓：gen-cosmic 逻辑后续可能重构，当前不新增 /preview/cosmic，避免把现有临时数据流固化到 UI/API/测试。
后续 gen-cosmic 重构完成、核心输入/输出模型稳定后，再评估 /preview/cosmic；如继续做 /preview/spec，也应复用同一套稳定的预览抽象。
```

生产部署路由边界：

```text
FastAPI 会把 Vite 构建产物挂载到 /static/dist。
因此直接打开 /static/dist/preview/fpa 时，不能让 StaticFiles 把 preview/fpa 当成真实文件路径。
服务端在挂载 /static/dist 之前声明 /static/dist、/static/dist/、/static/dist/login、/static/dist/config、
/static/dist/license、/static/dist/history、/static/dist/prompt-debug、/static/dist/preview/{path:path}，
统一返回 SPA index.html。
同时保留 /preview/{path:path} 顶层 history 路由，便于后续独立入口或反向代理直接访问。
不使用 /static/dist/{path:path} 全量通配，避免把 /static/dist/assets/... 静态资源误返回为 HTML。
```

本轮修复过的问题：

```text
现象：直接访问 http://127.0.0.1:9090/static/dist/preview/fpa 后，在页面输入三级模块序号 1，页面表现为空白。
根因：生产服务端没有为 /static/dist 下的前端 history 路由提供 SPA fallback，这些路径被静态文件挂载当作文件路径处理。
修复：新增 /static/dist 下的已知前端路由 fallback，并补充 /preview/{path:path} 顶层 fallback。
测试：tests/test_web_tasks.py 覆盖 /static/dist、/static/dist/、/static/dist/config、/static/dist/preview/fpa 等路径均返回 text/html 的 SPA 入口。
注意：修改 web_app/server.py 后，正在运行的 9090 服务需要重启才能加载新路由。
```

展示内容：

```text
三级模块名称
功能过程数
AI / 兜底 标记
FPA 行表格
warning 列表
说明详情
```

## AI 缓存

正式 `gen-fpa` 已启用三级模块 AI 规划缓存。

### 缓存作用

AI 缓存用于避免同一个三级模块在相同规则、相同输入和相同模型下重复调用 LLM。

主要收益：

```text
节省时间：大项目可能包含很多三级模块，缓存命中后可以跳过对应模块的 AI 调用。
节省费用：避免重复消耗 token。
稳定输出：同一输入复用同一份 AI 规划，减少模型随机性导致的拆分波动。
支持重跑：当只是重新生成 MD/Excel、调整模板写入或验证后处理时，不需要重新规划所有三级模块。
```

缓存不是为了绕过规则校验。它只复用 AI 的原始规划结果，最终 FPA 行仍由代码统一后处理。

缓存文件：

```text
md/fpa_ai_cache.json
```

缓存范围：

```text
只用于正式 gen-fpa。
预览模式默认不读写缓存。
无 API Key 时不读写缓存。
```

缓存内容：

```text
AI 返回的原始 rows JSON。
```

说明：

```text
缓存不保存后处理后的最终 FPA 行。
命中缓存后仍会重新执行类型校验、归类映射、界面合并和 warning 后处理。
这样后处理规则调整后，旧缓存仍能被新规则重新规范化。
```

### 缓存失效条件

缓存 key 会随以下内容变化而变化：

```text
FPA profile 名称发生变化。
FPA profile 版本发生变化。
FPA 核心规则发生变化。
领域上下文发生变化。
三级模块名称、描述或功能过程列表发生变化。
模板判定原则发生变化。
模型名称发生变化。
```

这些内容任一变化，都会产生新的缓存 key，正式 `gen-fpa` 会重新调用 AI。

当前 `base_url` 和 `api_key` 不参与缓存 key。原因是它们是调用通道和凭证，不直接代表模型能力或业务输入；如果同一 `model` 名称在不同服务商下实际能力不同，应通过更明确的 `model` 名称区分。

缓存 key 由以下内容计算：

```text
profile.name
profile.version
profile.core_rules
领域上下文 domain_context
三级模块 group
判定原则 judgement_rules
model
```

日志会显示：

```text
FPA AI 缓存命中 [...]
FPA AI 规划完成: ... 缓存命中 N 个 ...
```

## Golden Case

已新增 Golden Case 文档：

```text
docs/fpa/fpa-golden-cases.md
```

覆盖样例：

```text
垂直行业管理
数据导入模块
外部用户中心引用
普通外部服务调用
复杂多界面模块
```

用途：

```text
人工验收 AI 拆分粒度。
检查界面合并和多界面 split_reason。
检查 EI / ILF / EQ / EO / EIF 类型判断。
检查是否存在按钮、弹窗、数据库表、字段造行。
```

## 错误与 Warning 策略

AI 调用或解析失败时：

```text
不中断整体任务。
记录 warning。
该三级模块使用兜底 FPA 行。
```

常见 warning：

```text
AI 返回空响应。
AI 响应不是合法 JSON。
AI 响应缺少 rows 列表。
AI 行缺少 name。
AI 行缺少 explanation。
classification_basis_index 越界。
classification_basis 未匹配模板规则。
AI type 非法。
AI type 与关键词规则明显冲突。
多条界面开发行缺少 split_reason。
```

统计日志示例：

```text
FPA AI 规划完成: 尝试 N 个三级模块，成功 M 个，空响应 A 个，解析失败 B 个，
AI 生成 X 行，兜底生成 Y 行，配置跳过 Z 个三级模块，缓存命中 C 个，后处理 warning W 个
```

### strict_fpa 类型冲突规则收紧

本轮修复过的问题：

```text
现象：
添加垂直行业 AI type=EI 与关键词规则明显冲突，已使用 EQ 兜底。

原因：
旧版 strict_fpa infer_type() 把功能点名称和说明拼接后统一匹配。
说明中出现“列表”“查询结果”等辅助文字时，会先命中 EQ，再错误覆盖名称明确为“添加”的 AI EI 结果。

修复：
strict_fpa 事务动作改为优先检查功能点名称。
名称没有明确动作时，才参考说明文本。
has_obvious_conflict() 不再因为说明中的普通事务关键词覆盖合法 AI type。
普通外部服务调用误判 EIF、名称中的明确 EI/EQ/EO 动作冲突等确定性场景仍会自动纠正。
```

当前原则：

```text
strict_fpa 以 AI 规划为主。
关键词规则用于 AI 缺失、非法 type 和确定性冲突兜底。
关键词规则不是与 AI 并列的第二套主判断器。
说明中的辅助文字不能覆盖名称中的明确业务动作。
```

## 下一阶段设计决策：profile / strategy / rule_set

状态：第二阶段已推进 rule_set 外部规则文件、version 和 extends 继承；审核产物仍待后续推进。

### 核心抽象

后续 FPA 不再只用一个 `fpa_profile` 承载所有差异，而拆成三层：

```text
profile  = FPA 方法学 / 业务口径
strategy = AI 与 rules 的执行优先级
rule_set = 具体用户可配置规则集
```

三者职责：

```text
profile:
  回答“按什么口径生成 FPA？”
  例如 custom_rules、strict_fpa、后续其他组织口径。

strategy:
  回答“AI 和 rules 谁先判断？”
  例如 rules_first、ai_first、rules_only、ai_only。

rule_set:
  回答“使用哪一套具体规则？”
  例如 custom_rules_default、strict_fpa_default、strict_fpa_conservative、client_a_rules。
```

### profile 命名决策

`custom_rules` 后续改名为：

```text
custom_rules
```

原因：

```text
custom_rules 容易绑定“当前项目”，后续多项目、多客户时语义不稳。
custom_rules 更准确表达“用户自定义规则主导”的定位。
custom_rules 更适合作为 CLI、配置文件和 UI 中的 profile 名称。
```

由于系统尚未上线：

```text
不保留 custom_rules 兼容别名。
配置、CLI、Web UI、文档、测试统一改为 custom_rules。
```

### 默认组合

已确认默认组合：

```text
custom_rules = rules_first + custom_rules_default
strict_fpa   = ai_first    + strict_fpa_default
```

含义：

```text
custom_rules:
  用户自定义规则优先。
  规则能判断的，不交给 AI。
  规则无法判断时，再由 AI 兜底。

strict_fpa:
  AI 优先。
  AI 输出合法且覆盖充分时，以 AI 为主。
  AI 缺失、非法、不完整时，再由 rules 补漏。
```

### strategy 定义

```text
rules_first:
  先执行 rules。
  rules 能确定拆分和类型时直接采用。
  规则结果为空、名称为空、类型非法或未覆盖功能过程时，视为需要 AI 复核。
  有 API Key 时交给 AI 重新规划该三级模块。
  无 API Key、AI 调用失败或 AI 解析失败时，保留规则结果并记录 warning。

ai_first:
  先执行 AI。
  AI 输出合法且覆盖充分时采用 AI。
  AI 调用失败、返回非法、不完整或置信不足时，由 rules 补漏。
  rules 补漏必须标记来源，不伪装为 AI。

rules_only:
  完全不调用 AI。
  rules 判不了时提示无法判定。

ai_only:
  完全依赖 AI。
  AI 返回不完整或不确定时只 warning / error，不用 rules 补行。
```

### “无法判定”的定义

rules 无法判定：

```text
没有命中任何规则。
命中多个互斥规则。
缺少必要上下文，例如无法确认数据是否由外部系统维护。
规则返回 unknown。
规则要求人工确认。
```

AI 无法判定：

```text
API Key 缺失。
AI 调用失败。
AI 返回空响应。
AI 返回不是合法 JSON。
AI type 不属于 EI / EQ / EO / ILF / EIF。
rows 为空。
source_processes 覆盖不足。
说明明显缺失。
AI 返回 needs_review = true。
AI confidence 低于阈值。
```

后续建议让 AI 输出：

```json
{
  "rows": [
    {
      "name": "添加垂直行业",
      "type": "EI",
      "confidence": 0.86,
      "needs_review": false,
      "uncertainty": ""
    }
  ]
}
```

### strict_fpa 的确认边界

已确认：

```text
strict_fpa 默认 ai_first。
strict_fpa 无 AI 时默认不生成，只提示需要 API Key。
AI 不完整时，rules 补漏缺失行，并标记 generation=rules_fallback。
rules 不改 AI 已给出的合法 type；业务冲突只 warning。
只有 type 非法、JSON 非法、结构非法时才硬处理。
```

进一步解释：

```text
AI 合法输出默认保留。
rules 可以补缺失行。
rules 不应静默覆盖 AI 已给出的合法业务判断。
如果 AI 给出 EI，rules 认为 EQ，但 AI type 合法，应记录 warning，不直接改 type。
如果 AI 给出 UNKNOWN 或非法 type，rules 才能替换为合法类型。
```

### rule_set 设计

rule_set 独立于 profile，是为了支持同一口径下的多套组织规则。

示例：

```text
strict_fpa_default:
  标准严格 FPA 默认规则。

strict_fpa_conservative:
  更保守的严格 FPA 规则，只在明确“外部维护数据组”时判 EIF。

client_a_rules:
  客户 A 的规则偏好。

client_b_rules:
  客户 B 的规则偏好。
```

第一版 rule_set 支持状态：

```text
已完成：关键词规则，使用 keyword_rules 追加 EI / EQ / EO 事务类型规则。
已完成：外部数据源规则，使用 external_data_rules 追加 EIF 外部数据组规则。
已完成：ILF / EIF 判定规则第一版，使用 internal_data_rules 追加 ILF 内部数据组规则，EIF 继续使用 external_data_rules。
已完成：规则段继承策略，keyword_rules / internal_data_rules / external_data_rules 均支持 merge: append / replace。
待推进：功能过程覆盖检查规则。
```

后续可扩展：

```text
是否必须生成数据功能。
是否允许一个 FPA 行覆盖多个功能过程。
最少/最多行数提示。
配置重复规则检测。
别名冲突检测。
按单条规则 ID 删除或覆盖。
```

当前配置结构：

```yaml
rule_sets:
  client_a_rules:
    extends: strict_fpa_default
    keyword_rules:
      merge: append
      items:
        - type: EO
          keywords: ["打印供应商清单"]
    internal_data_rules:
      merge: replace
      items:
        - keywords: ["供应商准入关系"]
          data_name: "供应商准入关系"
    external_data_rules:
      merge: append
      items:
        - source_aliases: ["供应商平台"]
          data_name: "供应商平台供应商档案"
          data_nouns: ["供应商", "档案", "信息"]
```

### 审计字段

无论 AI 还是 rules，只要发生兜底、补漏、冲突、无法判定，都必须显式记录。

建议统一字段：

```text
generation:
  ai
  rules
  rules_fallback
  ai_fallback

fallback_reason:
  no_api_key
  ai_failed
  ai_invalid_json
  ai_invalid_type
  ai_incomplete
  rules_missed
  rules_conflict
  coverage_missing

profile
strategy
rule_set
source_processes
coverage_status
warnings
```

### AI 缓存 key

后续 AI 缓存必须包含：

```text
profile
strategy
rule_set
rule_set 配置内容
profile core rules
user prompt template
model
judgement_rules
domain_context
三级模块输入内容
```

原因：

```text
不同 strategy 或 rule_set 下，同一三级模块的 AI 结果语义不同。
如果缓存 key 不包含这些维度，可能复用旧口径结果。
```

### Web 与 CLI 暴露

Web 高级选项后续应显示：

```text
FPA profile:
  custom_rules
  strict_fpa

FPA strategy:
  rules_first
  ai_first
  rules_only
  ai_only

FPA rule_set:
  custom_rules_default
  strict_fpa_default
  ...
```

CLI 后续参数：

```powershell
ard --from-excel 功能清单.xlsx --gen-fpa --fpa-profile strict_fpa --fpa-strategy ai_first --fpa-rule-set strict_fpa_default
```

预览和正式生成必须使用同一套：

```text
profile
strategy
rule_set
```

否则预览不具备正式生成参考价值。

## FPA 审核工作簿与预览审核面板

状态：预览 audit JSON、预览页审核信息、正式审核副本第一版已实现。

### 目标

正式生成时额外生成一个审核副本 Excel，不替代正式交付 Excel。

建议文件名：

```text
FPA工作量评估-check.xlsx
```

用途：

```text
让用户检查 AI / rules 如何生成每一行。
让用户检查哪些功能过程已覆盖，哪些未覆盖。
让用户检查哪些行由 AI 生成，哪些由 rules 补漏。
让用户检查 warning、fallback_reason、rule_set、raw AI response。
```

### 统一数据结构

建议先抽象统一结构：

```text
FpaAuditReport
```

当前已实现字段：

```text
profile / profile_version
strategy
rule_set
module
coverage.process_total
coverage.covered_count
coverage.missing_count
coverage.covered_processes
coverage.missing_processes
generation_counts
warnings
```

当前预览页已展示：

```text
功能过程覆盖数。
未覆盖数。
规则集名称。
生成方式统计。
缺失功能过程列表。
```

正式生成已额外产出：

```text
FPA工作量评估-check.xlsx
```

当前审核副本包含：

```text
Sheet: FPA结果
  正式 FPA 行结果。
  额外包含 generation、type_reason、source_processes、warnings、profile、strategy、rule_set。

Sheet: 覆盖审核
  按三级模块展示功能过程覆盖情况。
  包含功能过程总数、已覆盖数、未覆盖数、已覆盖功能过程、未覆盖功能过程、生成方式统计和 warnings。

Sheet: Warnings
  汇总行级 warning 和模块级 warning。
  包含级别、FPA行序号、模块序号、对象、Warning、来源规则ID、来源说明。
  未覆盖功能过程会作为模块级 warning 写入。

Sheet: AI原始返回
  按三级模块展示 AI 原始 rows JSON。
  展示来源：ai、ai_cache、rules、rules_fallback。
  展示 AI 调用或解析异常，以及规则优先策略未调用 AI 的说明。

Sheet: 规则命中详情
  按 FPA 行展示规则/后处理命中来源。
  包含模块序号、功能点名称、生成方式、rule_set、命中对象、规则ID、规则说明、建议类型、是否采用和 warnings。
  当前生成时会把规则/后处理命中事件写入 audit trace，check.xlsx 优先使用生成期记录；缺少 trace 时才基于已落表字段兜底还原。
```

当前格式增强：

```text
五张 Sheet 均启用首行冻结和自动筛选。
首行表头加粗并使用浅蓝底色。
有 warning 的 FPA 行使用浅黄色底色。
rules_fallback 行使用浅橙色底色。
存在未覆盖功能过程的模块行使用浅橙色底色。
规则命中详情中有 warning 的行使用浅黄色底色，rules_fallback 行使用浅橙色底色。
```

同一个 `FpaAuditReport` 同时服务：

```text
正式生成：
  FpaAuditReport -> FPA工作量评估-check.xlsx

预览页面：
  FpaAuditReport -> /api/fpa/preview-module JSON -> 页面审核面板
```

这样可以保证：

```text
正式审核 Excel 和预览页面看到的是同一套口径。
不会出现预览说一套、正式文件写另一套。
```

### K4 落地：warning 来源细化

已完成：

```text
生成 FPA 行时同步记录规则/后处理命中事件。
AI type 校验、非法 type 兜底、AI 优先冲突保留、关键词冲突纠正、归类序号校验、名称规范化、说明兜底、rules_fallback 补齐等都会记录 rule_id / rule_desc / suggested_type / adopted / warnings。
正式生成会把这些事件写入 fpa_audit_trace.json。
FPA工作量评估-check.xlsx 的“规则命中详情”优先读取生成期 audit trace，不再只靠 generation、类型理由、源功能过程和 warnings 事后推断。
Warnings Sheet 新增“来源规则ID”“来源说明”两列，用于定位每条 warning 来自哪条规则或后处理。
缺少 audit trace 时仍保留旧的兜底还原逻辑，方便单独从 MD 生成审核副本。
```

### K5 落地：审核列可配置

已完成：

```text
system_config.yaml 新增 fpa_check_columns。
留空或不配置时，FPA工作量评估-check.xlsx 保持默认列不变。
支持按 Sheet 名称配置列名列表，既可隐藏列，也可调整列顺序。
当前支持 FPA结果、覆盖审核、Warnings、规则命中详情、AI原始返回 五张 Sheet。
未知列名会被忽略；某个 Sheet 配置后若没有任何有效列，会回退到默认列。
格式高亮改为按列名定位，不依赖固定列号，因此隐藏/调整列顺序后仍可保留 warning / rules_fallback / 未覆盖行高亮。
```

配置示例：

```yaml
fpa_check_columns:
  FPA结果: ["序号", "新增/修改功能点", "类型", "生成方式", "后处理警告"]
  Warnings: ["级别", "对象", "Warning", "来源规则ID"]
  规则命中详情: ["功能点名称", "规则ID", "规则说明", "建议类型", "是否采用", "Warnings"]
```

### 审核 Excel Sheet 草案

```text
Sheet: FPA结果
  正式 FPA 行结果。
  额外包含 generation、profile、strategy、rule_set、type_reason、source_processes、warnings。

Sheet: 三级模块列表
  module_index、客户端类型、一级模块、二级模块、三级模块、功能过程数、覆盖率、是否已覆盖。

Sheet: 功能过程覆盖
  module_index、功能过程名称、功能过程描述、被哪些 FPA 行覆盖、覆盖方式、是否未覆盖。

Sheet: AI原始返回
  module_index、module_path、model、profile、strategy、rule_set、raw_json、parse_status。

Sheet: 规则命中
  module_index、功能点名称、rule_set、rule_id、规则说明、建议类型、是否采用。

Sheet: Warnings
  严重级别、module_index、功能点名称、warning、fallback_reason、建议处理方式。
```

### 预览页面展示草案

FPA 预览页在现有结果表格下方增加审核 Tabs：

```text
结果
覆盖
规则
AI 原文
Warnings
```

各 Tab 内容：

```text
结果:
  功能点名称、类型、生成方式、类型理由、源功能过程、warning。

覆盖:
  功能过程、是否覆盖、覆盖它的 FPA 行、覆盖方式。

规则:
  rule_set、rule_id、命中对象、建议类型、规则说明、是否采用。

AI 原文:
  模型、profile、strategy、rule_set、raw_json、parse_status。

Warnings:
  严重级别、模块、功能点、问题、建议处理方式。
```

### 预览接口扩展草案

当前：

```json
{
  "module": {},
  "rows": [],
  "warnings": [],
  "used_ai": true,
  "profile": "strict_fpa"
}
```

后续：

```json
{
  "module": {},
  "rows": [],
  "warnings": [],
  "used_ai": true,
  "profile": "strict_fpa",
  "strategy": "ai_first",
  "rule_set": "strict_fpa_default",
  "audit": {
    "coverage": [],
    "rule_matches": [],
    "ai_raw": {},
    "warnings": []
  }
}
```

### 第二阶段落地状态

已完成 profile / strategy / rule_set 的第二阶段工程落地：

```text
current_project 已改名为 custom_rules。
不保留 current_project 兼容别名。
custom_rules 默认 rules_first + custom_rules_default。
strict_fpa 默认 ai_first + strict_fpa_default。
正式生成、预览、CLI、Web UI、配置文件都已透传 fpa_strategy / fpa_rule_set。
Web 高级选项和 FPA 预览页已支持配置驱动的 profile / strategy / rule_set 下拉选择。
strict_fpa 无 API Key 时会提示需要 API Key，不再静默使用规则生成。
ai_first 保留 AI 合法 type；与 rules 冲突时只记录 warning。
ai_first 在 AI 覆盖不完整时追加 rules_fallback 行。
ai_only 不使用 rules 补行，AI 失败或被配置限制跳过时直接报错。
rules_first 会先检查规则结果质量；规则结果为空、名称为空、类型非法或未覆盖功能过程时，有 API Key 则触发 AI 复核，无 API Key 则保留规则结果并记录 warning。
FPA AI 缓存 key 和 cache entry 已记录 profile、strategy、rule_set 及 rule_set 配置内容。
新增 fpa_config.yaml 统一配置文件。
rule_set 不再支持 version。
rule_set 支持 extends 继承，并检测循环继承；keyword_rules、internal_data_rules、external_data_rules 可按规则段配置 merge: append / replace。
rule_set keyword_rules 会参与 strict_fpa EI / EQ / EO 事务类型兜底。
rule_set internal_data_rules 会参与 strict_fpa ILF 数据组识别。
rule_set external_data_rules 会参与 strict_fpa EIF 数据组识别。
正式 FPA MD 头部写入 rule_set。
预览接口返回 rule_set。
```

本轮未实现，继续留在暂缓任务池：

```text
功能过程覆盖检查规则配置化。
预览页审核面板。
```

### 推荐实施顺序

```text
1. 先定义 FpaAuditReport 数据结构。
2. 让预览接口返回 audit。
3. 让预览页面展示 audit tabs。
4. 再把同一份 audit 写成 FPA工作量评估-check.xlsx。
5. 最后把正式生成下载包纳入 check.xlsx。
```

原因：

```text
预览反馈快，便于先验证用户能否看懂审核信息。
审核结构稳定后，再落 Excel 副本更稳。
```

## 测试覆盖

新增：

```text
tests/test_gen_fpa_ai.py
tests/test_gen_fpa_preview.py
tests/test_fpa_profiles.py
tests/test_fpa_external_data_rules.py
tests/test_gen_fpa_strict_profile.py
docs/fpa/fpa-golden-cases.md
```

更新：

```text
tests/test_gen_xlsx.py
tests/conftest.py
tests/test_web_tasks.py
```

覆盖点：

```text
Markdown code block JSON 可解析。
AI 合法 JSON 能映射归类和类型。
classification_basis_index 越界时不乱填。
多条界面开发行缺少 split_reason 时合并。
关键词类型兜底规则。
AI 返回非法 JSON 时记录 warning 并兜底。
按 module_index 预览成功。
可生成 FPA 预览用三级模块列表。
Web /api/fpa/preview-modules 可返回下拉框可用模块。
预览模式不生成 FPA Excel。
缺失三级模块时返回明确错误。
run_pipeline 的 gen-fpa / gen-all 仍能生成交付物。
Web FPA 预览接口可返回预览结果。
Web FPA 预览缺少模块目标时返回明确错误。
Web FPA 预览已迁移到独立 /preview/fpa 页面，生成页只保留入口。
Web FPA 预览已改为先生成基础数据，再下拉选择三级模块。
AI 缓存命中时不再调用 LLM。
缓存条目记录 profile.name 和 profile.version。
Golden Case 兜底拆分和类型规则不退化。
默认 custom_rules profile 可注册获取，未知 profile 会明确报错。
system_config.yaml 可读取 fpa_profile，默认 custom_rules。
正式生成和预览遇到未知 profile 时明确报错。
strict_fpa 不生成界面开发/接口开发/逻辑处理开发行。
strict_fpa 可区分 ILF、EIF、EI、EQ、EO 基础场景。
strict_fpa 可在同一三级模块中识别主数据 + 管理员关系等多个内部数据组。
strict_fpa 后处理会规范化 AI 输出中的“界面开发/接口开发/逻辑处理开发”名称。
strict_fpa 不把普通外部服务调用误判为 EIF。
strict_fpa 可识别 CRM、客户中心、财务核算系统等外部系统维护的数据组为 EIF。
strict_fpa 外部数据组识别已形成代码内规则表，覆盖统一用户中心、CRM、客户中心、财务核算系统、ERP、OA、主数据平台等来源。
strict_fpa 支持通过 fpa_config.yaml 的 rule_sets.<name>.keyword_rules / internal_data_rules / external_data_rules 扩展规则；每段规则可使用 merge: append / replace 控制追加或替换父规则段。
strict_fpa 外部数据组规则表有专门单元测试，覆盖已知来源正例和短信平台、支付网关、文件存储、地图服务、OCR 服务等普通外部服务反例。
strict_fpa 在外部数据引用场景下仍按事务动作识别选择/引用为 EI、查看/详情为 EQ。
strict_fpa AI 后处理可纠正普通外部服务调用误报 EIF，并保留名称本身明确表示外部数据组的 EIF 行。
strict_fpa 保留“添加垂直行业”合法 AI EI，不会因为说明中的列表/查询文字错误覆盖为 EQ。
Web 正式生成和 FPA 预览均可选择 custom_rules / strict_fpa。
README 和 FPA 方案说明文档已覆盖 profile 选择方式。
Golden Case 已新增固定 JSON fixture 集和自动差异报告测试。
```

已执行验证：

```powershell
.\scripts\test.ps1 tests/test_config_utils.py tests/test_fpa_profiles.py tests/test_fpa_external_data_rules.py tests/test_gen_fpa_golden_cases.py tests/test_fpa_golden_fixture_reports.py tests/test_gen_fpa_strict_profile.py tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py tests/test_web_tasks.py tests/test_gen_xlsx.py tests/test_pipeline.py
npm run build
```

结果：

```text
126 passed
前端构建通过
```

本轮针对“生成基础数据 + 下拉选择三级模块”已执行：

```powershell
.\scripts\test.ps1 tests/test_web_tasks.py tests/test_gen_fpa_preview.py
npm run build
```

结果：

```text
24 passed
前端构建通过
```

本轮针对 profile / strategy / rule_set 第一阶段已执行：

```powershell
.\scripts\test.ps1 tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py tests/test_fpa_profiles.py tests/test_config_utils.py tests/test_web_tasks.py
.\scripts\test.ps1 tests/test_pipeline.py -vv
npm run build
```

结果：

```text
76 passed
19 passed
前端构建通过
```

本轮针对 rule_set 外部配置第二阶段已执行：

```powershell
.\scripts\test.ps1 tests/test_fpa_profiles.py tests/test_config_utils.py tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py
```

结果：

```text
59 passed
```

本轮针对 rule_set 关键词和 ILF/EIF 配置化已执行：

```powershell
.\scripts\test.ps1 tests/test_fpa_profiles.py tests/test_config_utils.py tests/test_fpa_external_data_rules.py tests/test_gen_fpa_strict_profile.py -q
.\scripts\test.ps1 tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py tests/test_fpa_acceptance.py tests/test_fpa_golden_fixture_reports.py tests/test_pipeline.py::TestGenFpa -q
.\scripts\test.ps1 tests/test_config_utils.py tests/test_fpa_profiles.py tests/test_fpa_external_data_rules.py tests/test_gen_fpa_golden_cases.py tests/test_fpa_golden_fixture_reports.py tests/test_gen_fpa_strict_profile.py tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py tests/test_fpa_acceptance.py tests/test_web_tasks.py tests/test_gen_xlsx.py tests/test_pipeline.py -q
.\scripts\test.ps1 -q
```

结果：

```text
80 passed
57 passed
200 passed
346 passed, 2 skipped
```

本轮针对 rule_set 字段级覆盖策略已执行：

```powershell
.\scripts\test.ps1 tests/test_config_utils.py tests/test_fpa_profiles.py tests/test_fpa_external_data_rules.py tests/test_web_tasks.py -q
.\scripts\test.ps1 tests/test_config_utils.py tests/test_fpa_profiles.py tests/test_fpa_external_data_rules.py tests/test_gen_fpa_golden_cases.py tests/test_fpa_golden_fixture_reports.py tests/test_gen_fpa_strict_profile.py tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py tests/test_fpa_acceptance.py tests/test_web_tasks.py tests/test_gen_xlsx.py tests/test_pipeline.py -q
.\scripts\test.ps1 -q
```

结果：

```text
98 passed
203 passed
349 passed, 2 skipped
```

本轮针对 rules_first 低质量规则结果转 AI 已执行：

```powershell
.\scripts\test.ps1 tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py -q
.\scripts\test.ps1 tests/test_config_utils.py tests/test_fpa_profiles.py tests/test_fpa_external_data_rules.py tests/test_gen_fpa_golden_cases.py tests/test_fpa_golden_fixture_reports.py tests/test_gen_fpa_strict_profile.py tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py tests/test_fpa_acceptance.py tests/test_web_tasks.py tests/test_gen_xlsx.py tests/test_pipeline.py -q
.\scripts\test.ps1 -q
```

结果：

```text
29 passed
207 passed
353 passed, 2 skipped
```

本轮针对 FPA 审核副本已执行：

```powershell
.\scripts\test.ps1 tests/test_pipeline.py::TestGenFpa -vv
```

结果：

```text
5 passed
```

本轮针对 AI 原始返回审计已执行：

```powershell
.\scripts\test.ps1 tests/test_gen_fpa_ai.py tests/test_pipeline.py::TestGenFpa -vv
```

结果：

```text
17 passed
```

本轮针对规则命中详情 Sheet 已执行：

```powershell
.\scripts\test.ps1 tests/test_gen_fpa_ai.py tests/test_pipeline.py::TestGenFpa -vv
```

结果：

```text
17 passed
```

本轮针对 K4 warning 来源细化已执行：

```powershell
.\scripts\test.ps1 tests/test_gen_fpa_ai.py tests/test_pipeline.py::TestGenFpa -vv
```

结果：

```text
17 passed
```

本轮针对 K5 审核列配置已执行：

```powershell
.\scripts\test.ps1 tests/test_config_utils.py tests/test_gen_fpa_ai.py tests/test_pipeline.py::TestGenFpa -vv
```

结果：

```text
50 passed
```

本轮针对 F 组无真实 API 验收已补充自动化测试：

```text
tests/test_fpa_acceptance.py
```

覆盖内容：

```text
strict_fpa / rules_only 使用 vertical_industry_management golden case 正式生成 FPA MD、summary 和 FPA工作量评估-check.xlsx。
校验 check.xlsx 五张 Sheet 均生成。
校验覆盖审核中功能过程总数、已覆盖数、未覆盖数。
校验规则命中详情包含 strict_fpa.internal_data_group、strict_fpa.transaction.ei、strict_fpa.transaction.eq。
校验 AI原始返回 Sheet 在规则路径下记录 source=rules 和“规则优先策略未调用 AI”。
校验 summary 中 FPA 工作量汇总值为 13。
校验 custom_rules / rules_only 下，预览结果与正式生成 FPA MD 的行名称和类型完全一致。
使用 mock AI 返回 classification_basis_index 越界样例，校验 Warnings Sheet 可追溯到 postprocess.classification_basis_index，规则命中详情也记录对应 rule_id。
使用 mock AI 验证第二次正式生成命中 fpa_ai_cache，LLM 不再被调用，audit trace 和 check.xlsx 的 AI原始返回 Sheet 均标记 source=ai_cache。
```

已执行：

```powershell
.\scripts\test.ps1 tests/test_fpa_acceptance.py tests/test_fpa_golden_fixture_reports.py tests/test_gen_fpa_preview.py tests/test_gen_fpa_ai.py tests/test_pipeline.py::TestGenFpa -vv
```

结果：

```text
39 passed
```

当前 F 组状态：

```text
F2. 部分完成：无真实 API 的 mock / fixture / golden cases / 本地规则路径验收已自动化，覆盖 warning、缓存、预览和正式生成的关键审计结果；真实模型验收仍保留。
F3. 部分完成：代表样例的拆分粒度、类型判断、覆盖情况、预览/正式一致性和汇总值已自动化复核；真实业务输入复核仍保留。
```

本轮针对 F2 真实模型验收已尝试：

```text
已确认 API Key、base_url、model 配置存在，未在日志或文档中记录密钥。
选取 mixed_internal_external_data_functions、payment_gateway_refund、master_data_org_reference 作为代表样例。
受限沙箱内调用真实模型失败，LLM 返回连接错误；FPA 流程按设计回退 rules_fallback，并在 warning 中记录 AI 调用或解析失败。
因为本次输出来自 rules_fallback，不能作为真实模型说明质量、warning 质量或缓存行为的验收结论。
申请沙箱外网络调用被策略拒绝，原因是会向外部 LLM 端点发送仓库 fixture / 业务样例数据。
结论：F2 真实模型验收当前受环境/数据外发策略阻塞；需在明确允许外发样例数据的环境、脱敏样例集或本地/内网模型端点下重新执行。
```

本轮继续推进 F2 真实模型验收：

```text
用户明确允许将 FPA 验收样例发送到已配置 LLM API 后，执行 scripts/run_fpa_real_model_validation.py。
模型端点：api.deepseek.com。
模型：deepseek-v4-flash[1m]。
代表样例：
- mixed_internal_external_data_functions
- payment_gateway_refund
- master_data_org_reference

结果：
- 三例均完成真实模型正式生成，FPA 行来源均为 ai。
- 三例均生成 check.xlsx 五张 Sheet：FPA结果、覆盖审核、Warnings、规则命中详情、AI原始返回。
- 复跑同一输出目录后，AI原始返回 Sheet 来源均为 ai_cache，缓存链路可用。
- warning 来源可追溯：mixed_internal_external_data_functions 命中 postprocess.ai_first_type_conflict；master_data_org_reference 命中 postprocess.ai_first_type_conflict 和 coverage.missing_process；payment_gateway_refund 无 warning。
- 规则命中详情记录 postprocess.ai_type_validation / postprocess.ai_first_type_conflict，是否采用字段能区分 AI 优先保留与校验通过。
- 汇总值：mixed_internal_external_data_functions 为 10.0 人/天，payment_gateway_refund 为 4.0 人/天，master_data_org_reference 为 3.0 人/天。

观察：
- 真实模型输出与 strict_fpa golden 规则结果在名称精确匹配上不完全一致，例如 OA流程单据 / OA审批流程单据、规则命名后缀与 AI 自然命名不同；这属于真实模型说明/命名质量验收发现，不影响五张 Sheet、warning 来源、规则命中详情、缓存和汇总链路可用性。
- payment_gateway_refund 类型判断稳定，输出 ILF + EI + EQ，未把支付网关错误拆成 EIF。
- mixed_internal_external_data_functions 能拆出本系统 ILF、外部 EIF、EI、EQ；master_data_org_reference 能拆出选择事务 EI 和组织主数据 EIF。
```

本轮继续推进 F3 真实业务输入复核：

```text
新增脚本：
- scripts/run_fpa_real_business_validation.py

输入：
- 1111/md/0.1.gen-basedata-功能清单-模块树.md
- 1111/md/0.2.gen-basedata-录入文档元数据-模板.md

输入规模：
- 功能过程：56
- 三级模块：19

rules_only 结果：
- FPA 行数：65
- 类型分布：EI 31、EO 6、EQ 19、ILF 9
- 覆盖缺口：0
- warning：0
- 汇总值：96.0 人/天
- AI原始返回 Sheet 来源：rules

ai_first 真实模型结果：
- 模型端点：api.deepseek.com
- 模型：deepseek-v4-flash[1m]
- FPA 行数：69
- 类型分布：EI 29、EO 6、EQ 21、ILF 13
- 覆盖缺口：0
- warning：40，均来自 postprocess.ai_first_type_conflict
- 汇总值：98.0 人/天
- AI原始返回 Sheet 来源：ai

验收观察：
- 真实业务输入下，当前 strict_fpa 规则路径和真实模型路径均能覆盖全部原始功能过程。
- 真实模型倾向于额外拆出数据组，因此 ILF 数量高于规则路径，汇总值从 96.0 上升到 98.0。
- 真实模型对查询/导出类功能能区分 EQ / EO，未出现覆盖缺口。
- AI 优先策略保留有效 AI type；与规则建议不一致时进入 postprocess.ai_first_type_conflict，便于人工审核。

本轮发现并修复：
- check.xlsx 覆盖审核原先会用三级模块名的子串匹配归属 FPA 行；当“垂直行业管理”既是一级/二级模块又是三级模块名时，会误吞后续“合伙商管理”等模块的 AI 行。已改为优先按源功能过程精确归属，再用完整模块路径兜底。
- Warnings Sheet 原先会把覆盖审核汇总里的行级 postprocess warning 重复标成 coverage.missing_process。已改为只有真实未覆盖功能过程才输出 coverage.missing_process。

已补测试：
- test_fpa_audit_grouping_prefers_source_process_over_l3_substring
- 扩展 test_fpa_acceptance_mock_ai_warning_source_reaches_check_workbook，确保已覆盖模块不会把 postprocess warning 误标为 coverage.missing_process。
```

本轮针对 A1-A3 Golden Case 已补充：

```text
tests/fixtures/fpa_golden_cases/oa_approval_reference.json
tests/fixtures/fpa_golden_cases/master_data_org_reference.json
tests/fixtures/fpa_golden_cases/payment_gateway_refund.json
```

覆盖内容：

```text
A1. OA 审批流程引用：OA流程单据 EIF、关联审批单 EI、查看审批进度 EQ。
A2. 主数据平台组织引用：组织主数据 EIF、选择归属组织 EI。
A3. 支付网关退款反例：支付网关普通外部服务不生成 EIF、发起退款 EI、查看退款结果 EQ。
```

同步修复：

```text
strict_fpa 外部数据组识别增加否定句保护，例如“不作为外部维护数据组”不会误判 EIF。
主数据平台组织/机构场景优先命名为“组织主数据”，再回退通用“外部主数据”。
```

已执行：

```powershell
.\scripts\test.ps1 tests/test_fpa_golden_fixture_reports.py tests/test_fpa_external_data_rules.py tests/test_fpa_acceptance.py tests/test_gen_fpa_strict_profile.py -vv
```

结果：

```text
43 passed
```

本轮针对 A4-A5 Golden Case 已补充：

```text
tests/fixtures/fpa_golden_cases/internal_vs_external_org_reference.json
tests/fixtures/fpa_golden_cases/mixed_internal_external_data_functions.json
```

覆盖内容：

```text
A4. 内部组织维护 ILF 与外部组织引用 EIF 对照：本系统维护内部组织信息按 ILF，引用主数据平台组织主数据按 EIF。
A5. 同一三级模块同时包含多个数据功能：CRM客户档案 EIF、OA流程单据 EIF、供应商准入协同信息 ILF，并保留对应 EI / EQ 事务功能。
```

同步修复：

```text
strict_fpa 数据功能识别支持同一三级模块同时输出多个 EIF，并可与明确“本系统维护”的 ILF 并存。
收紧内部数据功能触发条件，避免把“CRM 系统维护”“ERP 系统维护”“OA 系统维护”等外部系统维护误识别为本系统 ILF。
主数据平台命中“组织主数据”时不再同时输出通用“外部主数据”。
```

已执行：

```powershell
.\scripts\test.ps1 tests/test_fpa_golden_fixture_reports.py tests/test_fpa_external_data_rules.py tests/test_fpa_acceptance.py tests/test_gen_fpa_strict_profile.py -vv
```

结果：

```text
47 passed
```

本轮针对 A6 文件级验收已补充：

```text
tests/test_fpa_acceptance.py::test_fpa_acceptance_real_excel_to_md_to_formal_check_workbook
```

覆盖内容：

```text
使用 mixed_internal_external_data_functions 代表场景动态创建最小真实 Excel。
通过 generate_md_files() 从 Excel 生成模块树 MD 和元数据 MD。
使用生成出的 MD 走 strict_fpa / rules_only 正式 FPA 规划。
生成 summary 和 FPA工作量评估-check.xlsx。
校验正式 FPA 行与 JSON golden strict_fpa 预期一致。
校验 FPA 工作量汇总值为 10。
校验 check.xlsx 五张 Sheet、覆盖审核、规则命中详情均符合预期。
```

已执行：

```powershell
.\scripts\test.ps1 tests/test_fpa_acceptance.py tests/test_fpa_golden_fixture_reports.py tests/test_fpa_external_data_rules.py tests/test_gen_fpa_preview.py tests/test_gen_fpa_ai.py tests/test_pipeline.py::TestGenFpa -vv
```

结果：

```text
64 passed
```

## 暂缓推进任务池

以下事项已确认暂不推进。后续如需继续，可按本节末尾的指令模板恢复。

### A. 真实项目 Golden Case

```text
A1. 已完成：增加 OA 审批流程引用样例：OA流程单据 EIF、关联审批单 EI、查看审批进度 EQ。
A2. 已完成：增加主数据平台组织引用样例：组织主数据 EIF、选择归属组织 EI。
A3. 已完成：增加支付网关退款反例：普通支付服务不生成 EIF、发起退款 EI、查看退款结果 EQ。
A4. 已完成：增加内部组织维护 ILF 与外部组织引用 EIF 的对照样例。
A5. 已完成：增加一个三级模块同时包含多个 ILF / EIF 的复杂样例。
A6. 已完成：在 JSON fixture 之外，补充真实 Excel / MD 验收样例。
```

### B. strict_fpa 数据组识别

```text
B1. 已完成：增强多个外部数据组同时出现时的识别。
B2. 已完成：增强外部数据引用与本系统关联数据同时出现时的识别。
B3. 已完成：增强名称模糊、描述明确场景的识别。
B4. 已完成：明确外部同步后由本系统继续维护的数据应判 ILF 还是 EIF。
B5. 已完成：评估 AI 辅助识别复杂数据组，并保留代码校验和 warning。
```

实现记录：

```text
strict_fpa 外部数据组识别支持同一三级模块中多个非内置外部来源同时出现时提取多条泛化 EIF，例如企业信用记录、合同档案。
strict_fpa 已覆盖同一三级模块中 CRM 客户档案、ERP 业务单据、组织主数据等多个外部数据组并存时输出多条 EIF。
strict_fpa 在外部数据引用与本系统保存关联关系、匹配关系、映射关系、绑定关系并存时，会额外识别本系统关联数据组 ILF，例如客户订单匹配关系。
strict_fpa 在功能过程名称较模糊、但描述明确说明外部维护数据组时，会优先从描述提取 EIF 名称，例如企业信用记录、合同档案。
strict_fpa 在功能过程名称较模糊、但描述明确说明本系统保存关系数据时，会优先从描述提取 ILF 名称，例如客户活动匹配关系。
strict_fpa 明确外部同步后的数据边界：仅引用外部维护数据时按 EIF；同步进入本系统后继续维护本地字段时按本系统 ILF，例如组织本地档案，并且不为同一数据组重复生成 EIF。
外部同步动作本身按进入系统边界的事务功能 EI 计量。
strict_fpa 默认 ai_first 下允许 AI 辅助识别复杂 ILF / EIF；当 AI 返回合法数据功能、但当前代码规则无法确认该数据组边界时，保留 AI type 并记录“AI 数据功能需人工复核” warning。
该 warning 会写入行级后处理警告和 audit trace，来源规则 ID 为 postprocess.ai_data_group_review，可进入预览 audit 和正式 FPA工作量评估-check.xlsx 的审核链路。
已知外部数据规则可确认的 EIF 不增加人工复核 warning；普通外部服务 EIF 仍沿用既有类型冲突 warning，避免重复提示。
普通外部服务反例保持不变，短信平台、支付网关、文件存储、地图服务、OCR 服务等仍不会被误判为 EIF。
```

已执行：

```powershell
.\scripts\test.ps1 tests/test_gen_fpa_strict_profile.py tests/test_fpa_external_data_rules.py tests/test_fpa_golden_fixture_reports.py -vv
```

结果：

```text
51 passed
```

### C. 类型冲突规则

```text
C1. 已完成：细化 EI / EQ / EO / ILF / EIF 关键词优先级。
C2. 已完成：建立类型冲突矩阵。
C3. 已完成：增加可配置类型映射表。
C4. 已完成：增加可配置 AI 类型冲突规则表。
C5. 已完成：对比不同类型策略下的 Excel 公式结果。
```

实现记录：

```text
strict_fpa 事务关键词优先级已细化：
1. rule_set.keyword_rules 仍然最高优先级。
2. 导出、报表、下载、生成文件等派生/格式化输出优先按 EO。
3. 如果功能名称以查询/查看/详情/检索/列表开头，按 EQ，避免“查看导入结果”被导入关键词误判为 EI。
4. 导入、同步、发起、写入、保存、提交、新增、修改、删除等进入或改变系统边界的数据事务优先按 EI，避免“导入并查看”“同步并查看”“发起退款并查询结果”被查询词误判为 EQ。
5. 普通服务调用仍不能直接判 EIF；例如调用支付网关查询支付状态按 EQ。

strict_fpa 已建立类型冲突矩阵：
1. 先从高置信规则推导 expected_type：开发工作项、普通外部服务误判 EIF、名称明确动作、已知外部数据组、内部数据规则、本系统数据组、说明中的高置信事务动作。
2. expected_type 与 AI type 在 EI / EQ / EO / ILF / EIF 之间不一致时，进入类型冲突 warning。
3. 事务功能与数据功能互错会被识别：例如保存客户配置被标为 EQ、查询详情被标为 EI、客户档案被标为 EI、统一用户中心账号被标为 EQ。
4. 说明中仅出现“引用/选择/关联”等低置信 EI 动作时，不强行覆盖 AI 的复杂 ILF / EIF 复核路径，避免把“外部维护、本系统只引用”的复杂数据组误转成普通类型冲突。
5. 外部系统维护或提供的数据不会因为“维护”关键词被误识别为本系统 ILF，除非文本同时明确本系统维护本地数据功能。

strict_fpa 已支持 type_mapping_rules 通用类型映射表：
1. 配置路径为 rule_sets.<name>.type_mapping_rules，结构与 keyword_rules / internal_data_rules / external_data_rules 一致，支持 merge: append / replace。
2. 单条规则包含 type、keywords、reason；type 允许 EI / EQ / EO / ILF / EIF。
3. type_mapping_rules 优先于内置事务关键词，可用于少量已确认项目特例，例如“本地报表快照”虽然包含“报表”，但可配置为 ILF。
4. type_mapping_rules 会参与 strict_fpa.infer_type 和类型冲突矩阵；AI type 与映射结果不一致时保留 AI type 并记录冲突 warning。
5. keyword_rules 仍限定为 EI / EQ / EO 事务功能关键词；需要直接映射到 ILF / EIF 时使用 type_mapping_rules。

strict_fpa 已支持 ai_type_conflict_rules：
1. 配置路径为 rule_sets.<name>.ai_type_conflict_rules，结构与其他规则段一致，支持 merge: append / replace。
2. 单条规则包含 expected_type、ai_type、keywords、conflict、reason；expected_type 和 ai_type 均允许 EI / EQ / EO / ILF / EIF。
3. 规则在 C2 类型冲突矩阵前生效，按 expected_type + ai_type + keywords 命中后返回 conflict。
4. conflict: false 可压制已确认可接受的 AI 类型差异，例如规则认为“本地报表快照”为 ILF、AI 返回 EO 时不提示冲突。
5. conflict: true 可强制人工复核项目级特例，即使矩阵原本不会提示冲突。
6. ai_first / ai_only 策略仍保留合法 AI type；该规则只影响是否记录类型冲突 warning。

C5 已增加确定性 Excel 公式投影校验：
1. 新增 calculate_fpa_excel_formula_projection(xlsx_path)，不依赖 Excel / LibreOffice 复算引擎。
2. 校验正式 FPA Excel 的 L1 汇总公式必须为 =SUM(L3:L末行)，每行 L 列必须为 =J行*K行。
3. 使用 J 列调整值和 K 列要素数量投影计算 Excel 公式应得总工作量。
4. vertical_industry_management golden case 下，custom_rules / rules_only 的 MD 汇总和 Excel 投影均为 8；strict_fpa / rules_only 的 MD 汇总和 Excel 投影均为 13。
5. 该校验补充已有可选 fpa_excel_recalc_check：默认路径仍不依赖外部 Excel 公式缓存，可选复算只作为环境具备时的额外 warning 校验。
```

已执行：

```powershell
.\scripts\test.ps1 tests/test_fpa_acceptance.py::test_fpa_acceptance_formula_projection_matches_summary_across_type_strategies tests/test_gen_xlsx.py::TestFpaTotalCalculation -vv
```

结果：

```text
8 passed
```

### D. 配置校验

```text
D1. 已完成：为 fpa_config.yaml 增加统一结构校验入口。
D2. 已完成：校验 profile / profiles / prompt_sets / rule_sets 的必填项和引用关系。
D3. 已完成：校验 rule_set extends 不存在和循环继承，并给出明确错误。
D4. 已完成：校验 external_data_rules 的 source_aliases / data_name / data_nouns 结构。
D4a. 已完成：校验 keyword_rules 的 type / keywords / reason 结构。
D4b. 已完成：校验 internal_data_rules 的 keywords / data_name / reason 结构。
D4c. 已完成：校验三类规则段必须使用 merge / items 对象结构，merge 只允许 append / replace。
D4d. 已完成：校验 type_mapping_rules 的 type / keywords / reason 结构。
D4e. 已完成：校验 ai_type_conflict_rules 的 expected_type / ai_type / keywords / conflict / reason 结构。
D5. 已完成：出现已废弃字段 version 时提示用户删除，不再把它当作规则集版本。
D6. 已完成：普通外部服务被配置为数据组时记录 warning。
```

实现记录：

```text
config_utils.py 新增 validate_fpa_config()，load_fpa_config() 读取后立即校验。
结构错误统一抛 FpaConfigError，并尽量包含配置文件名和键路径。
测试覆盖 profile 引用、rule_set 引用、prompt_set 空值、extends 不存在、extends 循环、废弃 version、三类规则段旧列表结构、非法 merge、external_data_rules / keyword_rules / internal_data_rules 非法结构。
普通外部服务误配为 external_data_rules 时不抛 FpaConfigError；resolve_fpa_rule_set_config() 会在 FpaRuleSetConfig.config_warnings 中记录 warning。
当前覆盖短信平台、支付网关、OCR、文件存储、对象存储、地图服务等普通外部服务别名。
预览 preview_fpa_module 返回的 warnings / audit.warnings 会包含该配置 warning。
正式生成 audit trace 的模块 warnings 会包含该配置 warning，FPA工作量评估-check.xlsx 的覆盖审核、Warnings、AI原始返回 Sheet 均可见。
Warnings Sheet 中来源规则ID 为 config.external_data_rules.external_service。
```

### E. 领域上下文

```text
E1. 已完成：为项目保存 domain_context.json。
E2. 已完成：显式记录系统边界、本系统维护数据组、外部引用数据组、普通外部服务。
E3. 已完成：将领域上下文稳定传入 FPA prompt。
```

实现记录：

```text
E1/E2 已增加项目级 FPA 领域上下文文件：
1. 默认配置初始化会复制 config/domain_context.json.example 为配置目录/domain_context.json，不覆盖已有文件。
2. domain_context.json 固定记录 system_boundary、internal_data_groups、external_data_groups、external_services。
3. 数据组和普通外部服务使用对象列表；对象必须包含 name，可选 aliases 和 description。
4. external_data_groups 额外要求 source，用于明确外部引用数据组由哪个外部系统维护。
5. 新增 load_fpa_domain_context() 严格加载入口；缺文件、JSON 解析失败或结构错误均抛出明确的 FpaConfigError。
6. load_optional_fpa_domain_context() 在文件缺失时返回空对象，已有配置目录仍可使用元数据上下文继续生成；文件存在但 JSON 或结构非法时仍明确失败。
7. _build_domain_context(meta) 会将项目级 domain_context.json 合并到已有元数据上下文，统一传入正式生成和预览 prompt。
8. AI cache key 已包含合并后的 domain_context；领域边界发生变化时会自动失效旧缓存。
```

### F. 验收

```text
F1. 已完成：补充 strict_fpa 人工验收记录。
F2. 已使用真实模型跑代表性样例，检查说明质量、warning、缓存和正式生成结果；预览链路无真实 AI 调用，已由 mock / fixture / rules 路径覆盖。
F3. 已使用真实业务输入复核拆分粒度、类型判断、覆盖和汇总值。
```

F1 记录文件：

```text
docs/fpa/strict-fpa-acceptance-record.md
```

### H. 旧兼容逻辑清理

```text
H6 已完成：
- 复核配置初始化和迁移逻辑后，确认全局 CLI 初始化、exe 首次运行自动初始化、Web 用户目录初始化都应使用同一份默认配置模板清单。
- 新增 copy_default_config_files(...) 和 DEFAULT_CONFIG_TEMPLATE_FILES，统一维护 .env、system_config.yaml、fpa_config.yaml 的初始化来源。
- CLI --init-config、exe _auto_init_config、auth.init_user_dir 均改为复用该统一逻辑。
- 修复 Web 用户目录初始化漏复制 FPA 配置的问题；当前初始化 fpa_config.yaml。
- migrate_config 仍保留“只追加 example 中新增顶层键，不覆盖用户配置”的当前行为；未发现 FPA 主线需要删除的旧兼容迁移分支。

已补测试：
- test_copy_default_config_files_copies_all_templates_without_overwrite
- test_init_user_dir_copies_all_default_config_files
```

### G. 可选增强

```text
G1. 已完成：增加 Excel COM / LibreOffice 复算校验，只做 warning。
G2. 已完成：预览模式增加 --use-preview-cache / --keep-preview-files。
G3. 已完成：预览模式增加纯内存解析，减少临时 MD 文件。
G4. 已完成：已确认模板真实公式仍为 调整值 × 要素数量，无需翻译额外业务公式，已补模板公式守护测试。
```

G1 实现记录：

```text
新增配置：
- system_config.yaml: fpa_excel_recalc_check，默认 false。

行为：
- 默认不执行复算校验，避免无 Excel / LibreOffice 的服务器和 CI 环境产生噪声。
- 开启后，pipeline 在生成 FPA工作量评估.xlsx 并读取 MD 汇总值后，调用 validate_fpa_excel_recalculation(...)。
- 校验依次尝试 Excel COM、LibreOffice/soffice。
- 复算成功后读取 FPA功能点估算 Sheet 的 L1 缓存总工作量，与代码汇总值比较。
- 引擎不可用、复算失败、缓存不可读或结果不一致均只记录 warning，不阻断生成。

已补测试：
- load_fpa_excel_recalc_check 默认 false。
- validate_fpa_excel_recalculation 复算成功且缓存值一致时无 warning。
- 缓存值与代码汇总不一致时返回 warning。
- Excel COM / LibreOffice 均不可用时返回 warning。
```

G2 实现记录：

```text
新增 CLI 参数：
- --use-preview-cache：FPA 预览复用已有 fpa-preview-md，缓存齐备时不重新解析 Excel。
- --keep-preview-files：保留 FPA 预览生成的中间 MD 文件，便于调试。

目录行为：
- 默认行为不变：未传 work_dir 且未开启 keep 时使用临时目录，预览结束后清理。
- 传入 work_dir 或 CLI --output-dir 时使用 <work_dir>/fpa-preview-md。
- 未传 work_dir 且开启 keep 时使用输入 Excel 同目录下的 .fpa-preview/fpa-preview-md。
- preview_fpa_module / preview_fpa_modules 返回 preview_md_dir 和 preview_cache_used，CLI 在开启 keep/cache 时打印对应状态。

已补测试：
- test_preview_fpa_module_can_use_cached_preview_md
- test_preview_fpa_module_keep_preview_files_without_work_dir
```

G3 实现记录：

```text
新增内存解析入口：
- excel_source.read_base_data_from_excel(...)

行为：
- preview_fpa_module / preview_fpa_modules 默认直接从 Excel 读取模块树和元数据内存结构，不写 fpa-preview-md。
- 只有传入 work_dir、CLI --output-dir、--keep-preview-files 或 --use-preview-cache 时，才走文件型 fpa-preview-md 路径。
- generate_md_files(...) 复用同一套 read_base_data_from_excel(...)，避免内存解析和文件生成逻辑分叉。
- preview 返回 preview_md_dir="" 表示本次为纯内存解析；preview_cache_used=false。

已补测试：
- test_preview_fpa_module_uses_memory_parse_by_default
- test_preview_fpa_modules_uses_memory_parse_by_default
```

G4 实现记录：

```text
复核模板：
- data/out_templates/FPA工作量评估-输出模板.xlsx
- tests/fixtures/output_templates/FPA工作量评估-输出模板.xlsx

结论：
- FPA功能点估算 Sheet 中 L3 公式为 =J3*K3。
- L1 汇总公式为 =SUM(L3:...)。
- 当前 Python calculate_fpa_row_workload(row) = 调整值 × 要素数量 与模板真实工作量公式一致。
- 当前无需把额外业务公式翻译为 Python 规则。

已补测试：
- test_fpa_template_workload_formula_matches_python_total_rule
```

### 后续恢复指令

继续全部任务：

```text
按照 docs/fpa/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，从 A1 开始按顺序继续推进。每完成一项更新文档并跑相关测试。
```

推进指定分组：

```text
按照 docs/fpa/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，推进 B 组 strict_fpa 数据组识别。每完成一项更新文档并跑相关测试。
```

推进指定事项：

```text
按照 docs/fpa/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，只推进 D6：普通外部服务被配置为数据组时记录 warning。完成后更新文档并跑相关测试。
```

需要我先重新评估优先级时：

```text
读取 docs/fpa/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，结合当前代码状态重新排序，先给出推荐，不修改代码。
```

已落地固定 Golden Case fixture 集：

```text
tests/fixtures/fpa_golden_cases/vertical_industry_management.json
tests/fixtures/fpa_golden_cases/customer_list_import.json
tests/fixtures/fpa_golden_cases/external_user_center_reference.json
tests/fixtures/fpa_golden_cases/crm_customer_archive_reference.json
tests/fixtures/fpa_golden_cases/erp_order_reference.json
tests/fixtures/fpa_golden_cases/sms_notification_service.json
tests/test_fpa_golden_fixture_reports.py
```
