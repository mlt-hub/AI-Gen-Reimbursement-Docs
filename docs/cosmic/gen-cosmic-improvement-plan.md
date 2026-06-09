# gen-cosmic 改进方案

## 背景

当前 `gen-cosmic` 是批处理式初稿生成链路：模块树输入、AI 生成、Markdown 中间稿、再解析 Markdown 写入 Excel。它可以产出 COSMIC 拆分草稿，但与 `软评填报参考手册2024` 的送审口径仍存在差距。

本方案目标是把 `gen-cosmic` 从“可生成初稿”改造成“送审规则驱动、可审阅、可追踪、可验证”的 COSMIC 生成器。

## 目标行为

生成结果应明确区分三种状态：

| 状态 | 含义 | 后续动作 |
| --- | --- | --- |
| `通过` | 满足手册硬性规则，可写入正式 Excel。 | 生成正式产物。 |
| `待审` | 存在业务口径不确定项，但可供人工确认。 | 进入审阅或写入带标记草稿。 |
| `阻断` | 违反硬性规则，不应直接作为送审结果。 | 停止正式 Excel 写入，输出校验报告。 |

硬性规则至少包括：

1. 功能过程必须有触发事件。
2. 第一个子过程必须为输入 `E`。
3. 最后一个子过程必须为写 `W` 或输出 `X`。
4. 一个功能过程至少包含两个子过程及相应数据移动。
5. 一个功能过程必须完全属于一个模块，不能跨多个模块。
6. 功能用户的发起者或接收者之一必须能对应功能架构图上的最小颗粒度模块。

## 总体改造方向

建议分三层改造：

1. **规则口径层**：将手册规则固化到 prompt、校验器和文档。
2. **结构化结果层**：建立稳定 JSON 数据契约，减少 Markdown 作为结构化数据源的职责。
3. **输出审阅层**：根据校验状态决定写正式 Excel、草稿 Excel、审阅报告或预览数据。

目标链路：

```text
模块树 + 元数据
  -> AI structured JSON
  -> CosmicDraft JSON
  -> cosmic_validator
  -> 可审阅 Markdown
  -> Excel / 校验报告 / 预览数据
```

Markdown 保留为人类可读材料，但不再作为主链路唯一结构化数据源。

## 一阶段：规则固化到 prompt

修改范围：

- `config/ai_system_prompts_config.yaml.example`
- 用户配置中的 `cosmic_split` prompt
- `ai_gen_reimbursement_docs/cosmic_ai.py`

需要补充到 COSMIC prompt 的规则：

1. 功能用户的发起者或接收者之一必须对应三级模块或最小颗粒度模块。
2. 前端/后端、前台/后台交互不识别为 COSMIC 边界。
3. 上一页、下一页、排序、展示或隐藏菜单、点击确认等控制命令不计列。
4. 校验、分析、统计、格式化、连接数据库、连接服务器、建立容器等通常不单独作为数据移动。
5. 内部接口只有在调用已开发接口并跨有效边界时才可计列。
6. 非功能内容不得拆成 COSMIC 功能过程。
7. 错误和确认消息应按手册规则合并识别，不能重复计列。

建议要求 AI 输出每个数据移动的依据说明：

```json
{
  "order": 1,
  "sub_process": "提交查询条件",
  "move_type": "E",
  "data_group": "查询条件",
  "data_attrs": "客户编号,时间范围,状态",
  "reuse": "新增",
  "basis": "人类用户向系统提交查询条件，跨越用户与被度量软件边界。"
}
```

`basis` 不直接写入正式 Excel，但用于 Markdown 审阅稿、校验报告和后续预览页。

## 二阶段：新增结构化校验器

新增模块：

- `ai_gen_reimbursement_docs/cosmic_validator.py`
- `tests/test_cosmic_validator.py`

新增结构化 issue 模型：

```python
CosmicIssue(
    severity="error|warning|info",
    code="FIRST_MOVE_NOT_ENTRY",
    message="第一个子过程必须为输入 E",
    field="movements[0].move_type",
)
```

本系统尚未上线，不需要保留旧版本兼容路径。`CosmicItem.warnings` 应删除或停止写入，结构化 `CosmicIssue` 是唯一问题事实源：

```python
CosmicValidationResult(
    item=cosmic_item,
    status="passed|review_required|blocked",
    issues=[...],
)
```

校验分级建议：

| 级别 | 示例 | 行为 |
| --- | --- | --- |
| `error` | 无触发事件、首步非 `E`、末步非 `W/X`、少于两个数据移动、无所属三级模块。 | 阻断正式 Excel。 |
| `warning` | 功能用户泛化、疑似控制命令、疑似数据运算、数据属性过少、内部接口边界不明。 | 进入待审。 |
| `info` | 移动类型由模糊匹配得出、复用度待确认、依据说明缺失。 | 记录提示。 |

第一轮可优先落地确定性规则：

1. `MISSING_TRIGGER`
2. `FIRST_MOVE_NOT_ENTRY`
3. `LAST_MOVE_NOT_WRITE_OR_EXIT`
4. `TOO_FEW_MOVEMENTS`
5. `MISSING_MODULE_PATH`
6. `MISSING_PROCESS_NAME`
7. `EMPTY_DATA_GROUP`
8. `EMPTY_DATA_ATTRS`
9. `NO_COSMIC_ITEMS`
10. `MISSING_CFP_FORMULA`
11. `GENERIC_FUNCTION_USER`

第二轮再做启发式规则：

1. `POSSIBLE_CONTROL_COMMAND`
2. `POSSIBLE_DATA_OPERATION_ONLY`
3. `POSSIBLE_INTERNAL_TECHNICAL_STEP`
4. `UNCLEAR_INTERFACE_BOUNDARY`
5. `POSSIBLE_NON_FUNCTIONAL_SCOPE`

## 三阶段：CFP 口径收口

当前最大业务风险是 CFP 规则来源不唯一：

1. 手册说明每个子过程 CFP 默认 1，优化未改子过程填 0。
2. 当前 `CosmicItem.total_cfp()` 写死 `复用 = 1/3`，其他为 1。
3. Excel 写入又依赖模板中的 `CFP计算公式`。

建议确立唯一准绳：

1. **正式产物以 Excel 模板公式为准。**
2. Python 模型只记录 `reuse`、`cfp_override`、`cfp_basis` 等结构化字段。
3. 如果模板未配置 `CFP计算公式`，必须输出 `MISSING_CFP_FORMULA` error，不能静默留空后继续汇总。
4. `利旧`、`复用`、`优化未改子过程 CFP=0` 的规则应从模板或配置中读取，不应写死在 `CosmicItem.total_cfp()`。

建议后续模型扩展：

```python
DataMovement(
    order=1,
    sub_process="...",
    move_type="E",
    data_group="...",
    data_attrs="...",
    reuse="新增|复用|利旧|不涉及修改",
    cfp_override=None,
    cfp_basis="模板公式计算"
)
```

在未确认 CFP 口径前，不建议继续扩大依赖 `CosmicItem.total_cfp()` 的业务逻辑。

## 四阶段：建立 JSON 草稿产物

新增产物：

| 路径 | 内容 |
| --- | --- |
| `md/3.3.gen-cosmic-AI填充-COSMIC.json` | AI 结构化草稿和校验结果。 |
| `md/3.4.gen-cosmic-校验报告.md` | 面向人工的规则校验报告。 |
| `md/3.3.gen-cosmic-AI填充-COSMIC.md` | 可读审阅稿。 |

建议 JSON 顶层结构：

```json
{
  "project": "...",
  "source": {
    "tree_md": "...",
    "meta_md": "...",
    "manual": "软评填报参考手册2024"
  },
  "items": [
    {
      "module_l1": "...",
      "module_l2": "...",
      "module_l3": "...",
      "user": "...",
      "trigger": "...",
      "process": "...",
      "movements": [],
      "issues": [],
      "status": "passed"
    }
  ],
  "summary": {
    "passed": 0,
    "review_required": 0,
    "blocked": 0
  }
}
```

这样后续 Web 预览、CLI 报告、Excel 写入都使用同一份结构化数据。

## 五阶段：Excel 写入策略

修改范围：

- `ai_gen_reimbursement_docs/gen_cosmic.py`
- `ai_gen_reimbursement_docs/cosmic_writer.py`
- `ai_gen_reimbursement_docs/pipeline.py`

建议策略：

1. 有 `error` 时默认不写正式 Excel。
2. 如需在待审状态写出草稿，可增加 `gen_cosmic.allow_draft_excel_output` 配置，允许写入带标记草稿；草稿不得登记为正式 artifact。
3. `warning` 写入 Excel 批注，并同步写校验报告。
4. CFP 公式缺失时进入阻断，不能无提示继续生成汇总。
5. Excel 写入只接受结构化草稿和校验报告，避免再次从 Markdown 解析引入格式风险。

## 六阶段：预览页准备

COSMIC 预览应等结构化数据契约稳定后再实现。

预览页至少需要展示：

1. 模块路径。
2. 功能用户。
3. 触发事件。
4. 功能过程。
5. 数据移动链。
6. 移动类型。
7. 数据组和数据属性。
8. 复用度和 CFP。
9. 校验问题列表。
10. AI 依据说明。

实现前必须先补充 COSMIC 审阅术语映射，遵循 `docs/fpa/result-review-terminology.md`。不能直接把 FPA 页面术语套到 COSMIC 页面。

## 推荐实施顺序

1. 确认 CFP 口径：模板公式、手册规则、代码汇总三者谁为准。
2. 新增 `cosmic_validator.py`，先做确定性硬规则、全局规则和功能用户泛化 warning。
3. 删除或停止写入现有 `warnings`，统一改为结构化 `CosmicIssue`。
4. 更新 `cosmic_split` prompt，减少明显违规 AI 输出。
5. 新增 JSON 草稿产物和校验报告。
6. 调整 Excel 写入，让正式输出和草稿输出都受校验状态控制。
7. 再评估 `/preview/cosmic` 的数据契约和 UI。

## 测试建议

新增测试应覆盖：

1. 首步不是 `E` 时产生 `error`。
2. 末步不是 `W/X` 时产生 `error`。
3. 少于两个数据移动时产生 `error`。
4. 缺少触发事件时产生 `error`。
5. 功能用户不含三级模块或配置匹配结果时产生 `warning`。
6. 控制命令类子过程产生 `warning` 或被过滤。
7. 数据运算类子过程产生 `warning` 或被过滤。
8. CFP 公式缺失时产生 `MISSING_CFP_FORMULA` error 并进入阻断。
9. 有 `error` 时不写正式 Excel。
10. JSON 草稿、Markdown 审阅稿、Excel 写入使用同一份结构化数据。

## 风险和开放问题

1. CFP 口径必须先确认，否则下游 `gen-list` 的 CFP 总和仍可能不可信。
2. 功能用户“必须对应最小颗粒度模块”的规则需要明确是强制使用三级模块名，还是允许元数据规则映射到业务角色。
3. 内部接口是否计列需要业务上下文，单靠关键词难以完全判断，宜进入待审状态。
4. 非功能内容识别不能只靠 AI，需要模块树或元数据中有明确标记。
5. 预览页不应早于结构化草稿产物，否则会固化当前 Markdown 绕行链路。

## 剩余改进清单

第一阶段结构化校验链路已经落地。以下事项是从当前基线继续走向稳定送审结果的后续改进清单。

### 已完成：结构化主链路落地

当前代码已经完成第一阶段主链路替换：

1. `_generate_cosmic` 直接调用 `generate_cosmic_items` 获取结构化 `list[CosmicItem]`。
2. `cosmic_validator` 产出 `CosmicValidationReport`。
3. `write_cosmic_xlsx` 接收 `CosmicValidationReport`，Excel 批注来自结构化 issue。
4. Markdown 只作为审阅稿和日志，不作为正式管线结构化输入。

### 已完成：正式和草稿产物隔离

正式 Excel 和草稿 Excel 已使用不同路径和不同状态字段。草稿 Excel 可用于人工排查，不登记为正式 artifact，也不更新 `gen-list` 读取的正式 CFP 总和。

已明确并测试：

1. `formal_excel_path` / `formal_excel_written`。
2. `draft_excel_path` / `draft_excel_written`。
3. `cfp_total` 只来自正式 Excel 成功写入后的结果。
4. 上一轮残留正式 Excel 不得被本轮阻断结果误登记。

### 部分完成：空结果和失败状态工程化

无 API Key、AI 生成异常、AI 调用后返回空结果、AI 超限导致全为空、模块树没有三级模块、部分模块失败、结构化结果为空，当前都会进入结构化全局 issue。阶段可以完成，但问题状态会进入 `blocked` 或 `review_required`，不会被登记为无问题正式结果。

当前已区分：

1. `NO_API_KEY`：未设置 API Key。
2. `AI_GENERATION_FAILED`：AI 调用或解析全部失败。
3. `AI_GENERATION_EMPTY`：AI 调用完成但返回空功能过程列表。
4. `AI_LIMIT_SKIPPED_ALL`：配置限制导致全部模块或功能过程跳过。
5. `NO_L3_MODULES`：模块树没有可生成 COSMIC 的三级模块。
6. `AI_L3_LIMIT_PARTIAL_SKIP`：三级模块数量限制导致部分模块跳过。
7. `AI_PROCESS_LIMIT_PARTIAL_SKIP`：功能过程数量限制导致部分功能过程跳过。
8. `USER_ABORTED_GENERATION`：交互模式下用户主动终止生成。
9. `PARTIAL_AI_FAILURE`：部分模块失败但仍有可校验结果。
10. `NO_COSMIC_ITEMS`：最终没有功能过程。

后续仍可进一步区分：

1. `AI_LIMIT_PARTIAL_PLACEHOLDER`：限制跳过后生成了空占位功能过程。
2. `AI_MODULE_PARSE_FAILED`：单个模块响应解析失败。
3. `AI_RETRY_EXHAUSTED`：重试后仍失败。

### P1：CFP 口径收口

`MISSING_CFP_FORMULA` 已实现为 error，并会阻断正式输出；但还需要继续处理以下问题：

1. `CosmicItem.total_cfp()` 中 `复用 = 1/3` 不应作为正式业务口径继续扩散。
2. `复用`、`利旧`、`不涉及修改`、人工覆盖 CFP 的规则需要配置化或模板化；当前确认后 Python CFP 汇总已支持 `gen_cosmic.cfp_policy` 作为组织级默认口径，并允许确认 JSON 的 `cfp_policy` 按项目覆盖。
3. JSON 草稿已经记录报告级 `cfp_basis`，当前可区分模板公式和未确认；后续可扩展到行级人工覆盖。
4. `gen-list` 只能读取正式 CFP 总和。
5. 当前保存确认时可通过 `gen_cosmic.governance.cfp_formula_consistency_check` 启用 `CFP_POLICY_FORMULA_MISMATCH` 诊断；已能解析公式中的简单数字和 `1/3` 分数，后续仍需完整解析 Excel 模板公式、元数据公式和 `cfp_policy_effective` 是否表达一致口径。

### P1：功能用户规则增强

第一阶段已经把功能用户拆分和模块匹配结果记录到 JSON 草稿的 `items[].basis.function_user`，并要求只有匹配三级模块才直接通过；只匹配一/二级模块、泛化角色或未匹配时进入 `GENERIC_FUNCTION_USER` 待审。后续需要把功能用户口径进一步工程化：

1. 明确是否允许元数据规则把业务角色映射到三级模块，而不要求用户文本直接包含三级模块名。
2. 建立“模块路径 -> 可接受功能用户”的判定表；当前后端已支持 `gen_cosmic.governance.function_user_role_map` 作为组织级默认映射，并允许确认 JSON 按项目覆盖。
3. 对一对多、多对一、泛化角色等情况继续给出稳定 issue code，并记录人工确认结果；当前可通过 `gen_cosmic.governance.require_unique_function_user` 启用 `FUNCTION_USER_ROLE_CONFLICT` 诊断。
4. 在预览或审阅页支持人工确认功能用户；当前 `apply_function_user` 动作、角色映射和重校验闭环已落地，后续应补审批流和冲突处理。

### P1：Prompt 和后置校验协同

Prompt 需要和校验器同步升级，减少明显违规输出，而不是只靠后置校验拦截。

当前 prompt 已加入第一版 COSMIC 送审口径硬约束；后置校验也会对内部技术交互、控制命令、纯数据运算/技术操作、错误/确认消息、部分非功能或技术改造事项产生待审 warning，并把命中依据写入 `items[].basis.movement_semantics` 或 `items[].basis.process_semantics`。这些规则已可通过 `gen_cosmic.governance.rule_matrix` 覆盖或扩展。下一步应继续补复杂非功能内容等更依赖上下文的规则，并细分业务错误、持久化读写错误和系统错误消息。

重点规则：

1. 前端/后端、前台/后台交互不识别为 COSMIC 边界；当前后置校验已能产生 `INTERNAL_TECHNICAL_BOUNDARY` 待审项，后续仍需结合接口清单判断是否跨有效边界。
2. 上一页、下一页、排序、展示/隐藏菜单、点击确认等控制命令不计列；当前 prompt 已约束，后置校验已能产生 `CONTROL_COMMAND_MOVEMENT` 待审项。
3. 校验、分析、统计、格式化、连接数据库等通常不单独作为数据移动；当前 prompt 已约束，后置校验已能产生 `DATA_OPERATION_ONLY_MOVEMENT` 待审项。
4. 非功能内容不得拆成 COSMIC 功能过程；当前 prompt 已约束，后置校验已能产生 `NON_FUNCTIONAL_SCOPE` 待审项，后续仍需结合模块树或元数据做更可靠识别。
5. 错误和确认消息按手册规则合并识别；当前后置校验已能产生 `ERROR_CONFIRMATION_MESSAGE` 待审项，后续仍需细分不同错误来源。
6. 当前 `gen_cosmic.governance.auto_apply_review_actions` 和 `auto_apply_issue_codes` 已提供默认关闭的自动建议动作入口；关键词、作用范围、issue code、severity、文案和建议动作已升级为可维护的 `rule_matrix`，后续应补审批和回滚策略。

### P2：COSMIC 预览页

`/preview/cosmic` 应等 JSON 草稿、校验报告、正式/草稿产物状态稳定后再实现。预览页的数据源必须是结构化 JSON，不得读 Markdown 表格。

预览页前置条件：

1. COSMIC 审阅术语映射已补充到 [`docs/fpa/result-review-terminology.md`](../fpa/result-review-terminology.md)，页面必须使用 `新增/修改功能过程`、`数据移动`、`数据移动类型`、`功能用户`、`触发事件`、`审阅项`、`依据` 等 COSMIC 术语。
2. 行级 issue、全局 issue、AI 依据说明都在 JSON 中可用。
3. 人工确认已有最小 JSON 契约：`review_items[].review_id` 作为稳定锚点，`review_items[].confirmation.status` 默认 `unconfirmed`，并预留 `decision/note/confirmed_by/confirmed_at`。
4. 导出策略已有最小 JSON 契约：`export_policy.formal_excel.status` 表示正式 Excel 是否允许导出，`export_policy.draft_excel.status` 表示草稿 Excel 是否不需要、可配置开启或被阻断。当前 `/preview/cosmic` 已支持前端编辑 `review_items[].confirmation` 并导出确认后的 JSON；`/sessions/:sessionId/cosmic/preview` 已支持自动读取任务输出目录内的 COSMIC JSON 草稿，并按 `review_id` 合并已保存的会话级确认 JSON。确认状态会刷新 `confirmation_summary` 和 `export_policy`：warning/info 审阅项全部处理后，正式 Excel 策略进入 `allowed_after_confirmation`；error 级审阅项仍阻断正式输出。会话端点已支持在策略允许时写出 `项目功能点拆分表-确认后.xlsx` 并同步刷新 `md/3.5.gen-cosmic-CFP-总和.md`，远程 session 会刷新下载 ZIP，前端交付物清单和运行历史也会即时显示确认后 Excel 与确认后 CFP 汇总。
5. 预览列表已有最小 JSON 契约：`preview_rows[]` 按功能过程提供模块路径、功能用户、触发事件、数据移动数量、状态、issue 数量和关联 `review_id`，前端列表页不需要自行把 `items` 与 `review_items` 二次关联。

### P2：真实样例回归集

除单元测试外，需要准备小型固定样例覆盖：

1. 全部通过。
2. 只有 warning，生成草稿 Excel。
3. blocked，不写正式 Excel。
4. 无 API Key。
5. AI 空结果。
6. 缺 CFP 公式。
7. 功能用户泛化。
8. 控制命令、内部技术步骤、非功能事项等启发式规则。
