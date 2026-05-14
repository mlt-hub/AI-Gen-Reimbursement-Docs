# AI-Gen-Reimbursement-docs

AI生成项目报账文档
AI-Generated Project Reimbursement Documents
ai_gen_reimbursement_docs

# COSMIC 功能点拆分工具

从需求说明书（.docx）自动生成 COSMIC 功能点拆分表（.xlsx），
以及从 Excel 功能清单生成全套交付物。

## 使用方式

### docx → Excel（传统流程）

```bash
# 一键全流程
cosmic --docx "需求书.docx" --all

# 分阶段
cosmic --docx "需求书.docx" --init-md   # 生成模板 MD
cosmic --docx "需求书.docx" --fill-md   # AI 填充
cosmic --docx "需求书.docx" --md        # 生成 Excel

# 批量处理当前目录所有 docx
cosmic --docx-all
```

### Excel 功能清单 → 全套交付物

从 `功能清单-录入-模板.xlsx` 生成 4 个交付物，产物输出到源文件所在目录的 `products/`。

```bash
# 全流程（按依赖顺序自动执行）
cosmic --from-excel 功能清单-录入-模板.xlsx --gen-all

# 分步执行（可在 FPA 中填写核减后工作量）
# 第1步：生成功能清单模块树.md和文档元数据.md
cosmic --from-excel 功能清单-录入-模板.xlsx --gen-basedata  

# 第2.1步：FPA工作量评估.xlsx
cosmic --from-excel 功能清单-录入-模板.xlsx --gen-fpa 

# 第2.2步：功能点拆分表.xlsx
cosmic --from-excel 功能清单-录入-模板.xlsx --gen-cosmic 

# 第3步：需求清单.xlsx
cosmic --from-excel 功能清单-录入-模板.xlsx --gen-list      

# 单独生成需求说明书（无依赖，可随时执行）
cosmic --from-excel 功能清单-录入-模板.xlsx --gen-spec

# 不指定 --from-excel 时，默认找当前目录下的源文件
cosmic --gen-all
```

可选 `--output-dir` 指定输出目录，默认源文件所在目录。

### 模板路径覆盖

默认从 Excel 的 sheet 8 读取模板路径，回退到 `data/templates/`。也可用 CLI 参数覆盖：

```bash
cosmic --from-excel 功能清单-录入-模板.xlsx --gen-fpa \
  --fpa-template 自定义路径/FPA模板.xlsx
cosmic --from-excel 功能清单-录入-模板.xlsx --gen-spec \
  --spec-template 自定义路径/说明书模板.docx
```

| CLI 参数 | 对应模板 |
|----------|---------|
| `--fpa-template` | FPA工作量评估-模板 |
| `--cosmic-template` | 项目功能点拆分表-模板 |
| `--list-template` | 项目需求清单-模板 |
| `--spec-template` | 项目需求说明书-模板 |

优先级：CLI 参数 > Excel sheet 8 配置 > `data/templates/` 默认目录。

### 生成顺序说明

```
第0步：功能清单模块树.md + 文档元数据.md （模块树统计验证）
第1步：FPA模板.md → AI填充FPA.md → FPA工作量评估.xlsx
第2步：cosmic模板.md → AI填充cosmic.md → 项目功能点拆分表.xlsx
第3步：项目需求清单.xlsx      → CFP 总和
项目需求说明书.docx          → 无依赖，可随时执行（基于数据源中间文件）
```

## 源文件结构

`功能清单-录入-模板.xlsx` 含 10 个 sheet：

| Sheet | 内容 |
|-------|------|
| `模板说明` | 模板使用说明 |
| `1、工单需求内容录入` | 工单信息、项目描述 |
| `2、功能清单内容录入` | 模块树 + 功能过程（含合并单元格继承） |
| `3、FPA工作量评估元数据录入` | 子系统、资产标识、判定原则、公式 |
| `4、项目需求说明书元数据录入` | docx 替换文本 |
| `5、预估工作量和FPA核减后的工作量元数据录入` | 工作量、CFP限制 |
| `6、项目功能点拆分表元数据录入` | COSMIC 拆分配置 |
| `7、项目需求清单元数据录入` | 需求清单配置 |
| `8、待生成文档的模板路径录入` | 各模板文件路径 |
| `9、测试元数据自动统计` | 解析后的唯一值统计（自动写入文档元数据） |

## 数据源中间文件

`--from-excel` 流程自动生成以下中间文件（在 `products/md/` 下）：

| 文件 | 说明 |
|------|------|
| `功能清单模块树.md` | 模块树和功能过程列表（表格格式） |
| `文档元数据.md` | 所有元数据的键值对 + 统计验证数据 |
| `FPA模板.md` | FPA 工作量评估模板（空表格） |
| `AI填充FPA.md` | AI 填充后的 FPA 数据 |
| `cosmic模板.md` | COSMIC 拆分模板（空表格） |
| `AI填充cosmic.md` | AI 填充后的 COSMIC 数据 |

## 模块树统计验证

`--gen-basedata` 和 `--gen-all` 生成后会验证：
从 `功能清单模块树.md` 统计入口/L1/L2/L3/功能过程唯一值数，
与 `文档元数据.md` 中 `## 9、测试元数据自动统计` 对比。
结果输出到 CLI 和日志文件。

## 日志

运行日志输出到 `{输出目录}/log/`，包含：
- `global_cosmic_tool.log` — 全局日志（持续追加）
- `功能清单_run_{时间戳}.log` — 本次运行日志
- `ai_prompts/` — 每次 AI 调用的提示词
- `ai_responses/` — 每次 AI 调用的响应

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--docx` | 需求说明书 .docx 文件路径 |
| `--init-md` | 生成拆分表模板 MD |
| `--fill-md` | AI 填充 COSMIC 数据到模板 MD |
| `--md` | 从 MD 文件生成 Excel |
| `--all` | 一键全流程: docx → MD → AI 填充 → Excel |
| `--docx-all` | 批量处理当前目录所有 Word 文件 |
| `--from-excel` | Excel 功能清单路径（配合 --gen-* 使用） |
| `--gen-basedata` | 第0步：生成功能清单模块树.md 和 文档元数据.md |
| `--gen-fpa` | 第1步：生成 FPA 工作量评估 |
| `--gen-cosmic` | 第2步：生成 COSMIC 功能点拆分表 |
| `--gen-list` | 第3步：生成需求清单 |
| `--gen-spec` | 生成需求说明书 |
| `--gen-all` | 全流程按依赖顺序执行 |
| `--output-dir` | 输出目录（默认源文件所在目录的 `products/`） |
| `--fpa-template` | FPA工作量评估 模板路径 |
| `--cosmic-template` | 项目功能点拆分表 模板路径 |
| `--list-template` | 项目需求清单 模板路径 |
| `--spec-template` | 项目需求说明书 模板路径 |
| `--api-key` | API Key |
| `--model` | 模型名称 |
| `--show-tree` | 仅显示模块树 |
| `--no-llm` | 跳过 AI 阶段 |
| `--log` | 查看日志 |

## 发布版（exe）

从 [发布仓](https://github.com/mlt-hub/cosmic-tool-release/releases) 下载 `cosmic_v*.zip`，解压即可使用，无需安装 Python。
