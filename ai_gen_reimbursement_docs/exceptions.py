"""COSMIC 工具自定义异常类。

替代代码中散落的泛用 ValueError/Exception，提供精确的错误类型，
使调用方可根据异常类型作出不同处理。
"""


class CosmicToolError(Exception):
    """所有 COSMIC 异常的基类。"""
    pass


class ConfigError(CosmicToolError):
    """配置相关错误：缺失配置项、格式错误、文件不存在等。"""

    def __init__(self, message: str, config_path: str = ""):
        super().__init__(message)
        self.config_path = config_path


class ParseError(CosmicToolError):
    """解析相关错误：docx 解析失败、Excel 格式不符、Markdown 解析失败等。"""

    def __init__(self, message: str, file_path: str = "", details: str = ""):
        super().__init__(message)
        self.file_path = file_path
        self.details = details


class AIError(CosmicToolError):
    """AI 调用相关错误：API 连接失败、响应格式异常、token 超限等。"""

    def __init__(self, message: str, attempt: int = 0, model: str = ""):
        super().__init__(message)
        self.attempt = attempt
        self.model = model


class TemplateError(CosmicToolError):
    """模板相关错误：模板文件缺失、占位符未替换、格式不匹配等。"""

    def __init__(self, message: str, template_path: str = ""):
        super().__init__(message)
        self.template_path = template_path


class ValidationError(CosmicToolError):
    """数据校验错误：模块数量不符、CFP 超出预期值等。"""

    def __init__(self, message: str, expected: object = None, actual: object = None):
        super().__init__(message)
        self.expected = expected
        self.actual = actual


class FileWriteError(CosmicToolError):
    """文件写入错误：权限不足、文件被占用等。"""

    def __init__(self, message: str, file_path: str = ""):
        super().__init__(message)
        self.file_path = file_path


class CancelledError(BaseException):
    """任务已被用停止。继承 BaseException 确保不被 except Exception 捕获。"""
    pass
