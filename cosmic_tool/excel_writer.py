"""Write COSMIC decompositions to Excel template."""

import copy
from itertools import groupby

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

from .models import CosmicItem


# Read a reference cell style from the template to apply to new cells
_REF_STYLE = Font(name='微软雅黑', size=11, color='FF000000')
_REF_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
_REF_BORDER = Border(
    left=Side(style='thin', color='FF000000'),
    right=Side(style='thin', color='FF000000'),
    top=Side(style='thin', color='FF000000'),
    bottom=Side(style='thin', color='FF000000'),
)
_CENTER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
_LEFT_ALIGN = Alignment(horizontal='left', vertical='center', wrap_text=True)


def _get_ref_style(ws, row: int, col: int) -> dict:
    """Extract style from a reference cell."""
    cell = ws.cell(row=row, column=col)
    return {
        'font': copy.copy(cell.font),
        'fill': copy.copy(cell.fill),
        'alignment': copy.copy(cell.alignment),
        'border': copy.copy(cell.border),
        'number_format': cell.number_format,
    }


def _apply_style(cell, style: dict) -> None:
    """Apply style dict to a cell."""
    cell.font = style['font']
    cell.fill = style['fill']
    cell.alignment = style['alignment']
    cell.border = style['border']
    cell.number_format = style['number_format']


def write_to_template(
    template_path: str,
    output_path: str,
    items: list[CosmicItem]
) -> None:
    """Write COSMIC items to Excel template.

    Preserves header rows (1-5) and formatting, fills data starting at row 6.
    """
    wb = openpyxl.load_workbook(template_path)
    ws = wb['2、功能点拆分表']

    # --- Clear existing data (rows 6+) ---
    # 1. Remove merged cells in data area
    merged_to_remove = []
    for mr in ws.merged_cells.ranges:
        if mr.min_row >= 6:
            merged_to_remove.append(str(mr))
    for mr_str in merged_to_remove:
        ws.unmerge_cells(mr_str)

    # 2. Clear cell values
    for row in ws.iter_rows(min_row=6, max_row=ws.max_row, min_col=1, max_col=13):
        for cell in row:
            cell.value = None

    # 3. Clear data validations (if any) for data area
    if ws.data_validations:
        new_dvs = []
        for dv in ws.data_validations.dataValidation:
            # Keep validations that don't overlap with data area
            keep = True
            if hasattr(dv, 'sqref') and dv.sqref:
                dv_range = str(dv.sqref)
                # Simple check: if range refers to rows >= 6, remove it
                try:
                    min_row = int(dv_range.split(':')[0].replace('$', '').lstrip('ABCDEFGHIJKLM'))
                    if min_row >= 6:
                        keep = False
                except (ValueError, IndexError):
                    pass
            if keep:
                new_dvs.append(dv)
        ws.data_validations.dataValidation = new_dvs

    # --- Flatten all rows ---
    all_rows = []
    for item in items:
        all_rows.extend(item.to_rows())

    if not all_rows:
        print("No data rows to write.")
        wb.save(output_path)
        return

    # Get reference style from row 6 of template (or use default)
    ref_style = _get_ref_style(ws, 6, 1)

    # Column K (数据属性) should be left-aligned
    # Column H (子过程描述) should be left-aligned

    # --- Write data rows ---
    start_row = 6
    for i, row_data in enumerate(all_rows):
        row_num = start_row + i
        for col_idx in range(1, 14):
            cell = ws.cell(row=row_num, column=col_idx)
            col_letter = get_column_letter(col_idx)
            key_map = {
                1: 'project', 2: 'module_l1', 3: 'module_l2', 4: 'module_l3',
                5: 'user', 6: 'trigger', 7: 'process', 8: 'sub_process',
                9: 'move_type', 10: 'data_group', 11: 'data_attrs',
                12: 'reuse', 13: 'cfp'
            }
            if col_idx == 13:
                # CFP 列用公式：=IF(L{row}="新增",1,IF(L{row}="复用",1/3,0))
                cell.value = f'=IF(L{row_num}="新增",1,IF(L{row_num}="复用",1/3,0))'
                cell.number_format = '0.00'
            else:
                cell.value = row_data.get(key_map[col_idx], '')

            # Apply style
            _apply_style(cell, ref_style)

            # Special alignment for long text columns
            if col_idx in (8, 10, 11):
                cell.alignment = _LEFT_ALIGN

    # --- Apply merged cells for repeating values ---
    total_rows = len(all_rows)

    # Merge project name (column A) - all rows
    if total_rows > 1:
        ws.merge_cells(start_row=start_row, start_column=1,
                       end_row=start_row + total_rows - 1, end_column=1)

    # Merge L1 module (column B)
    _merge_column_groups(ws, start_row, total_rows, 2, all_rows, 'module_l1')

    # Merge L2 module (column C)
    _merge_column_groups(ws, start_row, total_rows, 3, all_rows, 'module_l2')

    # Merge L3 module (column D)
    _merge_column_groups(ws, start_row, total_rows, 4, all_rows, 'module_l3')

    # Merge process name (column G)
    _merge_column_groups(ws, start_row, total_rows, 7, all_rows, 'process')

    # Keep the already-set data validations for reuse dropdown
    # Add new data validation for L column (复用度) - dropdown
    _add_reuse_validation(ws, start_row, total_rows)

    wb.save(output_path)
    print(f"Written {total_rows} rows to {output_path}")


def _merge_column_groups(ws, start_row, total_rows, col, all_rows, key):
    """Merge cells in a column for groups of consecutive same values."""
    i = 0
    while i < total_rows:
        val = all_rows[i].get(key, '')
        j = i
        while j < total_rows and all_rows[j].get(key, '') == val:
            j += 1
        count = j - i
        if count > 1:
            ws.merge_cells(
                start_row=start_row + i,
                start_column=col,
                end_row=start_row + j - 1,
                end_column=col
            )
        i = j


def _add_reuse_validation(ws, start_row, total_rows):
    """Add dropdown validation for 复用度 column (L)."""
    from openpyxl.worksheet.datavalidation import DataValidation
    if total_rows > 0:
        dv = DataValidation(
            type="list",
            formula1='"新增,复用,利旧"',
            allow_blank=True
        )
        dv.sqref = f"L{start_row}:L{start_row + total_rows - 1}"
        ws.add_data_validation(dv)


def write_environment_sheet(
    template_path: str,
    output_path: str,
    project_name: str,
    target: str,
    necessity: str
) -> None:
    """Write construction goals and necessity to the environment sheet."""
    wb = openpyxl.load_workbook(template_path)
    ws = wb['1、环境图']

    # Find and update the target/necessity cells
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=27):
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                if '建设目标' in cell.value and len(cell.value) < 20:
                    # The cell to the right is where the target text goes
                    target_cell = ws.cell(row=cell.row, column=cell.column + 1)
                    # Find the merged range containing this cell
                    # Actually just write to the cell - it's part of a merged range
                    if target:
                        target_cell.value = target
                if '建设必要性' in cell.value and len(cell.value) < 20:
                    necessity_cell = ws.cell(row=cell.row, column=cell.column + 1)
                    if necessity:
                        necessity_cell.value = necessity

    wb.save(output_path)
    print(f"Updated 1、环境图 sheet with project info")


def copy_template_sheets(
    template_path: str,
    output_path: str,
    func_point_sheet_only: bool = False
) -> None:
    """Copy the complete template preserving all sheets."""
    wb = openpyxl.load_workbook(template_path)
    wb.save(output_path)
    print(f"Template copied to {output_path}")
