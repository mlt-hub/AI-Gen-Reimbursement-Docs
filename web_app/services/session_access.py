from fastapi import HTTPException, Request

from web_app.dependencies import get_auth_user, is_local_mode
from web_app.services.session_manager import SessionManager


def require_session_access(
    session_manager: SessionManager,
    session_id: str,
    request: Request,
    user: str | None = None,
) -> None:
    """校验当前请求是否可访问 session；远程模式按 owner 隔离。"""
    if not session_manager.can_access(
        session_id,
        user or get_auth_user(request),
        local_mode=is_local_mode(request),
    ):
        raise HTTPException(404, "未知会话")
