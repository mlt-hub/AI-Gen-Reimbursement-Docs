"""Markdown 表格解析工具函数。"""


def parse_md_table_row(line: str, min_cols: int = 1) -> list[str] | None:
    """解析一行 Markdown 表格行，返回单元格列表，或 None。

    自动处理 split('|') 带来的首尾空串，保留中间的空单元格。
    不处理分隔行（|---|---|），由调用方自行跳过。

    Args:
        line: "| a | b | c |" 格式的一行
        min_cols: 最少期望列数，不足时返回 None

    Returns:
        清理后的单元格字符串列表（已 strip），如果格式不符返回 None
    """
    line = line.rstrip()
    if not (line.startswith("|") and line.endswith("|")):
        return None
    cells = [c.strip() for c in line.split("|")]
    cells = cells[1:-1]  # 去掉 split('|') 产生的首尾空串
    if len(cells) < min_cols:
        return None
    return cells
