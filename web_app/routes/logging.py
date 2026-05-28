import logging

from fastapi import APIRouter, Depends, HTTPException

from web_app.dependencies import require_local


def create_router(session_handler: logging.Handler) -> APIRouter:
    router = APIRouter()

    @router.get("/api/log-level")
    async def get_log_level():
        """返回当前日志级别。"""
        from ai_gen_reimbursement_docs.config_utils import load_log_level

        return {"level": load_log_level()}

    @router.post("/api/log-level")
    async def set_log_level(data: dict, _local: None = Depends(require_local)):
        """运行时设置日志级别（仅本机）。"""
        level = data.get("level", "INFO").strip().upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise HTTPException(400, f"无效的日志级别: {level}")
        lv = getattr(logging, level, logging.INFO)
        session_handler.setLevel(lv)
        return {"ok": True, "level": level}

    return router
