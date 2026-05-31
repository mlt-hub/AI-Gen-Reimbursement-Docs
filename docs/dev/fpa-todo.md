# FPA 暂缓推进任务与恢复指令

本文档记录当前暂不推进的 FPA 后续事项，以及后续让 Codex 继续处理这些事项时可直接使用的指令。

## 任务主入口

所有暂不推进事项统一记录在：

```text
docs/dev/gen-fpa-implementation-notes.md
```

对应章节：

```text
暂缓推进任务池
后续恢复指令
```

## 任务分组

当前暂缓事项按以下分组维护：

```text
A. 真实项目 Golden Case
B. strict_fpa 数据组识别
C. 类型冲突规则
D. 配置校验
E. 领域上下文
F. 验收
G. 可选增强
H. 旧兼容逻辑清理
I. 多预览页面扩展
J. profile / strategy / rule_set 三层模型
K. FPA 审核工作簿与预览审核面板
```

## 旧兼容逻辑清理清单

基于 `AGENTS.md` 的项目约束：本系统尚未上线，不需要保留旧版本兼容路径。

已完成的清理：

```text
已确认 FPA MD 读取当前要求新 14 列格式，不再保留旧 10 列兼容读取路径。
已更新 FPA system prompt 示例，移除“每个功能过程记 1 个 FPA 功能点”的旧口径。
已将改进计划中“必须兼容旧文件”的表述改为“旧兼容路径处理”。
已清理测试注释中的“接口行”旧说法。
已将改进计划中的“接口行/逻辑接口开发”旧口径改为“非界面业务动作行”。
```

## 多预览页面扩展

FPA 预览已迁移为独立页面：

```text
/preview/fpa
/static/dist/
/static/dist/preview/fpa
```

当前状态：

```text
FPA 预览页和生产静态目录根路径已支持生产静态目录深链访问。
FastAPI 在 /static/dist 挂载前提供 /static/dist、/static/dist/、/static/dist/config、/static/dist/preview/{path:path} 等已知前端路由 fallback，避免 deep link 被当作静态文件路径。
顶层 /preview/{path:path} 也返回 SPA 入口，为后续 COSMIC / SPEC 预览页复用。
不会对 /static/dist/{path:path} 做全量通配，避免影响 assets 静态资源。
FPA 预览页已改为“生成基础数据 -> 下拉选择三级模块 -> 生成预览”的两段式流程。
新增 /api/fpa/preview-modules，只解析功能清单并返回三级模块列表，不调用 AI，不生成 FPA Excel。
前端主流程不再暴露手填三级模块名称/序号，避免名称重复和输入错误。
API Key 输入框已明确为 placeholder 提示语，不把 sk-...、here、****here 等占位值作为真实 Key 提交。
strict_fpa 类型冲突规则已收紧：AI 为主，名称明确动作优先，说明中的列表/查询文字不会错误覆盖“添加垂直行业”的合法 EI。
```

## 已确认的下一阶段 FPA 重构方向

状态：第二阶段已推进 rule_set 外部配置。审核工作簿和预览审核面板继续暂缓。

```text
profile  = FPA 方法学 / 业务口径
strategy = AI 与 rules 的执行优先级
rule_set = 具体用户可配置规则集
```

已确认默认组合：

```text
custom_rules = rules_first + custom_rules_default
strict_fpa   = ai_first    + strict_fpa_default
```

关键决策：

```text
已将 current_project 改名为 custom_rules。
系统未上线，不保留 current_project 兼容别名。
strict_fpa 默认 ai_first。
custom_rules 默认 rules_first。
strict_fpa 无 API Key 时默认不生成，只提示需要 API Key。
AI 不完整时，rules 补漏缺失行，并标记 generation=rules_fallback。
rules 不改 AI 已给出的合法 type；业务冲突只 warning。
只有 type 非法、JSON 非法、结构非法时才硬处理。
预览和正式生成已使用同一套 profile / strategy / rule_set。
AI 缓存 key 已包含 profile、strategy、rule_set、prompt、model、输入模块内容。
支持多套 rule_set 的配置入口已落地。
rule_set 外部配置文件已落地。
rule_set_version 已写入预览结果、AI cache 和正式 FPA MD。
rule_set extends 继承已落地，当前支持继承父规则集并追加 external_data_rules。
```

第一版 rule_set 建议支持：

```text
关键词规则。
外部数据源规则。
ILF / EIF 判定规则。
功能过程覆盖检查规则。
```

本轮代码落地点：

```text
ai_gen_reimbursement_docs/fpa_profiles.py
  定义 VALID_FPA_STRATEGIES、默认 strategy、默认 rule_set、FpaExecutionConfig。

ai_gen_reimbursement_docs/config_utils.py
  增加 load_fpa_strategy、load_fpa_rule_set。
  load_fpa_profile 会将系统配置中的无效 profile 回退为 custom_rules，避免旧占位配置阻断默认运行。

ai_gen_reimbursement_docs/gen_fpa.py
  正式生成与预览均解析 FpaExecutionConfig。
  rules_first / rules_only 直接使用规则生成。
  ai_first / ai_only 需要 API Key。
  ai_first 在 AI 覆盖不完整时追加 rules_fallback 行。
  ai_first 保留 AI 合法 type；规则冲突仅记录 warning。
  ai_only 不使用 rules 补行，AI 失败或被限制跳过时直接报错。
  FPA AI cache key 和 cache entry 写入 profile、strategy、rule_set。

ai_gen_reimbursement_docs/pipeline.py
  run_pipeline、run_pipeline_simple、gen-fpa、gen-all 均透传 fpa_strategy / fpa_rule_set。

ai_gen_reimbursement_docs/cli/main.py
  增加 --fpa-strategy、--fpa-rule-set。

web_app
  高级选项和 FPA 预览页增加 FPA 执行策略。
  Store 持久化 fpaStrategy / fpaRuleSet。
  Web 正式生成和预览接口透传 fpa_strategy / fpa_rule_set。
```

第二阶段代码落地点：

```text
config/fpa_rule_sets_config.yaml.example
  新增独立 rule_set 示例配置文件。
  内置 custom_rules_default、strict_fpa_default。
  示例 strict_fpa_conservative、client_a_rules 展示 extends、version、external_data_rules。

ai_gen_reimbursement_docs/fpa_profiles.py
  新增 FpaRuleSetConfig。
  新增 resolve_fpa_rule_set_config。
  支持内置 rule_set 与用户配置 rule_set 合并。
  支持 extends 继承，并检测循环继承。
  当前 rule_set 的 external_data_rules 会参与 strict_fpa 外部数据组识别。

ai_gen_reimbursement_docs/config_utils.py
  新增 load_fpa_rule_sets_config。
  配置自动迁移会处理 fpa_rule_sets_config.yaml。

ai_gen_reimbursement_docs/cli/main.py
  --init-config 会初始化 fpa_rule_sets_config.yaml。

ai_gen_reimbursement_docs/gen_fpa.py
  正式 FPA MD 头部写入 profile、strategy、rule_set、rule_set_version。
  预览结果返回 rule_set_version。
  AI cache key 和 cache entry 写入 rule_set_version。
```

本轮未做、后续继续：

```text
J1. 已完成：将 rule_set 从“名称入口”升级为外部 YAML 配置文件。
J2. 部分完成：rule_set_version 已写入 AI cache key、正式 MD、预览结果；审核工作簿待实现。
J3. 部分完成：支持 rule_set extends 继承并追加 external_data_rules；字段级覆盖策略后续继续细化。
J4. 部分完成：外部数据源规则可由 rule_set 配置追加；关键词规则、ILF/EIF 判定规则仍在代码中。
J5. 细化 rules_first 中“rules 无法判定再交给 AI”的判定条件；当前 custom_rules 的内置规则可覆盖现有场景，因此 rules_first 直接使用规则生成。
J6. 增加 UI 中的 rule_set 下拉选择；当前先提供文本输入和配置入口。
```

## FPA 审核工作簿与预览审核面板

状态：预览 audit JSON 与预览页审核信息第一版已实现；审核工作簿仍待实现。

目标：

```text
正式生成额外产出 FPA工作量评估-check.xlsx。
预览页展示同一套审核信息。
正式 Excel 保持干净，check Excel 用于审查 AI/rules 如何生成每一行。
```

建议先抽象：

```text
FpaAuditReport
```

同一份 FpaAuditReport 用于：

```text
正式生成 -> 写入 FPA工作量评估-check.xlsx
预览接口 -> 返回 audit JSON
预览页面 -> 展示审核 Tabs
```

审核内容：

```text
FPA 行结果。
三级模块列表。
功能过程覆盖。
AI 原始返回。
规则命中详情。
Warnings。
profile / strategy / rule_set / rule_set_version。
generation / fallback_reason / source_processes。
```

推荐实施顺序：

```text
1. 已完成：定义 FpaAuditReport 数据结构。
2. 已完成：预览接口返回 audit。
3. 已完成基础版：预览页面展示审核信息。
4. 待实现：正式生成写入 FPA工作量评估-check.xlsx。
5. 待实现：Web 下载包纳入 check.xlsx。
```

当前预览 audit 内容：

```text
profile / profile_version。
strategy。
rule_set / rule_set_version。
三级模块信息。
功能过程总数、已覆盖数量、未覆盖数量。
已覆盖功能过程列表。
未覆盖功能过程列表。
generation_counts。
warnings。
```

预览页当前展示：

```text
功能过程覆盖数。
未覆盖数。
规则集名称。
规则集版本。
生成方式统计。
缺失功能过程列表。
```

后续预留：

```text
I1. 增加 /preview/cosmic 页面，复用 PreviewLayout。
I2. 增加 /preview/spec 页面，复用 PreviewLayout。
I3. 将 COSMIC / SPEC 预览各自的输入、结果表格、warning 面板拆成独立组件。
I4. 如后续需要 Golden Case 对比，可增加 /preview/golden-cases。
```

后续如继续清理，可优先检查以下残留点。本清单记录当前状态。

```text
H1. 已初步清理：未发现当前 FPA 主流程仍保留旧版“每个功能过程固定生成界面开发 + 接口开发”的代码分支。
H2. 已初步清理：旧逐行 AI 填充函数和调用路径已移除；文档保留旧流程作为历史背景。
H3. 已初步清理：FPA MD 读取当前要求新 14 列格式，不再保留旧 10 列兼容读取路径。
H4. 已初步清理：FPA system prompt 和改进计划中的旧口径表述已调整；后续如新增 prompt，仍需复核。
H5. 已初步清理：测试注释中的“接口行”旧说法已调整；后续新增 fixture 时仍需复核命名。
H6. 待复核：配置初始化和迁移逻辑是否存在其他不再需要的旧兼容项。
H7. 已初步清理：改进计划中“必须兼容旧文件”的表述已改为未上线项目的新约束；README 后续如新增 FPA 段落仍需复核。
```

推进该分组时建议使用：

```text
按照 docs/dev/fpa-todo.md 的“H. 旧兼容逻辑清理”，先列出当前代码和文档中的旧兼容残留点，给出删除方案，不修改代码。
```

确认方案后再使用：

```text
按照 docs/dev/fpa-todo.md 的“H. 旧兼容逻辑清理”，删除已确认的旧兼容逻辑，更新文档并跑完整相关测试。
```

## 指令模板

### 继续全部任务

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，从 A1 开始按顺序继续推进。每完成一项更新文档并跑相关测试。
```

### 推进指定分组

示例：

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，推进 B 组 strict_fpa 数据组识别。每完成一项更新文档并跑相关测试。
```

### 推进指定事项

示例：

```text
按照 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，只推进 D5：普通外部服务被配置为数据组时记录 warning。完成后更新文档并跑相关测试。
```

### 只重新评估优先级，不修改代码

```text
读取 docs/dev/gen-fpa-implementation-notes.md 的“暂缓推进任务池”，结合当前代码状态重新排序，先给出推荐，不修改代码。
```

## 文档引用关系说明

后续待办只在一份文档中详细维护，避免多份文档各写一套清单后逐渐不一致。

```text
docs/dev/gen-fpa-implementation-notes.md
  -> 暂缓推进任务池的详细主入口

docs/fpa-profiles.md
  -> 面向使用者的 FPA profile 说明，只引用任务池入口

docs/dev/gen-fpa-improvement-plan.md
  -> 原始改进规划，只引用任务池入口
```

可以理解为：

```text
gen-fpa-implementation-notes.md = 待办清单主入口
fpa-profiles.md = 使用者说明，放跳转提示
gen-fpa-improvement-plan.md = 改进规划，放跳转提示
```

以后如果需要继续推进，只需引用“暂缓推进任务池”，Codex 就应从统一清单接着处理。
