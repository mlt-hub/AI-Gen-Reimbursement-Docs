from pathlib import Path

from fastapi import APIRouter, HTTPException, Request


def _read_version(base_dir: Path) -> str:
    try:
        import tomllib

        toml = base_dir / "pyproject.toml"
        if toml.exists():
            return tomllib.load(toml.open("rb"))["project"]["version"]
    except Exception:
        pass
    return "unknown"


def _request_is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost")


def _resolved_work_mode(request: Request) -> str:
    from ai_gen_reimbursement_docs.config_utils import load_web_work_mode

    configured = load_web_work_mode()
    if configured in ("local", "remote"):
        return configured
    return "local" if _request_is_local(request) else "remote"


def _readable_directory(path: Path) -> bool:
    return path.exists() and path.is_dir()


def create_router(*, base_dir: Path, mode_info: dict[str, dict[str, str]]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/is-local")
    async def is_local(request: Request):
        """判断请求是否来自本机。"""
        return {"local": _request_is_local(request)}

    @router.get("/api/modes")
    async def get_modes():
        """返回操作模式列表，供前端动态渲染下拉框。"""
        return mode_info

    @router.get("/api/version")
    async def get_version():
        """返回当前版本号（从 pyproject.toml 读取）。"""
        return {"version": _read_version(base_dir)}

    @router.get("/api/health")
    async def health(request: Request):
        """返回 Web UI 需要的轻量健康检查信息。"""
        input_templates = base_dir / "data" / "in_templates"
        output_templates = base_dir / "data" / "out_templates"
        templates_readable = _readable_directory(input_templates) and _readable_directory(output_templates)

        return {
            "ok": templates_readable,
            "version": _read_version(base_dir),
            "work_mode": _resolved_work_mode(request),
            "api": {
                "version": True,
                "modes": True,
                "config": True,
            },
            "paths": {
                "templates_readable": templates_readable,
                "output_writable": None,
            },
            "features": {
                "prompt_debug": True,
                "ai_interactions": True,
            },
        }

    @router.post("/api/play-notify")
    async def play_notify(request: Request):
        """播放完成提示音（仅本机模式生效）。"""
        host = request.client.host if request.client else ""
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(403, "仅本机模式支持提示音")
        from ai_gen_reimbursement_docs.cli.notify import play_notify_sound

        play_notify_sound()
        return {"ok": True}

    return router
