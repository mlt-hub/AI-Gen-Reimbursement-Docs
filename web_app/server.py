"""
Web UI for ai-gen-reimbursement-docs.
启动: python -m uvicorn web_app.server:app --host 0.0.0.0 --port 8080
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from web_app.routes.artifacts import create_router as create_artifacts_router
from web_app.routes.auth import router as auth_router
from web_app.routes.config import router as config_router
from web_app.routes.history import create_router as create_history_router
from web_app.routes.logging import create_router as create_logging_router
from web_app.routes.prompt_debug import router as prompt_debug_router
from web_app.routes.system import create_router as create_system_router
from web_app.routes.tasks import create_router as create_tasks_router
from web_app.routes.templates import router as templates_router
from web_app.services.logging_bootstrap import setup_web_logging
from web_app.services.session_manager import SessionManager
from web_app.services.task_runner import cleanup_expired_sessions as _cleanup_expired_sessions

os.environ['AI_REIMBURSEMENT_MODE'] = 'web'

session_manager = SessionManager()

# ── 常量 ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
_handler = setup_web_logging(session_manager=session_manager, base_dir=BASE_DIR)

MODE_INFO: dict[str, dict[str, str]] = {
    "from-excel-gen-all": {"label": "gen-all → 全套报账文档", "desc": "生成全套报账文档"},
    "from-excel-gen-basedata": {
        "label": "gen-basedata → 基础数据：模块树+元数据",
        "desc": "仅解析 功能清单Excel 生成中间 MD",
    },
    "from-excel-gen-fpa": {"label": "gen-fpa → FPA工作量评估", "desc": "生成FPA工作量评估.xlsx"},
    "from-excel-gen-spec": {"label": "gen-spec → 项目需求说明书", "desc": "生成项目需求说明书.docx"},
    "from-excel-gen-cosmic": {
        "label": "gen-cosmic → 项目功能点拆分表",
        "desc": "生成项目功能点拆分表.xlsx",
    },
    "from-excel-gen-list": {"label": "gen-list → 项目需求清单", "desc": "生成项目需求清单.xlsx"},
    
}

_MODE_MAP: dict[str, str] = {
    "from-excel-gen-all": "gen-all",
    "from-excel-gen-basedata": "gen-basedata",
    "from-excel-gen-fpa": "gen-fpa",
    "from-excel-gen-cosmic": "gen-cosmic",
    "from-excel-gen-list": "gen-list",
    "from-excel-gen-spec": "gen-spec",
}

def _spa_index():
    """SPA 入口：返回 Vite 构建产物。"""
    dist_index = Path(__file__).parent / "static" / "dist" / "index.html"
    if dist_index.exists():
        return HTMLResponse(dist_index.read_text(encoding="utf-8"))
    return HTMLResponse("<html><body>前端未构建，请运行 npm run dev 或 npm run build</body></html>")


# ── FastAPI App ───────────────────────────────────────────

def cancel_all_sessions() -> None:
    """服务关闭时标记所有 session 为已取消，唤醒等待输入的线程。"""
    for sid in session_manager.ids():
        session_manager.cancel(sid)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    cancel_all_sessions()


app = FastAPI(title="AI生成项目报账文档", lifespan=lifespan)
app.include_router(create_artifacts_router(session_manager, base_dir=BASE_DIR))
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(create_logging_router(_handler))
app.include_router(create_history_router(base_dir=BASE_DIR))
app.include_router(prompt_debug_router)
app.include_router(create_system_router(base_dir=BASE_DIR, mode_info=MODE_INFO))
app.include_router(
    create_tasks_router(
        session_manager=session_manager,
        mode_info=MODE_INFO,
        mode_map=_MODE_MAP,
        base_dir=BASE_DIR,
    )
)
app.include_router(templates_router)


def cleanup_expired_sessions(max_age_seconds: int = 24 * 3600) -> int:
    """清理过期 session 及其远程临时目录。"""
    return _cleanup_expired_sessions(session_manager, max_age_seconds)


# SPA history 路由必须先于 /static/dist 挂载声明。
# 否则 /static/dist/... 会被 StaticFiles 当作真实文件路径处理。
@app.get("/static/dist")
@app.get("/static/dist/")
@app.get("/static/dist/login")
@app.get("/static/dist/config")
@app.get("/static/dist/license")
@app.get("/static/dist/tasks")
@app.get("/static/dist/history")
@app.get("/static/dist/prompt-debug")
@app.get("/static/dist/admin/invites")
async def static_dist_spa_page():
    return _spa_index()


@app.get("/static/dist/tasks/{path:path}")
async def static_dist_tasks_page(path: str):
    return _spa_index()


@app.get("/static/dist/preview/{path:path}")
async def static_dist_preview_page(path: str):
    return _spa_index()


@app.get("/static/dist/sessions/{path:path}")
async def static_dist_sessions_page(path: str):
    return _spa_index()


# 静态文件：Vite 构建产物
_dist_dir = Path(__file__).parent / "static" / "dist"
if _dist_dir.exists():
    app.mount("/static/dist", StaticFiles(directory=str(_dist_dir)), name="static_dist")
# 保留旧 static/ 挂载以支持旧文件和资源
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
async def index():
    """SPA 入口：生产环境返回 dist/index.html，开发环境回退 static/index.html。"""
    return _spa_index()


@app.get("/login")
async def login_page():
    return _spa_index()


@app.get("/config")
async def config_page():
    return _spa_index()


@app.get("/license")
async def license_page():
    return _spa_index()


@app.get("/tasks")
async def tasks_page():
    return _spa_index()


@app.get("/tasks/{path:path}")
async def task_detail_page(path: str):
    return _spa_index()


@app.get("/history")
async def history_page():
    return _spa_index()


@app.get("/preview/{path:path}")
async def preview_page(path: str):
    return _spa_index()


@app.get("/sessions/{path:path}")
async def sessions_page(path: str):
    return _spa_index()


@app.get("/prompt-debug")
async def prompt_debug():
    return _spa_index()


@app.get("/admin/invites")
async def admin_invites_page():
    return _spa_index()

