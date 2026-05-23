# AI-Gen-Reimbursement-docs

AI 生成项目报账文档 — 从功能清单自动生成全套报账交付物。

`ard`（AI Reimbursement Documents）

---

## 快速开始

```bash
# 零参数：自动识别当前目录的功能清单并执行全流程
ard

# 显式指定文件
ard --from-excel 功能清单-录入模板.xlsx --gen-all
```

无参数运行时，`ard` 自动搜索当前目录的 `.xlsx` 文件，识别符合功能清单录入文档规范的文件（包含「功能清单-内容录入」Sheet），找到唯一匹配则自动执行全流程。

---

## 使用方式

### Excel 功能清单 → 全套交付物

从功能清单 Excel 生成 4 个交付物。

```bash
# 全流程（按依赖顺序自动执行）
ard --from-excel 功能清单-录入模板.xlsx --gen-all

# 分步执行
ard --from-excel 功能清单-录入模板.xlsx --gen-basedata  # 模块树 + 元数据
ard --from-excel 功能清单-录入模板.xlsx --gen-fpa       # FPA 工作量评估
ard --from-excel 功能清单-录入模板.xlsx --gen-cosmic    # COSMIC 功能点拆分表
ard --from-excel 功能清单-录入模板.xlsx --gen-list      # 需求清单
ard --from-excel 功能清单-录入模板.xlsx --gen-spec      # 需求说明书

# 指定输出目录
ard --from-excel 功能清单-录入模板.xlsx --gen-all --output-dir ./output

# 指定项目名称（自动创建子目录）
ard --from-excel 功能清单-录入模板.xlsx --gen-all --project-name 项目A
```

### 生成顺序

```
第0步：功能清单模块树.md + 文档元数据.md（模块树统计验证）
第1步：FPA 模板.md → AI 填充 → FPA 工作量评估.xlsx
第2步：COSMIC 模板.md → AI 填充 → 项目功能点拆分表.xlsx
第3步：项目需求清单.xlsx
       项目需求说明书.docx（基于数据源中间文件，可随时执行）
```

### 模板路径覆盖

```bash
ard --from-excel 功能清单-录入模板.xlsx --gen-fpa \
  --fpa-out-template 自定义路径/FPA模板.xlsx

ard --from-excel 功能清单-录入模板.xlsx --gen-spec \
  --spec-out-template 自定义路径/说明书模板.docx
```

| CLI 参数 | 对应模板 |
|----------|---------|
| `--fpa-out-template` | FPA 工作量评估模板 |
| `--cosmic-out-template` | COSMIC 功能点拆分表模板 |
| `--list-out-template` | 需求清单模板 |
| `--spec-out-template` | 需求说明书模板 |

优先级：CLI 参数 > Excel Sheet 8 配置 > `data/out_templates/` 默认目录。

---

## Web UI

启动 Web 界面，支持本机模式和远程服务模式。

```bash
ard --web                          # CLI 快捷启动
python -m uvicorn web_app.server:app --host 0.0.0.0 --port 8080  # 手动启动
```

浏览器打开 `http://localhost:8080`。

| 模式 | 适用场景 | 说明 |
|------|---------|------|
| 本机模式 | 单人本机使用 | 直接读本地 xlsx，产物写本地目录，点按钮打开 |
| 服务模式 | 多人远程访问 | 浏览器上传文件，产物打包 ZIP 下载 |

---

## 配置

### 初始化

```bash
ard --init-config
```

在 `~/.ai-gen-reimbursement-docs/` 下生成配置文件：
- `.env` — API Key / 端点 / 模型
- `system_config.yaml` — Sheet 名称映射、模板路径、AI 限制
- `business_rules.yaml` — CFP 计算公式

### API Key

```bash
# 方式 1：配置文件（推荐）
# 编辑 ~/.ai-gen-reimbursement-docs/.env
ANTHROPIC_API_KEY=sk-xxx

# 方式 2：命令行参数
ard --from-excel 功能清单.xlsx --gen-all --api-key sk-xxx

# 方式 3：环境变量
set ANTHROPIC_API_KEY=sk-xxx
```

---

## 源文件结构

`功能清单-录入模板.xlsx` 包含以下 Sheet：

| Sheet | 内容 |
|-------|------|
| `模板说明` | 使用说明 |
| `1、工单需求-元数据录入` | 工单信息、项目描述 |
| `2、功能清单-内容录入` | 模块树 + 功能过程 |
| `3、FPA工作量评估-元数据录入` | 子系统、判定原则、公式 |
| `4、项目需求说明书-元数据录入` | DOCX 替换文本 |
| `5、预估工作量-元数据录入` | 工作量预估 |
| `6、项目功能点拆分表-元数据录入` | COSMIC 拆分配置 |
| `7、项目需求清单-元数据录入` | 需求清单配置 |
| `8、各文档-模板路径录入` | 自定义模板路径 |
| `9、测试元数据自动统计` | 解析统计（运行时自动生成） |

---

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--from-excel` | Excel 功能清单路径 |
| `--gen-all` | 全流程按依赖顺序执行 |
| `--gen-basedata` | 第0步：生成模块树 + 元数据 MD |
| `--gen-fpa` | 第1步：生成 FPA 工作量评估 |
| `--gen-cosmic` | 第2步：生成 COSMIC 功能点拆分表 |
| `--gen-list` | 第3步：生成需求清单 |
| `--gen-spec` | 生成需求说明书 |
| `--output-dir` | 输出目录（默认源文件所在目录） |
| `--project-name` | 项目名称（自动创建子目录） |
| `--clean` | 删除旧输出再重新生成 |
| `--api-key`, `-k` | API Key |
| `--model`, `-m` | 模型名称（默认 deepseek-v4-flash） |
| `--max-tokens` | 覆盖 AI max_tokens |
| `--init-config` | 初始化配置文件 |
| `--web` | 启动 Web UI |
| `--log` | 查看日志（可选 `tail`/`watch`/`open`） |
| `--version`, `-v` | 显示版本号 |
| `--test-sound` | 测试提示音 |
| `--fpa-out-template` | FPA 模板路径覆盖 |
| `--cosmic-out-template` | COSMIC 模板路径覆盖 |
| `--list-out-template` | 需求清单模板路径覆盖 |
| `--spec-out-template` | 需求说明书模板路径覆盖 |

---

## 日志

运行日志存放在 `{输出目录}/日志/`：

- `global_ai_gen_reimbursement_docs.log` — 全局日志
- `功能清单_run_{时间戳}.log` — 本次运行日志
- `ai_prompts/` — 每次 AI 调用的提示词
- `ai_responses/` — 每次 AI 调用的响应

---

## 发布版（exe）

从 [发布仓](https://github.com/mlt-hub/ai-gen-reimbursement-docs-release/releases) 下载 `ard-v*.zip`，解压后双击运行或命令行使用，无需安装 Python。

### 本地打包

```powershell
.\build_exe.ps1
```

产物在 `dist/` 目录下。
