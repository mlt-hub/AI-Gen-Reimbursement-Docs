"""自定义异常类单元测试。"""
import pytest
from ai_gen_reimbursement_docs.exceptions import (
    CosmicToolError, ConfigError, ParseError, AIError,
    TemplateError, ValidationError,
)


class TestCosmicToolError:
    def test_base_exception(self):
        with pytest.raises(CosmicToolError):
            raise CosmicToolError("基础异常")

    def test_is_exception(self):
        assert issubclass(CosmicToolError, Exception)


class TestConfigError:
    def test_basic(self):
        e = ConfigError("缺少 API Key", config_path="/tmp/.env")
        assert str(e) == "缺少 API Key"
        assert e.config_path == "/tmp/.env"

    def test_default_path(self):
        e = ConfigError("配置错误")
        assert e.config_path == ""

    def test_catch_as_cosmic_error(self):
        try:
            raise ConfigError("test")
        except CosmicToolError:
            pass  # 可被基类捕获


class TestParseError:
    def test_basic(self):
        e = ParseError("解析失败", file_path="/tmp/test.docx", details="第 42 行格式错误")
        assert e.file_path == "/tmp/test.docx"
        assert e.details == "第 42 行格式错误"

    def test_defaults(self):
        e = ParseError("解析失败")
        assert e.file_path == ""
        assert e.details == ""


class TestAIError:
    def test_basic(self):
        e = AIError("API 调用超时", attempt=3, model="deepseek-v4-flash")
        assert e.attempt == 3
        assert e.model == "deepseek-v4-flash"

    def test_defaults(self):
        e = AIError("API 失败")
        assert e.attempt == 0
        assert e.model == ""


class TestTemplateError:
    def test_basic(self):
        e = TemplateError("模板缺失", template_path="/tmp/template.xlsx")
        assert e.template_path == "/tmp/template.xlsx"


class TestValidationError:
    def test_basic(self):
        e = ValidationError("模块数量不符", expected=10, actual=7)
        assert e.expected == 10
        assert e.actual == 7

    def test_defaults(self):
        e = ValidationError("校验失败")
        assert e.expected is None
        assert e.actual is None


class TestExceptionHierarchy:
    """验证所有异常都是 CosmicToolError 的子类。"""
    @pytest.mark.parametrize("exc_class", [
        ConfigError, ParseError, AIError, TemplateError, ValidationError,
    ])
    def test_subclass_of_cosmic_error(self, exc_class):
        assert issubclass(exc_class, CosmicToolError)
