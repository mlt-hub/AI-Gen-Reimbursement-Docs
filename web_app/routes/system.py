from pathlib import Path

from fastapi import APIRouter, HTTPException, Request


def create_router(*, base_dir: Path, mode_info: dict[str, dict[str, str]]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/is-local")
    async def is_local(request: Request):
        """判断请求是否来自本机。"""
        host = request.client.host if request.client else ""
        return {"local": host in ("127.0.0.1", "::1", "localhost")}

    @router.get("/api/modes")
    async def get_modes():
        """返回操作模式列表，供前端动态渲染下拉框。"""
        return mode_info

    @router.get("/api/version")
    async def get_version():
        """返回当前版本号（从 pyproject.toml 读取）。"""
        try:
            import tomllib

            toml = base_dir / "pyproject.toml"
            if toml.exists():
                return {"version": tomllib.load(toml.open("rb"))["project"]["version"]}
        except Exception:
            pass
        return {"version": "unknown"}

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
