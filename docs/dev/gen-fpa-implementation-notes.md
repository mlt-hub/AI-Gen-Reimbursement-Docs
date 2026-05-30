# gen-fpa 三级模块规划改造实施记录

日期：2026-05-29

## 背景

本次修改基于 `docs/dev/gen-fpa-improvement-plan.md` 推进第一阶段改造。由于系统尚未上线，本次实现不保留旧版兼容路径，`gen-fpa` 后续只采用“三级模块整体规划 FPA 行”的新流程。

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
| 系统提示词 | `~/.ai-gen-reimbursement-docs/ai_system_prompts_config.yaml` 中的 `ai_prompts.fpa_eval.system` | 配置文件 |
| 用户提示词 | `gen_fpa.py` 的 `_build_fpa_planning_prompt()` 动态拼接 | 代码 |
| FPA 核心规则 | `gen_fpa.py` 顶部的 `FPA_CORE_RULES` | 代码 |
| 领域上下文 | `gen_fpa.py` 的 `_build_domain_context(meta)` 从元数据 MD 提取 | 代码 + Excel/MD 数据 |
| 功能过程上下文 | `parse_module_tree_md()` 读取模块树 MD 后按三级模块聚合 | Excel -> MD -> 代码 |
| 计算依据归类判定原则 | FPA 输出模板 Excel 的附录 Sheet | Excel 模板 |
| 类型兜底规则 | `gen_fpa.py` 的 `_infer_fpa_type()` | 代码 |
| AI 失败兜底拆分规则 | `gen_fpa.py` 的 `_fallback_fpa_rows_for_l3()` | 代码 |
| 多界面合并规则 | `gen_fpa.py` 的 `_normalize_ai_fpa_rows_for_l3()` | 代码 |

### 系统提示词

读取方式：

```python
load_ai_system_prompt("fpa_eval")
```

配置文件：

```text
~/.ai-gen-reimbursement-docs/ai_system_prompts_config.yaml
```

如果配置文件中没有 `fpa_eval.system`，代码会使用内置默认系统提示词。

### 用户提示词

用户提示词不是独立配置文件，而是在 `_build_fpa_planning_prompt()` 中动态生成。

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

当前领域上下文来自元数据 MD，主要字段包括：

```text
子系统（模块）
资产标识
新增/修改功能点前缀生成规则
功能用户-接收者判定
```

这些字段由功能清单 Excel 的元数据 Sheet 生成到 MD 后，再由代码读取。

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

目前系统只把“系统提示词”放在配置文件中，其他关键口径仍在代码中。

这样做的好处：

```text
兜底行为稳定。
AI 不听 prompt 或返回异常时，代码仍能保证基本输出。
测试可以覆盖真实后处理规则。
```

代价：

```text
如果要维护多套 FPA 方案，不能只改系统提示词。
FPA_CORE_RULES、用户提示词、类型兜底、失败兜底和 Golden Case 都需要跟着切换。
```

后续如要支持多套方案，建议抽象为 profile：

```text
current_project
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
  current_project
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
current_project
strict_fpa
```

`current_project`：

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
如果只需要报账模板口径，就继续完善 current_project。
如果需要严格 FPA，就新增 strict_fpa，不要在 current_project 上硬改到半严格状态。
```

### 不要把 current_project 改成半严格状态

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

因此，`current_project` 和 `strict_fpa` 应保持清晰边界。

`current_project` 的边界：

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
而是不要把严格 FPA 的规则一点点混进 current_project。
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
current_project：当前报账模板口径。
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
CurrentProjectProfile
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
current_project 和 strict_fpa 的差异主要集中在 core_rules、fallback_rows_for_l3、infer_type、命名规则。
```

### 配置项

建议在 `system_config.yaml` 增加：

```yaml
fpa_profile: current_project
```

可选值：

```text
current_project
strict_fpa
```

读取函数：

```python
def load_fpa_profile(default: str = "current_project") -> str:
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

### current_project profile

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
同一三级模块在 current_project 和 strict_fpa 下可能生成完全不同的行。
profile version 变化意味着规则语义变化，应自动失效旧缓存。
```

缓存文件可以继续使用：

```text
md/fpa_ai_cache.json
```

缓存 entry 建议增加：

```json
{
  "profile": "current_project",
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
把当前逻辑迁入 CurrentProjectProfile。
默认 profile = current_project。
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
CurrentProjectProfile 承载 current_project 的核心规则、prompt、兜底拆分、类型推断、冲突判断和命名规则。
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
默认配置下仍为 current_project。
非法 profile 给出明确错误。
缓存 key 包含 profile。
```

已落地：

```text
config/system_config.yaml.example 新增 fpa_profile: current_project。
config_utils.py 新增 load_fpa_profile()。
正式 gen-fpa、gen-all、run_pipeline_simple、CLI 预览和 Web 预览共用 profile 选择入口。
CLI 新增 --fpa-profile，可覆盖 system_config.yaml。
Web 预览接口接受 fpa_profile；未传时读取 system_config.yaml。
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
current_project Golden Case 不受影响。
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
界面默认 current_project。
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
补充 current_project 和 strict_fpa 对比文档。
补充 Golden Case 输入样例。
补充用户选择建议。
```

已落地：

```text
新增 docs/fpa-profiles.md，面向用户说明 current_project / strict_fpa 的选择建议、使用方式和输出差异。
README.md 增加 FPA 方案章节和 --fpa-profile 参数说明。
docs/dev/fpa-golden-cases.md 增加 strict_fpa 的典型期望输出形态。
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
POST /api/fpa/preview-module
```

请求使用 `multipart/form-data`，支持两种输入方式：

```text
本机模式：xlsx_path
远程模式：file
```

参数：

```text
module_name
module_index
api_key
model
base_url
```

行为：

```text
不创建任务 session。
不写运行历史。
不生成 FPA Excel。
远程上传文件只写入临时目录，预览结束后清理。
本机路径仅限本机访问。
API Key / model / base_url 为空时读取系统配置。
```

前端新增：

```text
web_app/src/components/FpaPreview.vue
```

入口位置：

```text
任务设置 -> 高级区域 -> FPA 预览
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
docs/dev/fpa-golden-cases.md
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

## 测试覆盖

新增：

```text
tests/test_gen_fpa_ai.py
tests/test_gen_fpa_preview.py
tests/test_fpa_profiles.py
tests/test_fpa_external_data_rules.py
tests/test_gen_fpa_strict_profile.py
docs/dev/fpa-golden-cases.md
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
预览模式不生成 FPA Excel。
缺失三级模块时返回明确错误。
run_pipeline 的 gen-fpa / gen-all 仍能生成交付物。
Web FPA 预览接口可返回预览结果。
Web FPA 预览缺少模块目标时返回明确错误。
AI 缓存命中时不再调用 LLM。
缓存条目记录 profile.name 和 profile.version。
Golden Case 兜底拆分和类型规则不退化。
默认 current_project profile 可注册获取，未知 profile 会明确报错。
system_config.yaml 可读取 fpa_profile，默认 current_project。
正式生成和预览遇到未知 profile 时明确报错。
strict_fpa 不生成界面开发/接口开发/逻辑处理开发行。
strict_fpa 可区分 ILF、EIF、EI、EQ、EO 基础场景。
strict_fpa 可在同一三级模块中识别主数据 + 管理员关系等多个内部数据组。
strict_fpa 后处理会规范化 AI 输出中的“界面开发/接口开发/逻辑处理开发”名称。
strict_fpa 不把普通外部服务调用误判为 EIF。
strict_fpa 可识别 CRM、客户中心、财务核算系统等外部系统维护的数据组为 EIF。
strict_fpa 外部数据组识别已形成代码内规则表，覆盖统一用户中心、CRM、客户中心、财务核算系统、ERP、OA、主数据平台等来源。
strict_fpa 支持通过 system_config.yaml 的 fpa_external_data_rules 扩展外部数据组规则，扩展规则只追加，不覆盖内置规则。
strict_fpa 外部数据组规则表有专门单元测试，覆盖已知来源正例和短信平台、支付网关、文件存储、地图服务、OCR 服务等普通外部服务反例。
strict_fpa 在外部数据引用场景下仍按事务动作识别选择/引用为 EI、查看/详情为 EQ。
strict_fpa AI 后处理可纠正普通外部服务调用误报 EIF，并保留名称本身明确表示外部数据组的 EIF 行。
Web 正式生成和 FPA 预览均可选择 current_project / strict_fpa。
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
123 passed
前端构建通过
```

## 暂缓推进任务池

以下事项已确认暂不推进。后续如需继续，可按本节末尾的指令模板恢复。

### A. 真实项目 Golden Case

```text
A1. 增加 OA 审批流程引用样例：OA流程单据 EIF、关联审批单 EI、查看审批进度 EQ。
A2. 增加主数据平台组织引用样例：组织主数据 EIF、选择归属组织 EI。
A3. 增加支付网关退款反例：普通支付服务不生成 EIF、发起退款 EI、查看退款结果 EQ。
A4. 增加内部组织维护 ILF 与外部组织引用 EIF 的对照样例。
A5. 增加一个三级模块同时包含多个 ILF / EIF 的复杂样例。
A6. 在 JSON fixture 之外，补充真实 Excel / MD 验收样例。
```

### B. strict_fpa 数据组识别

```text
B1. 增强多个外部数据组同时出现时的识别。
B2. 增强外部数据引用与本系统关联数据同时出现时的识别。
B3. 增强名称模糊、描述明确场景的识别。
B4. 明确外部同步后由本系统继续维护的数据应判 ILF 还是 EIF。
B5. 评估 AI 辅助识别复杂数据组，并保留代码校验和 warning。
```

### C. 类型冲突规则

```text
C1. 细化 EI / EQ / EO / ILF / EIF 关键词优先级。
C2. 建立类型冲突矩阵。
C3. 增加可配置类型映射表。
C4. 增加可配置 AI 类型冲突规则表。
C5. 对比不同类型策略下的 Excel 公式结果。
```

### D. 配置校验

```text
D1. 补充 OA、统一认证平台、供应商平台、主数据平台、财务平台的 fpa_external_data_rules 示例。
D2. 增加配置重复规则检测。
D3. 增加别名冲突检测。
D4. 增加 data_nouns 为空时的提示。
D5. 普通外部服务被配置为数据组时记录 warning。
```

### E. 领域上下文

```text
E1. 为项目保存 domain_context.json。
E2. 显式记录系统边界、本系统维护数据组、外部引用数据组、普通外部服务。
E3. 将领域上下文稳定传入 FPA prompt。
```

### F. 验收

```text
F1. 补充 strict_fpa 人工验收记录。
F2. 使用真实模型跑代表性样例，检查说明质量、warning、缓存、预览和正式生成结果。
F3. 复核拆分粒度、类型判断和汇总值。
```

### G. 可选增强

```text
G1. 增加 Excel COM / LibreOffice 复算校验，只做 warning。
G2. 预览模式增加 --use-preview-cache / --keep-preview-files。
G3. 预览模式增加纯内存解析，减少临时 MD 文件。
G4. 如模板真实公式不是 调整值 × 要素数量，将业务公式翻译为 Python 规则并补测试。
```

### 后续恢复指令

继续全部任务：

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，从 A1 开始按顺序继续推进。每完成一项更新文档并跑相关测试。
```

推进指定分组：

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，推进 B 组 strict_fpa 数据组识别。每完成一项更新文档并跑相关测试。
```

推进指定事项：

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，只推进 D5：普通外部服务被配置为数据组时记录 warning。完成后更新文档并跑相关测试。
```

需要我先重新评估优先级时：

```text
读取 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，结合当前代码状态重新排序，先给出推荐，不修改代码。
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
