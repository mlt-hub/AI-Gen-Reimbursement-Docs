# COSMIC 功能点拆分工具

## 项目概述

解析软件需求说明书（.docx），自动生成 COSMIC 功能点拆分表（.xlsx）。

## 核心文件

| 文件 | 说明 |
|------|------|
| `ai_gen_reimbursement_docs/main.py` | CLI 入口，参数解析，流程编排 |
| `ai_gen_reimbursement_docs/docx_parser.py` | docx 解析器，模块树构建，映射规则管理 |
| `ai_gen_reimbursement_docs/docx_to_md.py` | docx → Markdown 转换 |
| `ai_gen_reimbursement_docs/md_handler.py` | Markdown 模板导出/填充/解析 |
| `ai_gen_reimbursement_docs/config_utils.py` | 配置加载 |
| `ai_gen_reimbursement_docs/models.py` | 数据模型 |
| `config/docx_parse_mapping_rules.yaml.example` | 层级映射配置示例 |
| `config/docx_expected_result.example.json` | 预期结果 JSON 示例 |
| `data/word_template.docx` | Word 样式模板 |
| `docs/术语.md` | 术语文档 |

## 关键逻辑

- **解析流程**：`build_module_tree()` 先检查 `###` 标记 → 无标记则提示
- **三种策略**：`标题样式`（style_id）、`多级列表格式`（numId, ilvl）、`编号格式`（ilvl + numFmt）
- **章节检测**：`_find_chapter_boundaries()` 优先 `###文档开始###`/`###文档结束###`，降级为文本匹配
- **原文生成**：`convert_to_md()` 将 docx 第4章转为 Markdown
- **映射保存**：每次解析自动写入 `~/.ai-gen-reimbursement-docs/docx_parse_mapping_rules.yaml`

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--docx` | 指定 docx 文件 |
| `--mapping` | 指定映射规则名 |
| `--chapter-detection` | 指定章节检测配置名 |
| `--show-tree` | 仅显示模块树 |
| `--init-md` | 生成拆分表模板 |
| `--fill-md` | AI 填充 COSMIC 数据 |
| `--all` | 一键全流程 |

## 代码风格

- 中文注释，logger 以中文输出
- 函数名用下划线命名法
- 使用 Python type hints
- 避免硬编码，优先从配置读取
- 代码用中文注释，越详细越好

## 依赖

- `python-docx`（字数转换）
- `openpyxl`（Excel 输出）
- `anthropic`（AI 填充）
