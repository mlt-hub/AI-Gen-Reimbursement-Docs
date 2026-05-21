# 日志体系文档

## 1. Logger 层级

```
root
 └── ai_gen_reimbursement_docs (父 logger, level=DEBUG)
      ├── ai_gen_reimbursement_docs.pipeline
      ├── ai_gen_reimbursement_docs.gen_fpa
      ├── ai_gen_reimbursement_docs.gen_cosmic
      ├── ai_gen_reimbursement_docs.gen_spec
      ├── ai_gen_reimbursement_docs.gen_list
      ├── ai_gen_reimbursement_docs.excel_source
      ├── ai_gen_reimbursement_docs.llm_client
      ├── ai_gen_reimbursement_docs.config_utils
      └── ai_gen_reimbursement_docs.cli.logging
```

全部子 logger 通过 `logging.getLogger('ai_gen_reimbursement_docs.xxx')` 创建，消息自动传播到父 logger。

## 2. Handler 全景

```
调用方                          | Handler 注册时机            | 类型       | Level  | 输出目标
────────────────────────────────┼───────────────────────────┼───────────┼────────┼──────────────────────────
init_global_logging()           | CLI main() 启动            | File      | DEBUG  | global_ai_gen_reimbursement_docs.log (全局累积)
                                | Web UI 服务启动            | File      | DEBUG  | global_run_{时间戳}.log (本次服务周期)
                                |                           | Stream    | INFO   | 控制台 (stderr)
────────────────────────────────┼───────────────────────────┼───────────┼────────┼──────────────────────────
setup_logging()                 | run_pipeline() 每次执行    | File      | DEBUG  | {输出目录}/日志/{功能清单}_run_{序号}_{时间戳}.log
────────────────────────────────┼───────────────────────────┼───────────┼────────┼──────────────────────────
SessionHandler (Web UI 专用)    | server.py 启动              | 自定义    | DEBUG  | session_queues → SSE → 浏览器
────────────────────────────────┼───────────────────────────┼───────────┼────────┼──────────────────────────
AI prompt/response 文件          | call_llm() 每次调用        | 文件写入   | —      | {日志目录}/ai_prompts/{时间戳}_{tag}_prompt.txt
                                |                           | 文件写入   | —      | {日志目录}/ai_responses/{时间戳}_{tag}_response.txt
────────────────────────────────┼───────────────────────────┼───────────┼────────┼──────────────────────────
write_combined_ai_log()         | 管道完成后（CLI + Web）     | 文件写入   | —      | {日志目录}/ai_对话日志.md
                                |                           |           |        | {日志目录}/ai_prompts_日志.md
                                |                           |           |        | {日志目录}/ai_responses_日志.md
```

## 3. 日志目录位置

| 模式 | 全局日志 | 任务日志 |
|------|---------|---------|
| 源码运行 | `{项目根}/log/` | `{输出目录}/日志/` |
| exe 运行 | `~/.ai-gen-reimbursement-docs/log/` | `{输出目录}/日志/` |
| Web UI 运行 | 同 exe/源码 | `{输出目录}/日志/` |

## 4. 日志格式

| Handler | 格式 | 示例 |
|---------|------|------|
| 文件（全局 + 任务） | `%(asctime)s \| %(levelname)-8s \| %(name)s \| %(message)s` | `2026-05-19 14:30:01 \| INFO     \| ai_gen_reimbursement_docs.pipeline \| 第1步：FPA...` |
| 控制台 | `%(message)s` | `第1步：FPA...` |
| SSE | JSON `{level, msg, time}` | `{"level":"INFO","msg":"第1步：FPA...","time":"14:30:01"}` |
| AI prompt 文件 | Markdown header + 内容 | `# AI Prompt: fpa_EI_xxx\n[system]\n...\n[user]\n...` |

## 5. 调用链

### CLI

```
main()
 ├── init_global_logging()          → 3 个 handler（全局文件 + 运行文件 + 控制台）
 │
 └── run_pipeline()
      ├── setup_logging()            → 1 个 handler（任务文件）
      │
      ├── call_llm()                 → 2 个文件（ai_prompts/*.txt + ai_responses/*.txt）
      │
      └── write_combined_ai_log()   → 3 个合并 MD
```

### Web UI

```
server.py 启动
 ├── SessionHandler                  → SSE 推送
 ├── init_global_logging()          → 3 个 handler（全局文件 + 运行文件 + 控制台）
 │
 └── 每次请求 → run_pipeline()
      ├── setup_logging()            → 1 个 handler（任务文件）
      ├── call_llm()                 → 2 个文件（ai_prompts / ai_responses）
      └── write_combined_ai_log()   → 3 个合并 MD
```

## 6. 关键代码位置

| 文件 | 行号 | 作用 |
|------|------|------|
| [cli/logging.py:9](ai_gen_reimbursement_docs/cli/logging.py#L9) | `init_global_logging()` | 全局日志 + 控制台 |
| [cli/logging.py:49](ai_gen_reimbursement_docs/cli/logging.py#L49) | `setup_logging()` | 任务日志 |
| [cli/logging.py:86](ai_gen_reimbursement_docs/cli/logging.py#L86) | `write_combined_ai_log()` | AI 对话合并日志 |
| [llm_client.py:157](ai_gen_reimbursement_docs/llm_client.py#L157) | `_save_prompt_log()` | 保存 AI prompt |
| [llm_client.py:183](ai_gen_reimbursement_docs/llm_client.py#L183) | `_save_response_log()` | 保存 AI response |
| [server.py:33](web_app/server.py#L33) | `SessionHandler` | Web UI SSE 日志路由 |
| [pipeline.py:85](ai_gen_reimbursement_docs/pipeline.py#L85) | `run_pipeline()` | 日志目录创建 + setup_logging 调用 |
