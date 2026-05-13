"""docx_parser 测试 —— get_module_by_name。"""
from cosmic_tool.models import FunctionModule
from cosmic_tool.docx_parser import get_module_by_name


class TestGetModuleByName:
    def test_finds_existing(self):
        modules = [FunctionModule(name="系统管理", level=1)]
        result = get_module_by_name(modules, "系统管理")
        assert result is not None
        assert result.name == "系统管理"

    def test_returns_none_not_found(self):
        modules = [FunctionModule(name="系统管理", level=1)]
        assert get_module_by_name(modules, "不存在") is None

    def test_returns_first_match(self):
        modules = [
            FunctionModule(name="同名", level=1),
            FunctionModule(name="同名", level=2, parent="xxx"),
        ]
        result = get_module_by_name(modules, "同名")
        assert result.level == 1

    def test_empty_list(self):
        assert get_module_by_name([], "anything") is None
