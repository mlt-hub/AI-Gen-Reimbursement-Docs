import os
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from ai_gen_reimbursement_docs.auth import user_config_dir
from web_app.dependencies import get_auth_user, is_local_mode, require_auth, require_local
from web_app.services.config_service import (
    config_dir,
    mask_env_content,
    read_config,
    redact_env_dict,
    save_config_to_dir,
)


router = APIRouter()


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
