import logging
import tomllib
from pathlib import Path

from ai_gen_reimbursement_docs.cli.logging import PathShortener, init_global_logging
from web_app.services import pipeline_runtime
from web_app.services.session_manager import SessionManager


def setup_web_logging(
    *,
    session_manager: SessionManager,
    base_dir: Path,
) -> pipeline_runtime.SessionHandler:
    """初始化 Web 日志，并返回 session 日志 handler。"""
    parent = logging.getLogger("ai_gen_reimbursement_docs")
    parent.setLevel(logging.DEBUG)

    handler = pipeline_runtime.SessionHandler(session_manager)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(PathShortener())
    parent.addHandler(handler)

    init_global_logging()
    parent.info(
        "[Web UI] AI生成项目报账文档 v%s（FastAPI 服务启动）",
        _read_project_version(base_dir),
    )
    return handler


def _read_project_version(base_dir: Path) -> str:
    try:
        with open(base_dir / "pyproject.toml", "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "unknown"
