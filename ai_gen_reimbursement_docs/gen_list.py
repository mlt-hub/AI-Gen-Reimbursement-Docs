"""生成 项目需求清单.xlsx"""

import copy as _cpy
import logging
import os

from openpyxl.styles import Alignment

from ai_gen_reimbursement_docs.constants import (
    REQ_COL_SEQ, REQ_COL_PROJECT, REQ_COL_SUBSYSTEM, REQ_COL_L1, REQ_COL_L2,
    REQ_COL_L3, REQ_COL_PROC_TYPE, REQ_COL_WORKLOAD, REQ_COL_CFP, REQ_TOTAL_COLS,
    REQ_COL_KEY_MAP,
)
from ai_gen_reimbursement_docs.excel_source import (
    parse_module_tree_md, safe_load_workbook,
)

logger = logging.getLogger('ai_gen_reimbursement_docs.gen_list')


def parse_meta_md(meta_md_path: str) -> dict[str, str]:
    """解析文档元数据.md 为扁平字典。支持跨多行的表格值。"""
    from ai_gen_reimbursement_docs.gen_spec import parse_meta_md
    return parse_meta_md(meta_md_path)


def generate_list_xlsx_from_md(
    meta_md_path: str,
    tree_md_path: str,
    template_path: str,
    output_path: str,
    cfp_total: float = 0,
    fpa_reduced: float = 0,
) -> str:
    """生成项目需求清单.xlsx。

    cfp_total: 送审功能点 = gen-fpa-FPA工作量-总和.md 的原始值
    fpa_reduced: 送审工作量 = FPA 核减后的工作量
    """
    logger.info("开始生成项目需求清单.xlsx...")

    meta = parse_meta_md(meta_md_path)
    rows = parse_module_tree_md(tree_md_path)

    wb = safe_load_workbook(template_path, '项目需求清单')

    # ====== Sheet 1: 项目信息概览 ======
    ws1 = wb['项目信息概览']

    title = meta.get("项目信息概览-标题", "")
    ws1.cell(1, 1, title)

    ws1.cell(3, 2, meta.get("项目信息概览-项目名称", ""))
    ws1.cell(3, 3, meta.get("项目信息概览-子系统名称", ""))
    ws1.cell(3, 4, meta.get("项目信息概览-项目类型", ""))
    ws1.cell(3, 5, meta.get("项目信息概览-所属域", ""))
    ws1.cell(3, 6, meta.get("项目信息概览-所属系统", ""))
    ws1.cell(3, 7, meta.get("项目信息概览-需求部门", ""))
    ws1.cell(3, 8, meta.get("项目信息概览-需求负责人", ""))
    ws1.cell(3, 9, meta.get("项目信息概览-需求负责人联系方式", ""))

    if fpa_reduced > 0:
        ws1.cell(3, 10, fpa_reduced)

    if cfp_total > 0:
        ws1.cell(3, 11, cfp_total)

    # ====== Sheet 2: 功能清单 ======
    ws2 = wb['功能清单']

    fl_title = meta.get("功能清单-标题", "")
    ws2.cell(1, 1, fl_title)

    for merge_range in list(ws2.merged_cells.ranges):
        ws2.unmerge_cells(str(merge_range))

    if ws2.max_row >= 3:
        ws2.delete_rows(3, ws2.max_row - 2)

    project_name = meta.get("功能清单-项目名称", "")
    subsystem = meta.get("功能清单-子系统", "")

    data_rows_data = []
    seen_modules = set()
    seq = 0

    _center = Alignment(horizontal='center', vertical='center')
    _center_wrap = Alignment(horizontal='center', vertical='center', wrap_text=True)

    _tmpl_border = _cpy.copy(ws2.cell(2, 1).border)

    for r in rows:
        key = (r["一级模块"], r["二级模块"], r["三级模块"])
        if key not in seen_modules:
            seen_modules.add(key)
            seq += 1
            row_idx = seq + 2
            _req_data = {
                "序号": seq, "项目名称": project_name, "子系统": subsystem,
                "一级模块": r["一级模块"], "二级模块": r["二级模块"],
                "三级模块": r["三级模块"], "功能过程类型": r["功能过程类型"],
            }
            for col_idx in range(1, REQ_TOTAL_COLS):
                c = ws2.cell(row_idx, col_idx)
                c.alignment = _center
                c.border = _tmpl_border
            for col_idx, key in REQ_COL_KEY_MAP.items():
                ws2.cell(row_idx, col_idx, _req_data.get(key, ""))
            ws2.cell(row_idx, REQ_COL_PROJECT).alignment = _center_wrap
            if fpa_reduced > 0:
                ws2.cell(row_idx, REQ_COL_WORKLOAD, fpa_reduced)
            if cfp_total > 0:
                ws2.cell(row_idx, REQ_COL_CFP, cfp_total)
            data_rows_data.append({
                "row": row_idx,
                "project_name": project_name,
                "subsystem": subsystem,
                "module_l1": r["一级模块"],
                "module_l2": r["二级模块"],
            })

    if seq > 0:
        ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=REQ_TOTAL_COLS)
        ws2.cell(1, 1).alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    for col_idx in [REQ_COL_PROJECT, REQ_COL_SUBSYSTEM, REQ_COL_L1, REQ_COL_L2]:
        i = 0
        while i < len(data_rows_data):
            val_key = {REQ_COL_PROJECT: "project_name", REQ_COL_SUBSYSTEM: "subsystem",
                       REQ_COL_L1: "module_l1", REQ_COL_L2: "module_l2"}[col_idx]
            curr_val = data_rows_data[i][val_key]
            j = i
            while j < len(data_rows_data) and data_rows_data[j][val_key] == curr_val:
                j += 1
            count = j - i
            if count > 1:
                ws2.merge_cells(
                    start_row=data_rows_data[i]["row"],
                    start_column=col_idx,
                    end_row=data_rows_data[j - 1]["row"],
                    end_column=col_idx
                )
                ws2.cell(data_rows_data[i]["row"], col_idx).border = _tmpl_border
            i = j

    if len(data_rows_data) > 1:
        for _col in (REQ_COL_WORKLOAD, REQ_COL_CFP):
            ws2.merge_cells(
                start_row=data_rows_data[0]["row"],
                start_column=_col,
                end_row=data_rows_data[-1]["row"],
                end_column=_col
            )
            _top_cell = ws2.cell(data_rows_data[0]["row"], _col)
            _top_cell.border = _tmpl_border
            _top_cell.alignment = _center

        for _col in (REQ_COL_WORKLOAD, REQ_COL_CFP):
            for _r in range(data_rows_data[0]["row"], data_rows_data[-1]["row"] + 1):
                ws2.cell(_r, _col).border = _tmpl_border

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    try:
        wb.save(output_path)
    except PermissionError:
        logger.error(
            "无法写入 %s —— 文件可能被 Excel/WPS 占用，请关闭后重试", output_path
        )
        raise
    logger.info(f"项目需求清单已生成: {output_path} ({len(seen_modules)} 模块)")

    return output_path
