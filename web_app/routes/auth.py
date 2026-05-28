from fastapi import APIRouter, Request
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from ai_gen_reimbursement_docs.auth import (
    allow_register,
    create_token,
    init_user_dir,
    register_user,
    remove_token,
    verify_user,
)
from web_app.dependencies import get_auth_user, is_local_mode


router = APIRouter()


@router.post("/api/auth/register")
async def auth_register(data: dict):
    """注册新用户。"""
    if not allow_register():
        raise HTTPException(403, "管理员已关闭注册")
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or len(password) < 4:
        raise HTTPException(400, "用户名不能为空，密码至少4位")
    if not register_user(username, password):
        raise HTTPException(409, "用户名已存在")
    init_user_dir(username)
    return {"ok": True}


@router.post("/api/auth/login")
async def auth_login(data: dict, request: Request):
    """登录，返回 token 并设置 cookie。"""
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not verify_user(username, password):
        raise HTTPException(401, "用户名或密码错误")

    token = create_token(username)
    resp = JSONResponse({"ok": True, "username": username})
    resp.set_cookie(
        "ard_token", token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
    )
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
        "is_local": is_local_mode(request),
        "allow_register": allow_register(),
    }
