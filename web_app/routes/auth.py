from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from ai_gen_reimbursement_docs.auth import (
    ADMIN_INITIAL_PASSWORD,
    ADMIN_USERNAME,
    allow_register,
    change_password,
    create_invite,
    create_token,
    disable_invite,
    get_user_role,
    InviteError,
    list_invites,
    REMEMBER_ME_DAYS,
    register_user_with_invite,
    remove_token,
    user_must_change_password,
    user_exists,
    verify_user,
)
from web_app.dependencies import get_auth_user, is_local_mode, require_admin


router = APIRouter()


@router.post("/api/auth/register")
async def auth_register(data: dict):
    """注册新用户。"""
    username = data.get("username", "").strip()
    password = data.get("password", "")
    invite_code = data.get("invite_code", "").strip()
    if not username or len(password) < 6:
        raise HTTPException(400, "用户名不能为空，密码至少6位")
    if user_exists(username):
        raise HTTPException(409, "用户名已存在")
    try:
        registered = register_user_with_invite(username, password, invite_code)
    except InviteError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not registered:
        raise HTTPException(400, "注册失败")
    return {"ok": True}


@router.post("/api/auth/login")
async def auth_login(data: dict, request: Request):
    """登录，返回 token 并设置 cookie。"""
    username = data.get("username", "").strip()
    password = data.get("password", "")
    remember_me = bool(data.get("remember_me", False))
    if not verify_user(username, password):
        raise HTTPException(401, "用户名或密码错误")

    username = username.lower()
    token = create_token(username, remember_me=remember_me)
    resp = JSONResponse({
        "ok": True,
        "username": username,
        "role": get_user_role(username),
        "must_change_password": user_must_change_password(username),
    })
    cookie_options = {
        "key": "ard_token",
        "value": token,
        "httponly": True,
        "samesite": "lax",
        "secure": request.url.scheme == "https",
    }
    if remember_me:
        cookie_options["max_age"] = 86400 * REMEMBER_ME_DAYS
    resp.set_cookie(**cookie_options)
    return resp


@router.post("/api/auth/logout")
async def auth_logout(request: Request):
    """退出登录。"""
    token = request.cookies.get("ard_token", "")
    if token:
        remove_token(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("ard_token")
    return resp


@router.get("/api/auth/me")
async def auth_me(request: Request):
    """返回当前登录用户。"""
    username = get_auth_user(request)
    return {
        "username": username,
        "role": get_user_role(username) if username else "",
        "must_change_password": user_must_change_password(username) if username else False,
        "is_local": is_local_mode(request),
        "allow_register": allow_register(),
    }


@router.post("/api/auth/change-password")
async def auth_change_password(data: dict, request: Request):
    """修改当前登录用户密码。"""
    username = get_auth_user(request)
    if not username and not is_local_mode(request):
        raise HTTPException(401, "请先登录")
    if not username:
        raise HTTPException(400, "本机模式无需修改登录密码")

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    if len(new_password) < 6:
        raise HTTPException(400, "新密码至少6位")
    if new_password == ADMIN_INITIAL_PASSWORD and username == ADMIN_USERNAME:
        raise HTTPException(400, "新密码不能继续使用初始密码")
    if not change_password(username, current_password, new_password):
        raise HTTPException(400, "当前密码错误或修改失败")
    return {
        "ok": True,
        "username": username,
        "role": get_user_role(username),
        "must_change_password": False,
    }


@router.post("/api/admin/invites")
async def admin_create_invite(data: dict, admin: str = Depends(require_admin)):
    """创建邀请码。"""
    invite = create_invite(
        admin,
        expires_in_days=data.get("expires_in_days"),
        max_uses=data.get("max_uses"),
    )
    return invite


@router.get("/api/admin/invites")
async def admin_list_invites(admin: str = Depends(require_admin)):
    """列出邀请码，不返回明文 code。"""
    return {"invites": list_invites()}


@router.post("/api/admin/invites/{invite_id}/disable")
async def admin_disable_invite(invite_id: int, admin: str = Depends(require_admin)):
    """停用邀请码。"""
    if not disable_invite(invite_id):
        raise HTTPException(404, "邀请码不存在")
    return {"ok": True}
