# COSMIC 功能点拆分工具

从需求说明书（.docx）自动生成 COSMIC 功能点拆分表（.xlsx）。

## 使用方式

```bash
# 批量处理当前目录所有 docx
cosmic

# 一键全流程
cosmic --docx "需求书.docx" --all

# 分阶段
cosmic --docx "需求书.docx" --init-md   # 生成空白 MD
cosmic --docx "需求书.docx" --fill-md   # AI 填充
cosmic --docx "需求书.docx" --md        # 生成 Excel
```

## 发布版（exe）

从 [Releases](https://github.com/mlt-hub/cosmic-tool/releases) 下载 `cosmic_v*.exe`，无需安装 Python。

## 开发者

```bash
pip install -e .
cosmic --version
```
