import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from ai_gen_reimbursement_docs.auth import user_config_dir
from web_app.dependencies import get_auth_user, is_local_mode, require_auth, require_local
from web_app.services.config_service import (
    AdvancedConfigError,
    build_web_config_view,
    config_dir,
    list_advanced_config_files,
    list_config_backups,
    mask_env_content,
    read_advanced_config_file,
    read_config,
    read_config_from_dir,
    redact_env_dict,
    restore_config_backup,
    save_advanced_config_file,
    save_config_to_dir,
    save_web_config_to_dir,
    validate_advanced_config_content,
)


router = APIRouter()


def _require_local_advanced_config(request: Request) -> Path:
    if not is_local_mode(request):
        raise HTTPException(403, "高级配置文件只能由本机管理员编辑")
    return config_dir()


@router.get("/api/default-work-mode")
async def get_default_work_mode():
    """返回配置文件中预设的工作模式（auto/local/remote）。"""
    from ai_gen_reimbursement_docs.config_utils import load_web_work_mode

    return {"work_mode": load_web_work_mode()}


@router.get("/api/config")
async def get_config():
    data = read_config()
    if isinstance(data.get("_env"), dict):
        data["_env"] = redact_env_dict(data["_env"])
    return data


@router.get("/api/web-config")
async def get_web_config(request: Request, user: str = Depends(require_auth)):
    """返回面向 Web UI 配置中心的脱敏业务视图。"""
    local_mode = is_local_mode(request)
    global_config = read_config()
    user_config = None
    username = user or None

    if not local_mode and user:
        user_config = read_config_from_dir(user_config_dir(user))

    return build_web_config_view(
        global_config=global_config,
        user_config=user_config,
        username=username,
        local_mode=local_mode,
    )


@router.put("/api/web-config")
async def save_web_config(data: dict, request: Request, user: str = Depends(require_auth)):
    """保存第一阶段 Web 配置，并返回最新脱敏业务视图。"""
    local_mode = is_local_mode(request)
    username = user or None
    target_dir = config_dir() if local_mode else user_config_dir(user)

    await save_web_config_to_dir(
        data,
        target_dir,
        allow_shared_credentials_write=local_mode,
        actor=username or "local-admin",
        audit_root=config_dir(),
        backup_root=config_dir(),
        backup_scope="global" if local_mode else f"user-{user}",
    )

    global_config = read_config()
    user_config = None
    if not local_mode and user:
        user_config = read_config_from_dir(user_config_dir(user))

    return build_web_config_view(
        global_config=global_config,
        user_config=user_config,
        username=username,
        local_mode=local_mode,
    )


@router.get("/api/web-config/backups")
async def get_web_config_backups(request: Request, user: str = Depends(require_auth)):
    """列出当前配置作用域可恢复的备份。"""
    local_mode = is_local_mode(request)
    scope = "global" if local_mode else f"user-{user}"
    return {
        "scope": {
            "mode": "local" if local_mode else "remote",
            "username": user or "",
        },
        "items": list_config_backups(
            backup_root=config_dir(),
            scope=scope,
        ),
    }


@router.post("/api/web-config/backups/restore")
async def restore_web_config_backup(data: dict, request: Request, user: str = Depends(require_auth)):
    """恢复当前配置作用域的一份备份，并返回最新脱敏业务视图。"""
    backup_id = str(data.get("backup_id") or "").strip()
    if not backup_id:
        raise HTTPException(400, "请提供 backup_id")

    local_mode = is_local_mode(request)
    username = user or None
    scope = "global" if local_mode else f"user-{user}"
    target_dir = config_dir() if local_mode else user_config_dir(user)

    try:
        restore_config_backup(
            target_dir=target_dir,
            backup_root=config_dir(),
            scope=scope,
            backup_id=backup_id,
            actor=username or "local-admin",
            audit_root=config_dir(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    global_config = read_config()
    user_config = None
    if not local_mode and user:
        user_config = read_config_from_dir(user_config_dir(user))

    return build_web_config_view(
        global_config=global_config,
        user_config=user_config,
        username=username,
        local_mode=local_mode,
    )


@router.get("/api/web-config/files")
async def get_web_config_files(request: Request, _user: str = Depends(require_auth)):
    """列出 Web UI 可编辑的高级配置文件。"""
    target_dir = _require_local_advanced_config(request)
    return {
        "scope": {"mode": "local", "username": ""},
        "items": list_advanced_config_files(target_dir=target_dir),
    }


@router.get("/api/web-config/files/{file_id}")
async def get_web_config_file(file_id: str, request: Request, _user: str = Depends(require_auth)):
    """读取一个高级配置文件的原文。"""
    target_dir = _require_local_advanced_config(request)
    try:
        return read_advanced_config_file(file_id=file_id, target_dir=target_dir)
    except AdvancedConfigError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/api/web-config/files/{file_id}/validate")
async def validate_web_config_file(file_id: str, data: dict, request: Request, _user: str = Depends(require_auth)):
    """校验一个高级配置文件，校验失败不写入。"""
    _require_local_advanced_config(request)
    try:
        return validate_advanced_config_content(
            file_id=file_id,
            content=str(data.get("content") or ""),
        )
    except AdvancedConfigError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/api/web-config/files/{file_id}")
async def save_web_config_file(file_id: str, data: dict, request: Request, user: str = Depends(require_auth)):
    """校验并保存一个高级配置文件。"""
    target_dir = _require_local_advanced_config(request)
    try:
        return save_advanced_config_file(
            file_id=file_id,
            content=str(data.get("content") or ""),
            target_dir=target_dir,
            actor=user or "local-admin",
            audit_root=config_dir(),
            backup_root=config_dir(),
            backup_scope="global",
        )
    except AdvancedConfigError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/config")
async def save_config(data: dict, _local: None = Depends(require_local)):
    """保存系统配置（仅本机）。data 含 _env / _system / _biz 三个 key。"""
    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    await save_config_to_dir(data, cfg_dir)
    return {"ok": True}


@router.get("/api/config-read")
async def config_read(request: Request):
    """读取配置文件内容。远程登录用户返回个人配置+全局默认，本机返回本机配置。"""
    username = get_auth_user(request)
    if username and not is_local_mode(request):
        user_dir = user_config_dir(username)
        result: dict = {}
        for key, fname in [("env", ".env"), ("system_config", "system_config.yaml")]:
            fp = user_dir / fname
            if key == "env":
                result[key] = mask_env_content(fp) if fp.exists() else ""
            else:
                result[key] = fp.read_text(encoding="utf-8") if fp.exists() else ""

        biz_path = Path(os.path.expanduser("~")) / ".ai-gen-reimbursement-docs" / "business_rules.yaml"
        result["business_rules"] = biz_path.read_text(encoding="utf-8") if biz_path.exists() else ""

        global_dir = Path(os.path.expanduser("~")) / ".ai-gen-reimbursement-docs"
        fp_sys = global_dir / "system_config.yaml"
        result["global_system"] = fp_sys.read_text(encoding="utf-8") if fp_sys.exists() else ""
        fp_env = global_dir / ".env"
        result["global_env"] = mask_env_content(fp_env) if fp_env.exists() else ""
        result["username"] = username
        return result

    cfg_dir = Path(os.path.expanduser("~")) / ".ai-gen-reimbursement-docs"
    result = {}
    for key, fname in [
        ("env", ".env"),
        ("system_config", "system_config.yaml"),
        ("business_rules", "business_rules.yaml"),
    ]:
        fp = cfg_dir / fname
        if key == "env":
            result[key] = mask_env_content(fp) if fp.exists() else ""
        else:
            result[key] = fp.read_text(encoding="utf-8") if fp.exists() else ""
    return result


@router.get("/api/user/config")
async def get_user_config(user: str = Depends(require_auth)):
    """返回当前用户的个人配置（可编辑的 key-value）。"""
    if not user:
        data = read_config()
        if isinstance(data.get("_env"), dict):
            data["_env"] = redact_env_dict(data["_env"])
        return data

    user_dir = user_config_dir(user)
    result: dict = {"_env": {}, "_system": {}}

    env_path = user_dir / ".env"
    if env_path.exists():
        env: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        result["_env"] = redact_env_dict(env)

    sys_path = user_dir / "system_config.yaml"
    if sys_path.exists():
        try:
            import yaml

            result["_system"] = yaml.safe_load(sys_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    return result


@router.post("/api/user/config")
async def save_user_config(data: dict, user: str = Depends(require_auth)):
    """保存当前用户的个人配置。"""
    if not user:
        await save_config_to_dir(data, config_dir())
        return {"ok": True}

    user_dir = user_config_dir(user)
    await save_config_to_dir(data, user_dir)
    return {"ok": True}
