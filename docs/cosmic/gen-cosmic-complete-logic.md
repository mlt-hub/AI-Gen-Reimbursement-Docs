# gen-cosmic 完整逻辑说明

## 文档定位

本文面向维护和继续开发 `gen-cosmic` 的工程人员，集中说明当前 COSMIC 生成链路的完整实现逻辑。本文描述的是当前代码事实，不是改造愿景；历史推进记录和待办清单见：

- [`gen-cosmic-current-logic.md`](gen-cosmic-current-logic.md)
- [`gen-cosmic-improvement-plan.md`](gen-cosmic-improvement-plan.md)

核心原则：

1. `gen-cosmic` 的正式事实源是结构化 `CosmicItem`、`CosmicValidationReport` 和 JSON 草稿，不是 Markdown 表格。
2. 批处理阶段先生成结构化草稿，再校验，再按状态决定是否写 Excel。
3. `passed/review_required/blocked` 是产物写入和后续 `gen-list` 能否读取 CFP 总和的关键状态。
4. Web 审阅保存会应用人工或自动审阅动作，再重新校验并刷新导出策略。

## 主链路总览

批处理入口是 `ai_gen_reimbursement_docs.pipeline._generate_cosmic`。它在全流程中负责生成 COSMIC 项目功能点拆分表，并把结果写回 `PipelineResult`。

完整顺序：

1. 校验 COSMIC Excel 模板是否存在。
2. 读取项目名称、FPA 核减后工作量和模块树。
3. 写出 `md/3.1.gen-cosmic-FPA核减后的工作量-总和.md`。
4. 调用 `init_cosmic_template_md` 生成空白 COSMIC Markdown 模板。
5. 如果配置了 API Key，调用 `generate_cosmic_items_with_diagnostics` 生成结构化 `CosmicItem` 列表。
6. 如果没有 API Key，生成全局 issue `NO_API_KEY`，不调用 AI。
7. 读取元数据中的 `CFP计算公式`。
8. 调用 `generate_cosmic_artifacts` 生成 JSON 草稿、审阅 Markdown、校验报告，并按校验状态写正式或草稿 Excel。
9. 将状态、正式 Excel 路径、草稿 Excel 路径、JSON 草稿路径、校验报告路径和 CFP 总和写入 `PipelineResult`。
10. 只有正式 Excel 成功写入时，才写出或刷新 `md/3.5.gen-cosmic-CFP-总和.md`，供后续 `gen-list` 使用。

## 输入来源

### 模块树

模块树来自前序阶段产物，最终由 `build_modules_from_tree_md` 转为 `FunctionModule` 列表。COSMIC AI 只处理 `level == 3` 的三级模块。

### 元数据

元数据来自 `文档元数据.md`，主要用于：

- 项目名称。
- `CFP计算公式`。
- 功能用户默认发起者/接收者规则。
- 环境说明 sheet 中的建设目标、建设必要性。

### 模板

模板来自 `templates_dict['cosmic']`，对应“项目功能点拆分表”模板。Excel 写入由 `cosmic_writer.write_cosmic_xlsx` 负责，并受 cosmic manifest 影响：

- 结果 sheet 名称。
- 表头行、数据起始行、样式源行。
- 字段列映射。
- 命名单元格。
- 合并列、warning 标记列、复用度列、CFP 公式列。

### 运行配置

主要配置项：

| 配置 | 作用 |
| --- | --- |
| `ANTHROPIC_API_KEY` / 传入 API Key | 是否调用 AI。 |
| `ANTHROPIC_BASE_URL`、模型名、`max_tokens` | AI 调用参数。 |
| `flow_max_ai.gen_cosmic` | 限制调用 AI 的三级模块数量。 |
| `gen_cosmic_ai_limit` | 限制调用 AI 的功能过程数量。 |
| `gen_cosmic.allow_draft_excel_output` | `review_required` 时是否允许写草稿 Excel。 |
| `gen_cosmic.cfp_policy` | 确认后 Python CFP 汇总的组织级默认口径。 |
| `gen_cosmic.governance.*` | 自动治理、角色映射、规则矩阵、审计签名、外部 ledger 等。 |

## AI 生成逻辑

AI 入口是 `cosmic_ai.generate_cosmic_items_with_diagnostics`。旧包装函数 `generate_cosmic_items` 仍存在，但正式管线使用带 diagnostics 的版本。

### 三级模块筛选

函数先筛选 `level == 3` 的模块：

- 无三级模块时，不调用 AI，返回空 diagnostics。
- 有三级模块时，根据 `flow_max_ai("gen_cosmic")` 和 `load_gen_cosmic_ai_limit()` 控制调用范围。

### Prompt 内容

每个三级模块会生成一个 prompt，要求模型返回 JSON 数组。Prompt 包含：

- 项目名称。
- 一级、二级、三级模块路径。
- 功能描述和功能过程。
- 功能用户和触发事件默认规则。
- COSMIC 送审口径硬约束。

当前 prompt 已明确约束：

1. 功能用户的发起者或接收者之一必须对应三级模块或最小颗粒度模块。
2. 前端/后端、前台/后台交互不识别为 COSMIC 边界。
3. 上一页、下一页、排序、展示或隐藏菜单、点击确认等控制命令不计列为数据移动。
4. 校验、分析、统计、格式化、连接数据库、连接服务器、建立容器等通常不单独作为数据移动。
5. 非功能内容不得拆成 COSMIC 功能过程。
6. 每个功能过程必须由触发事件启动，且至少包含两个数据移动。

### 响应解析

`_parse_llm_response` 从模型文本中提取 JSON 数组，并转为 `CosmicItem` 和 `DataMovement`。

解析阶段会做基础归一：

- 移动类型模糊匹配为 `E/X/R/W`，并标记 `move_type_flagged`。
- 复用度默认 `新增`。
- 缺数据属性、属性过少、移动数过少、首步非 `E`、末步非 `W/X`、功能过程名为空等会写入旧 `warnings` 字段。

注意：旧 `warnings` 只是兼容字段；正式校验、预览、Excel 标记以结构化 `CosmicIssue` 为准。

### 失败和空结果诊断

AI 调用失败不会直接让 pipeline 崩溃，而是转成全局 issue 后继续写结构化报告。

常见 issue：

| issue code | 含义 |
| --- | --- |
| `NO_API_KEY` | 未配置 API Key，未调用 AI。 |
| `NO_L3_MODULES` | 模块树中没有可生成 COSMIC 的三级模块。 |
| `AI_GENERATION_FAILED` | AI 调用或整体生成失败。 |
| `AI_GENERATION_EMPTY` | AI 未返回可校验功能过程。 |
| `AI_LIMIT_SKIPPED_ALL` | 配置限制导致没有任何三级模块被 AI 处理。 |
| `AI_L3_LIMIT_PARTIAL_SKIP` | 三级模块限制导致部分模块跳过。 |
| `AI_PROCESS_LIMIT_PARTIAL_SKIP` | 功能过程限制导致部分模块跳过。 |
| `AI_LIMIT_PARTIAL_PLACEHOLDER` | 限制跳过后保留了空占位功能过程。 |
| `PARTIAL_AI_FAILURE` | 部分模块失败但仍有可校验结果。 |
| `AI_MODULE_PARSE_FAILED` | 单模块响应解析失败。 |
| `AI_RETRY_EXHAUSTED` | 重试后仍失败。 |
| `USER_ABORTED_GENERATION` | 交互模式下用户主动终止。 |

## 数据模型

### `DataMovement`

表示一次 COSMIC 数据移动：

| 字段 | 含义 |
| --- | --- |
| `order` | 数据移动序号。 |
| `sub_process` | 子过程描述。 |
| `move_type` | 标准移动类型，通常为 `E/X/R/W`。 |
| `data_group` | 数据组。 |
| `data_attrs` | 数据属性。 |
| `reuse` | 复用度，默认 `新增`。 |
| `move_type_flagged` | 移动类型是否由模糊匹配得到。 |
| `cfp_override` | 行级人工 CFP 覆盖值。 |
| `cfp_basis` | 行级 CFP 覆盖依据。 |

### `CosmicItem`

表示一个功能过程：

| 字段 | 含义 |
| --- | --- |
| `project` | 项目名称。 |
| `module_l1/module_l2/module_l3` | 模块路径。 |
| `user` | 功能用户，格式通常为 `发起者：xxx|接收者：xxx`。 |
| `trigger` | 触发事件。 |
| `process` | 功能过程名称。 |
| `movements` | 数据移动列表。 |
| `warnings` | 旧兼容字段，正式链路不以它作为问题事实源。 |

`CosmicItem.total_cfp()` 仍保留旧兼容逻辑：`复用 = 1/3`，其他为 `1`。当前正式链路不依赖它计算正式 CFP；这是后续应清理的旧兼容路径。

### 校验模型

`cosmic_validator.py` 定义：

- `CosmicIssue`
- `CosmicValidationResult`
- `CosmicValidationReport`

`CosmicValidationReport` 是 Excel 写入、JSON 草稿、Markdown 校验报告和 Web 预览的核心报告对象。

## 结构化校验逻辑

主入口是 `validate_cosmic_items`。

### 全局校验

全局校验先于单项校验执行：

- 空 items 产生 `NO_COSMIC_ITEMS`。
- 缺 CFP 公式产生 `MISSING_CFP_FORMULA`。
- pipeline 或 Web 审阅重校验传入的全局 issue 会合并进报告。

### 单功能过程校验

`validate_cosmic_item` 对每个 `CosmicItem` 执行：

1. 模块路径必须完整。
2. 功能过程名称不能为空。
3. 触发事件不能为空。
4. 功能用户必须能匹配三级模块或最小颗粒度模块，否则产生 `GENERIC_FUNCTION_USER`。
5. 启用 `require_unique_function_user` 时，多业务角色冲突产生 `FUNCTION_USER_ROLE_CONFLICT`。
6. 功能过程命中非功能或复杂非功能规则时进入待审。
7. 数据移动少于 2 步产生 error。
8. 首步必须为 `E`。
9. 末步必须为 `W` 或 `X`。
10. 移动类型、数据组、数据属性等基础字段会产生 warning。
11. 数据移动命中控制命令、纯技术操作、内部技术边界、错误/确认消息等规则时产生 warning，并附建议动作。

### 状态计算

状态由 issue severity 决定：

| 状态 | 条件 | 产物策略 |
| --- | --- | --- |
| `passed` | 无 error、无 warning。 | 默认写正式 Excel 和 CFP 总和。 |
| `review_required` | 无 error，但有 warning。 | 默认不写正式 Excel；开启草稿配置后写草稿 Excel。 |
| `blocked` | 有 error 或存在 blocked item。 | 不写正式 Excel，不更新正式 CFP 总和。 |

### 治理规则矩阵

内置规则矩阵覆盖：

- `NON_FUNCTIONAL_SCOPE`
- `COMPLEX_NON_FUNCTIONAL_SCOPE`
- `CONTROL_COMMAND_MOVEMENT`
- `DATA_OPERATION_ONLY_MOVEMENT`
- `ERROR_CONFIRMATION_MESSAGE`
- `INTERNAL_TECHNICAL_BOUNDARY`
- `EXTERNAL_INTERFACE_BOUNDARY_REVIEW`

`gen_cosmic.governance.rule_matrix` 可以覆盖同 code 的内置规则，也可以新增组织级规则。规则字段包括：

- `code`
- `target`: `process` 或 `movement`
- `severity`
- `message`
- `scope_policy`
- `governance_category`
- `description`
- `terms`
- `suggested_actions`

`gen_cosmic.governance.boundary_context` 会把组织级词表并入相关内置规则：

- `external_systems`
- `internal_components`
- `non_functional_terms`
- `valid_boundary_terms`

## 产物生成逻辑

产物入口是 `gen_cosmic.generate_cosmic_artifacts`。

输入：

- `items`
- COSMIC Excel 模板路径。
- 正式 Excel 输出路径。
- 元数据路径。
- `md_dir`
- 项目名称。
- CFP 公式。
- 模块列表。
- 审阅 Markdown 路径。
- 是否允许草稿 Excel。
- 全局 issue。

内部顺序：

1. 调用 `validate_cosmic_items` 得到 `CosmicValidationReport`。
2. 写 `md/3.3.gen-cosmic-AI填充-COSMIC.json`。
3. 写 `md/3.3.gen-cosmic-AI填充-COSMIC.md` 审阅稿。
4. 如果 `passed`，调用 `write_cosmic_xlsx` 写正式 Excel。
5. 如果 `review_required` 且开启 `allow_draft_excel_output`，写草稿 Excel。
6. 其他状态只写 JSON 草稿和校验报告。
7. 写 `md/3.4.gen-cosmic-校验报告.md`。
8. 返回 `CosmicGenerationResult`。

## JSON 草稿结构

JSON 草稿由 `write_cosmic_validation_json` 写出，核心字段包括：

| 字段 | 含义 |
| --- | --- |
| `project` | 项目名称。 |
| `status` | 总状态。 |
| `summary` | passed/review_required/blocked/error/warning 计数。 |
| `issue_codes` | issue code 计数。 |
| `issues` | 全局 issue。 |
| `items` | 功能过程和行级校验结果。 |
| `review_items` | 前端审阅项。 |
| `preview_rows` | 前端列表摘要。 |
| `cfp_basis` | CFP 公式来源说明。 |
| `export_policy` | 确认和导出策略。 |
| `confirmation_summary` | 审阅项确认汇总。 |

Web 保存后还会写入或刷新：

- `review_actions`
- `review_audit`
- `review_audit_hash_chain`
- `cfp_policy`
- `cfp_policy_effective`
- `governance_effective`

## Excel 写入逻辑

Excel 写入入口是 `cosmic_writer.write_cosmic_xlsx`，输入必须是 `CosmicValidationReport`。

核心逻辑：

1. 打开 COSMIC 模板 workbook。
2. 按 manifest 解析结果 sheet、表头行、数据起始行、样式源行和列映射。
3. 删除旧数据区。
4. 将 `CosmicItem.to_rows()` 扁平化为行。
5. 写项目、模块、功能用户、触发事件、功能过程、子过程、移动类型、数据组、数据属性、复用度、CFP 等列。
6. 按模板样式源行复制样式。
7. 合并项目、模块、功能用户、触发事件、功能过程等重复单元格。
8. 写复用度下拉。
9. 写 CFP 公式，公式来自元数据或配置，并替换 `{row}`。
10. 根据结构化 issue 添加 Excel 批注和 warning 标记。
11. 保存 source data 快照，便于排查。
12. 安全保存 workbook。

正式批处理只在 `passed` 时写正式 Excel；`review_required` 写草稿 Excel 需要显式开启配置。

## CFP 逻辑

### 批处理阶段

批处理正式 Excel 的 CFP 以模板公式为准。`generate_cosmic_artifacts` 只有在正式 Excel 成功写出时才刷新 `md/3.5.gen-cosmic-CFP-总和.md`。

缺公式时：

- 产生 `MISSING_CFP_FORMULA`。
- 报告状态进入 `blocked`。
- 不写正式 Excel。
- 不更新正式 CFP 总和。

### 确认后导出阶段

Web 确认后导出会按确认后的结构化 JSON 重新计算 Python 侧 CFP 汇总。

有效 policy 合并顺序：

1. 内置默认值。
2. `gen_cosmic.cfp_policy`。
3. 确认 JSON 顶层 `cfp_policy`。

非法、非数字和负数不会覆盖已确定的有效值。

行级 `cfp_override` 优先级最高。若单条数据移动存在合法 `cfp_override`，确认后 CFP 汇总使用该值，并在 `cfp_basis` 中记录来源。

### 公式一致性诊断

启用 `gen_cosmic.governance.cfp_formula_consistency_check=true` 后，保存确认时会比较：

- 有效 `cfp_policy_effective`。
- 从 Excel 公式中解析出的常见复用度分支。

当前可解析简单数字、`1/3` 分数，以及常见 `IF`、`IFS`、`SWITCH`、`CHOOSE(MATCH(...))`、`XLOOKUP`、`LOOKUP` 分支。无法覆盖完整 Excel 公式语义；完整语义解析和正式审批流仍是后续工作。

## Markdown 逻辑

Markdown 有两个角色：

1. 空白模板：`md/3.2.gen-cosmic-COSMIC-模板.md`。
2. 人类审阅稿：`md/3.3.gen-cosmic-AI填充-COSMIC.md`。

正式管线不再从填充 Markdown 反解析结构化数据。`fill_md_with_ai`、`parse_md_to_items` 仍保留为旧兼容或排查路径，但不应作为新链路事实源。

## Web 审阅逻辑

Web COSMIC 审阅页是 `web_app/src/views/CosmicPreviewPage.vue`，路由为：

- `/sessions/:sessionId/cosmic/preview`

相关 API 在 `web_app/routes/artifacts.py`：

| API | 作用 |
| --- | --- |
| `GET /api/sessions/{session_id}/cosmic/draft` | 读取任务输出目录里的 COSMIC JSON 草稿。 |
| `GET /api/sessions/{session_id}/cosmic/confirmation` | 读取已保存的会话级 COSMIC 确认 JSON。 |
| `PUT /api/sessions/{session_id}/cosmic/confirmation` | 保存确认 JSON，应用审阅动作并重校验。 |
| `POST /api/sessions/{session_id}/cosmic/export-confirmed` | 按确认后的 JSON 导出确认后 Excel。 |

### 页面能力

页面支持：

- 读取任务草稿。
- 合并已保存确认 JSON。
- 查看功能过程、数据移动、状态和审阅项。
- 编辑功能过程、功能用户、触发事件和数据移动。
- 编辑确认状态、决策和备注。
- 应用建议动作。
- 保存确认 JSON。
- 在策略允许时导出确认后 Excel。

### 保存确认时的重校验

`PUT /cosmic/confirmation` 会执行 `_revalidate_cosmic_payload`：

1. 加载 COSMIC governance 配置。
2. 按配置自动应用白名单内审阅动作。
3. 应用 payload 中的 `review_actions`。
4. 写入或更新 `review_audit`。
5. 合并原有 confirmation 状态。
6. 计算 `cfp_policy_effective`。
7. 执行 `validate_cosmic_items` 重校验。
8. 把新状态、issues、basis 回写到原始 `items`。
9. 写入 `governance_effective`。
10. 重新计算 `confirmation_summary` 和 `export_policy`。

## 审阅动作

`review_actions` 是人工或自动治理动作的结构化列表。当前支持：

| action | 作用 |
| --- | --- |
| `apply_function_user` | 应用候选功能用户，或从 `function_user_role_map` 中取组织级映射。 |
| `exclude_movement` | 排除单条数据移动，不进入确认后 Excel 和 CFP 汇总。 |
| `merge_movement` | 将单条数据移动合并到上一条或指定序号。 |
| `exclude_process` | 排除整个功能过程及其所有数据移动。 |
| `set_movement_cfp` | 对单条数据移动设置行级 CFP 覆盖。 |
| `rollback_review_action` | 根据回滚契约恢复功能用户、排除标记、合并标记或 CFP 覆盖。 |

自动治理入口由以下配置控制：

- `gen_cosmic.governance.auto_apply_review_actions`
- `gen_cosmic.governance.auto_apply_issue_codes`

默认关闭。只有显式开启且 issue code 进入白名单时，后端才会自动应用 `review_items[].details.suggested_actions`。

## 审计逻辑

保存确认时 `_stamp_review_audit` 会为已应用动作生成或更新 `review_audit`。

审计记录包含：

- action 信息。
- `approval_status`。
- `confirmed_by`。
- `applied_by`。
- `applied_at`。
- `rollback_action`。
- `previous_audit_hash`。
- `audit_hash`。
- 可选 `audit_signature`。

`approval_status` 默认规则：

- 自动治理动作：`auto_applied`。
- 人工动作：`approved`。
- 如果 action 已显式给出 `approval_status`，则保留。

hash 链默认开启。保存前会校验已有 hash 链或签名；失败时会产生：

- `AUDIT_HASH_CHAIN_INVALID`
- `AUDIT_SIGNATURE_INVALID`

HMAC 签名由 `gen_cosmic.governance.audit_signature_secret_env` 指定的环境变量控制，默认环境变量名是 `COSMIC_REVIEW_AUDIT_SIGNING_KEY`。

外部追加式 ledger 由 `gen_cosmic.governance.audit_ledger_path_env` 指定，默认环境变量名是 `COSMIC_REVIEW_AUDIT_LEDGER_PATH`。当前 ledger 是 JSONL 镜像，不等价于真正 WORM 或第三方不可篡改存储。

## 确认后导出逻辑

`POST /api/sessions/{session_id}/cosmic/export-confirmed` 的流程：

1. 找到任务 COSMIC JSON 草稿。
2. 优先读取 `cosmic-confirmation.json`，不存在则读取草稿。
3. 读取 CFP 公式。
4. 应用 `review_actions`。
5. 计算 `export_policy`。
6. 只有 `formal_excel.status` 为 `allowed` 或 `allowed_after_confirmation` 时允许导出。
7. 读取 COSMIC Excel 模板。
8. 将确认后的 payload 转为 `CosmicValidationReport`。
9. 写出 `cosmic文档/项目功能点拆分表-确认后.xlsx`。
10. 按确认后的非排除数据移动和 `cfp_policy_effective` 计算 CFP 总和。
11. 写出 `md/3.5.gen-cosmic-CFP-总和.md`。
12. 更新 session 交付物列表。
13. 远程 session 会刷新下载 ZIP。

确认后导出不覆盖原批处理正式 Excel。

## 治理配置页面

Web 配置页 `Config.vue` 已有 COSMIC 治理专用区域。后端 API：

- `GET /api/web-config/cosmic-governance`
- `PUT /api/web-config/cosmic-governance`

读写位置是 `system_config.yaml` 中的：

- `gen_cosmic.allow_draft_excel_output`
- `gen_cosmic.cfp_policy`
- `gen_cosmic.governance.auto_apply_review_actions`
- `gen_cosmic.governance.auto_apply_issue_codes`
- `gen_cosmic.governance.function_user_role_map`
- `gen_cosmic.governance.require_unique_function_user`
- `gen_cosmic.governance.cfp_formula_consistency_check`
- `gen_cosmic.governance.audit_hash_chain`
- `gen_cosmic.governance.audit_signature_secret_env`
- `gen_cosmic.governance.audit_ledger_path_env`
- `gen_cosmic.governance.boundary_context`
- `gen_cosmic.governance.rule_matrix`

保存时会：

1. 校验 payload。
2. 保留 `system_config.yaml` 其他未知键。
3. 保存前备份。
4. 写配置审计。
5. 清理配置缓存。

## 主要文件职责

| 文件 | 职责 |
| --- | --- |
| `ai_gen_reimbursement_docs/pipeline.py` | 编排 gen-cosmic 阶段，处理 AI diagnostics 和 PipelineResult。 |
| `ai_gen_reimbursement_docs/gen_cosmic.py` | 生成 COSMIC 模板、结构化产物、校验报告、正式/草稿 Excel。 |
| `ai_gen_reimbursement_docs/cosmic_ai.py` | 构造 prompt、调用 LLM、解析 JSON、返回 diagnostics。 |
| `ai_gen_reimbursement_docs/cosmic_models.py` | 定义 `DataMovement` 和 `CosmicItem`。 |
| `ai_gen_reimbursement_docs/cosmic_validator.py` | 结构化校验、治理规则、JSON/Markdown 校验报告。 |
| `ai_gen_reimbursement_docs/cosmic_writer.py` | 基于模板和 manifest 写 COSMIC Excel。 |
| `ai_gen_reimbursement_docs/cosmic_confirmation.py` | 计算人工确认汇总和导出策略。 |
| `ai_gen_reimbursement_docs/config_utils.py` | 读取 COSMIC 配置、CFP policy 和 governance。 |
| `web_app/routes/artifacts.py` | COSMIC 草稿读取、确认保存、确认后导出、审阅动作和审计。 |
| `web_app/routes/config.py` | COSMIC governance 配置 API。 |
| `web_app/services/config_service.py` | 结构化读写 COSMIC governance 配置。 |
| `web_app/src/views/CosmicPreviewPage.vue` | COSMIC 审阅和确认前端。 |
| `web_app/src/views/Config.vue` | COSMIC 治理配置前端。 |

## 主要产物

| 路径 | 内容 |
| --- | --- |
| `md/3.1.gen-cosmic-FPA核减后的工作量-总和.md` | FPA 核减后工作量。 |
| `md/3.2.gen-cosmic-COSMIC-模板.md` | 空白 COSMIC Markdown 模板。 |
| `md/3.3.gen-cosmic-AI填充-COSMIC.md` | AI 结果审阅 Markdown。 |
| `md/3.3.gen-cosmic-AI填充-COSMIC.json` | 结构化 COSMIC 草稿。 |
| `md/3.4.gen-cosmic-校验报告.md` | 校验报告和 Excel 输出策略说明。 |
| `md/3.5.gen-cosmic-CFP-总和.md` | CFP 总和，仅正式批处理或确认后正式导出成功时更新。 |
| `cosmic文档/项目功能点拆分表.xlsx` | 批处理正式 COSMIC Excel。 |
| `cosmic文档/项目功能点拆分表-草稿.xlsx` | 待审时可选草稿 Excel。 |
| `cosmic文档/项目功能点拆分表-确认后.xlsx` | Web 确认后导出的正式 Excel。 |
| `cosmic-confirmation.json` | 会话级 COSMIC 审阅确认结果。 |
| `log/ai_prompts/*generate_cosmic_prompt.md` | AI prompt 日志。 |
| `log/ai_responses/*` | AI response 日志。 |
| `log/source_data/*excel_source.json` | Excel 写入源数据快照。 |

## 测试覆盖

主要测试文件：

| 测试 | 覆盖重点 |
| --- | --- |
| `tests/test_cosmic_ai.py` | AI 解析、diagnostics、失败和限制行为。 |
| `tests/test_cosmic_validator.py` | 结构化校验、规则矩阵、固定回归夹具。 |
| `tests/fixtures/cosmic_regression_cases.json` | 核心 COSMIC 治理场景样例。 |
| `tests/test_cosmic_confirmation.py` | confirmation summary 和 export policy。 |
| `tests/test_cosmic_writer_manifest.py` | COSMIC Excel manifest、列映射、命名单元格。 |
| `tests/test_pipeline.py` | pipeline 中 COSMIC 状态和异常路径。 |
| `tests/test_web_tasks.py` | 草稿读取、确认保存、审阅动作、重校验、确认后导出。 |
| `tests/test_web_config_routes.py` | COSMIC governance 配置 API。 |
| `tests/test_web_config_service.py` | COSMIC governance 配置读写和保留未知键。 |
| `tests/test_web_frontend_contracts.py` | 前端页面契约。 |

## 当前边界和后续风险

当前链路已经具备结构化生成、校验、审阅、确认后导出、CFP policy、审阅动作、回滚契约和审计 hash/signature 的基础能力。但仍有明确边界：

1. `CosmicItem.total_cfp()` 旧兼容口径仍存在，不应扩散到正式业务逻辑。
2. Excel 公式解析不是完整 Excel 引擎，只覆盖常见分支写法。
3. 功能用户强绑定仍缺正式审批权限和状态机。
4. 复杂边界、复杂非功能事项和错误/确认消息来源仍依赖人工确认和规则矩阵。
5. 规则矩阵配置页目前主要是 JSON 文本编辑，不是完整可视化规则编辑器。
6. 自动治理默认关闭，且仍应补权限审批。
7. `rollback_review_action` 后端能力已具备，但前端可视化回滚交互仍需产品化。
8. 外部 JSONL ledger 只是追加式镜像，不等于 WORM 或第三方不可篡改存储。
9. 真实项目脱敏端到端回归样例仍需补齐。
10. `fill_md_with_ai`、`parse_md_to_items`、`CosmicItem.warnings` 等旧兼容路径仍需后续清理。
