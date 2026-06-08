# AI 记忆实现方案

## 背景

当前项目通过 `llm_client.call_llm()` 发起单次 AI 调用。模型本身不会跨调用保留项目状态，因此所谓“记忆”需要由项目侧保存、检索、筛选并注入到本次 prompt 中。

记忆的目标不是“完全不传上下文”，而是避免每次传入全部通用信息，只把与当前任务相关的少量已确认信息注入给 AI，并且让这些注入内容可审计、可调试、可禁用。

## 目标行为

- 通用信息只维护一份，不在每个 AI 调用点重复拼接。
- 每次 AI 调用前按任务类型、模块、关键词筛选相关记忆。
- 记忆注入内容必须出现在 prompt 日志和提示词调试页中，便于复盘。
- 用户确认过的偏好、边界、术语、修正规则可以跨会话复用。
- AI 输出不能直接写入长期记忆，必须经过用户确认或明确规则转换。

## 记忆分层

### 1. 领域上下文

现有 `domain_context.json` 已经承担 FPA 领域边界上下文，例如：

- 系统边界
- 内部数据组
- 外部数据组
- 外部服务

这类信息是项目事实，适合继续保留在当前机制中。

### 2. 项目级记忆

建议新增 `project_memory.json`，用于保存跨会话复用的通用信息，例如：

- 甲方偏好
- 常用命名口径
- 历史人工修正
- 已确认的 FPA 判定边界
- 业务术语和别名

示例结构：

```json
{
  "preferences": {
    "fpa_profile": "unified_ui",
    "naming_style": "三级模块名-动作"
  },
  "fpa_rules": [
    {
      "scope": "费用申请",
      "memory": "涉及审批流时，保存、提交、审批应按独立功能过程审阅",
      "source": "人工确认",
      "updated_at": "2026-06-08"
    }
  ],
  "business_terms": [
    {
      "term": "报账单",
      "aliases": ["费用单", "报销单"],
      "meaning": "项目费用报销主单据"
    }
  ]
}
```

### 3. 会话内记忆

会话内记忆只在本次运行中有效，例如：

- 本次上传文件
- 已确认参数
- 用户刚修正的问题
- 生成产物路径
- 当前任务进度

这类信息可以复用现有 `runtime_context`、Web `SessionManager` 或任务运行上下文，不建议写入长期记忆文件。

## 推荐架构

### 不在 `call_llm` 中拼业务记忆

`llm_client.call_llm()` 应继续只负责：

- API 调用
- 重试
- token 和模型配置
- prompt/response 日志
- 错误封装

业务记忆应在 prompt 组装层注入。例如 FPA 当前适合在 `gen_fpa.py` 的 `_build_fpa_ai_prompt_context(...)` 附近处理。这样提示词调试页和日志能看到最终注入内容，也避免底层客户端承担业务规则。

### 新增统一 Memory 服务

建议新增 `ai_gen_reimbursement_docs/memory.py`：

- `load_project_memory()`：读取并校验项目级记忆。
- `select_relevant_memory(task, domain, module, payload)`：按任务和输入筛选相关记忆。
- `render_memory_prompt(memory_items)`：把筛选结果渲染为稳定 prompt 片段。
- `record_feedback(...)`：把用户确认过的修正沉淀为记忆候选。

### Prompt 注入格式

建议固定为单独段落：

```text
# 项目记忆
以下信息是用户已确认的项目级约束。若与本次输入冲突，以本次输入为准，并在结果中说明冲突。
- ...
```

只注入与当前任务相关的少量条目，避免 token 失控。

## 拟修改文件范围

第一阶段建议只做轻量机制：

| 文件 | 变更 |
| --- | --- |
| `ai_gen_reimbursement_docs/memory.py` | 新增记忆读取、校验、筛选、渲染逻辑 |
| `ai_gen_reimbursement_docs/config_utils.py` | 增加记忆文件名、路径、可选加载入口 |
| `ai_gen_reimbursement_docs/gen_fpa.py` | 在 FPA prompt context 中注入相关项目记忆 |
| `tests/test_memory.py` | 新增记忆加载、校验、筛选单测 |
| `tests/test_gen_fpa_ai.py` | 扩展 prompt 注入相关断言 |

第二阶段如果需要 Web 管理入口，再增加：

| 文件 | 变更 |
| --- | --- |
| `web_app/routes/config.py` | 增加记忆配置读写 API |
| `web_app/services/config_service.py` | 增加记忆配置服务 |
| `web_app/src/views/...` | 增加项目记忆查看、编辑、禁用入口 |

## 验证方式

- 记忆文件不存在时，不影响现有生成流程。
- 非法记忆格式能给出清晰错误。
- 与当前模块相关的记忆会注入 prompt。
- 无关记忆不会注入 prompt。
- prompt debug 和 AI prompt 日志能看到最终注入的记忆片段。
- FPA 现有测试保持通过。

建议运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_memory.py tests/test_gen_fpa_ai.py
.\.venv\Scripts\python.exe -m pytest
```

## 风险与约束

- 记忆污染：AI 输出不能自动进入长期记忆，必须来自用户确认或确定性规则。
- token 失控：不能整份记忆每次注入，应限制条数和总字符数。
- 行为不可解释：注入内容必须进入 prompt 日志和调试页。
- 隐私泄露：记忆文件不应保存 API Key、身份证、手机号等敏感字段。
- 冲突处理：记忆与本次输入冲突时，应以本次输入为准，并在结果或调试信息中记录冲突。

## 建议实施顺序

1. 新增 `memory.py` 和 `project_memory.json.example`。
2. 在 `config_utils.py` 增加可选加载和校验。
3. 在 FPA prompt 组装入口注入筛选后的记忆。
4. 扩展提示词调试信息，展示记忆来源和命中条目。
5. 增加单测和 FPA 回归测试。
6. 视使用情况再补 Web 管理入口。
