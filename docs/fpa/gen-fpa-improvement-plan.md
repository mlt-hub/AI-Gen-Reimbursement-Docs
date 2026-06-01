# gen-fpa 模块改进方案

日期：2026-05-29

## 背景

`gen-fpa` 负责生成《FPA工作量评估.xlsx》，当前流程为：

```text
功能清单 Excel
  -> gen-basedata 生成模块树和元数据 MD
  -> gen-fpa 生成 FPA 规则骨架 MD
  -> AI 填充“计算依据归类”和“计算依据说明”
  -> 根据输出模板写入 FPA Excel
```

核心代码位置：

```text
ai_gen_reimbursement_docs/pipeline.py
ai_gen_reimbursement_docs/gen_fpa.py
```

其中 `pipeline.py` 负责模式分发和步骤编排，`gen_fpa.py` 负责 FPA 行构建、AI 调用、Markdown 中间文件读写和 Excel 输出。

## 当前实现概览

### 入口

CLI 和 Web UI 最终都会进入：

```python
run_pipeline(mode="gen-fpa", ...)
```

`pipeline.py` 中的 `gen-fpa` 分支会调用：

```python
_generate_fpa(...)
```

该函数执行以下步骤：

1. 检查 FPA 输出模板。
2. 生成 `1.1.gen-fpa-FPA-模板.md`。
3. 如果配置了 API Key，则复制为 `1.3.gen-fpa-AI填充-FPA.md` 并调用 AI 填充。
4. 根据最终 MD 生成 Excel。
5. 从 `1.2.gen-fpa-FPA工作量-总和.md` 读取 FPA 工作量汇总。

### FPA 行生成

当前 `_build_fpa_rule_rows()` 会把每个功能过程固定拆成两行：

```text
界面开发：类型 EI，调整值 2，要素数量 1
接口开发：类型 ILF，调整值 1，要素数量 1
```

这个策略需要变更。固定按功能过程拆“界面 + 接口”，会把简单页面拆得过细，尤其是同一个三级模块下存在多个按钮、查询、列表、维护弹窗时，容易把页面操作误拆成多条界面工作量，最终变成“造工作量”。

新的目标是：

```text
以三级模块作为一个整体，让 AI 先规划 FPA 行。
界面类能力尽量合并为一个三级模块级界面开发行。
非界面类逻辑接口按功能动作拆分为一行一个。
```

当前行字段主要用于输出表格：

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
```

### AI 填充

当前 `_ai_fill_fpa()` 对每一行单独调用一次 LLM。当前 prompt 主要包含：

```text
新增/修改功能点描述
计算依据归类判定原则列表
JSON 输出格式要求
```

AI 返回后，代码会尝试解析 JSON，并回填：

```text
类型
计算依据归类
计算依据说明
```

新的目标不再是“先按规则生成所有行，再让 AI 填 F/G 列”，而是：

```text
先按三级模块聚合功能过程
  -> 对每个三级模块调用一次 AI
  -> AI 返回该三级模块应生成的 FPA 行列表
  -> 代码校验、规范化、写入 MD
  -> 根据 MD 生成 Excel
```

## 主要问题

### 1. 当前拆分粒度不合理

当前实现把每个功能过程固定拆成：

```text
功能过程-界面开发
功能过程-接口开发
```

这会带来明显问题：

- 界面类功能被拆得过细。
- 一个三级模块的列表、查询、按钮、弹窗可能被重复计算界面工作量。
- 简单维护类页面会被拆成多条界面行，放大工作量。
- 同一个页面上的多个操作被拆散，失去业务整体性。
- AI 只能在已经拆碎的行上补说明，无法重新规划合理粒度。

正确方向应是：

```text
三级模块整体分析
界面合并
接口按动作拆分
```

以“垂直行业管理”为例，界面不应拆成列表界面、查询界面、添加界面、编辑界面、管理员界面等多行，而应合并为一行：

```text
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-界面开发，具体为以下：
1、新增垂直行业列表，可以分页切换
2、新增条件查询组件，输入行业名称搜索、可重置搜索条件
3、添加/编辑/删除/管理员等按钮
4、添加垂直行业界面，输入垂直行业名称保存
5、编辑更新垂直行业界面
6、管理员界面，可展示/添加/删除管理员
7、更新垂直行业状态组件
```

### 2. AI 输入上下文不足

当前 `_build_fpa_rule_rows()` 已经读取了：

```python
client_type = r["客户端类型"]
l1 = r["一级模块"]
l2 = r["二级模块"]
l3 = r["三级模块"]
proc = r["功能过程"]
proc_desc = r["功能过程描述"]
proc_type = r["功能过程类型"]
```

但这些原始上下文字段没有作为结构化字段保留下来，也没有传给 AI。

当前 AI 实际看到的主要是：

```text
新增/修改功能点描述：【客户端】一级模块-二级模块-三级模块-功能过程-界面开发
```

这会带来几个问题：

- AI 只能根据标题推断功能内容。
- “计算依据说明”容易泛化，缺少业务细节。
- 同名或相似功能过程容易生成重复、模板化说明。
- 无法稳定体现原始“功能过程描述”中的业务规则和数据边界。

### 3. AI 调用粒度错误

当前 AI 是逐 FPA 行调用。即使 prompt 增加上下文，也只能对单行做说明，无法决定“哪些功能过程应该合并，哪些应该拆开”。

新的调用粒度应改为：

```text
一个三级模块调用一次 AI
```

输入给 AI 的内容应包括该三级模块下的所有功能过程：

```text
客户端类型
一级模块
二级模块
三级模块
三级模块整体功能描述
功能过程列表
每个功能过程的类型和描述
FPA 类型约束
判定原则列表
```

AI 输出该三级模块的 FPA 行列表。

### 4. AI 可以直接覆盖 FPA 类型

当前 AI 返回 JSON 中如果包含 `type`，代码会执行：

```python
row["类型"] = _data["type"].strip()
```

旧方案的默认类型由规则骨架生成：

```text
界面开发 -> EI
接口开发 -> ILF
```

该映射属于旧版问题背景，不再作为当前实现口径。让 AI 默认覆盖类型风险较高：

- AI 可能把非界面业务动作误判成 EI、EO、EQ、ILF 或 EIF。
- 类型变化会影响模板中的基准值公式。
- 类型是规则层决策，AI 更适合补充说明，不宜默认改动。

在新方案下，AI 可以为每行建议 `type`，但必须受规则约束。不能让 AI 任意输出类型。

这里需要明确三个概念的边界：

```text
拆分依据：决定生成哪些 FPA 行。
类型来源：优先由 AI 结合业务描述和判定原则给出专业判断，代码规则负责校验和兜底。
归类约束：决定每一行“计算依据归类”填模板判定原则中的哪一条。
```

“计算依据归类判定原则列表”属于归类约束，不应作为拆分依据。类型可以由 AI 参考业务描述和判定原则进行专业判断，但必须经过代码校验；AI 失败或类型非法时，再使用关键词规则兜底。

原因：

- 拆分首先是业务粒度问题，例如界面是否合并、接口按哪些动作拆。
- 类型首先来自 FPA 专业判断，需要结合功能点名称、功能过程描述、数据维护行为、输入输出行为、外部接口边界等信息。
- 判定原则列表适合在行已经确定后，选择模板中对应的计算依据文案。
- 如果让判定原则列表主导拆分，AI 可能为了匹配规则把简单界面拆得过细。
- 如果让判定原则列表主导类型，AI 可能把添加、编辑、查询等动作误判成不稳定类型。

类型判断策略：

```text
优先：AI 根据功能点名称、功能过程描述、判定原则列表给出 type 建议和理由。
校验：代码检查 type 是否在 EI/ILF/EQ/EO/EIF 范围内，并检查与关键词规则是否明显冲突。
兜底：AI 没返回 type、返回非法 type 或 AI 调用失败时，使用关键词规则。
```

兜底关键词规则：

```text
界面开发 -> EI
添加/编辑/删除/维护/保存 -> ILF
查询/查看/详情/列表检索 -> EQ
导出/报表输出/生成文件 -> EO
导入 -> 通常判定为 EI；只有明确仅读取展示且不维护内部数据时，才可考虑 EQ
外部接口 -> 结合语义判断，引用外部数据组时倾向 EIF，普通调用外部服务不直接判 EIF
```

原因：

```text
查询通常是读取并返回数据，不应简单归为 ILF。
添加、编辑、删除、维护、保存通常涉及内部数据维护，倾向 ILF。
导出通常产生对外输出结果或文件，倾向 EO。
导入通常表示外部数据跨越系统边界进入系统，并新增或更新内部逻辑文件，倾向 EI。
只有所谓“导入”仅读取外部数据用于展示、不新增/修改/删除任何内部数据时，才可考虑 EQ。
外部接口是否是 EIF，取决于是否引用外部应用维护的数据组，而不是只要出现“外部接口”四个字。
```

第一阶段采用“AI 判断 + 代码校验 + 关键词兜底”策略：

```text
拆分规则先决定 FPA 行。
AI 可以输出 type 和 type_reason。
代码校验 type 是否在 EI/ILF/EQ/EO/EIF 范围内。
AI type 合法且未与关键词规则明显冲突时，采用 AI type。
AI type 缺失、非法或明显冲突时，记录 warning，并使用关键词规则兜底。
判定原则列表只用于选择“计算依据归类”。
classification_basis_index 不反向覆盖 type。
```

### 5. JSON 解析失败被静默吞掉

当前解析异常处理为：

```python
except Exception:
    pass
```

这会导致：

- AI 返回了非 JSON，用户不知道。
- JSON 字段缺失，日志没有提示。
- F/G 列未填充，排查困难。
- 真实生产问题被隐藏。

### 6. `_filled_count` 统计语义不准确

当前 `_filled_count` 在调用 AI 前递增：

```python
_filled_count += 1
resp = _call_llm(...)
```

因此它实际表示“尝试调用 AI 的行数”，不是“成功填充的行数”。

如果 LLM 调用失败、返回空、JSON 解析失败，日志仍可能显示：

```text
FPA AI 填充完成: AI 填充 N/M 行
```

这会误导用户。建议拆分为：

```text
attempted_count：尝试调用 AI 的行数
success_count：成功解析并至少填充一个目标字段的行数
failed_count：调用失败或解析失败的行数
skipped_count：因限制配置跳过的行数
```

新方案下，统计对象也应从“行”改成“三级模块 + 行”：

```text
attempted_module_count：尝试调用 AI 的三级模块数
success_module_count：成功生成至少一行 FPA 的三级模块数
failed_module_count：AI 调用失败或解析失败的三级模块数
generated_row_count：最终生成的 FPA 行数
fallback_row_count：AI 失败后规则兜底生成的行数
```

### 7. 判定原则读取范围写死

当前判定原则从模板附录读取：

```python
for row_num in range(2, 15):
    val = ws.cell(row_num, 3).value
```

这意味着只读取 C2 到 C14。

如果模板后续扩展更多判定原则，新增规则不会进入 prompt，AI 只能在旧规则中选择。

### 8. FPA 汇总值可能与最终 Excel 不一致

`init_fpa_template_md()` 在 AI 填充前写入：

```text
1.2.gen-fpa-FPA工作量-总和.md
```

汇总逻辑是：

```text
调整值 * 要素数量
```

但最终 Excel 中的 FPA 工作量通常由模板公式计算，可能受以下因素影响：

- 类型
- 变更状态
- 基准值公式
- 工作量公式
- 模板配置

因此，MD 中的汇总值可能不是最终 Excel 的真实汇总值。

### 9. 缺少 AI 失败兜底策略

新方案把 FPA 行规划交给 AI 后，必须设计兜底。否则某个三级模块 AI 失败时，可能整块没有 FPA 行。

建议兜底策略：

```text
每个三级模块至少生成 1 行界面开发 EI。
每个功能过程至少生成 1 行非界面业务动作行，并按动作语义判定 EI / EQ / EO / ILF / EIF。
```

兜底结果可能偏粗，但比整块丢失更安全。

### 10. 测试覆盖不足

已有测试覆盖了：

- 接收者判定。
- FPA 行数生成。
- 默认类型和调整值。
- 说明格式化。
- `run_pipeline(mode="gen-fpa")` 能生成文件。

但缺少以下测试：

- AI 返回合法 JSON 时能正确回填。
- AI 返回 markdown code block JSON 时能正确解析。
- AI 返回非法 JSON 时会记录 warning 且不中断。
- `classification_basis_index` 越界时不会错误填充。
- AI 默认不能覆盖 FPA 类型。
- 判定原则读取动态行数。
- `_filled_count` 或统计日志语义准确。
- 三级模块整体 AI 能把界面合并为一行。
- 非界面逻辑接口能按功能动作拆分为多行。
- AI 失败时能走兜底行生成。
- AI 输出过细界面行时，代码或 prompt 能约束其合并。

## 改进目标

### 稳定性目标

1. AI 填充失败可观测，不静默。
2. FPA 类型默认由规则约束，避免 AI 随意覆盖。
3. 汇总值尽量与最终 Excel 保持一致。
4. 测试覆盖 AI 响应解析和异常路径。

### 质量目标

1. Prompt 使用三级模块整体上下文。
2. 界面类功能按三级模块整体合并，避免拆得过细。
3. 非界面逻辑接口按功能动作拆分，做到一行一个动作。
4. “计算依据说明”更贴近功能过程描述。
5. 判定原则只能从模板规则中选择，减少自造分类。
6. 界面开发和逻辑接口开发说明边界更清楚。

### 可控性目标

1. 第一阶段可以改变 FPA 行生成策略，但不改变最终 Excel 表结构。
2. 不引入新外部依赖。
3. 保留最终 Excel 列结构，避免破坏下游模板。
4. AI 输出必须经过代码校验和兜底。
5. 需要支持更多 FPA 类型时，必须通过明确规则启用。

## 推荐方案

## 第一阶段：三级模块整体规划

第一阶段应直接调整核心拆分逻辑。原因是旧逻辑的主要问题不是 prompt 不够好，而是“先固定拆分再让 AI 补说明”的方向不对。

### 1. 按三级模块聚合输入

新增聚合结构，将 `parse_module_tree_md()` 得到的功能过程按以下维度分组：

```text
客户端类型
一级模块
二级模块
三级模块
```

每个分组包含：

```text
三级模块整体功能描述
功能过程列表
功能过程类型
功能过程描述
```

建议新增函数：

```python
def _group_rows_by_l3(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    ...
```

输出结构示例：

```python
{
    "client_type": "地市后台",
    "l1": "垂直行业营销",
    "l2": "垂直行业管理",
    "l3": "垂直行业管理",
    "l3_desc": "...",
    "processes": [
        {
            "name": "添加垂直行业",
            "type": "新增",
            "desc": "..."
        },
        {
            "name": "编辑垂直行业",
            "type": "修改",
            "desc": "..."
        }
    ]
}
```

### 2. 由 AI 生成三级模块的 FPA 行列表

新增函数：

```python
def _ai_plan_fpa_rows_for_l3(
    group: dict[str, object],
    judgement_rules: list[str],
    domain_context: dict[str, object] | None,
    api_key: str,
    model: str,
    base_url: str,
) -> list[dict[str, object]]:
    ...
```

AI 输出 JSON：

```json
{
  "rows": [
    {
      "name": "垂直行业管理界面开发",
      "classification_basis_index": 1,
      "explanation": "..."
    },
    {
      "name": "添加垂直行业-逻辑接口开发",
      "classification_basis_index": 2,
      "explanation": "..."
    }
  ]
}
```

代码需要校验：

```text
rows 必须是列表
name 不能为空
type 必须在 EI/ILF/EQ/EO/EIF 范围内；非法时使用关键词规则兜底
classification_basis_index 必须在判定原则范围内
explanation 不能为空，否则使用兜底说明
同一三级模块存在多条界面开发行时，每条界面行必须有 split_reason
```

### 3. 界面类合并规则

界面类不要按功能过程拆细。一个三级模块下的列表、查询条件、按钮、弹窗、状态组件、管理员维护组件等，应合并为一条界面开发行。

命名规则：

```text
【客户端类型】一级模块-二级模块-三级模块-界面开发
```

说明格式：

```text
【客户端类型】一级模块-二级模块-三级模块-界面开发，具体为以下：
1、...
2、...
3、...
```

示例：

```text
【地市后台】垂直行业营销-垂直行业管理-垂直行业管理-界面开发，具体为以下：
1、新增垂直行业列表，可以分页切换
2、新增条件查询组件，输入行业名称搜索、可重置搜索条件
3、添加/编辑/删除/管理员等按钮
4、添加垂直行业界面，输入垂直行业名称保存
5、编辑更新垂直行业界面
6、管理员界面，可展示/添加/删除管理员
7、更新垂直行业状态组件
```

约束：

```text
同一三级模块默认合并为 1 条界面开发行。
只有存在独立页面、独立业务对象、独立业务流程或独立用户端时，才允许拆成多条界面开发行。
不要把列表、查询、按钮、弹窗分别拆成多条界面行。
```

#### 多界面拆分判断

一个三级模块下可能存在不止 1 个界面开发行，但必须有明确的独立性依据。判断时不要看组件数量，而要看是否形成独立业务视图或操作场景。

允许拆成多条界面行的情况：

```text
独立页面：有独立入口、独立路由、独立菜单、独立 Tab、详情页、审批页、导入页等。
独立业务对象：维护不同数据对象，字段集合、生命周期、增删改查行为明显不同。
独立业务流程：服务不同业务目标，角色、状态流转、前后置步骤明显不同。
独立用户端：面向不同端或不同用户群，例如后台、移动端、大屏端。
```

不应拆成多条界面行的情况：

```text
同一页面内的列表。
同一页面内的查询条件。
同一页面内的新增、编辑、删除、启停按钮。
同一页面内的新增/编辑弹窗。
同一页面内的状态切换组件。
同一业务对象的字段维护。
```

示例：

```text
可以拆：
客户列表界面开发
客户详情界面开发
客户审批界面开发

不应拆：
客户列表界面开发
客户查询条件界面开发
客户新增按钮界面开发
客户编辑弹窗界面开发
客户状态切换界面开发
```

如果 AI 生成多条名称包含“界面开发”的行，必须为每条界面行输出 `split_reason`。没有明确 `split_reason` 时，代码应记录 warning，并优先合并为 1 条界面开发行。

### 4. 非界面逻辑接口拆分规则

除界面类之外，逻辑接口按功能动作拆分：

```text
一个动作一行
一行表示一个后端逻辑能力或数据处理能力
```

命名规则：

```text
功能动作-逻辑接口开发
```

以“垂直行业管理”为例，应生成：

```text
1、垂直行业管理界面开发：EI
2、添加垂直行业-逻辑处理开发：ILF
3、编辑垂直行业-逻辑处理开发：ILF
4、查询垂直行业-查询处理开发：EQ
5、删除垂直行业-逻辑处理开发：ILF
6、新增垂直行业管理员-逻辑处理开发：ILF
7、删除垂直行业管理员-逻辑处理开发：ILF
```

新增表、数据表维护、字段保存等不单独生成一行。它们应归属到对应动作中：

```text
有“添加”功能时，新增表/保存数据归属到添加动作。
没有“添加”功能时，归属到最相关的编辑、查询或任意主要动作。
不要为了数据表本身额外生成工作量行。
```

### 5. Prompt 设计

新的 prompt 应以三级模块为单位。

Prompt 中必须把 FPA 核心规则、领域上下文、模块输入、拆分规则、类型规则、归类规则分开写，避免不同 AI 平台按各自训练语料理解 FPA，也避免 AI 把“计算依据归类判定原则列表”误解为拆分规则。

#### FPA 核心规则注入

不同 AI 平台对 FPA 的理解可能存在偏差。有的模型会混入 COSMIC 思路，有的会把技术接口、数据库表、按钮、弹窗都当成功能点，有的会把“外部接口调用”等同于 `EIF`。因此不能只依赖模型自带知识，必须把本项目采用的 FPA 核心口径作为固定规则喂给 AI。

建议新增固定 prompt 片段：

```python
FPA_CORE_RULES = """
FPA 核心规则：

1. EI（External Input，外部输入）
   从应用边界外进入系统的输入处理过程，通常会维护内部逻辑文件或控制系统行为。
   导入通常属于 EI，因为外部文件或外部数据跨越应用边界进入系统，并新增或更新内部逻辑文件。

2. EQ（External Inquiry，外部查询）
   读取数据并返回结果，不维护内部逻辑文件，通常不包含复杂派生、汇总或文件生成。
   查询、查看、详情、列表检索通常倾向 EQ。

3. EO（External Output，外部输出）
   向应用边界外输出数据，通常包含派生、汇总、报表、导出文件或面向外部的输出结果。
   导出、报表输出、生成文件通常倾向 EO。

4. ILF（Internal Logical File，内部逻辑文件）
   本系统维护的逻辑相关数据组。添加、编辑、删除、维护、保存本系统内部业务数据时，通常涉及 ILF。

5. EIF（External Interface File，外部接口文件）
   由其他系统维护、本系统引用的逻辑相关数据组。
   EIF 不等同于调用外部服务；只有当本系统引用外部系统维护的数据组时，才倾向 EIF。

反例与限制：
- 查询不应默认判为 ILF。
- 外部接口调用不等于 EIF。
- 短信、支付、OCR、地图等外部服务调用通常不直接判 EIF。
- 数据库表、字段、保存表动作不要单独生成功能点，应归属到业务动作。
- 同一页面内的列表、查询条件、按钮、弹窗、状态切换通常不拆成多条界面行。
- 不得为了增加工作量而拆分细碎功能点。
"""
```

调用 AI 时应把它作为稳定上下文注入：

```text
FPA 核心规则：
{fpa_core_rules}

领域上下文：
{domain_context}

当前三级模块：
...
```

分层后，AI 判断依据为：

```text
系统提示词：角色、输出格式、禁止编造、拆分纪律。
FPA 核心规则：EI/EO/EQ/ILF/EIF 的定义和本项目判定口径。
领域上下文：本系统边界、ILF、EIF、外部服务。
模块输入：当前三级模块和功能过程列表。
```

#### 领域上下文注入

在调用 AI 判定 FPA 之前，建议先给 AI 提供当前项目的领域上下文摘要。原因是 FPA 类型判断经常依赖系统边界和数据归属：

```text
这是维护本系统内部业务数据，还是读取外部系统维护的数据？
这个查询返回的是本系统数据，还是外部应用维护的数据组？
导入的数据是否最终落到本系统内部逻辑文件？
所谓“外部接口”是外部数据组，还是普通外部服务调用？
```

这些问题仅靠三级模块名称和功能过程描述容易误判。领域上下文可以帮助 AI 更稳定地判断 `ILF`、`EIF`、`EI`、`EQ`、`EO`。

领域上下文建议包含：

```json
{
  "system_boundary": "当前系统负责垂直行业营销管理，包括垂直行业维护、行业管理员关系维护、行业状态管理等。",
  "internal_logical_files": [
    {
      "name": "垂直行业",
      "description": "本系统维护的行业基础数据，包括行业名称、状态、创建时间等。"
    },
    {
      "name": "垂直行业管理员关系",
      "description": "本系统维护垂直行业与管理员账号之间的关联关系。"
    }
  ],
  "external_interface_files": [
    {
      "name": "统一用户中心人员账号",
      "owner": "统一用户中心",
      "usage": "本系统读取人员账号用于选择和展示行业管理员。"
    }
  ],
  "external_services_not_eif": [
    {
      "name": "短信平台",
      "usage": "仅提供短信发送能力，不作为本系统引用的外部数据组。"
    }
  ]
}
```

领域上下文来源可以分阶段实现：

```text
第一阶段：从功能清单元数据、三级模块描述、功能过程描述中提取简短摘要；允许用户在配置或预览页手动补充。
第二阶段：根据项目文档、需求说明、历史 FPA 结果沉淀可复用的领域上下文。
第三阶段：为每个项目保存 domain_context.json，作为 FPA 生成的显式输入。
```

领域上下文来源优先级：

```text
1. 用户手工提供的 domain_context。
2. 项目级 domain_context.json。
3. 功能清单元数据、三级模块描述、功能过程描述自动摘要。
4. 空领域上下文。
```

如果多个来源同时存在，应按优先级合并：

```text
用户手工补充内容优先。
项目级 domain_context.json 作为稳定项目背景。
自动摘要只作为补充，不覆盖人工明确写入的系统边界、ILF、EIF、外部服务说明。
```

领域上下文不是让 AI 编造业务事实，而是给 AI 明确边界。Prompt 中应要求：

```text
只能使用领域上下文和模块输入中出现的信息。
无法判断数据归属时，需要在 type_reason 中说明不确定点。
不要因为名称出现“外部接口”就直接判 EIF。
不要因为名称出现“导入”就忽略其维护内部数据的 EI 特征。
```

建议格式：

```text
你正在为一个三级模块规划 FPA 工作量评估行。

FPA 核心规则：
{fpa_core_rules}

领域上下文：
{domain_context}

输入信息：
- 客户端类型：{client_type}
- 一级模块：{l1}
- 二级模块：{l2}
- 三级模块：{l3}
- 三级模块整体功能描述：{l3_desc}

功能过程列表：
1. 功能过程：添加垂直行业
   类型：新增
   描述：...
2. 功能过程：编辑垂直行业
   类型：修改
   描述：...

计算依据归类判定原则列表：
1) ...
2) ...

规划规则：
1. 先从三级模块整体视角规划 FPA 行，不要机械地为每个功能过程生成界面行。
2. 界面类能力默认合并为 1 行，名称必须包含“界面开发”。
3. 只有存在独立页面、独立业务对象、独立业务流程或独立用户端时，才允许拆成多条界面开发行。
4. 如果拆成多条界面开发行，必须为每条界面行输出 split_reason。
5. 界面说明应覆盖列表、分页、查询条件、按钮、弹窗、状态组件、管理组件等界面元素。
6. 非界面功能按业务动作拆分，一行一个动作，名称应包含添加/编辑/删除/维护/保存/查询/查看/导入/导出/外部接口等动作关键词。
7. 新增表、保存表、字段维护不要单独成行，应归属到添加/编辑/查询等动作中。
8. 不要为了增加工作量而拆分细碎界面行。

类型规则：
1. 必须输出 type，取值只能是 EI、ILF、EQ、EO、EIF。
2. 必须输出 type_reason，说明为什么选择该类型。
3. type 应结合功能点名称、功能过程描述、数据维护行为、输入输出行为、外部接口边界判断。
4. 不要只按关键词机械判断；关键词只作为代码兜底规则。
5. 添加/编辑/删除/维护/保存等内部数据维护动作通常倾向 ILF。
6. 查询/查看/详情/列表检索等读取返回动作通常倾向 EQ。
7. 导出/报表输出/生成文件等对外输出动作通常倾向 EO。
8. 导入通常属于 EI，因为外部数据跨越应用边界进入系统，并新增或更新内部逻辑文件；只有明确仅读取展示且不维护内部数据时，才可考虑 EQ。
9. 外部接口需要判断是否引用外部应用维护的数据组，不要只因名称包含“外部接口”就固定判为 EIF。
10. 如果无法确定类型，优先选择最保守的类型，并在 type_reason 中说明不确定点。

归类规则：
1. 计算依据归类判定原则列表只用于选择 classification_basis_index。
2. classification_basis_index 必须从判定原则列表中选择。
3. 不要用判定原则列表决定是否拆分界面行。
4. 不要为了匹配判定原则而新增不存在的 FPA 行。

说明规则：
1. explanation 必须基于输入的功能过程和描述。
2. 不要编造不存在的功能、表、接口或页面。
3. 只输出 JSON，不要输出 Markdown。

输出格式：
{
  "rows": [
    {
      "name": "三级模块界面开发",
      "type": "EI",
      "type_reason": "该行描述用户界面交互和页面组件能力。",
      "split_reason": "",
      "classification_basis_index": 1,
      "explanation": "..."
    },
    {
      "name": "添加xxx-逻辑处理开发",
      "type": "ILF",
      "type_reason": "该行描述内部业务数据维护逻辑。",
      "classification_basis_index": 2,
      "explanation": "..."
    },
    {
      "name": "查询xxx-查询处理开发",
      "type": "EQ",
      "type_reason": "该行描述按条件读取并返回业务数据，不维护内部数据。",
      "classification_basis_index": 3,
      "explanation": "..."
    }
  ]
}
```

#### AI 输出 JSON Schema

AI 必须输出一个 JSON 对象，顶层只有 `rows` 字段：

```json
{
  "rows": []
}
```

`rows` 为数组，每个元素的字段定义如下：

```text
name：必填，字符串，表示“新增/修改功能点”名称。
type：必填，字符串，只能是 EI、ILF、EQ、EO、EIF。
type_reason：必填，字符串，说明 type 判断依据。
split_reason：可选字符串；当同一三级模块存在多条界面开发行时，每条界面开发行必填。
classification_basis_index：必填，整数，从 1 开始，对应判定原则列表序号。
explanation：必填，字符串，写入“计算依据说明”。
source_processes：可选字符串数组，表示该行来自哪些功能过程。
```

示例：

```json
{
  "rows": [
    {
      "name": "查询垂直行业-查询处理开发",
      "type": "EQ",
      "type_reason": "按条件读取垂直行业数据并返回列表和分页信息，不维护内部数据。",
      "split_reason": "",
      "classification_basis_index": 3,
      "explanation": "查询垂直行业-查询处理开发，具体为以下：\n1、接收行业名称、分页参数等查询条件；\n2、根据查询条件读取垂直行业数据；\n3、返回垂直行业列表、状态、管理员数量等展示字段；\n4、返回分页列表和总数信息。",
      "source_processes": ["查询垂直行业"]
    }
  ]
}
```

#### AI 结果后处理规则

AI 返回结果必须经过代码后处理，不能直接写入 MD：

```text
rows 不是数组：整块走兜底，并记录 warning。
name 为空：丢弃该行，并记录 warning。
type 缺失或非法：使用关键词规则兜底，并记录 warning。
type 与关键词兜底轻微不一致：保留 AI type，记录 warning，并保留 type_reason。
type 与拆分规则明显冲突：使用关键词规则兜底，并记录 warning。
classification_basis_index 缺失或越界：计算依据归类留空，并记录 warning。
explanation 为空：使用兜底说明，并记录 warning。
同一三级模块存在多条界面开发行且缺少 split_reason：记录 warning，并优先合并为 1 条界面开发行。
source_processes 缺失：根据 name 和功能过程名称做尽力匹配；无法匹配时留空。
```

明显冲突示例：

```text
名称包含“界面开发”，AI type 返回 EIF。
名称包含“查询”，且说明明确“不维护内部数据”，AI type 返回 ILF。
名称包含“导入”，且说明明确“写入内部业务数据”，AI type 返回 EQ。
```

#### 最终提示词模板

实现时建议把提示词明确拆成系统提示词和用户提示词。

系统提示词只放稳定角色、边界和输出纪律：

```text
你是一个资深 FPA 功能点评估专家，负责根据功能清单为 FPA 工作量评估表规划功能点行。

你必须遵守以下原则：

1. 从三级模块整体视角规划 FPA 行，不要机械地为每个功能过程生成界面行。
2. 界面类能力默认合并为 1 行；只有存在独立页面、独立业务对象、独立业务流程或独立用户端时，才允许拆成多条界面开发行。
3. 不得把同一页面内的列表、查询条件、按钮、弹窗、状态组件拆成多条界面工作量。
4. 非界面功能按业务动作拆分，一行表示一个独立业务动作或数据处理能力。
5. 新增表、保存表、字段维护等数据表动作不要单独成行，应归属到添加、编辑、查询、导入、导出或外部接口等业务动作中。
6. 不得为了增加工作量而拆分细碎功能点。
7. explanation 必须基于输入内容，不得编造不存在的功能、表、接口或页面。
8. 只输出 JSON，不要输出 Markdown、解释文字或代码块。
```

用户提示词放本次调用所需的完整上下文：

```text
请为以下三级模块规划 FPA 工作量评估行。

FPA 核心规则：
{fpa_core_rules}

领域上下文：
{domain_context}

输入信息：
- 客户端类型：{client_type}
- 一级模块：{l1}
- 二级模块：{l2}
- 三级模块：{l3}
- 三级模块整体功能描述：{l3_desc}

功能过程列表：
{process_list}

计算依据归类判定原则列表：
{numbered_judgement_rules}

输出要求：
只输出 JSON，格式如下：

{
  "rows": [
    {
      "name": "三级模块界面开发",
      "type": "EI",
      "type_reason": "说明为什么该功能点属于该类型",
      "split_reason": "",
      "classification_basis_index": 1,
      "explanation": "计算依据说明",
      "source_processes": ["功能过程名称"]
    }
  ]
}

字段要求：
- name：必填，新增/修改功能点名称。
- type：必填，只能是 EI、ILF、EQ、EO、EIF。
- type_reason：必填，说明 type 判断依据。
- split_reason：可选；同一三级模块拆出多条界面开发行时，每条界面行必填。
- classification_basis_index：必填，必须从判定原则列表中选择，序号从 1 开始。
- explanation：必填，必须基于输入的功能过程和描述。
- source_processes：可选，表示该行来自哪些功能过程。
```

其中：

```text
{fpa_core_rules} 使用固定的 FPA_CORE_RULES。
{domain_context} 使用用户手工上下文、项目级 domain_context.json 或自动摘要。
{numbered_judgement_rules} 来自 FPA 模板附录的“计算依据归类判定原则列表”。
```

### 6. 无 AI 或 AI 失败时的兜底生成

兜底函数：

```python
def _fallback_fpa_rows_for_l3(group: dict[str, object], meta: dict[str, str]) -> list[dict[str, object]]:
    ...
```

兜底规则：

```text
1. 每个三级模块生成 1 行名称包含“界面开发”的界面行，兜底类型为 EI。
2. 每个功能过程生成 1 行非界面能力行，名称保留添加/编辑/删除/维护/保存/查询/查看/导入/导出/外部接口等关键词。
3. 兜底行通过“新增/修改功能点”描述内容关键词判定 type。
4. 如果功能过程名称疑似纯页面查看、列表展示，可不额外生成非界面业务动作行，第一阶段可先不做智能过滤。
5. 兜底说明使用功能过程名称和描述拼接，不编造细节。
```

这样在无 API Key 或 AI 失败时仍能生成可用的 FPA 骨架。

### 7. FPA MD 表结构

最终 Excel 仍使用原列结构。MD 建议保留现有列，并新增审计列：

```text
来源三级模块
来源功能过程
生成方式
类型判断理由
类型兜底标记
```

其中：

```text
来源三级模块：用于审计该行来自哪个三级模块。
来源功能过程：界面行可填多个功能过程，用顿号或 JSON 字符串；非界面业务动作行填对应动作。
生成方式：ai 或 fallback。
类型判断理由：记录 AI 返回的 type_reason 或关键词兜底原因。
类型兜底标记：ai、fallback_keyword、fallback_default。
```

Excel 生成时忽略这些审计列。

### 8. 旧兼容路径处理

根据 `AGENTS.md` 的项目约束，本系统尚未上线，不需要保留旧版本兼容路径。

新方案会扩展 FPA MD 的中间表结构，当前不再兼容旧 10 列 FPA MD：

```text
FPA MD 生成和读取统一使用新审计列格式。
Excel 生成时只读取写入模板所需业务列，审计列不写入 Excel。
如果发现旧 10 列兼容读取逻辑残留，应删除并补充测试。
```

读取 MD 时应明确要求新表头结构：

```text
序号、子系统(模块)、资产标识、新增/修改功能点、类型、计算依据归类、计算依据说明、变更状态、调整值、要素数量、生成方式、类型理由、源功能过程、后处理警告
```

### 9. 类型判断、校验与兜底策略

允许类型：

```text
EI
ILF
EQ
EO
EIF
```

优先策略：

```text
AI 输出 type 和 type_reason。
代码校验 type 是否在允许类型范围内。
如果 type 合法且没有明显冲突，采用 AI type。
```

兜底关键词规则：

```text
新增/修改功能点描述内容包含“界面开发” -> EI
新增/修改功能点描述内容包含“添加/编辑/删除/维护/保存” -> ILF
新增/修改功能点描述内容包含“查询/查看/详情/列表检索” -> EQ
新增/修改功能点描述内容包含“导出/报表输出/生成文件” -> EO
新增/修改功能点描述内容包含“导入” -> EI
新增/修改功能点描述内容包含“外部接口” -> 记录 warning；如描述明确引用外部数据组，则按 EIF，否则按 ILF 兜底
```

建议按上述顺序兜底。原因是一个名称可能同时包含多个关键词，应先识别界面与明确的数据维护、查询、导入、导出动作；外部接口需要更谨慎，不应机械固定类型。

### 10. EIF 判定边界

`EIF` 的关键不是“是否调用外部接口”，而是：

```text
本系统是否引用了另一个系统维护的数据组。
```

也就是说，`EIF` 更接近“外部接口文件 / 外部接口数据组”，不是“HTTP 接口调用”这个技术动作本身。

可以倾向 `EIF` 的情况：

```text
从 CRM 系统读取客户基础信息。
从统一用户中心读取组织、人员、角色数据。
从商品中心读取商品目录。
从外部行业库读取行业分类数据。
从第三方资质库读取企业认证结果。
```

这些场景有共同特征：

```text
数据由外部系统维护。
本系统读取或引用这组数据。
这组数据对本系统业务有独立意义。
本系统不负责维护这组数据。
```

不应仅凭“外部接口”四个字判定为 `EIF` 的情况：

```text
发送短信验证码。
调用支付接口创建支付单。
调用文件服务上传附件。
调用 OCR 服务识别图片。
调用地图服务获取经纬度。
```

这些更像外部服务能力调用，不一定是引用外部系统维护的数据组。它们应优先归属到对应业务动作中，例如添加、提交、校验、导入、查询等，而不是单独生成 `EIF` 行。

判断 `EIF` 时建议使用三个问题：

```text
1. 这是不是一个外部系统维护的数据组？
2. 本系统是否读取或引用这组数据作为业务处理依据？
3. 本系统是否不负责维护这组数据，只消费它？
```

三个问题都为“是”时，才倾向 `EIF`。

如果只是：

```text
调用外部服务执行一次动作
```

则不要仅因为名称里包含“外部接口”就判定为 `EIF`。

校验规则：

```text
AI type 缺失或非法时，使用关键词规则兜底。
AI type 与关键词兜底结果不一致时，不立即覆盖；记录 warning，保留 AI type，并在 MD 审计列保留 type_reason。
如果 AI type 与拆分规则明显冲突，例如“界面开发”被判为 EIF，则使用关键词规则兜底。
判定原则列表负责产生 classification_basis_index。
classification_basis_index 不反向覆盖 type。
无法通过关键词判定 type 时，记录 warning，并默认按 ILF 兜底。
```

示例：

```text
垂直行业管理界面开发
  命中关键词 = 界面开发
  type = EI
  classification_basis_index = 从判定原则列表中选择最匹配项

添加垂直行业-逻辑接口开发
  命中关键词 = 添加
  type = ILF
  classification_basis_index = 从判定原则列表中选择最匹配项

查询垂直行业-查询处理开发
  命中关键词 = 查询
  type = EQ
  classification_basis_index = 从判定原则列表中选择最匹配项

导出垂直行业列表-导出处理开发
  命中关键词 = 导出
  type = EO
  classification_basis_index = 从判定原则列表中选择最匹配项

导入垂直行业数据-导入处理开发
  命中关键词 = 导入
  type = EI
  classification_basis_index = 从判定原则列表中选择最匹配项

同步外部接口数据-外部接口处理开发
  命中关键词 = 外部接口
  type = 由 AI 判断；明确引用外部数据组时可为 EIF，否则不机械判定 EIF
  classification_basis_index = 从判定原则列表中选择最匹配项
```

### 11. 改进 AI 响应解析日志

解析失败时记录 warning：

```python
except Exception as exc:
    logger.warning(
        "FPA AI 响应解析失败 [%s]: %s，响应片段=%s",
        row_tag,
        exc,
        resp[:300],
    )
```

字段缺失时记录 warning：

```python
if _basis is None:
    logger.warning("FPA AI 未返回有效归类 [%s]，序号=%s，响应片段=%s", row_tag, _idx, resp[:300])
```

建议不要因为单个三级模块 AI 失败中断整个任务。

### 12. 修正统计

将 `_filled_count` 改为三级模块规划统计：

```python
attempted_module_count = 0
success_module_count = 0
parse_failed_count = 0
empty_response_count = 0
generated_row_count = 0
fallback_row_count = 0
```

递增时机：

```text
attempted_module_count：调用 LLM 前递增
empty_response_count：LLM 返回空时递增
parse_failed_count：JSON 解析异常时递增
success_module_count：成功生成至少一行合法 FPA 行时递增
generated_row_count：AI 最终生成的合法行数
fallback_row_count：兜底生成的行数
```

日志示例：

```text
FPA AI 规划完成: 尝试 5 个三级模块，成功 4 个，空响应 0 个，解析失败 1 个，AI 生成 28 行，兜底生成 6 行
```

如果全部失败，日志应为 warning。

### 13. 动态读取判定原则

把固定范围：

```python
for row_num in range(2, 15):
```

改成：

```python
for row_num in range(2, ws.max_row + 1):
```

并跳过空值。

### 14. AI 缓存策略

三级模块逐个调用 AI 后，较大项目会带来成本和耗时。建议设计缓存，但第一版可以只保留接口，不强制启用。

缓存键：

```text
hash(
  FPA_CORE_RULES
  + domain_context
  + 三级模块上下文
  + 功能过程列表
  + 判定原则列表
  + model
)
```

缓存文件建议：

```text
md/fpa_ai_cache.json
```

缓存策略：

```text
正式 gen-fpa 可写入和读取缓存。
预览模式默认不写缓存，避免调试结果污染正式缓存。
预览模式可增加 --use-preview-cache / --keep-preview-files 作为后续增强。
当输入 hash 变化时，必须重新调用 AI。
缓存命中时日志应明确标记 cache_hit。
```

### 15. 增加 AI 规划测试

新增测试文件：

```text
tests/test_gen_fpa_ai.py
```

建议覆盖：

1. 三级模块整体规划：

```json
{
  "rows": [
    {"name":"垂直行业管理界面开发","type":"EI","type_reason":"该行描述用户界面交互和页面组件能力。","classification_basis_index":1,"explanation":"..."},
    {"name":"添加垂直行业-逻辑接口开发","type":"ILF","type_reason":"该行描述内部业务数据维护逻辑。","classification_basis_index":1,"explanation":"..."}
  ]
}
```

断言：

```text
界面行只有 1 行
非界面业务动作行按动作生成多行
合法 AI type 能被采用
计算依据归类能从 index 映射
```

2. Markdown code block：

````text
```json
{"rows":[...]}
```
````

断言仍能解析。

3. 非法 JSON：

```text
这里不是 JSON
```

断言：

```text
不中断
原三级模块走兜底生成
日志包含“FPA AI 响应解析失败”
触发兜底行生成
```

4. 越界 index：

```json
{"classification_basis_index":99,"explanation":"..."}
```

断言：

```text
计算依据归类不乱填
日志有 warning
```

5. 空响应：

断言：

```text
不中断
统计中 empty_response_count 增加
触发兜底行生成
```

6. AI 输出过细界面行：

AI 返回多个名称包含“界面开发”的行时，第一阶段建议记录 warning，并只保留第一条或合并为一条。

断言：

```text
无 split_reason 时，最终同一三级模块只有 1 条界面开发行
有有效 split_reason 时，允许保留多条界面开发行
```

7. 类型兜底关键词判定：

断言：

```text
名称包含“界面开发” -> EI
名称包含“添加/编辑/删除/维护/保存” -> ILF
名称包含“查询/查看/详情/列表检索” -> EQ
名称包含“导出” -> EO
名称包含“导入” -> EI
名称包含“外部接口” -> 记录 warning；明确引用外部数据组时按 EIF，否则不机械判定 EIF
```

8. AI type 与关键词不一致：

断言：

```text
轻微不一致时记录 warning，保留 AI type 和 type_reason
明显冲突时使用关键词兜底
```

### 16. Golden Case 验收样例

除单元测试外，应保留少量固定业务样例，用于人工验收 AI 输出质量。建议至少包含：

```text
垂直行业管理：验证三级模块界面合并、添加/编辑/删除为 ILF、查询为 EQ。
导入类模块：验证导入通常为 EI，且说明体现外部数据进入并维护内部数据。
外部用户中心引用模块：验证引用统一用户中心人员账号时可识别 EIF，短信/支付/OCR 等外部服务不直接判 EIF。
复杂多界面模块：验证只有独立页面、独立业务对象、独立流程、独立端才允许拆多条界面开发行。
```

Golden Case 验收标准：

```text
不出现按按钮、弹窗、查询条件拆碎界面行。
不把查询默认判为 ILF。
不把外部接口调用默认判为 EIF。
不把数据库表、字段、保存表动作单独生成功能点。
explanation 能对应输入功能过程，不编造不存在的业务。
```

## 第二阶段：汇总值一致性

### 已确认方向

第二阶段不把“Excel 公式自动计算”作为默认依赖。默认方案应把 FPA 汇总口径代码化：

```text
同一套 Python 业务计算规则
  -> 得出 FPA 工作量总和
  -> 写入 1.2.gen-fpa-FPA工作量-总和.md
  -> 供 pipeline 后续步骤稳定使用
```

核心目标是：

```text
MD 汇总值、pipeline result.fpa_reduced、后续 COSMIC/List 使用值来自同一套代码计算规则。
FPA Excel 保留模板原有逐行公式和汇总公式，不用静态数值覆盖。
```

### 问题

当前 `1.2.gen-fpa-FPA工作量-总和.md` 在 Excel 生成前写入，汇总来自 MD 行的 `调整值 × 要素数量`。

最终 Excel 模板中可能存在自己的公式、基准值映射、工作量公式、隐藏列或汇总单元格，因此会产生风险：

```text
MD 汇总值 != Excel 最终显示值
pipeline 传给后续步骤的 fpa_reduced != 用户在 Excel 中看到的值
```

### 不推荐默认依赖 Excel 公式引擎

`openpyxl` 不会重新计算公式，只会读取公式或已有缓存值。

如果不用 `openpyxl` 计算公式，也可以选择：

```text
Excel COM：最接近 Microsoft Excel 实际显示，但依赖 Windows + Office。
LibreOffice headless：可服务器化，但和 Excel 公式兼容性不是 100%。
第三方公式计算库：无 Office 依赖，但 Excel 函数兼容范围有限。
```

这些方案适合作为“校验模式”或“可选复算模式”，不适合作为默认主流程依赖。

### 推荐默认方案

第二阶段默认实现应为：

```text
1. 明确 FPA 行级工作量计算口径。
2. 在代码中实现 calculate_fpa_total(rows, profile)。
3. MD 汇总和 pipeline result 使用 calculate_fpa_total 的结果。
4. Excel 模板中的逐行工作量公式和汇总公式继续保留。
5. 测试中断言 MD 汇总值与 result.fpa_reduced 一致，并断言 Excel 公式未被静态数值覆盖。
```

建议函数形态：

```python
def calculate_fpa_row_workload(row: dict[str, object]) -> float:
    return float(row.get("调整值", 0)) * float(row.get("要素数量", 0))


def calculate_fpa_total(rows: list[dict[str, object]]) -> float:
    return sum(calculate_fpa_row_workload(row) for row in rows)
```

如果后续确认 Excel 模板实际公式不是 `调整值 × 要素数量`，则应把模板公式背后的业务规则翻译成 Python 规则，而不是依赖 Excel 引擎隐式计算。

### 可选校验模式

可后续增加可选配置：

```yaml
fpa_excel_recalc_check: none
```

可选值：

```text
none：默认，不调用外部 Excel 引擎。
excel_com：Windows + Microsoft Excel 环境下打开、重算、保存后读取结果。
libreoffice：使用 soffice --headless 重算后读取结果。
```

校验模式只做对比和 warning：

```text
代码计算汇总值 != Excel/LibreOffice 复算值
  -> 记录 warning
  -> 不默认覆盖主流程结果
```

### 第二阶段验收标准

```text
gen-fpa 后，1.2.gen-fpa-FPA工作量-总和.md 与 result.fpa_reduced 一致。
生成的 FPA Excel 仍保留逐行工作量公式和汇总公式。
gen-all 后续 COSMIC/List 使用的 FPA 值来自代码汇总。
custom_rules 与 strict_fpa 都通过一致性测试。
不要求本机安装 Excel 或 LibreOffice 才能跑通默认流程。
```

## 第三阶段：类型判断规则精细化

第一阶段已经支持 AI 判断以下类型，并使用关键词规则兜底：

```text
EI
ILF
EO
EQ
EIF
```

第三阶段可进一步精细化类型判断和冲突处理规则：

```text
查询类动作在什么情况下采用 EQ，什么情况下采用 ILF。
导入类动作在什么情况下采用 EI，什么情况下极少数可考虑 EQ。
导出类动作在什么情况下采用 EO，什么情况下采用 ILF。
外部接口类动作在什么情况下采用 EIF。
AI type 与关键词兜底不一致时，哪些属于明显冲突。
模板中的基准值公式是否完整支持这些类型组合。
```

## 调试能力：单三级模块 FPA 预览

### 背景

`gen-fpa` 改为“三级模块整体规划”后，需要一个快速验证能力：

```text
只选择 1 个三级模块
只调用这 1 个三级模块的 FPA AI 规划
立即展示规划结果
不写入正式 FPA Excel
不产生完整交付物
```

这个能力用于调试 prompt、拆分规则、类型判断和说明质量，不应混入正式生成流程。

### 目标

1. 快速验证某个三级模块的 FPA 拆分结果。
2. 立即展示 AI 返回的行列表、类型、类型理由、归类、说明。
3. 不写入 `FPA工作量评估.xlsx`。
4. 不更新 `1.2.gen-fpa-FPA工作量-总和.md`。
5. 不写运行历史，不进入交付物下载列表。
6. 可在 CLI 和 Web UI 中使用。

### 非目标

1. 不替代正式 `gen-fpa`。
2. 不生成完整 Excel。
3. 不做整项目 FPA 汇总。
4. 不修改正式输出目录中的已有交付物。

### 建议命名

CLI 参数：

```powershell
ard --from-excel 功能清单.xlsx --preview-fpa-module "垂直行业管理"
```

可选参数：

```powershell
ard --from-excel 功能清单.xlsx --preview-fpa-module "垂直行业管理" --json
ard --from-excel 功能清单.xlsx --preview-fpa-module-index 1
```

Web API：

```http
POST /api/fpa/preview-module
```

Web UI：

```text
FPA 预览
选择三级模块
生成预览
展示结果表
```

### 核心流程

预览模式流程：

```text
读取功能清单 Excel
  -> 生成或读取基础 MD 数据
  -> 按三级模块聚合功能过程
  -> 定位目标三级模块
  -> 读取 FPA 判定原则
  -> 调用 _ai_plan_fpa_rows_for_l3()
  -> 校验、规范化、类型兜底
  -> 返回 PreviewResult
  -> CLI/Web 直接展示
```

预览模式不执行：

```text
generate_fpa_xlsx_from_md()
写入 FPA Excel
写入 FPA 总和 MD
写入运行历史
打包 zip
```

### 复用与新增函数

建议新增公共函数：

```python
def preview_fpa_module(
    *,
    file_path: str,
    module_name: str = "",
    module_index: int | None = None,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    template_path: str = "",
    work_dir: str = "",
) -> dict:
    ...
```

返回结构：

```json
{
  "module": {
    "client_type": "地市后台",
    "l1": "垂直行业营销",
    "l2": "垂直行业管理",
    "l3": "垂直行业管理",
    "process_count": 6
  },
  "rows": [
    {
      "name": "垂直行业管理界面开发",
      "type": "EI",
      "type_reason": "...",
      "classification_basis": "...",
      "classification_basis_index": 1,
      "explanation": "...",
      "source_processes": ["添加垂直行业", "编辑垂直行业", "查询垂直行业"],
      "generation": "ai"
    }
  ],
  "warnings": [],
  "used_ai": true
}
```

内部应复用：

```text
generate_md_files()
parse_module_tree_md()
_group_rows_by_l3()
FPA 核心规则 prompt 片段
领域上下文构建/读取逻辑
_ai_plan_fpa_rows_for_l3()
_fallback_fpa_rows_for_l3()
FPA 判定原则读取逻辑
类型校验与兜底逻辑
```

### 工作目录策略

预览模式虽然不写 Excel，但第一版仍可能需要目录。原因是现有基础数据流程依赖：

```python
generate_md_files(file_path, md_dir)
```

该函数会把功能清单 Excel 转成中间 MD 文件，例如：

```text
0.1.gen-basedata-功能清单-模块树.md
0.2.gen-basedata-录入文档元数据-模板.md
0.4.gen-basedata-AI填充-录入文档元数据.md
```

后续 FPA 预览需要从模块树数据中按三级模块聚合。如果直接复用正式输出目录，就可能产生或覆盖：

```text
md/0.1.gen-basedata-功能清单-模块树.md
md/0.2.gen-basedata-录入文档元数据-模板.md
```

这会污染正式输出目录。因此第一版建议使用临时目录。

#### 方案 A：复用现有 MD 生成流程

流程：

```text
创建临时目录
  -> generate_md_files(file_path, temp_md_dir)
  -> parse_module_tree_md(temp_tree_md)
  -> 按三级模块聚合
  -> 执行 FPA 预览
  -> 清理临时目录
```

优点：

```text
复用现有代码。
改动小。
风险低。
与正式流程的数据来源一致。
```

缺点：

```text
需要临时目录。
仍会产生临时 MD 文件。
需要处理临时目录清理。
```

第一版建议采用方案 A。

临时目录策略：

```text
CLI：系统临时目录 / ard-fpa-preview-*
Web 本机：系统临时目录 / ard-fpa-preview-*
Web 远程：session work_dir 下的 preview 子目录
```

保留策略：

```text
CLI 预览结束后默认清理临时目录。
Web 预览跟随 session 临时目录清理。
如果需要排查，可增加 --keep-preview-files。
```

#### 方案 B：纯内存读取 Excel

后续可新增纯内存解析函数，绕过 MD 文件：

```python
def read_module_tree_rows_from_excel(file_path: str) -> list[dict[str, str]]:
    ...
```

流程：

```text
读取功能清单 Excel
  -> 直接解析功能清单行
  -> 按三级模块聚合
  -> 执行 FPA 预览
  -> 直接返回结果
```

优点：

```text
不需要临时目录。
不会产生任何中间文件。
预览模式更干净。
更符合“只看结果、不写文件”的直觉。
```

缺点：

```text
需要抽取或复写现有 Excel -> 模块树解析逻辑。
需要确保与正式 generate_md_files() 的解析口径完全一致。
测试范围更大。
```

方案 B 适合作为第二步优化。第一版先用方案 A 跑通预览能力，等预览稳定后，再把 Excel 解析逻辑抽成纯内存公共函数，让正式流程和预览流程共同复用。

### CLI 展示格式

默认表格输出：

```text
三级模块：垂直行业管理
功能过程数：6

序号  类型  功能点名称                         归类
1     EI    垂直行业管理界面开发               ...
2     ILF   添加垂直行业-逻辑处理开发          ...
3     ILF   编辑垂直行业-逻辑处理开发          ...
4     EQ    查询垂直行业-查询处理开发          ...

说明：
[1] 垂直行业管理界面开发
...
```

`--json` 输出完整结构，便于测试和排查。

### Web UI 展示格式

建议在开发/高级区域增加“FPA 预览”入口：

```text
三级模块下拉框
预览按钮
结果表格
说明详情
warning 列表
```

结果表格列：

```text
序号
类型
新增/修改功能点
类型理由
计算依据归类
计算依据说明
生成方式
```

### 错误处理

需要明确错误：

```text
未找到功能清单。
未找到三级模块。
存在多个同名三级模块，请用 module_index 指定。
未配置 FPA 模板，无法读取判定原则。
AI 调用失败，已使用兜底生成。
AI 返回 JSON 无法解析，已使用兜底生成。
```

### 测试要求

新增测试：

```text
tests/test_gen_fpa_preview.py
```

覆盖：

```text
按三级模块名称预览成功。
同名三级模块时提示使用 index。
AI 成功时返回 AI 行。
AI 失败时返回 fallback 行。
预览模式不生成 FPA Excel。
预览模式不写运行历史。
--json 输出可解析。
```

Web 测试可覆盖：

```text
POST /api/fpa/preview-module 返回 rows。
远程模式下只使用当前用户 session 临时目录。
```

## 具体实施清单

### 第一阶段实施项

1. 新增三级模块聚合函数。
2. 将 `_build_fpa_rule_rows()` 从“功能过程固定拆两行”改为“三级模块整体生成 FPA 行”。
3. 新增三级模块 AI 规划函数。
4. Prompt 明确界面合并、接口按动作拆分。
5. 新增 FPA 核心规则 prompt 片段，并注入 FPA AI prompt。
6. 新增领域上下文构建/读取逻辑，并注入 FPA AI prompt。
7. 新增 AI 失败兜底生成逻辑。
8. FPA MD 增加审计列，Excel 生成忽略审计列。
9. FPA MD 读取使用新审计列格式，不保留旧 10 列兼容路径。
10. 新增 AI 输出 JSON Schema 校验和后处理逻辑。
11. 修复 JSON 解析失败静默问题。
12. 修正 `_filled_count` 统计语义，改为三级模块统计。
13. 判定原则读取范围改为 `ws.max_row`。
14. 预留 AI 缓存接口，正式模式可写入 `md/fpa_ai_cache.json`。
15. 新增单三级模块 FPA 预览函数。
16. 新增 CLI `--preview-fpa-module` / `--preview-fpa-module-index`。
17. 新增 Web 预览 API 和 UI 入口。
18. 增加 `tests/test_gen_fpa_ai.py` 和 `tests/test_gen_fpa_preview.py`。
19. 增加 Golden Case 验收样例。
20. 跑现有测试：

```powershell
.\scripts\test.ps1 tests/test_gen_xlsx.py tests/test_pipeline.py tests/test_gen_fpa_ai.py tests/test_gen_fpa_preview.py
```

### 第二阶段实施项

1. 实现代码化 FPA 汇总规则，例如 `calculate_fpa_total(rows, profile)`。
2. 让 MD 汇总和 pipeline result 使用同一代码计算结果。
3. 保留 Excel 模板逐行公式和汇总公式，不把 Excel 公式引擎作为默认依赖。
4. 增加汇总一致性测试，覆盖 custom_rules 和 strict_fpa。
5. 可选增加 Excel COM / LibreOffice 复算校验模式，只记录 warning。

### 第三阶段实施项

1. 复核 AI type 与关键词兜底规则是否符合模板口径。
2. 必要时增加可配置类型映射表和冲突规则表。
3. 增加复杂关键词优先级与 AI 冲突处理测试。
4. 对比不同类型策略下的 Excel 公式结果。

## 验收标准

### 功能验收

1. `gen-fpa` 能正常生成：

```text
1.1.gen-fpa-FPA-模板.md
1.3.gen-fpa-AI填充-FPA.md
FPA工作量评估.xlsx
```

2. 有 API Key 时，每个三级模块调用一次 AI 规划 FPA 行。
3. 无 API Key 时，仍能生成规则骨架 Excel。
4. AI 返回异常时，任务不中断，并在日志中可见。
5. 同一三级模块下界面类功能默认合并为 1 行。
6. 非界面逻辑接口按功能动作拆分。
7. 新增表、保存表等数据表动作不会单独造行。
8. type 优先采用 AI 专业判断，代码负责合法性校验和关键词兜底。
9. AI 失败时有兜底行。
10. AI prompt 中包含 FPA 核心规则，减少不同模型对 FPA 口径的偏差。
11. AI prompt 中包含领域上下文，能辅助判断 ILF/EIF/EI/EQ/EO。
12. AI 输出经过 JSON Schema 校验和后处理，不合法结果有 warning 和兜底。
13. FPA MD 使用新审计列格式；Excel 生成忽略审计列，只写入模板业务列。
14. 单三级模块预览能立即展示结果，且不生成 FPA Excel。
15. 判定原则超过 13 条时也能被读取。
16. Golden Case 样例输出符合预期。

### 测试验收

至少通过：

```powershell
.\scripts\test.ps1 tests/test_gen_xlsx.py tests/test_pipeline.py tests/test_gen_fpa_ai.py
```

如涉及 Web 流程，还需通过：

```powershell
.\scripts\test.ps1 tests/test_web_tasks.py
npm run build
```

### 日志验收

成功日志应能区分：

```text
尝试调用三级模块数
成功规划三级模块数
空响应行数
解析失败行数
AI 生成行数
兜底生成行数
因配置跳过的三级模块数
缓存命中数
后处理 warning 数
```

失败日志应包含：

```text
row_tag
异常信息
响应片段
```

## 推荐推进顺序

第一阶段已经完成基础版：`gen-fpa` 已改为三级模块整体规划，支持 custom_rules / strict_fpa 两套 profile。

第二阶段已经完成基础版：默认采用代码化业务计算规则，Excel 继续保留模板公式，Excel/LibreOffice 复算只作为可选校验。

后续增强事项当前暂缓推进。完整任务池和恢复推进指令统一记录在：

```text
docs/dev/gen-fpa-implementation-notes.md
```

对应章节：

```text
暂缓推进任务池
后续恢复指令
```
