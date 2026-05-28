import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from web_app.dependencies import require_auth, require_local
from web_app.services.artifact_service import cleanup_after_download, find_log_dir
from web_app.services.session_access import require_session_access
from web_app.services.session_manager import SessionManager


def create_router(session_manager: SessionManager) -> APIRouter:
    router = APIRouter()

    @router.get("/api/download/{session_id}")
    async def download(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """远程服务模式：下载交付物 ZIP。"""
        require_session_access(session_manager, session_id, request, user)
        state = session_manager.get(session_id)
        zip_path = state.zip_path if state else None
        if zip_path is None:
            if state is not None:
                raise HTTPException(409, "任务仍在运行，交付物尚未生成")
            raise HTTPException(404, "交付物不存在或会话已过期")
        if not zip_path.exists():
            raise HTTPException(404, "交付物文件已被清理")

        return FileResponse(
            zip_path,
            filename=f"交付物_{datetime.now():%Y%m%d_%H%M%S}.zip",
            media_type="application/zip",
            background=cleanup_after_download(session_manager, session_id),
        )

    @router.get("/api/open-folder")
    async def open_folder(session: str, _local: None = Depends(require_local)):
        """本机模式：在资源管理器中打开交付物目录。"""
        state = session_manager.get(session)
        out_dir = state.output_dir if state else None
        if out_dir is None:
            raise HTTPException(404, "未知会话")
        if not out_dir.exists():
            raise HTTPException(404, "交付物目录不存在")
        os.startfile(str(out_dir))
        return {"ok": True}

    @router.get("/api/ai-log/{session_id}")
    async def get_ai_log(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """返回 AI 对话日志内容。"""
        require_session_access(session_manager, session_id, request, user)
        log_dir = find_log_dir(session_manager, session_id)
        if log_dir is None:
            raise HTTPException(404, "未找到日志目录")

        combined = log_dir / "ai_对话日志.md"
        if not combined.exists():
            raise HTTPException(404, "AI 对话日志尚未生成")

        content = combined.read_text(encoding="utf-8")
        return {"content": content, "filename": combined.name}

    @router.get("/api/ai-interactions/{session_id}")
    async def list_ai_interactions(
        session_id: str,
        request: Request,
        user: str = Depends(require_auth),
    ):
        """列出 AI prompts 和 responses 文件清单及内容。"""
        require_session_access(session_manager, session_id, request, user)
        log_dir = find_log_dir(session_manager, session_id)
        if log_dir is None:
            raise HTTPException(404, "未找到日志目录")

        prompts_dir = log_dir / "ai_prompts"
        responses_dir = log_dir / "ai_responses"

        files: list[dict] = []

        if prompts_dir.is_dir():
            for fname in sorted(os.listdir(prompts_dir)):
                if fname.endswith(".txt"):
                    path = prompts_dir / fname
                    files.append({
                        "name": fname,
                        "type": "prompt",
                        "content": path.read_text(encoding="utf-8"),
                    })

        if responses_dir.is_dir():
            for fname in sorted(os.listdir(responses_dir)):
                if fname.endswith(".txt"):
                    path = responses_dir / fname
                    files.append({
                        "name": fname,
                        "type": "response",
                        "content": path.read_text(encoding="utf-8"),
                    })

        return {"interactions": files, "count": len(files)}

    return router
