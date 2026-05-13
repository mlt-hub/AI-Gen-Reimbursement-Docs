# COSMIC 项目分析报告

> 分析日期：2026-05-13 | 版本：v5.0.0 | 代码规模：~7,500 行 Python

---

## 一、项目概述

COSMIC 是一个基于 AI 的功能点拆分工具，将软件需求说明书（.docx）自动转换为 COSMIC 功能点拆分表（.xlsx）、FPA 工作量评估、需求清单等交付物。支持两种工作流：

| 工作流 | 输入 | 输出 |
|--------|------|------|
| **传统路径** | 需求说明书 .docx | 功能点拆分表 .xlsx |
| **Excel 路径** | 功能清单录入表 .xlsx | 全套交付物（FPA、需求清单、需求说明书、功能点拆分表） |

---

## 二、文件结构

```
ai_cosmic/
├── cosmic_tool/               # 主包（13 个 .py 文件）
│   ├── main.py                # CLI 入口 + 流程编排（1672 行）
│   ├── docx_parser.py         # docx 模块树解析（912 行）
│   ├── docx_to_md.py          # docx → Markdown 转换（366 行）
│   ├── md_handler.py          # Markdown 模板导出/填充/解析（451 行）
│   ├── cosmic_llm.py          # AI 生成 COSMIC 数据（656 行）
│   ├── excel_writer.py        # COSMIC 数据写入 Excel 模板（434 行）
│   ├── excel_source.py        # Excel 功能清单解析（362 行）
│   ├── gen_xlsx.py            # FPA 评估/需求清单生成（760 行）
│   ├── gen_spec.py            # 需求说明书生成（721 行）
│   ├── config_utils.py        # 配置加载（458 行）
│   ├── models.py              # 数据模型（67 行）
│   └── md_table.py            # Markdown 表格解析工具（24 行）
├── config/                    # 配置模板
├── tests/                     # 测试（仅 2 个文件）
├── docs/                      # 文档
├── data/                      # 运行时数据、模板
└── .github/workflows/         # CI/CD
```

---

## 三、优点

### 3.1 功能完整，双工作流设计

- **传统路径**：docx → 模块树解析 → Markdown → AI 填充 COSMIC → Excel 输出，覆盖完整链路
- **Excel 路径**：功能清单录入表 → 自动生成全套交付物（FPA 评估、需求清单、需求说明书、拆分表），"一键全流程"非常实用

### 3.2 配置驱动架构

- 系统提示词、模型参数、业务规则全部外置到 YAML，调整 prompt 无需改代码
- `_migrate_config()` 启动时自动检测新配置项并追加到用户配置，升级友好
- `.env` 文件 + 环境变量 + CLI 参数三级覆盖

### 3.3 三种解析策略自适应

| 策略 | 原理 | 适用场景 |
|------|------|----------|
| 标题样式 | 解析 Word style_id 到层级映射 | 使用标准标题样式编写的文档 |
| 多级列表格式 | 解析 numId + ilvl 到层级映射 | 使用 Word 多级列表编号的文档 |
| 编号格式 | 解析 ilvl + numFmt 到层级映射 | 使用自定义编号格式的文档 |
| AI 解析（降级）| 调用 LLM 提取标题层级 | 以上策略均失败时 |

### 3.4 自学习映射机制

每次解析新的 docx 文件时，自动将检测到的样式/编号映射保存到 `~/.cosmic-tool/docx_parse_mapping_rules.yaml`，后续同类型文档可复用。

### 3.5 工程化基础较好

- GitHub Actions 自动构建 + PyInstaller 打包 exe
- 日志系统完整，AI 每次调用的 prompt/response 独立存档
- 有术语文档 (`docs/user/术语.md`) 帮助理解领域概念
- 解析结果支持 `expected_result.json` 校验

### 3.6 中文生态友好

- 注释、日志、变量命名全面使用中文
- 模板文案、sheet 名称均为中文，符合国内使用场景

---

## 四、缺点

### 4.1 `main()` 函数严重膨胀 —— 1070 行

[cosmic_tool/main.py:526-1591](cosmic_tool/main.py) 是项目最大的单体函数，包含：

- 6 种运行模式的完整实现
- 批处理流程
- 配置初始化
- 参数解析
- 日志查看、版本显示、声音测试等辅助功能

至少 6 层嵌套分支判断，几乎不可维护，应拆分为独立处理函数。

### 4.2 AI 调用逻辑重复 5 次

相同模式在 5 个位置独立实现：

| 位置 | 函数 | 行数 |
|------|------|------|
| cosmic_llm.py | `generate_cosmic_items()` | 337, 431-438 |
| docx_parser.py | `ai_build_module_tree()` | 486, 495-501 |
| gen_spec.py | `_call_ai_for_text()` | 421-432 |
| gen_xlsx.py | `_call_llm()` | 111-122 |
| main.py | `_call_llm_once()` | 458-468 |

每个位置都独立实现了"创建 anthropic client → 调用 API → 提取文本 → 保存日志"。应抽取为公共 `llm_client.py` 模块。同样，AI 日志保存逻辑（save prompt / save response）也在 5 个模块中重复实现。

### 4.3 大量硬编码

| 类型 | 示例 | 涉及文件 |
|------|------|----------|
| 模型名 | `"deepseek-v4-flash"` | config_utils, md_handler, docx_parser, cosmic_llm, main |
| 路径 | `'data/templates/项目功能点拆分表-模板.xlsx'` | main |
| Excel Sheet 名 | `'1、工单需求-元数据录入'` 等 7+ 个 | excel_source, gen_xlsx |
| Excel 列号 | `col_idx in (8, 10, 11)`、`start_row = 6` | excel_writer, gen_xlsx |
| 默认角色 | `"操作员"`、`"地市后台"` | md_handler, cosmic_llm |
| 章节检测 | `"4"`、`"功能需求"`、`"5"` | docx_to_md, docx_parser |
| 列标题 | `"入口"`、`"一级模块"`、`"功能过程"` 等 | excel_source, gen_xlsx, gen_spec, md_handler |

### 4.4 配置加载严重重复

[cosmic_tool/config_utils.py](cosmic_tool/config_utils.py) 中至少 10 个 YAML 配置加载函数结构完全相同：

```
检查文件 → import yaml → safe_load → 访问 key → try/except 返回默认值
```

可抽取为通用 `_load_yaml_key(key, default)` 函数，减少约 150 行重复代码。

### 4.5 异常处理不一致且过于宽泛

- `_load_business_rules()` 吞掉所有异常返回 `{}`，调用方无法区分"文件不存在"和"格式损坏"
- 多处 `except Exception: pass` 或返回默认值，静默掩盖 bug
- `config_utils.py` 的加载函数中，仅 `load_max_tokens` 有 logger，其余 15+ 个函数无日志
- 没有自定义异常类，全部使用 `ValueError` 或 `Exception`

### 4.6 已知 Bug

| 文件 | 行号 | 严重程度 | 问题描述 |
|------|------|----------|----------|
| md_handler.py | 89 | **致命** | `item_groups.setdefault(key, [])` — `setdefault` 不是 dict 方法（应为 `setdefault`），运行时必然抛出 `AttributeError` |
| docx_parser.py | 848 | 中 | `get_project_name()` 被定义了两次，第一版引用 `hierarchy`、`l3_modules`、`processes` 三个未定义变量，是死代码 |
| gen_spec.py | 504-508 | 低 | `export_spec_template_md()` 末尾有重复的 `logger.info` + `return output_path`，属于拷贝残留 |

### 4.7 测试覆盖率极低

| 测试文件 | 测试数量 | 覆盖模块 |
|----------|----------|----------|
| test_md_table.py | 11 | md_table（24 行）|
| test_excel_stats.py | 2 | excel_source 部分 |

**估算覆盖率 < 5%**。以下核心模块完全没有测试：

- `docx_parser.py`（912 行）
- `cosmic_llm.py`（656 行）
- `excel_writer.py`（434 行）
- `md_handler.py`（451 行）
- `gen_xlsx.py`（760 行）
- `gen_spec.py`（721 行）

### 4.8 函数普遍过长

| 函数 | 行数 | 文件 |
|------|------|------|
| `main()` | ~1070 | main.py |
| `write_to_template()` | ~300 | excel_writer.py |
| `_build_modules_from_marks()` | ~230 | docx_parser.py |
| `generate_cosmic_items()` | ~190 | cosmic_llm.py |
| `generate_spec()` | ~165 | gen_spec.py |
| `generate_require_xlsx()` | ~145 | gen_xlsx.py |
| `parse_md_to_items()` | ~130 | md_handler.py |
| `generate_md_files()` | ~130 | excel_source.py |
| `generate_fpa_xlsx_from_md()` | ~120 | gen_xlsx.py |
| `_insert_module_details()` | ~115 | gen_spec.py |

超过 50 行的函数共 20+ 个，应拆分以提升可读性。

### 4.9 类型提示不完整

- `dict`、`list` 几乎全部缺少类型参数，应标注为 `dict[str, str]` 或 `list[dict]`
- excel_source.py、gen_xlsx.py 中大量函数无返回类型注解
- 闭包内嵌套函数（如 `_set_outline_lvl`）完全没有类型提示

### 4.10 模块耦合紧密

- 所有模块共享 `list[FunctionModule]` 作为数据传递结构，8 个模块直接依赖 models 的内部实现
- `gen_xlsx.py` 依赖 `gen_spec.py` 的 `_parse_meta_md` 函数，而不是抽取到独立的解析模块
- `cosmic_llm.py` 依赖 `docx_parser.py` 的 `FunctionModule` 和 `get_module_by_name`
- 函数内部 `import`（如 `cosmic_llm.py` 中 `from cosmic_tool.cosmic_llm import ...`）散落在 10+ 处，应统一提到模块顶部

---

## 五、安全评估

| 级别 | 问题 |
|------|------|
| 低 | API Key 通过命令行参数明文传递，可能出现在进程列表中 |
| 低 | `.env` 文件解析使用简单行扫描，未处理转义字符 |
| 低 | AI 返回的 JSON 未经 schema 验证直接 `json.loads()`，格式异常可能注入数据 |
| 信息 | 日志中保存了完整 prompt/response，需确保日志目录权限受控 |

---

## 六、优化建议（按优先级排序）

| 优先级 | 建议 | 预期收益 |
|--------|------|----------|
| **P0** | 修复 `setdefault` → `setdefault` bug（md_handler.py:89） | 修复运行时崩溃 |
| **P0** | 删除 `get_project_name()` 重复定义（docx_parser.py:848） | 消除死代码 |
| **P1** | 抽取 AI 调用公共模块 `llm_client.py` | 消除 ~200 行重复，统一错误处理和重试 |
| **P1** | 拆分 `main()` 为独立处理函数 | 提升可维护性 |
| **P2** | 抽取通用配置加载函数 | 减少 ~150 行重复 |
| **P2** | 硬编码常量提取到配置文件 | 提升灵活性 |
| **P3** | 为 docx_parser、cosmic_llm、excel_writer 补充测试 | 保障核心逻辑正确性 |
| **P3** | 长函数拆分（write_to_template、parse_md_to_items 等） | 提升可读性 |
| **P4** | 完善类型提示 | 启用静态检查 |
| **P4** | 引入自定义异常类 | 改善错误处理精度 |

---

## 七、总结

**功能得分：8/10** — 双工作流覆盖实际业务场景，配置驱动、策略多样、工程化基础扎实。

**质量得分：4/10** — 大函数、高重复、低测试覆盖率、硬编码严重、存在已知 bug，持续迭代成本高。

**建议**：当前阶段优先修复致命 bug（P0）并抽取 AI 公共模块（P1），可在不大规模重构的前提下显著改善代码质量。后续迭代中逐步补充测试、拆分大函数、消除硬编码。
