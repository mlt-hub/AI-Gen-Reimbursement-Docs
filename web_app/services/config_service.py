import os
import re
from pathlib import Path

from web_app.services.secret_service import encrypt_secret


DEFAULT_WEB_CONFIG = {
    "base_url": "",
    "model": "",
    "max_tokens": "",
    "allow_shared_ai_credentials": False,
    "out_templates": {},
    "project_name": "",
    "fpa_profile": "strict_fpa",
    "fpa_strategy": "",
    "fpa_rule_set": "",
    "fpa_confirmation_mode": "cautious",
}


def config_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".ai-gen-reimbursement-docs"


def read_config() -> dict:
    """读取所有配置文件，返回合并后的 dict。"""
    cfg_dir = config_dir()
    result: dict = {"_env": {}, "_system": {}, "_biz": {}}

    env_path = cfg_dir / ".env"
    if env_path.exists():
        env: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        result["_env"] = env

    for key, filename in [
        ("_system", "system_config.yaml"),
        ("_biz", "business_rules.yaml"),
    ]:
        path = cfg_dir / filename
        if path.exists():
            try:
                import yaml

                result[key] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass

    return result


def remote_session_retention_seconds(default: int = 24 * 3600) -> int:
    """读取远程 session 下载保留期，配置以天为主，内部换算为秒。"""
    system_config = read_config().get("_system", {})
    value = system_config.get("remote_session_retention_days", default / (24 * 3600))
    try:
        days = float(value)
    except (TypeError, ValueError):
        return default
    return int(days * 24 * 3600) if days > 0 else default


def mask_env_content(path: Path) -> str:
    """读取 .env 文件内容，遮住敏感值，不暴露任何原文片段。"""
    text = path.read_text(encoding="utf-8")
    sensitive_keys = re.compile(
        r'^(.*_(?:KEY|SECRET|TOKEN|PASSWORD)\s*=)(.+)$',
        re.IGNORECASE,
    )
    lines = []
    for line in text.splitlines():
        m = sensitive_keys.match(line.strip())
        if m:
            lines.append(f"{m.group(1)}***")
        else:
            lines.append(line)
    return "\n".join(lines)


def redact_env_dict(env: dict[str, str]) -> dict[str, str]:
    """Return env values with sensitive entries replaced by a marker."""
    sensitive_key = re.compile(r'_(?:KEY|SECRET|TOKEN|PASSWORD)$', re.IGNORECASE)
    return {
        key: ("***" if sensitive_key.search(key) and value else value)
        for key, value in env.items()
    }


def _field(value, source: str) -> dict:
    return {"value": value, "source": source}


def _configured_env_key(env: dict, key: str) -> bool:
    value = env.get(key, "")
    return bool(str(value).strip())


def _pick_env_field(user_env: dict, global_env: dict, key: str, default: str = "") -> dict:
    if _configured_env_key(user_env, key):
        return _field(str(user_env[key]), "personal")
    if _configured_env_key(global_env, key):
        return _field(str(global_env[key]), "global")
    return _field(default, "default")


def _pick_system_field(user_system: dict, global_system: dict, key: str, default):
    if key in user_system and user_system[key] not in (None, ""):
        return _field(user_system[key], "personal")
    if key in global_system and global_system[key] not in (None, ""):
        return _field(global_system[key], "global")
    return _field(default, "default")


def build_web_config_view(
    *,
    global_config: dict,
    user_config: dict | None = None,
    username: str | None = None,
    local_mode: bool = True,
) -> dict:
    """Build the business-facing, redacted Web UI config view.

    The view never returns API Key material. Remote users receive an effective
    merged view with per-field source markers.
    """
    user_config = user_config or {}
    user_env = user_config.get("_env") if isinstance(user_config.get("_env"), dict) else {}
    user_system = user_config.get("_system") if isinstance(user_config.get("_system"), dict) else {}
    global_env = global_config.get("_env") if isinstance(global_config.get("_env"), dict) else {}
    global_system = global_config.get("_system") if isinstance(global_config.get("_system"), dict) else {}

    if local_mode:
        user_env = {}
        user_system = {}

    personal_api_key = _configured_env_key(user_env, "ANTHROPIC_API_KEY") or _configured_env_key(
        user_env,
        "ANTHROPIC_API_KEY_ENC",
    )
    global_api_key = _configured_env_key(global_env, "ANTHROPIC_API_KEY") or _configured_env_key(
        global_env,
        "ANTHROPIC_API_KEY_ENC",
    )
    shared_credentials = bool(global_system.get("allow_shared_ai_credentials", False))
    usable_global_api_key = global_api_key and (local_mode or shared_credentials)
    api_key_source = "personal" if personal_api_key else "global" if usable_global_api_key else "default"

    return {
        "scope": {
            "mode": "local" if local_mode else "remote",
            "username": username or "",
        },
        "ai": {
            "api_key_configured": personal_api_key or usable_global_api_key,
            "api_key_source": api_key_source,
            "base_url": _pick_env_field(user_env, global_env, "ANTHROPIC_BASE_URL", DEFAULT_WEB_CONFIG["base_url"]),
            "model": _pick_env_field(user_env, global_env, "ANTHROPIC_MODEL", DEFAULT_WEB_CONFIG["model"]),
            "max_tokens": _pick_system_field(user_system, global_system, "max_tokens", DEFAULT_WEB_CONFIG["max_tokens"]),
            "allow_shared_ai_credentials": _field(
                shared_credentials,
                "global" if "allow_shared_ai_credentials" in global_system else "default",
            ),
        },
        "templates": {
            "out_templates": _pick_system_field(
                user_system,
                global_system,
                "out_templates",
                DEFAULT_WEB_CONFIG["out_templates"],
            ),
        },
        "run_defaults": {
            "project_name": _pick_system_field(
                user_system,
                global_system,
                "project_name",
                DEFAULT_WEB_CONFIG["project_name"],
            ),
            "fpa_profile": _pick_system_field(
                user_system,
                global_system,
                "fpa_profile",
                DEFAULT_WEB_CONFIG["fpa_profile"],
            ),
            "fpa_strategy": _pick_system_field(
                user_system,
                global_system,
                "fpa_strategy",
                DEFAULT_WEB_CONFIG["fpa_strategy"],
            ),
            "fpa_rule_set": _pick_system_field(
                user_system,
                global_system,
                "fpa_rule_set",
                DEFAULT_WEB_CONFIG["fpa_rule_set"],
            ),
            "fpa_confirmation_mode": _pick_system_field(
                user_system,
                global_system,
                "fpa_confirmation_mode",
                DEFAULT_WEB_CONFIG["fpa_confirmation_mode"],
            ),
        },
    }


def _existing_sensitive_env(target_dir: Path) -> dict[str, str]:
    data = read_config_from_dir(target_dir).get("_env", {})
    if not isinstance(data, dict):
        return {}
    sensitive_key = re.compile(r'_(?:KEY|SECRET|TOKEN|PASSWORD)$', re.IGNORECASE)
    return {
        str(key): str(value)
        for key, value in data.items()
        if sensitive_key.search(str(key)) and value
    }


def read_config_from_dir(cfg_dir: Path) -> dict:
    """读取指定配置目录，返回合并后的 dict。"""
    result: dict = {"_env": {}, "_system": {}, "_biz": {}}

    env_path = cfg_dir / ".env"
    if env_path.exists():
        env: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        result["_env"] = env

    for key, filename in [
        ("_system", "system_config.yaml"),
        ("_biz", "business_rules.yaml"),
    ]:
        path = cfg_dir / filename
        if path.exists():
            try:
                import yaml

                result[key] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass

    return result


async def save_config_to_dir(data: dict, target_dir: Path, *, preserve_existing_sensitive: bool = True):
    """保存配置到指定目录。"""
    target_dir.mkdir(parents=True, exist_ok=True)

    if "_env" in data:
        env = {
            str(k): str(v)
            for k, v in data["_env"].items()
            if str(v) and str(v) != "***"
        }
        if preserve_existing_sensitive:
            for key, value in _existing_sensitive_env(target_dir).items():
                env.setdefault(key, value)
        lines = []
        for k, v in env.items():
            lines.append(f"{k}={v}")
        (target_dir / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if "_system" in data and data["_system"]:
        import yaml

        path = target_dir / "system_config.yaml"
        path.write_text(
            yaml.dump(data["_system"], allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )


def _editable_value(payload: dict, section: str, key: str):
    value = payload.get(section, {}).get(key)
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


async def save_web_config_to_dir(
    payload: dict,
    target_dir: Path,
    *,
    allow_shared_credentials_write: bool = False,
) -> dict:
    """Save the first-phase Web config payload without writing plaintext API keys."""
    existing = read_config_from_dir(target_dir)
    env = dict(existing.get("_env") if isinstance(existing.get("_env"), dict) else {})
    system = dict(existing.get("_system") if isinstance(existing.get("_system"), dict) else {})

    ai = payload.get("ai") if isinstance(payload.get("ai"), dict) else {}
    api_key = ai.get("api_key")
    clear_api_key = bool(ai.get("clear_api_key", False))
    if clear_api_key:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_API_KEY_ENC", None)
    elif isinstance(api_key, str) and api_key.strip() and api_key.strip() != "***":
        env.pop("ANTHROPIC_API_KEY", None)
        env["ANTHROPIC_API_KEY_ENC"] = encrypt_secret(api_key, config_root=target_dir)

    base_url = _editable_value(payload, "ai", "base_url")
    if base_url is not None:
        env["ANTHROPIC_BASE_URL"] = str(base_url).strip()
    model = _editable_value(payload, "ai", "model")
    if model is not None:
        env["ANTHROPIC_MODEL"] = str(model).strip()
    max_tokens = _editable_value(payload, "ai", "max_tokens")
    if max_tokens is not None:
        system["max_tokens"] = max_tokens
    if allow_shared_credentials_write:
        shared = _editable_value(payload, "ai", "allow_shared_ai_credentials")
        if shared is not None:
            system["allow_shared_ai_credentials"] = bool(shared)

    out_templates = _editable_value(payload, "templates", "out_templates")
    if out_templates is not None:
        system["out_templates"] = out_templates if isinstance(out_templates, dict) else {}

    run_defaults = payload.get("run_defaults") if isinstance(payload.get("run_defaults"), dict) else {}
    for key in ("project_name", "fpa_profile", "fpa_strategy", "fpa_rule_set", "fpa_confirmation_mode"):
        value = run_defaults.get(key)
        if isinstance(value, dict) and "value" in value:
            value = value.get("value")
        if value is not None:
            system[key] = value

    await save_config_to_dir(
        {"_env": env, "_system": system},
        target_dir,
        preserve_existing_sensitive=False,
    )
    return read_config_from_dir(target_dir)
