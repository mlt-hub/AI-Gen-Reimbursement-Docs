"""集成测试：验证功能清单解析与原始数据一致性。"""

import openpyxl
from cosmic_tool.excel_source import _resolve_inherited_rows

EXCEL_PATH = "data/功能清单-录入-模板.xlsx"

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
    ws_data = wb['2、功能清单内容录入']
    rows = _resolve_inherited_rows(ws_data)
    wb.close()

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


def test_module_tree_build():
    """验证 _build_modules_from_tree_md 构建的模块数与原始数据一致。"""
    from cosmic_tool.main import _build_modules_from_tree_md

    modules = _build_modules_from_tree_md(
        "AI-Outputs/md/功能清单模块树.md"
    )
    l1 = {m.name for m in modules if m.level == 1}
    l2 = {m.name for m in modules if m.level == 2}
    l3 = {m.name for m in modules if m.level == 3}

    # 验证 L1 唯一值匹配原始B列唯一值
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws_data = wb['2、功能清单内容录入']
    raw_l1 = set()
    for cell in ws_data['B']:
        if cell.row == 1:
            continue
        v = cell.value
        if v is not None and str(v).strip():
            raw_l1.add(str(v).strip())
    wb.close()
    assert l1 == raw_l1, f"L1 不匹配: {l1} vs {raw_l1}"
