"""集成测试：验证功能清单解析与原始数据一致性。"""
import os
import pytest
import openpyxl
from ai_gen_reimbursement_docs.excel_source import _resolve_inherited_rows

# 测试数据路径（多来源查找）
_EXCEL_PATHS = [
    "F:/mlt/mlt-tests/AI-Cosmic/excel-to-docx/6/功能清单-录入-模板.xlsx",
    "data/功能清单-录入-模板.xlsx",
]
EXCEL_PATH = ""
for _p in _EXCEL_PATHS:
    if os.path.exists(_p):
        EXCEL_PATH = _p
        break

_MD_TREE_PATHS = [
    "F:/mlt/mlt-tests/AI-Cosmic/excel-to-docx/6/4/md/功能清单模块树.md",
    "F:/mlt/mlt-tests/AI-Cosmic/excel-to-docx/6/1/md/功能清单模块树.md",
    "AI-Outputs/md/功能清单模块树.md",
]
MD_TREE_PATH = ""
for _p in _MD_TREE_PATHS:
    if os.path.exists(_p):
        MD_TREE_PATH = _p
        break

pytestmark = pytest.mark.skipif(
    not EXCEL_PATH or not MD_TREE_PATH,
    reason="测试数据路径不存在，跳过集成测试"
)

# 数据集中的 sheet 名（含破折号）
SHEET_FUNC = "2、功能清单-内容录入"

# 对比维度: (col_letter, row_index_after_resolve)
_CHECKS: list[tuple[str, int, str]] = [
    ('A', 0, "入口（个数）"),
    ('B', 1, "一级模块（个数）"),
    ('C', 2, "二级模块（个数）"),
    ('D', 3, "三级模块（个数）"),
    ('G', 6, "功能过程（个数）"),
]


def test_resolved_unique_counts_match_raw():
    """resolve 后各列唯一值数 == 原始数据唯一值数（合并单元格继承不改变唯一值）。"""
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws_data = wb[SHEET_FUNC]
    rows = _resolve_inherited_rows(ws_data)

    for col_letter, idx, name in _CHECKS:
        raw_vals = set()
        for cell in ws_data[col_letter]:
            if cell.row == 1:
                continue
            v = cell.value
            if v is not None and str(v).strip():
                raw_vals.add(str(v).strip())

        resolved_vals = {r[idx] for r in rows if r[idx]}
        assert len(resolved_vals) == len(raw_vals), \
            f"{name}: 原始唯一值 {len(raw_vals)}, resolve 后 {len(resolved_vals)}"

    wb.close()


def test_module_tree_build():
    """验证 build_modules_from_tree_md 构建的模块数与原始数据一致。"""
    from ai_gen_reimbursement_docs.excel_source import build_modules_from_tree_md

    modules = build_modules_from_tree_md(MD_TREE_PATH)
    l1 = {m.name for m in modules if m.level == 1}

    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws_data = wb[SHEET_FUNC]
    raw_l1 = set()
    for cell in ws_data['B']:
        if cell.row == 1:
            continue
        v = cell.value
        if v is not None and str(v).strip():
            raw_l1.add(str(v).strip())
    wb.close()
    assert l1 == raw_l1, f"L1 不匹配: {l1} vs {raw_l1}"
