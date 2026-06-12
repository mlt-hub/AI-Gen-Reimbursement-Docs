# gen-fpa 高级参数遮挡修复方案

日期：2026-06-12

## 问题

生成页选择 `gen-fpa` 后，展开“高级参数”区域时，下方“执行监控”面板会遮住高级参数内容。用户无法稳定查看或操作高级参数底部字段。

## 目标行为

- “高级参数”展开后应完整占据自然高度。
- “执行监控”面板应始终位于主操作区之后，不覆盖高级参数。
- 页面整体可以自然滚动，执行监控内部的阶段进展和日志仍保持可滚动。
- 修复不改变生成任务、FPA 参数、执行监控数据等业务逻辑。

## 相关文件范围

- `web_app/src/views/Home.vue`
  - 生成页主布局。
  - 包含“主操作区”、“高级参数”和“执行监控”面板。
- `web_app/src/components/run/FpaRunSettingsSection.vue`
  - FPA 高级参数区域。
  - 当前无需调整业务表单，只作为展开内容的高度来源。
- `web_app/src/components/GenerationProgress.vue`
  - 执行监控中的阶段进展与产物区域。
  - 当前无需调整数据展示逻辑，只需确认滚动行为未被破坏。

## 诊断假设

1. 最可能原因：`Home.vue` 根容器和外层 `AppShell` 都使用固定视口高度与滚动容器组合，执行监控区又设置了最小高度。高级参数展开后，上下区块的高度分配不够自然，导致执行监控区视觉上覆盖高级参数。
2. 次可能原因：主操作区使用 `min-h-0`，在纵向 flex 布局中允许被压缩，展开后的高级参数没有稳定保留完整高度。
3. 较低可能原因：执行监控区内部的 `overflow-hidden`、`overflow-y-auto` 组合造成局部滚动边界混乱。

## 拟实施方案

仅调整前端布局，不修改业务逻辑。

1. 调整 `Home.vue` 中主操作区的 flex 行为。
   - 主操作区应按内容自然撑高。
   - 可增加 `shrink-0`。
   - 移除或避免会让主操作区在纵向布局中被压缩的 `min-h-0`。

2. 保持执行监控区在文档流中位于主操作区之后。
   - 执行监控不使用覆盖式定位。
   - 保留合理的最小高度。
   - 保留内部内容滚动，避免阶段进展或日志撑爆整页。

3. 复查窄屏和低高度视口。
   - 确认展开高级参数后，底部字段和执行监控之间有明确边界。
   - 确认页面滚动条能访问全部内容。

## 验证方式

1. 启动前端页面。
2. 进入生成页。
3. 选择 `gen-fpa`。
4. 展开“高级参数”。
5. 检查以下状态：
   - 所有高级参数字段完整可见。
   - “执行监控”面板位于高级参数下方，没有覆盖。
   - 未启动任务时的等待态显示正常。
   - 已有执行进度时，阶段进展与产物区域显示正常。
   - “运行详情 / 排错信息”展开后日志区域可滚动。
6. 至少检查桌面宽屏和较矮视口。

## 风险

- 首页整体滚动体验可能发生轻微变化。
- 如果执行监控区内部高度约束过松，运行中阶段卡片可能使页面变长。
- 如果执行监控区内部高度约束过紧，可能影响阶段进展和日志阅读体验。

## 验收标准

- `gen-fpa` 高级参数展开后不再被“执行监控”遮挡。
- 页面不出现双层滚动混乱。
- 生成任务启动、停止、进度展示、日志入口仍可正常使用。

---

# gen-fpa 用户确认机制 profile-aware 修正方案

日期：2026-06-12

## 背景

`gen-fpa` 已支持 `auto`、`cautious`、`strict` 三种用户确认模式。当前确认问题由后置 validator issue 转换而来，例如：

- `validator.split_crud_ei`：维护类 EI 是否合并。
- `validator.split_query_eq`：查询类 EQ 是否合并。
- `validator.ordinary_service_as_eif`：普通服务调用是否生成 EIF。
- `validator.query_as_ei`：只读查询是否按 EQ 计量。
- `validator.explanation_structure`：是否补齐结构化计算依据说明。

现有实现的问题是：确认问题生成逻辑只看 validator issue，不充分理解当前 `profile`、`rule_set` 和行级规则命中结果。因此在 `unified_ui`、`ui_api_mapping` 等 profile 已经明确规定口径时，仍可能继续询问用户。

## 核心问题

确认机制不应重复询问已经由规则体系确定的问题。

需要区分三类情况：

1. 规则已确定：不问，直接执行。
2. 规则冲突或材料不足：才问。
3. 质量或格式问题：不应伪装成业务口径确认。

当前实现把第 1 类和第 3 类也混入确认流程，导致用户被要求确认本来已经确定或应自动处理的问题。

## 目标行为

- 对 `profile`、`rule_set`、manifest 或行级规则命中已经明确规定的口径，不再弹出确认。
- 用户确认只用于真正存在业务歧义、材料不足或规则冲突的问题。
- `strict_fpa` 下仍保留有价值的人工确认能力。
- `unified_ui`、`ui_api_mapping` 下不再要求用户确认 profile 已明确规定的 UI、接口、合并和拆分口径。
- 说明结构、格式补齐等质量问题不走用户确认，改为自动补齐、重试或 warning。

## 需要覆盖的误问类型

### 类型判定误问

`validator.query_as_ei` 会把“查询、列表、查看 + EI”识别为疑点。

但在 `ui_api_mapping` 中：

- `界面开发` 行固定按 `EI`。
- 接口开发或明确接口、后端调用行固定按 `ILF`。

因此 `ui_api_mapping` 的 UI 行不应再询问“是否按 EQ 计量”。

### 合并和拆分误问

`validator.split_crud_ei`、`validator.split_query_eq` 在 `strict_fpa` 下可能有意义。

但在 `unified_ui` 中，如果 profile 已规定三级模块合并界面能力，或者当前行已按统一界面口径生成，就不应再询问“是否合并”。

### 接口和后端行误问

`ui_api_mapping` 的接口开发、后端调用行固定按 `ILF`，不应被普通 EIF 或服务调用确认逻辑打断。

只有输入明确涉及外部系统维护的数据组，且当前规则无法判断边界时，才可以保留 EIF 边界确认。

### rule_set 明确映射后仍问

如果 `fpa_config.yaml` 中的 type mapping、keyword rule、merge/split rule 已经命中，确认层必须知道这是已解析决策，不应再询问同一类型或同一合并口径。

### 说明结构类误问

`validator.explanation_structure` 属于说明质量或格式问题，不是业务口径确认。

即使在 `strict` 模式下，也不应问用户“是否补齐结构化说明”。应改为：

- 自动补齐。
- 触发一次 AI 重试。
- 或作为 warning 输出。

## profile 级策略

### strict_fpa

- 保留 CRUD 合并、查询合并、查询 EI/EQ、EIF 边界等真实口径确认。
- 如果 rule_set 已明确映射类型或合并规则，则不再问同一问题。
- `explanation_structure` 不进入用户确认。

### unified_ui

- 对已由统一界面口径覆盖的 UI 能力、合并和拆分问题不问。
- 对已命中统一界面合并规则的 CRUD/query split 不问。
- 仅保留 profile 未覆盖、材料也不足的边界问题，例如外部数据组 EIF 识别。

### ui_api_mapping

- `界面开发` 行固定 `EI`，不问 `query_as_ei`、`split_query_eq`、`split_crud_ei`。
- 接口开发、后端调用行固定 `ILF`，不问普通服务调用是否 EIF。
- 只有明确外部系统维护数据组证据冲突时，才保留 EIF 边界确认。

## 建议实现

引入一个 profile-aware 的确认策略层，不再让 `fpa_confirmation.py` 直接把 validator issue 裸转换成问题。

建议新增或扩展：

```python
ConfirmationPolicy
```

输入信息：

- `profile_name`
- `rule_set`
- 当前三级模块 `group`
- 当前生成行 `rows`
- validator issues
- rule hits / generation source
- 已确认的 `confirmed_decisions`

输出信息：

- `questions`
- `suppressed_issues`
- `suppression_reasons`

判断顺序：

1. issue 是否已被当前 profile 明确覆盖。
2. issue 是否已被当前 rule_set 明确覆盖。
3. issue 是否只是质量或格式问题。
4. issue 是否是真正需要用户选择口径的业务歧义。
5. 已确认过的 decision 是否可复用。

## 拟修改文件范围

- `ai_gen_reimbursement_docs/fpa_confirmation.py`
  - 增加 profile-aware / rule-aware 的确认过滤逻辑。
  - 调整确认问题文案，避免在非 `strict_fpa` 下出现“按 strict_fpa 口径”的误导。

- `ai_gen_reimbursement_docs/gen_fpa.py`
  - 在批量生成和预览生成两处调用确认问题生成逻辑时，传入 `profile`、`rows` 和必要的规则命中上下文。

- `ai_gen_reimbursement_docs/fpa_validator.py`
  - 如当前 issue metadata 不足，需要补充行名、类型、来源、生成方式或 source row 信息，供确认策略判断是否属于 UI 行、接口行或已命中规则行。

- `tests/test_fpa_confirmation.py`
  - 覆盖 profile-aware 确认策略。

- `tests/test_gen_fpa_ai.py`
  - 覆盖预览接口在 `unified_ui`、`ui_api_mapping` 下不返回误问。

- `tests/test_web_tasks.py`
  - 覆盖批量任务不因已确定口径而暂停等待确认。

## 验证方式

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fpa_confirmation.py
.\.venv\Scripts\python.exe -m pytest tests/test_gen_fpa_ai.py
.\.venv\Scripts\python.exe -m pytest tests/test_web_tasks.py
```

必要时补充针对单个 profile 的端到端预览验证：

1. 选择 `gen-fpa`。
2. 切换到 `unified_ui` 或 `ui_api_mapping`。
3. 设置确认模式为 `cautious` 和 `strict` 分别预览。
4. 确认已由 profile 明确规定的 UI 行、接口行、合并拆分口径不再出现确认问题。
5. 确认真正材料不足的边界问题仍可被提问。

## 风险

- 过滤过宽可能吞掉真实业务歧义。
- issue metadata 不足时，策略层可能无法准确判断某个问题是否已被 profile 覆盖。
- 非 `strict_fpa` profile 的文案如果未同步调整，仍可能误导用户。

第一版应保持保守：只压制能明确证明已经由 profile 或 rule_set 规定的问题；无法证明的仍沿用原确认逻辑。

## 验收标准

- `ui_api_mapping` 的 UI 行固定 `EI`、接口行固定 `ILF`，不再触发类型、查询合并或 CRUD 合并确认。
- `unified_ui` 已明确覆盖的界面能力合并、CRUD/query split 不再触发确认。
- rule_set 明确命中的类型或合并规则不再被重复询问。
- `explanation_structure` 不再作为用户确认问题出现。
- `strict_fpa` 下真实业务歧义确认能力保持可用。
- 预览和批量生成两条链路行为一致。
