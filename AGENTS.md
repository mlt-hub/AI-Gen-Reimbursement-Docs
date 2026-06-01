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

## Pull Request Rules

每一轮代码或文档修改结束后，Agent 必须：

- 自行总结本轮变更范围、关键行为变化和验证结果。
- 检查 `git status`，只纳入本轮相关文件，避免提交用户未要求处理的无关改动。
- 使用清晰的提交信息创建一次 Git commit。
- 在最终回复中给出提交哈希、提交标题、变更摘要和验证命令结果。

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
