"""docx_parser 纯函数测试 —— _clean_name, _clean_json_from_heading, _parse_ai_heading_response。"""
import pytest
from cosmic_tool.docx_parser import (
    _clean_name,
    _clean_json_from_heading,
    _parse_ai_heading_response,
    _filter_heading_paragraphs,
)


class TestCleanName:
    @pytest.mark.parametrize("raw, expected", [
        ("1.1 用户管理", "用户管理"),
        ("3.2.1 密码重置", "密码重置"),
        ("2.0 系统配置", "系统配置"),
        ("（一）系统管理", "（一）系统管理"),
        ("无编号标题", "无编号标题"),
        ("1.1.1 用户管理20", "用户管理"),
        ("###文档开始### 第4章", "第4章"),
        ("###L1:1:1### 功能需求", "功能需求"),
    ])
    def test_clean_name_parametrized(self, raw, expected):
        assert _clean_name(raw) == expected

    def test_empty_string(self):
        assert _clean_name("") == ""

    def test_only_numbers(self):
        assert _clean_name("123") == ""


class TestCleanJsonFromHeading:
    def test_strips_trailing_commas(self):
        raw = '{"name": "test", "level": 1,}'
        result = _clean_json_from_heading(raw)
        assert result.count("}") == 1
        assert ",}" not in result

    def test_removes_line_comments(self):
        raw = '{"name": "test" // 这是注释\n, "level": 1}'
        result = _clean_json_from_heading(raw)
        assert "//" not in result
        assert "注释" not in result

    def test_strips_markdown_wrapper(self):
        raw = '```json\n{"name": "test"}\n```'
        # parse function handles this, not _clean_json_from_heading
        # just verify it doesn't crash
        result = _clean_json_from_heading(raw)
        assert len(result) > 0


class TestParseAiHeadingResponse:
    def test_parses_valid_json(self):
        resp = '{"modules": [{"name": "系统管理", "level": 1, "children": ["用户管理"]}]}'
        result = _parse_ai_heading_response(resp)
        assert len(result) == 1
        assert result[0]["name"] == "系统管理"
        assert result[0]["level"] == 1

    def test_parses_multiple_modules(self):
        resp = """{"modules": [
            {"name": "系统管理", "level": 1},
            {"name": "用户管理", "level": 2, "parent": "系统管理"},
            {"name": "用户注册", "level": 3, "parent": "用户管理"}
        ]}"""
        result = _parse_ai_heading_response(resp)
        assert len(result) == 3

    def test_raises_parse_error_on_invalid(self):
        from cosmic_tool.exceptions import ParseError
        with pytest.raises(ParseError):
            _parse_ai_heading_response("not json")

    def test_raises_parse_error_on_empty_modules(self):
        from cosmic_tool.exceptions import ParseError
        with pytest.raises(ParseError):
            _parse_ai_heading_response('{"modules": []}')


class TestFilterHeadingParagraphs:
    def test_empty_input(self):
        assert _filter_heading_paragraphs([]) == []
