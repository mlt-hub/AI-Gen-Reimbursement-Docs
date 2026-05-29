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

`_build_fpa_rule_rows()` 会把每个功能过程拆成两行：

```text
界面开发：类型 EI，调整值 2，要素数量 1
接口开发：类型 ILF，调整值 1，要素数量 1
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

`_ai_fill_fpa()` 对每一行单独调用一次 LLM。当前 prompt 主要包含：

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

## 主要问题

### 1. AI 输入上下文不足

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

### 2. AI 可以直接覆盖 FPA 类型

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

### 3. JSON 解析失败被静默吞掉

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

### 4. `_filled_count` 统计语义不准确

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

### 5. 判定原则读取范围写死

当前判定原则从模板附录读取：

```python
for row_num in range(2, 15):
    val = ws.cell(row_num, 3).value
```

这意味着只读取 C2 到 C14。

如果模板后续扩展更多判定原则，新增规则不会进入 prompt，AI 只能在旧规则中选择。

### 6. FPA 汇总值可能与最终 Excel 不一致

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

### 7. AI 调用粒度偏细

当前每个 FPA 行调用一次 AI。

一个功能过程会生成两行：

```text
界面开发
接口开发
```

也就是同一个功能过程需要至少两次 AI 调用。

问题：

- 调用成本高。
- 两行说明可能不一致。
- 同一功能过程的上下文无法一起推理。
- 失败恢复和日志分析更复杂。

### 8. 测试覆盖不足

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

## 改进目标

### 稳定性目标

1. AI 填充失败可观测，不静默。
2. FPA 类型默认由规则决定，避免 AI 随意覆盖。
3. 汇总值尽量与最终 Excel 保持一致。
4. 测试覆盖 AI 响应解析和异常路径。

### 质量目标

1. Prompt 使用原始业务上下文。
2. “计算依据说明”更贴近功能过程描述。
3. 判定原则只能从模板规则中选择，减少自造分类。
4. 界面开发和接口开发说明边界更清楚。

### 可控性目标

1. 第一阶段不改变主流程和输出文件结构。
2. 不引入新外部依赖。
3. 保留旧 MD 表格列，避免破坏已有 Excel 生成逻辑。
4. 需要改变 AI 覆盖类型时，必须通过显式配置启用。

## 推荐方案

## 第一阶段：低风险增强

第一阶段只做局部增强，不改变调用粒度。

### 1. 保留功能过程上下文字段

在 `_build_fpa_rule_rows()` 生成每一行时增加内部字段：

```python
"_source": {
    "client_type": client_type,
    "l1": l1,
    "l2": l2,
    "l3": l3,
    "process": proc,
    "process_desc": proc_desc,
    "process_type": proc_type,
    "row_kind": "界面开发" 或 "接口开发",
}
```

这些字段仅用于 AI prompt，不写入最终 Excel。

为了在 MD 往返后仍能保留上下文，有两个选择：

#### 方案 A：扩展 MD 表格列

在 FPA MD 中增加隐藏用途列：

```text
客户端类型
一级模块
二级模块
三级模块
功能过程
功能过程描述
行类型
```

优点：

- 中间文件可读、可审计。
- AI 填充阶段从 MD 读取即可恢复上下文。
- 后续用户手动编辑 MD 时也有上下文。

缺点：

- MD 表格列变多。
- 需要同步调整读取逻辑。

#### 方案 B：生成旁路 JSON

生成：

```text
1.1.gen-fpa-FPA-上下文.json
```

用 `序号` 或 `新增/修改功能点` 关联 FPA 行。

优点：

- 不影响 MD 表格可读性。
- Excel 生成逻辑无需关注上下文列。

缺点：

- 中间文件数量增加。
- 手动修改 MD 时，上下文 JSON 可能与 MD 不一致。

建议采用方案 A。原因是当前项目已经大量使用 MD 作为中间可审计数据，扩展 MD 更符合现有风格。

### 2. 重写 FPA AI prompt

新的 prompt 应包含完整输入上下文。

建议格式：

```text
你正在为 FPA 工作量评估表填写“计算依据归类”和“计算依据说明”。

输入信息：
- 客户端类型：{client_type}
- 一级模块：{l1}
- 二级模块：{l2}
- 三级模块：{l3}
- 功能过程：{process}
- 功能过程类型：{process_type}
- 功能过程描述：{process_desc}
- 当前功能点：{func_point}
- 当前行类型：{row_kind}
- 当前 FPA 类型：{fpa_type}

计算依据归类判定原则列表：
1) ...
2) ...

要求：
1. classification_basis_index 必须从判定原则列表中选择，不能自造。
2. explanation 必须基于“功能过程描述”，不要编造不存在的页面、表、接口。
3. 如果当前行类型是“界面开发”，重点说明用户触发、页面交互、输入输出数据。
4. 如果当前行类型是“接口开发”，重点说明服务调用、数据读取/写入、接口边界。
5. 不要修改当前 FPA 类型。
6. 只输出 JSON，不要输出 Markdown。

输出格式：
{
  "classification_basis_index": 1,
  "explanation": "..."
}
```

### 3. 默认禁止 AI 覆盖类型

第一阶段建议直接移除 AI 覆盖类型逻辑，或者忽略响应中的 `type`。

也可以增加配置项：

```yaml
allow_ai_override_fpa_type: false
```

第一阶段建议先不新增配置，直接默认禁止覆盖。原因：

- 更可控。
- 配置项越少，用户理解成本越低。
- 目前没有明确需求要求 AI 改类型。

如果后续业务确实需要 AI 判断类型，再以第二阶段增强方式补配置。

### 4. 改进 AI 响应解析日志

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

建议不要因为单行 AI 失败中断整个任务。

### 5. 修正填充统计

将 `_filled_count` 改为更准确的统计：

```python
attempted_count = 0
success_count = 0
parse_failed_count = 0
empty_response_count = 0
```

递增时机：

```text
attempted_count：调用 LLM 前递增
empty_response_count：LLM 返回空时递增
parse_failed_count：JSON 解析异常时递增
success_count：至少成功写入“计算依据归类”或“计算依据说明”时递增
```

日志示例：

```text
FPA AI 填充完成: 尝试 10/20 行，成功 8 行，空响应 1 行，解析失败 1 行，跳过 10 行
```

如果全部失败，日志应为 warning。

### 6. 动态读取判定原则

把固定范围：

```python
for row_num in range(2, 15):
```

改成：

```python
for row_num in range(2, ws.max_row + 1):
```

并跳过空值。

### 7. 增加 AI 响应解析测试

新增测试文件：

```text
tests/test_gen_fpa_ai.py
```

建议覆盖：

1. 合法 JSON：

```json
{"classification_basis_index":1,"explanation":"..."}
```

断言：

```text
计算依据归类 = judgement_rules[0]
计算依据说明被填充
类型保持原值
```

2. Markdown code block：

```text
```json
{"classification_basis_index":1,"explanation":"..."}
```
```

断言仍能解析。

3. 非法 JSON：

```text
这里不是 JSON
```

断言：

```text
不中断
原行保留
日志包含“FPA AI 响应解析失败”
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

## 第三阶段：按功能过程批量调用 AI

### 当前方式

```text
每个 FPA 行调用一次 AI
```

一个功能过程至少两次调用：

```text
界面开发行
接口开发行
```

### 目标方式

```text
每个功能过程调用一次 AI
```

输出：

```json
{
  "ui": {
    "classification_basis_index": 1,
    "explanation": "..."
  },
  "interface": {
    "classification_basis_index": 2,
    "explanation": "..."
  }
}
```

### 优点

- 调用次数约减少一半。
- 同一功能过程上下文一致。
- 界面和接口说明可互相区分，减少重复。
- 日志更容易按功能过程定位。

### 风险

- 改动面大于第一阶段。
- 需要调整 `gen_fpa_ai_limit` 的语义。
- 需要更多测试覆盖批量解析。

建议第三阶段再实施。

## 具体实施清单

### 第一阶段实施项

1. 在 FPA MD 中增加上下文列。
2. 修改 MD 读取逻辑，兼容旧 10 列和新扩展列。
3. 重写 `_ai_fill_fpa()` prompt。
4. 忽略 AI 返回的 `type` 字段。
5. 修复 JSON 解析失败静默问题。
6. 修正 `_filled_count` 统计语义。
7. 判定原则读取范围改为 `ws.max_row`。
8. 增加 `tests/test_gen_fpa_ai.py`。
9. 跑现有测试：

```powershell
.\scripts\test.ps1 tests/test_gen_xlsx.py tests/test_pipeline.py tests/test_gen_fpa_ai.py
```

### 第二阶段实施项

1. 明确 FPA 汇总口径。
2. 如果继续使用规则汇总，重命名或注释说明其含义。
3. 如果使用 Excel 最终值，设计公式求值方案。
4. 增加汇总一致性测试。

### 第三阶段实施项

1. 改为按功能过程批量调用 AI。
2. 调整 `gen_fpa_ai_limit` 语义和日志文案。
3. 增加批量响应解析测试。
4. 对比 AI 调用次数和生成质量。

## 验收标准

### 功能验收

1. `gen-fpa` 能正常生成：

```text
1.1.gen-fpa-FPA-模板.md
1.3.gen-fpa-AI填充-FPA.md
FPA工作量评估.xlsx
```

2. 有 API Key 时，F/G 列能基于功能过程描述填充。
3. 无 API Key 时，仍能生成规则骨架 Excel。
4. AI 返回异常时，任务不中断，并在日志中可见。
5. AI 默认不会改变 FPA 类型。
6. 判定原则超过 13 条时也能被读取。

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
尝试调用行数
成功填充行数
空响应行数
解析失败行数
因配置跳过行数
```

失败日志应包含：

```text
row_tag
异常信息
响应片段
```

## 推荐推进顺序

建议先推进第一阶段。它能直接提升生成质量和排障能力，风险较低。

第二阶段涉及 FPA 汇总口径，建议先确认业务含义再动。

第三阶段属于架构优化，收益明显，但应在第一阶段测试稳定后再做。
