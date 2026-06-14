# FPA AI 交互记录统一改为 Markdown

状态：已完成

## 目标

将 FPA 相关的 AI 交互记录统一到 Markdown 日志格式，避免当前“页面只读到 prompt，response / thinking 丢失”的问题。

最终目标行为：

- `/api/ai-interactions/{session_id}` 只扫描 `*.md`
- AI prompt、AI response、AI thinking 全部改为 `*.md`
- FPA AI 交互记录页能同时展示三类内容

## 背景问题

当前实现存在两层不一致：

1. 交互记录接口只读取 prompt / response，且对 response 还存在 `.txt` 过滤。
2. 生成端部分日志已经是 `.md`，但 prompt / thinking 仍可能写成 `.txt`。

这会导致 UI 上只能看到部分记录，不能形成完整的 AI 交互链路。

## 修改范围

### 后端

- `ai_gen_reimbursement_docs/llm_client.py`
  - `_save_prompt_log`：`*_prompt.txt` 改为 `*_prompt.md`
  - `_save_thinking_log`：`*_thinking.txt` 改为 `*_thinking.md`
  - `_save_response_log` 保持 `*_response.md`

- `web_app/routes/artifacts.py`
  - `/api/ai-interactions/{session_id}` 只扫描三类目录中的 `*.md`
  - 返回结果新增 `thinking`
  - 结构化 FPA 调试记录中默认文件名同步切到 `.md`

### 前端

- `web_app/src/views/Home.vue`
  - `AiInteraction.type` 支持 `prompt | response | thinking`
  - 列表展示对应标识

- `web_app/src/views/FpaAiDebugPage.vue`
  - 同步支持 `thinking`
  - 与主页面保持一致的展示方式

### 测试

- `tests/test_web_fpa_debug.py`
  - 夹具日志改为 `.md`
  - 补充 `ai_thinking` 断言
  - 验证 `/api/ai-interactions/{session_id}` 返回完整三类记录

## 实施步骤

1. [x] 统一写入端扩展名。
2. [x] 统一读取端扫描规则。
3. [x] 前端补齐 `thinking` 类型展示。
4. [x] 更新测试夹具和断言。
5. [x] 扫一遍仓库中残留的 `.txt` 交互日志引用。

## 验收标准

- `ai_prompts`、`ai_responses`、`ai_thinking` 三个目录都只使用 `.md`
- `AI 交互记录` 页面能看到 prompt / response / thinking
- 相关测试通过
- 仓库中不再残留本轮需要迁移的 `.txt` 交互日志硬编码

## 风险

- 历史会话里旧的 `.txt` 日志不再被接口读取
- 需要确认结构化 FPA 调试记录里引用的文件名同步改为 `.md`

## 备注

这次不做 `.txt` 兼容分支，直接以 `.md` 作为唯一标准，和新的交互记录链路保持一致。

## 实施结果

- `llm_client` 的 prompt / response / thinking 日志统一使用 Markdown 扩展名。
- FPA 预览调试写入 `ai_prompts`、`ai_responses`、`ai_thinking` 三类 Markdown 文件，并在结构化记录中保存对应文件名。
- `/api/ai-interactions/{session_id}` 只扫描三类日志目录下的 `*.md`，返回 `prompt`、`response`、`thinking` 三类记录。
- `Home.vue` 与 `FpaAiDebugPage.vue` 的 AI 交互列表均支持 `thinking` 类型展示；FPA 结构化调试记录页也可查看 Thinking 文件内容。
- 旧 `.txt` 交互日志不再作为接口读取对象，符合本计划“不做 `.txt` 兼容分支”的约束。

## 验证记录

- `.\.venv\Scripts\python.exe -m pytest tests\test_llm_client.py tests\test_web_fpa_debug.py tests\test_web_tasks.py`
  - 结果：109 passed
- `npm run build`（工作目录：`web_app`）
  - 结果：通过
- `rg` 扫描本轮需要迁移的 prompt / response / thinking `.txt` 硬编码
  - 结果：未发现残留
