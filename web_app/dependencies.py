from pathlib import Path

from fastapi import HTTPException, Request

from ai_gen_reimbursement_docs.auth import get_username_by_token, is_admin, is_local_host


def get_auth_user(request: Request) -> str | None:
    """从 cookie 获取当前登录用户名。"""
    token = request.cookies.get("ard_token", "")
    return get_username_by_token(token)


def is_local_ip(request: Request) -> bool:
    """纯 IP 判断（不受 web_work_mode 影响）。"""
    host = request.client.host if request.client else ""
    return is_local_host(host)


def is_local_mode(request: Request) -> bool:
    """判断当前是否为本地模式。"""
    from ai_gen_reimbursement_docs.config_utils import load_web_work_mode

    wm = load_web_work_mode()
    if wm == "local":
        return True
    if wm == "remote":
        return False
    return is_local_ip(request)


def require_local(request: Request):
    """依赖：仅本机 IP 可访问（不受 web_work_mode 影响）。"""
    if not is_local_ip(request):
        raise HTTPException(403, "此接口仅限本机访问")


def require_auth(request: Request) -> str:
    """依赖：本地模式放行，远程模式需登录。返回用户名或空字符串。"""
    if is_local_mode(request):
        return ""
    username = get_auth_user(request)
    if not username:
        raise HTTPException(401, "请先登录")
    return username


def require_admin(request: Request) -> str:
    """依赖：远程模式需管理员；本地模式放行。"""
    username = require_auth(request)
    if is_local_mode(request):
        return username
    if not is_admin(username):
        raise HTTPException(403, "仅管理员可访问")
    return username


def config_dir() -> Path:
    return Path.home() / ".ai-gen-reimbursement-docs"
