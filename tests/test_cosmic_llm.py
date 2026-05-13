"""cosmic_llm 纯函数测试 —— _resolve_move_type, _clean_json, parse_user_rules。"""
import pytest
from cosmic_tool.cosmic_llm import (
    _resolve_move_type,
    _clean_json,
    parse_user_rules,
    _build_trigger,
)
from cosmic_tool.models import FunctionModule


class TestResolveMoveType:
    def test_standard_types_not_flagged(self):
        for t in ['E', 'X', 'R', 'W', 'e', 'x', 'r', 'w']:
            result, flagged = _resolve_move_type(t)
            assert result == t.upper()
            assert flagged is False

    def test_fuzzy_entry_maps_to_e(self):
        result, flagged = _resolve_move_type("entry")
        assert result == "E"
        assert flagged is True

    def test_fuzzy_exit_maps_to_x(self):
        result, flagged = _resolve_move_type("exit")
        assert result == "X"
        assert flagged is True

    def test_fuzzy_read_maps_to_r(self):
        result, flagged = _resolve_move_type("read")
        assert result == "R"
        assert flagged is True

    def test_fuzzy_write_maps_to_w(self):
        result, flagged = _resolve_move_type("write")
        assert result == "W"
        assert flagged is True

    def test_unknown_defaults_to_e_flagged(self):
        result, flagged = _resolve_move_type("zzzz_unknown")
        assert result == "E"
        assert flagged is True

    def test_case_insensitive(self):
        result, _ = _resolve_move_type("Entry")
        assert result == "E"


class TestCleanJson:
    def test_removes_trailing_comma_before_brace(self):
        result = _clean_json('{"a": 1,}')
        assert result == '{"a": 1}'

    def test_removes_trailing_comma_before_bracket(self):
        result = _clean_json('{"a": [1, 2,]}')
        assert result == '{"a": [1, 2]}'

    def test_replaces_single_quotes_outside_strings(self):
        result = _clean_json("{'a': 'value'}")
        assert result == '{"a": "value"}'

    def test_removes_line_comments(self):
        result = _clean_json('{"a": 1 // comment\n}')
        assert "comment" not in result

    def test_whitespace_handling(self):
        result = _clean_json('  {"a": 1}  ')
        assert result == '{"a": 1}'


class TestParseUserRules:
    def test_default_only(self):
        default, rules = parse_user_rules("默认：操作员")
        assert default == "操作员"
        assert rules == []

    def test_with_rules(self):
        text = "默认：操作员\n分销：分销员\n后台：后台管理员"
        default, rules = parse_user_rules(text)
        assert default == "操作员"
        assert len(rules) == 2
        assert ("分销", "分销员") in rules
        assert ("后台", "后台管理员") in rules

    def test_trim_pipe_suffix(self):
        """规则值末尾可能有 | 标记。"""
        default, rules = parse_user_rules("默认：操作员|\n分销：分销员|")
        assert default == "操作员"
        assert ("分销", "分销员") in rules

    def test_empty_input(self):
        default, rules = parse_user_rules("")
        assert default == ""
        assert rules == []

    def test_no_colon_skipped(self):
        default, rules = parse_user_rules("invalid line\n默认：操作员")
        assert default == "操作员"

    def test_empty_lines_skipped(self):
        default, rules = parse_user_rules("\n\n默认：后台管理员\n\n")
        assert default == "后台管理员"


class TestBuildTrigger:
    def test_default_user_trigger(self):
        m = FunctionModule(name="用户注册", level=3)
        assert _build_trigger(m) == "用户触发"

    def test_timed_trigger_by_name(self):
        m = FunctionModule(name="数据同步任务", level=3)
        assert _build_trigger(m) == "定时触发"

    def test_timed_trigger_by_description(self):
        m = FunctionModule(name="报表生成", level=3,
                           description="定时批量生成报表")
        assert _build_trigger(m) == "定时触发"
