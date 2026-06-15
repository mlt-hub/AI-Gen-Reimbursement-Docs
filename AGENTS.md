# AGENTS.md instructions for this repository

## Project Development Constraints

本系统尚未上线，开发时不需要保留旧版本兼容路径。

如需调整已有实现，优先选择更清晰、更一致、更易维护的方案；可以移除旧逻辑或旧分支，但必须同步更新相关文档和测试，确保当前目标行为清晰可验收。

## Collaboration Rules

每次对话默认先出方案，不直接修改代码或文档。Agent 必须先说明：

- 计划解决的问题和目标行为。
- 拟修改的文件范围。
- 验证方式和可能风险。

只有在用户明确发出“修改”“实施”“开始改”“按方案执行”等修改指令后，Agent 才能编辑文件、运行格式化或创建提交。用户仅提问、讨论、要求评估或要求方案时，不得自行改代码。

文档类任务完成后，应把对应的 FPA 计划或实施文档整理到合适的 `docs/fpa/done/` 位置，并补上完成状态或归档说明，避免已完成内容继续停留在待办区。

## Result Review Terminology

涉及 FPA、COSMIC 或其他生成结果的预览、审阅、修改页面时，必须先查阅并遵循 [`docs/fpa/result-review-terminology.md`](docs/fpa/result-review-terminology.md)。

- 用户可见文案必须优先使用该文档中的业务域术语映射。
- FPA 相关页面固定使用 `新增/修改功能点`、`类型`、`计算依据归类`、`计算依据说明`、`生成方式`。
- 不得在 FPA 页面中用 `功能点类型`、`类型判定依据`、`功能点说明`、`说明详情` 等同义词替代用户指定术语。
- 新增 COSMIC 或其他生成器审阅页前，先补充或确认该业务域的术语映射，再实施界面和代码修改。

## Pull Request Rules

每一轮代码或文档修改结束后，Agent 必须：

- 自行总结本轮变更范围、关键行为变化和验证结果。
- 检查 `git status`，只纳入本轮相关文件，避免提交用户未要求处理的无关改动。
- 使用清晰的提交信息创建一次 Git commit。
- 在最终回复中给出提交哈希、提交标题、变更摘要和验证命令结果。

## Worktree Cleanup Rules

如果本轮工作是在临时或新增 worktree 中完成的，Agent 必须在验证和提交完成后：

- 将本轮相关提交合并回主工作区的当前主分支。
- 合并前后检查 `git status`，保护主工作区中用户已有的未提交改动。
- 合并成功后清理本轮创建的临时 worktree。
- 在最终回复中说明合并目标分支、清理结果和主工作区剩余未提交改动。

## Python Test Environment

本仓库运行 Python 测试、脚本和 pytest 时，默认必须使用项目虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Output Template Progress Notes

- `gen-list` 已使用 `list` manifest 驱动项目需求清单写入：sheet 名、表头行、数据起始行、样式源行、关键列映射和项目概览命名单元格会影响实际输出。
- `gen-spec` 已使用 Word manifest 驱动占位符替换范围、功能需求锚点、模块清单列配置和样式配置。
- `gen-fpa` 已使用 `fpa` manifest 驱动 FPA 结果 sheet 名、表头行、数据起始行、样式源行、关键列定位、result sheet 的数据起始和 FPA 工作量汇总命名单元格；模板附录判定原则读取也已支持 `judgement_rules` sheet、表头定位、列、起始/结束行、最大读取行数和基础锚点配置，预检会校验声明的规则表头。
- `gen-cosmic` 已使用 `cosmic` manifest 驱动 COSMIC 结果 sheet 名、数据起始行、样式源行和结果字段列映射；合并列、warning 标记列、复用度校验列和 CFP 公式列会跟随列映射。
- pipeline 已支持 `active_output_template_profile` / `output_template_profiles` 基础解析，profile 可直接声明 `templates` 或通过 `template_pack` 指向带 `manifest.yaml` 的模板包目录。
- Web 配置页已支持输出模板 profile 基础选择能力：读取 `output_template_profiles`、选择或清空 `active_output_template_profile`，并展示所选 profile 的 `template_pack` 与 `templates` key。
- Web/API 保存 `active_output_template_profile` 时已支持联动 profile 中的 `fpa_profile`、`fpa_rule_set`、`fpa_strategy` 和 `fpa_confirmation_mode`。
- Word 导入模板草稿已支持发布为正式用户模板版本，发布后返回可应用到 `spec_out_template` 的正式模板路径。
- Word 导入模板草稿已支持基础在线调整：可移动 `{{模块清单表}}` / `{{功能过程详情}}` 锚点，并可将指定段落文本替换为 `{{字段名}}` 占位符；调整后会重置确认/发布状态。
- Word 导入模板草稿已支持基础版式渲染预览：后端提供页面尺寸、边距、页眉/正文/页脚、段落/表格、样式名和占位符的浏览器可渲染 layout model；Web 草稿列表可打开页面式预览。
- 尚未完成的输出模板方向包括：Office 级 Word 像素还原预览、复杂 Word 结构识别，以及 COSMIC/FPA/list 更复杂 Excel 锚点、复杂样式复制、图片/文本框和跨 sheet 公式重写。

<!-- CODEGRAPH_START -->
## CodeGraph

This project has a CodeGraph MCP server (`codegraph_*` tools) configured. CodeGraph is a tree-sitter-parsed knowledge graph of every symbol, edge, and file. Reads are sub-millisecond and return structural information grep cannot.

### When to prefer codegraph over native search

Use codegraph for **structural** questions — what calls what, what would break, where is X defined, what is X's signature. Use native grep/read only for **literal text** queries (string contents, comments, log messages) or after you already have a specific file open.

| Question | Tool |
|---|---|
| "Where is X defined?" / "Find symbol named X" | `codegraph_search` |
| "What calls function Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "How does X reach/become Y? / trace the flow from X to Y" | `codegraph_trace` |
| "What would break if I changed Z?" | `codegraph_impact` |
| "Show me Y's signature / source / docstring" | `codegraph_node` |
| "Give me focused context for a task/area" | `codegraph_context` |
| "See several related symbols' source at once" | `codegraph_explore` |
| "What files exist under path/" | `codegraph_files` |
| "Is the index healthy?" | `codegraph_status` |

### Rules of thumb

- For architecture, feature, and bug-context questions, prefer `codegraph_context` first.
- For a specific flow question, start with `codegraph_trace`.
- Do not grep first when looking up a symbol by name.
- Do not loop many `codegraph_node` calls; use `codegraph_explore` for related symbols.
- After editing files, allow for CodeGraph index lag before re-querying.

### If `.codegraph/` doesn't exist

Ask the user: "I notice this project doesn't have CodeGraph initialized. Want me to run `codegraph init -i` to build the index?"
<!-- CODEGRAPH_END -->
