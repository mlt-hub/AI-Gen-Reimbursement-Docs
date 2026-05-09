"""测试 Markdown 表格解析工具函数。"""

from cosmic_tool.md_table import parse_md_table_row


def test_正常行():
    cells = parse_md_table_row("| a | b | c |", min_cols=1)
    assert cells == ["a", "b", "c"]


def test_空单元格保留():
    cells = parse_md_table_row("| a |  | c |", min_cols=3)
    assert cells == ["a", "", "c"]


def test_全部空单元格():
    cells = parse_md_table_row("|  |  |  |", min_cols=3)
    assert cells == ["", "", ""]


def test_单个单元格():
    cells = parse_md_table_row("| 仅标题 |", min_cols=1)
    assert cells == ["仅标题"]


def test_只有竖线():
    cells = parse_md_table_row("||", min_cols=1)
    assert cells == [""]


def test_非表格行():
    assert parse_md_table_row("普通文本行", min_cols=1) is None


def test_不以竖线结尾():
    assert parse_md_table_row("| a | b", min_cols=1) is None


def test_不以竖线开头():
    assert parse_md_table_row("a | b |", min_cols=1) is None


def test_列数不足():
    assert parse_md_table_row("| a | b |", min_cols=3) is None


def test_分隔行():
    """分隔行应由调用方自行跳过，但解析器仍应返回内容。"""
    cells = parse_md_table_row("|------|------|", min_cols=1)
    assert cells is not None
    assert all(c == "------" for c in cells)


def test_空格处理():
    cells = parse_md_table_row("|  你好   |  世界  |", min_cols=2)
    assert cells == ["你好", "世界"]


def test_空行返回None():
    assert parse_md_table_row("", min_cols=1) is None
