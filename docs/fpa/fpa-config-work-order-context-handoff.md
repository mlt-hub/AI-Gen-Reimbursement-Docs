# FPA 配置与工单上下文会话交接

生成时间：2026-06-04

## 背景

本轮围绕 `f:\mlt\mlt-projects\ai_gen_reimbursement_docs` 中 FPA 配置、执行策略、规则集语义和工单上下文进入 FPA prompt 的行为进行了澄清、文档更新和实现调整。

仓库规则要求每轮修改后提交，因此本轮相关变更均已形成 git commit。

## 已完成决策

1. `ai_only` 的“仅 AI”语义

   `ai_only` 不使用规则生成行，不追加 `rules_fallback` 补齐行；AI 失败、解析失败或被 AI 限制跳过时直接报错。

   但 `rule_set` 仍用于配置校验、AI 结果后处理、非法类型兜底、明显类型冲突 warning、审核追踪和 AI cache key。合法 AI type 与规则建议冲突时，`ai_only` 保留 AI type，只记录 warning。

2. `custom_rules`

   `custom_rules` 不再作为当前可用 profile，也不再保留专门迁移错误提示。相关 legacy 处理和测试已删除。README 已同步改为当前 profile：`strict_fpa`、`unified_ui`、`multi_uis`、`ui_api_mapping`。

3. `keyword_rules` 与 `type_mapping_rules`

   `keyword_rules` 用于事务动作关键词，主要维护 `EI/EQ/EO`，例如新增、查询、导出。

   `type_mapping_rules` 是直接类型映射，支持 `EI/EQ/EO/ILF/EIF`，适合项目级特例、业务对象或数据组边界。`strict_fpa` 类型推断中，`type_mapping_rules` 先于普通事务关键词判断。

4. 工单上下文进入 FPA prompt

   因为 `功能清单-录入模板.xlsx` 已有 `1、工单需求-元数据录入` Sheet，FPA 不再要求用户把项目说明重复写入配置文件。

   FPA 会从解析后的 `meta` 中读取：

   - `工单标题`
   - `工单内容`
   - 或带 Sheet 前缀的 `1、工单需求-元数据录入.工单标题`
   - `1、工单需求-元数据录入.工单内容`

   并拼成 `domain_context.project_description` 放入 FPA prompt 的 `payload_json.domain_context`。

   不读取 `建设目标`、`建设必要性`，因为这些字段是 AI 生成内容，避免二次污染。

   `fpa_domain_context.json` 只维护系统边界和数据组等稳定领域上下文；即使配置中出现 `project_description`，FPA prompt 也会忽略配置值，优先使用 Excel 工单标题和工单内容。

   `project_description` 长度上限为 5000 字符，超出时截断并追加提示。

## 相关提交

1. `e8c0358 docs: clarify FPA ai_only rule set behavior`

   更新 `config/fpa_config.yaml.example` 和 `docs/fpa/fpa-profiles.md`，说明 `ai_only` 下 `rule_set` 的实际作用边界。

2. `24a9cd7 chore: remove legacy custom_rules handling`

   删除 `custom_rules` 专门迁移错误判断和 legacy 测试，更新 README 与当前 profile 说明。

3. `55d1ec0 docs: explain FPA type rule segments`

   文档说明 `keyword_rules` 与 `type_mapping_rules` 的区别、适用场景和优先级。

4. `552a119 feat: include work order context in FPA prompts`

   实现从工单标题/工单内容生成 `domain_context.project_description`，并补充测试和文档。

## 关键文件

- `ai_gen_reimbursement_docs/gen_fpa.py`
  - `_build_domain_context(meta)` 合并 FPA domain context，并加入 Excel 工单标题/内容生成的 `project_description`。
  - `_build_project_description_from_work_order(meta)` 只读取工单标题和工单内容。
  - `FPA_PROJECT_DESCRIPTION_MAX_CHARS = 5000`。

- `tests/test_gen_fpa_ai.py`
  - 覆盖工单标题/内容进入 `domain_context.project_description`。
  - 覆盖带 Sheet 前缀的 meta key。
  - 覆盖忽略配置文件中的 `project_description`。
  - 覆盖超长工单内容截断。
  - 覆盖 FPA preview prompt 包含 `project_description`。

- `docs/fpa/fpa-profiles.md`
  - 当前 FPA profile、strategy、domain context、rule set 规则段说明。

- `config/fpa_config.yaml.example`
  - `ai_only` 与规则段注释。

- `README.md`
  - 当前 FPA profile 示例。

## 验证记录

最近一次相关测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config_utils.py tests\test_gen_fpa_ai.py -q
```

结果：

```text
115 passed
```

最近一次工作区检查：

```powershell
git status --short
```

结果为空。

## 后续注意事项

- 如果继续调整 FPA 结果预览、审阅、修改页面，先查阅 `docs/fpa/result-review-terminology.md`，并遵守固定术语：`新增/修改功能点`、`类型`、`计算依据归类`、`计算依据说明`、`生成方式`。
- 不要重新引入 `custom_rules` 兼容别名或专门迁移路径。
- 不要把 `建设目标`、`建设必要性` 喂入 FPA prompt，除非用户重新明确修改该决策。
- 如果未来要把工单编号也传给 AI，建议新增独立元数据字段而非混进 `project_description`，并先确认是否真的会影响 FPA 判断。
- 如果要新增 `fpa_domain_context.json` 字段，应同步更新 `validate_fpa_domain_context()`、example 和配置测试。
