# AI 接入点一览

当前项目共有 **4 处 AI 调用点**，分布在 3 个文件中。所有调用均走 `anthropic` SDK，通过 `client.messages.create()` 发出请求。

---

## 1. COSMIC 功能点填充（核心链路）

| 项目 | 说明 |
|------|------|
| **文件** | `cosmic_tool/cosmic_llm.py` |
| **函数** | `generate_cosmic_items()` |
| **触发命令** | `--gen-cosmic`、`--fill-md`、`--all` |
| **调用次数** | 每 L3 模块 1 次（19 模块 × 1 次 = 19 次） |
| **max_tokens** | 6000（从 `~/.cosmic-tool/system_config.yaml` 读取） |
| **输入** | L3 模块的功能描述、功能过程列表 |
| **输出** | `CosmicItem[]` — 每个功能过程的 COSMIC 子过程分解（移动类型、数据组、数据属性等） |
| **特点** | 支持交互模式（`interactive=True`），调用前询问用户是否继续 |

调用链路：
```
fill_md_with_ai()          md_handler.py:280
  └─ generate_cosmic_items()   cosmic_llm.py:302
       └─ client.messages.create()    cosmic_llm.py:381
```

---

## 2. FPA 计算依据 AI 填充

| 项目 | 说明 |
|------|------|
| **文件** | `cosmic_tool/gen_xlsx.py` |
| **函数** | `_ai_fill_fpa()` → `_call_llm()` |
| **触发命令** | `--gen-fpa`、`--gen-all` |
| **调用次数** | 每行 1 次（112 行 × 1 次 = 112 次） |
| **max_tokens** | 2048（硬编码） |
| **输入** | 功能过程描述 + 类型（EI/ILF）+ 判定原则列表 |
| **输出** | `计算依据归类` + `计算依据说明` 两列 |
| **特点** | 跳过已填写的行，只填空白行 |

调用链路：
```
ai_fill_fpa_md()           gen_xlsx.py:303
  └─ _ai_fill_fpa()            gen_xlsx.py:225
       └─ _call_llm()              gen_xlsx.py:118
            └─ client.messages.create()   gen_xlsx.py:130
```

---

## 3. AI 辅助模块树解析（docx 模式）

| 项目 | 说明 |
|------|------|
| **文件** | `cosmic_tool/docx_parser.py` |
| **函数** | `ai_build_module_tree()` |
| **触发命令** | `--docx --parse-by-ai` |
| **调用次数** | 每次解析 1 次 |
| **max_tokens** | 4096（硬编码） |
| **输入** | docx 中所有标题段落的样式 ID 和文本 |
| **输出** | JSON 格式的 L1/L2/L3 模块层次结构 |
| **特点** | 失败时静默回退到硬编码 `build_module_tree()` |

调用链路：
```
ai_build_module_tree()     docx_parser.py:438
  └─ client.messages.create()    docx_parser.py:485
```

---

## 4. 需求说明书 AI 内容生成

| 项目 | 说明 |
|------|------|
| **文件** | `cosmic_tool/gen_docx.py` |
| **函数** | `_call_llm()` |
| **触发命令** | `--gen-spec`（通过 `#AI生成#` 标记触发） |
| **调用次数** | 按模板中 `#AI生成#` 标记数 |
| **max_tokens** | 1024（硬编码） |
| **输入** | 模板段落中 `#AI生成#` 标记后的提示词 |
| **输出** | 一段通顺的中文描述，替换标记位置 |
| **特点** | `#AI生成#` 标记在模板 docx 中预置；调用失败时保留提示词原文 |

调用链路：
```
generate_docx()            gen_docx.py:378
  └─ (docx 模板替换过程中)
       └─ _call_llm()          gen_docx.py:316
            └─ client.messages.create()   gen_docx.py:346
```

---

## 公共 AI 配置

所有调用统一从 `~/.cosmic-tool/.env` 读取：

```
ANTHROPIC_API_KEY=sk-xxx     # API Key
ANTHROPIC_BASE_URL=...       # 端点（默认: https://api.deepseek.com/anthropic）
ANTHROPIC_MODEL=...          # 模型名（默认: deepseek-v4-flash）
```

优先级：命令行 `--api-key` > `.env` 文件 > 系统环境变量 > `config.json`。

## 调用统计

| 场景 | 典型调用量 | 是否可关闭 |
|------|-----------|-----------|
| COSMIC 填充 | 19 次 / 项目 | 是，不传 `--api-key` |
| FPA 填充 | 112 次 / 项目 | 是，不传 `--api-key` |
| AI 模块树解析 | 1 次 / 项目 | 是，不用 `--parse-by-ai` |
| docx 内容生成 | 按模板标记数 | 是，不传 `--api-key` |
