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

但默认类型已经由规则骨架生成：

```text
界面开发 -> EI
接口开发 -> ILF
```

让 AI 默认覆盖类型风险较高：

- AI 可能把接口开发误判成 EI、EO 或 EQ。
- 类型变化会影响模板中的基准值公式。
- 类型是规则层决策，AI 更适合补充说明，不宜默认改动。

在新方案下，AI 可以为每行建议 `type`，但必须受规则约束。不能让 AI 任意输出类型。

建议允许的类型规则：

```text
界面开发行：默认 EI
逻辑接口开发行：默认 ILF
查询/读取类动作：可根据判定原则和模板规则在 EQ/EO/ILF 中选择，但第一阶段建议仍以 ILF 保守落地
外部接口/外部文件类：后续可扩展 EIF
```

第一阶段建议先采用保守策略：

```text
AI 输出 type，但代码只接受 EI 和 ILF。
界面开发必须为 EI。
逻辑接口开发必须为 ILF。
其他类型先记录 warning，不直接采用。
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
每个功能过程至少生成 1 行逻辑接口开发 ILF。
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
      "type": "EI",
      "row_kind": "界面开发",
      "classification_basis_index": 1,
      "explanation": "..."
    },
    {
      "name": "添加垂直行业-逻辑接口开发",
      "type": "ILF",
      "row_kind": "逻辑接口开发",
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
type 只能在允许集合内
row_kind 只能是界面开发或逻辑接口开发
classification_basis_index 必须在判定原则范围内
explanation 不能为空，否则使用兜底说明
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
同一三级模块原则上只生成 1 条界面开发行。
除非三级模块下存在多个完全独立页面，第一阶段仍建议保守合并。
不要把列表、查询、按钮、弹窗分别拆成多条界面行。
```

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
2、添加垂直行业-逻辑接口开发：ILF
3、编辑垂直行业-逻辑接口开发：ILF
4、查询垂直行业-逻辑接口开发：ILF
5、删除垂直行业-逻辑接口开发：ILF
6、新增垂直行业管理员-逻辑接口开发：ILF
7、删除垂直行业管理员-逻辑接口开发：ILF
```

新增表、数据表维护、字段保存等不单独生成一行。它们应归属到对应动作中：

```text
有“添加”功能时，新增表/保存数据归属到添加动作。
没有“添加”功能时，归属到最相关的编辑、查询或任意主要动作。
不要为了数据表本身额外生成工作量行。
```

### 5. Prompt 设计

新的 prompt 应以三级模块为单位。

建议格式：

```text
你正在为一个三级模块规划 FPA 工作量评估行。

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
2. 界面类能力原则上合并为 1 行，名称为“{三级模块}界面开发”，类型 EI。
3. 界面说明应覆盖列表、分页、查询条件、按钮、弹窗、状态组件、管理组件等界面元素。
4. 非界面逻辑接口按功能动作拆分，一行一个动作，名称为“动作名-逻辑接口开发”，类型 ILF。
5. 新增表、保存表、字段维护不要单独成行，应归属到添加/编辑/查询等动作中。
6. 不要为了增加工作量而拆分细碎界面行。
7. classification_basis_index 必须从判定原则列表中选择。
8. explanation 必须基于输入的功能过程和描述，不要编造不存在的功能。
9. 只输出 JSON，不要输出 Markdown。

输出格式：
{
  "rows": [
    {
      "name": "三级模块界面开发",
      "type": "EI",
      "row_kind": "界面开发",
      "classification_basis_index": 1,
      "explanation": "..."
    },
    {
      "name": "添加xxx-逻辑接口开发",
      "type": "ILF",
      "row_kind": "逻辑接口开发",
      "classification_basis_index": 2,
      "explanation": "..."
    }
  ]
}
```

### 6. 无 AI 或 AI 失败时的兜底生成

兜底函数：

```python
def _fallback_fpa_rows_for_l3(group: dict[str, object], meta: dict[str, str]) -> list[dict[str, object]]:
    ...
```

兜底规则：

```text
1. 每个三级模块生成 1 行界面开发 EI。
2. 每个功能过程生成 1 行逻辑接口开发 ILF。
3. 如果功能过程名称疑似纯页面查看、列表展示，可不额外生成接口行，第一阶段可先不做智能过滤。
4. 兜底说明使用功能过程名称和描述拼接，不编造细节。
```

这样在无 API Key 或 AI 失败时仍能生成可用的 FPA 骨架。

### 7. FPA MD 表结构

最终 Excel 仍使用原列结构。MD 建议保留现有列，并新增审计列：

```text
来源三级模块
来源功能过程
生成方式
```

其中：

```text
来源三级模块：用于审计该行来自哪个三级模块。
来源功能过程：界面行可填多个功能过程，用顿号或 JSON 字符串；接口行填对应动作。
生成方式：ai 或 fallback。
```

Excel 生成时忽略这些审计列。

### 8. 类型校验策略

第一阶段只允许：

```text
EI
ILF
```

校验规则：

```text
row_kind=界面开发 时，type 必须为 EI。
row_kind=逻辑接口开发 时，type 必须为 ILF。
不符合时记录 warning，并按 row_kind 修正。
```

后续如需支持 EO、EQ、EIF，再结合模板规则单独扩展。

### 9. 改进 AI 响应解析日志

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

### 10. 修正统计

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

### 11. 动态读取判定原则

把固定范围：

```python
for row_num in range(2, 15):
```

改成：

```python
for row_num in range(2, ws.max_row + 1):
```

并跳过空值。

### 12. 增加 AI 规划测试

新增测试文件：

```text
tests/test_gen_fpa_ai.py
```

建议覆盖：

1. 三级模块整体规划：

```json
{
  "rows": [
    {"name":"垂直行业管理界面开发","type":"EI","row_kind":"界面开发","classification_basis_index":1,"explanation":"..."},
    {"name":"添加垂直行业-逻辑接口开发","type":"ILF","row_kind":"逻辑接口开发","classification_basis_index":1,"explanation":"..."}
  ]
}
```

断言：

```text
界面行只有 1 行
接口行按动作生成多行
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

AI 返回多个 `row_kind=界面开发` 时，第一阶段建议记录 warning，并只保留第一条或合并为一条。

断言：

```text
最终同一三级模块只有 1 条界面开发行
```

## 第二阶段：汇总值一致性

### 问题

当前 `1.2.gen-fpa-FPA工作量-总和.md` 在 Excel 生成前写入，可能与最终 Excel 公式计算结果不一致。

### 方案

在 `generate_fpa_xlsx_from_md()` 保存 Excel 后，增加一个可选返回值或独立函数重新计算汇总。

可选实现：

```python
def write_fpa_summary_from_xlsx(fpa_xlsx_path: str, summary_md_path: str) -> float:
    total = read_fpa_xlsx_sum(fpa_xlsx_path)
    with open(summary_md_path, "w", encoding="utf-8") as f:
        f.write("# FPA 工作量\n\n")
        f.write(f"FPA工作量（人/天）: {total}\n")
    return total
```

然后在 `_generate_fpa()` 中：

```python
fpa_xlsx = generate_fpa_xlsx_from_md(...)
result.fpa_reduced = write_fpa_summary_from_xlsx(fpa_xlsx, fpa_sum_md)
```

注意：

- `openpyxl` 不会计算公式。
- 如果 Excel 中 L 列是公式，直接读取保存后的文件可能读不到公式结果。
- 当前项目已有 `read_fpa_xlsx_sum()`，但它依赖 `data_only=True`，对新写公式文件可能不可靠。

因此更稳妥的第一步是根据同一套公式输入在 Python 内计算汇总，或者继续使用当前规则汇总，并在文档中明确其含义是“送审工作量初始估算值”。

建议第二阶段先做需求确认：

```text
FPA工作量总和应以“规则调整值×要素数量”为准，还是以 Excel 最终公式计算值为准？
```

如果以 Excel 公式为准，需要设计公式求值方案。

## 第三阶段：扩展 FPA 类型

第一阶段建议只落 EI 和 ILF。第三阶段可根据模板规则扩展：

```text
EO
EQ
EIF
```

扩展前需要明确：

```text
哪些功能动作可判定为查询类 EQ。
哪些功能动作可判定为输出类 EO。
哪些外部数据或外部接口可判定为 EIF。
模板中的基准值公式是否完整支持这些类型。
```

## 具体实施清单

### 第一阶段实施项

1. 新增三级模块聚合函数。
2. 将 `_build_fpa_rule_rows()` 从“功能过程固定拆两行”改为“三级模块整体生成 FPA 行”。
3. 新增三级模块 AI 规划函数。
4. Prompt 明确界面合并、接口按动作拆分。
5. 新增 AI 失败兜底生成逻辑。
6. FPA MD 增加审计列，Excel 生成忽略审计列。
7. 修复 JSON 解析失败静默问题。
8. 修正 `_filled_count` 统计语义，改为三级模块统计。
9. 判定原则读取范围改为 `ws.max_row`。
10. 增加 `tests/test_gen_fpa_ai.py`。
11. 跑现有测试：

```powershell
.\scripts\test.ps1 tests/test_gen_xlsx.py tests/test_pipeline.py tests/test_gen_fpa_ai.py
```

### 第二阶段实施项

1. 明确 FPA 汇总口径。
2. 如果继续使用规则汇总，重命名或注释说明其含义。
3. 如果使用 Excel 最终值，设计公式求值方案。
4. 增加汇总一致性测试。

### 第三阶段实施项

1. 明确 EO、EQ、EIF 的业务判定规则。
2. 增加类型白名单配置或规则表。
3. 增加类型校验测试。
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
8. AI 输出类型会经过代码校验，不允许任意覆盖。
9. AI 失败时有兜底行。
10. 判定原则超过 13 条时也能被读取。

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
```

失败日志应包含：

```text
row_tag
异常信息
响应片段
```

## 推荐推进顺序

建议先推进第一阶段。这个阶段会改变 FPA 行生成策略，但这是必要改动，因为旧的“每个功能过程固定拆界面和接口”会系统性放大界面工作量。

第二阶段涉及 FPA 汇总口径，建议先确认业务含义再动。

第三阶段属于类型规则扩展，应在 EI/ILF 版本稳定后再做。
