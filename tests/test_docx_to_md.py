"""docx_to_md 纯函数测试 —— _detect_marker_level, _flush_list_buffer, _section_config。"""
import pytest
from unittest.mock import MagicMock
from cosmic_tool.docx_to_md import (
    _detect_marker_level,
    _flush_list_buffer,
    _inline_formatting,
)


class TestDetectMarkerLevel:
    def test_l1_marker(self):
        assert _detect_marker_level("###一级模块### 用户管理") == 2

    def test_l1_marker_colon(self):
        assert _detect_marker_level("###一级模块: 用户管理") == 2

    def test_l2_marker(self):
        assert _detect_marker_level("###二级模块### 用户注册") == 3

    def test_l3_marker(self):
        assert _detect_marker_level("###三级模块### 注册表单") == 4

    def test_process_marker(self):
        assert _detect_marker_level("###功能过程### 提交注册") == 5

    def test_doc_begin_marker_not_detected(self):
        """文档开始/结束标记不由此函数处理（由 _find_chapter_boundaries 处理）。"""
        assert _detect_marker_level("###文档开始###") is None

    def test_doc_end_marker_not_detected(self):
        assert _detect_marker_level("###文档结束###") is None

    def test_no_marker(self):
        assert _detect_marker_level("普通文本 无标记") is None

    def test_empty_string(self):
        assert _detect_marker_level("") is None

    def test_partial_marker(self):
        """非完整标记不应匹配。"""
        assert _detect_marker_level("##一级模块 不完整") is None


class TestFlushListBuffer:
    def test_flushes_items(self):
        buf = ["- item1", "- item2"]
        lines = ["# Header", ""]
        _flush_list_buffer(buf, lines)
        assert buf == []
        assert lines == ["# Header", "", "- item1", "- item2", ""]

    def test_empty_buffer_noop(self):
        buf = []
        lines = ["# Header"]
        _flush_list_buffer(buf, lines)
        assert buf == []
        assert lines == ["# Header"]

    def test_appends_blank_line_after(self):
        buf = ["- item"]
        lines = ["text"]
        _flush_list_buffer(buf, lines)
        assert lines[-1] == ""


class TestInlineFormatting:
    def test_bold_text(self):
        run = MagicMock()
        run.text = "标题"
        run.bold = True
        run.italic = False
        assert _inline_formatting(run) == "**标题**"

    def test_italic_text(self):
        run = MagicMock()
        run.text = "注释"
        run.bold = False
        run.italic = True
        assert _inline_formatting(run) == "*注释*"

    def test_bold_and_italic(self):
        run = MagicMock()
        run.text = "重点"
        run.bold = True
        run.italic = True
        assert _inline_formatting(run) == "***重点***"

    def test_plain_text(self):
        run = MagicMock()
        run.text = "普通文本"
        run.bold = False
        run.italic = False
        assert _inline_formatting(run) == "普通文本"

    def test_empty_text(self):
        run = MagicMock()
        run.text = ""
        assert _inline_formatting(run) == ""
