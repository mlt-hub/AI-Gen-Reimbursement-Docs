import os
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from web_app.services.config_audit_service import append_config_audit_record
from web_app.services.secret_service import SecretServiceError, decrypt_secret, encrypt_secret


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

ADVANCED_CONFIG_FILES = {
    "business_rules": {
        "filename": "business_rules.yaml",
        "format": "yaml",
        "label": "业务规则",
        "phase": 2,
    },
    "fpa_config": {
        "filename": "fpa_config.yaml",
        "format": "yaml",
        "label": "FPA 配置",
        "phase": 2,
    },
    "fpa_judgement_rules": {
        "filename": "fpa_judgement_rules.yaml",
        "format": "yaml",
        "label": "FPA 判定规则",
        "phase": 2,
    },
    "ai_system_prompts_config": {
        "filename": "ai_system_prompts_config.yaml",
        "format": "yaml",
        "label": "Prompt 配置",
        "phase": 3,
    },
    "domain_context": {
        "filename": "domain_context.json",
        "format": "json",
        "label": "领域上下文",
        "phase": 3,
    },
}

AI_TASK_MODES = {
    "from-excel-gen-all",
    "from-excel-gen-fpa",
    "from-excel-gen-cosmic",
    "from-excel-gen-list",
    "from-excel-gen-spec",
}


class AdvancedConfigError(ValueError):
    """Raised when an advanced config file cannot be parsed or validated."""


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


def _read_secret_from_env(env: dict, *, config_root: Path) -> str:
    plain = str(env.get("ANTHROPIC_API_KEY", "")).strip()
    if plain:
        return plain
    encrypted = str(env.get("ANTHROPIC_API_KEY_ENC", "")).strip()
    if not encrypted:
        return ""
    try:
        return decrypt_secret(encrypted, config_root=config_root)
    except SecretServiceError:
        return ""


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


def _first_explicit(explicit: dict, key: str) -> str:
    value = explicit.get(key, "")
    return str(value).strip() if value is not None else ""


def _effective_env_value(explicit: dict, explicit_key: str, env_key: str, user_env: dict, global_env: dict) -> str:
    value = _first_explicit(explicit, explicit_key)
    if value:
        return value
    if _configured_env_key(user_env, env_key):
        return str(user_env[env_key]).strip()
    if _configured_env_key(global_env, env_key):
        return str(global_env[env_key]).strip()
    return ""


def _effective_system_value(explicit: dict, key: str, user_system: dict, global_system: dict) -> str:
    value = _first_explicit(explicit, key)
    if value:
        return value
    if key in user_system and user_system[key] not in (None, ""):
        return str(user_system[key]).strip()
    if key in global_system and global_system[key] not in (None, ""):
        return str(global_system[key]).strip()
    default = DEFAULT_WEB_CONFIG.get(key, "")
    return str(default).strip()


def mode_requires_ai(mode: str, fpa_strategy: str = "") -> bool:
    if mode == "from-excel-gen-basedata":
        return False
    if mode == "from-excel-gen-fpa" and fpa_strategy == "rules_only":
        return False
    return mode in AI_TASK_MODES


def resolve_task_start_config(
    *,
    explicit: dict,
    global_config: dict,
    user_config: dict | None = None,
    local_mode: bool,
    global_config_root: Path,
    user_config_root: Path | None = None,
) -> dict:
    """Resolve a task-start parameter snapshot from explicit values and config files."""
    user_config = user_config or {}
    user_env = user_config.get("_env") if isinstance(user_config.get("_env"), dict) else {}
    user_system = user_config.get("_system") if isinstance(user_config.get("_system"), dict) else {}
    global_env = global_config.get("_env") if isinstance(global_config.get("_env"), dict) else {}
    global_system = global_config.get("_system") if isinstance(global_config.get("_system"), dict) else {}

    if local_mode:
        user_env = {}
        user_system = {}
        user_config_root = None

    fpa_strategy = _effective_system_value(explicit, "fpa_strategy", user_system, global_system)
    resolved = {
        "api_key": _first_explicit(explicit, "api_key"),
        "model": _effective_env_value(explicit, "model", "ANTHROPIC_MODEL", user_env, global_env),
        "base_url": _effective_env_value(explicit, "base_url", "ANTHROPIC_BASE_URL", user_env, global_env),
        "max_tokens": _effective_system_value(explicit, "max_tokens", user_system, global_system),
        "project_name": _effective_system_value(explicit, "project_name", user_system, global_system),
        "fpa_profile": _effective_system_value(explicit, "fpa_profile", user_system, global_system),
        "fpa_strategy": fpa_strategy,
        "fpa_rule_set": _effective_system_value(explicit, "fpa_rule_set", user_system, global_system),
        "fpa_confirmation_mode": _effective_system_value(explicit, "fpa_confirmation_mode", user_system, global_system),
        "api_key_source": "explicit" if _first_explicit(explicit, "api_key") else "missing",
        "uses_shared_api_key": False,
    }

    if resolved["api_key"]:
        return resolved

    if user_config_root is not None:
        user_api_key = _read_secret_from_env(user_env, config_root=user_config_root)
        if user_api_key:
            resolved["api_key"] = user_api_key
            resolved["api_key_source"] = "personal"
            return resolved

    shared_credentials = bool(global_system.get("allow_shared_ai_credentials", False))
    if local_mode or shared_credentials:
        global_api_key = _read_secret_from_env(global_env, config_root=global_config_root)
        if global_api_key:
            resolved["api_key"] = global_api_key
            resolved["api_key_source"] = "global"
            resolved["uses_shared_api_key"] = not local_mode

    return resolved


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


def _backup_file_name(path: Path, timestamp: str) -> str:
    return f"{path.name}.{timestamp}.bak"


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text through a same-directory temp file, then atomically replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{datetime.now():%Y%m%d_%H%M%S_%f}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def _atomic_copy_file(source: Path, destination: Path) -> None:
    """Copy to a same-directory temp file, then atomically replace destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(
        f".{destination.name}.{os.getpid()}.{datetime.now():%Y%m%d_%H%M%S_%f}.tmp",
    )
    try:
        shutil.copy2(source, temp_path)
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)


def _write_backup_copy(source: Path, destination: Path) -> None:
    if source.name == ".env":
        _atomic_write_text(destination, mask_env_content(source))
        shutil.copystat(source, destination)
        return
    shutil.copy2(source, destination)


def _prune_file_backups(*, backup_dir: Path, filename: str, keep: int) -> None:
    backups = sorted(
        backup_dir.glob(f"{filename}.*.bak"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[keep:]:
        old_backup.unlink(missing_ok=True)


def backup_single_config_file(
    *,
    source: Path,
    backup_root: Path,
    scope: str = "global",
    keep: int = 5,
) -> str | None:
    """Back up one existing config file and keep recent versions."""
    if not source.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_dir = backup_root / "backups" / "config" / scope
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / _backup_file_name(source, timestamp)
    _write_backup_copy(source, destination)
    _prune_file_backups(backup_dir=backup_dir, filename=source.name, keep=keep)
    return source.name


def backup_config_files(
    *,
    target_dir: Path,
    backup_root: Path,
    scope: str = "global",
    keep: int = 5,
) -> list[str]:
    """Back up existing config files before save and keep recent versions."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_dir = backup_root / "backups" / "config" / scope
    backup_dir.mkdir(parents=True, exist_ok=True)
    backed_up: list[str] = []

    for filename in (".env", "system_config.yaml"):
        source = target_dir / filename
        if not source.exists():
            continue
        destination = backup_dir / _backup_file_name(source, timestamp)
        _write_backup_copy(source, destination)
        backed_up.append(filename)

        _prune_file_backups(backup_dir=backup_dir, filename=source.name, keep=keep)

    return backed_up


def _backup_scope_dir(backup_root: Path, scope: str) -> Path:
    safe_scope = scope or "global"
    return backup_root / "backups" / "config" / safe_scope


def list_config_backups(
    *,
    backup_root: Path,
    scope: str = "global",
) -> list[dict]:
    """List restorable config backups for a scope without exposing file contents."""
    backup_dir = _backup_scope_dir(backup_root, scope)
    if not backup_dir.exists():
        return []

    items: list[dict] = []
    for path in backup_dir.glob("*.bak"):
        if path.name.startswith(".env."):
            config_file = ".env"
        elif path.name.startswith("system_config.yaml."):
            config_file = "system_config.yaml"
        else:
            continue
        stat = path.stat()
        items.append({
            "id": path.name,
            "file": config_file,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size_bytes": stat.st_size,
        })

    return sorted(items, key=lambda item: item["created_at"], reverse=True)


def _advanced_config_meta(file_id: str) -> dict:
    meta = ADVANCED_CONFIG_FILES.get(file_id)
    if not meta:
        raise AdvancedConfigError(f"未知高级配置文件: {file_id}")
    return meta


def list_advanced_config_files(*, target_dir: Path) -> list[dict]:
    """List advanced config files that the Web UI can edit."""
    items: list[dict] = []
    for file_id, meta in ADVANCED_CONFIG_FILES.items():
        path = target_dir / str(meta["filename"])
        stat = path.stat() if path.exists() else None
        items.append({
            "id": file_id,
            "label": meta["label"],
            "file": meta["filename"],
            "format": meta["format"],
            "phase": meta["phase"],
            "exists": path.exists(),
            "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat() if stat else "",
            "size_bytes": stat.st_size if stat else 0,
        })
    return items


def read_advanced_config_file(*, file_id: str, target_dir: Path) -> dict:
    """Read one advanced config file as editable text."""
    meta = _advanced_config_meta(file_id)
    path = target_dir / str(meta["filename"])
    return {
        "id": file_id,
        "label": meta["label"],
        "file": meta["filename"],
        "format": meta["format"],
        "phase": meta["phase"],
        "exists": path.exists(),
        "content": path.read_text(encoding="utf-8") if path.exists() else "",
    }


def _parse_advanced_config_content(file_id: str, content: str):
    meta = _advanced_config_meta(file_id)
    if meta["format"] == "json":
        try:
            return json.loads(content or "{}")
        except json.JSONDecodeError as exc:
            raise AdvancedConfigError(f"JSON 语法错误: 第 {exc.lineno} 行第 {exc.colno} 列，{exc.msg}") from exc

    try:
        import yaml

        return yaml.safe_load(content or "") or {}
    except Exception as exc:
        problem = getattr(exc, "problem", "") or str(exc)
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            raise AdvancedConfigError(f"YAML 语法错误: 第 {mark.line + 1} 行第 {mark.column + 1} 列，{problem}") from exc
        raise AdvancedConfigError(f"YAML 语法错误: {problem}") from exc


def _require_mapping_config(value: object, filename: str) -> dict:
    if not isinstance(value, dict):
        raise AdvancedConfigError(f"{filename} 必须是对象或 YAML 映射")
    return value


def _validate_fpa_judgement_rules_payload(value: object) -> None:
    cfg = _require_mapping_config(value, "fpa_judgement_rules.yaml")
    rules = cfg.get("judgement_rules")
    if not isinstance(rules, list) or not rules:
        raise AdvancedConfigError("fpa_judgement_rules.yaml 中的 judgement_rules 必须是非空字符串列表")
    for index, rule in enumerate(rules):
        if not isinstance(rule, str) or not rule.strip():
            raise AdvancedConfigError(f"fpa_judgement_rules.yaml 中的 judgement_rules[{index}] 必须是非空字符串")


def _validate_ai_system_prompts_payload(value: object) -> None:
    cfg = _require_mapping_config(value, "ai_system_prompts_config.yaml")
    prompts = cfg.get("ai_prompts", {})
    if prompts in (None, ""):
        return
    if not isinstance(prompts, dict):
        raise AdvancedConfigError("ai_system_prompts_config.yaml 中的 ai_prompts 必须是对象")
    for name, entry in prompts.items():
        if not isinstance(entry, dict):
            raise AdvancedConfigError(f"ai_system_prompts_config.yaml 中的 ai_prompts.{name} 必须是对象")
        for key in ("system", "examples"):
            if key in entry and not isinstance(entry.get(key), str):
                raise AdvancedConfigError(f"ai_system_prompts_config.yaml 中的 ai_prompts.{name}.{key} 必须是字符串")


def validate_advanced_config_content(*, file_id: str, content: str) -> dict:
    """Validate advanced YAML/JSON content and return parsed metadata."""
    parsed = _parse_advanced_config_content(file_id, content)
    meta = _advanced_config_meta(file_id)
    filename = str(meta["filename"])

    try:
        if file_id == "fpa_config":
            from ai_gen_reimbursement_docs.config_utils import validate_fpa_config

            validate_fpa_config(_require_mapping_config(parsed, filename))
        elif file_id == "fpa_judgement_rules":
            _validate_fpa_judgement_rules_payload(parsed)
        elif file_id == "domain_context":
            from ai_gen_reimbursement_docs.config_utils import validate_fpa_domain_context

            validate_fpa_domain_context(_require_mapping_config(parsed, filename))
        elif file_id == "ai_system_prompts_config":
            _validate_ai_system_prompts_payload(parsed)
        else:
            _require_mapping_config(parsed, filename)
    except AdvancedConfigError:
        raise
    except Exception as exc:
        raise AdvancedConfigError(str(exc)) from exc

    return {
        "ok": True,
        "file": filename,
        "format": meta["format"],
    }


def save_advanced_config_file(
    *,
    file_id: str,
    content: str,
    target_dir: Path,
    actor: str,
    audit_root: Path | None = None,
    backup_root: Path | None = None,
    backup_scope: str = "global",
) -> dict:
    """Validate and save one advanced config file with backup and audit."""
    audit_root = audit_root or target_dir
    backup_root = backup_root or target_dir
    meta = _advanced_config_meta(file_id)
    filename = str(meta["filename"])
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    try:
        validation = validate_advanced_config_content(file_id=file_id, content=content)
    except AdvancedConfigError:
        append_config_audit_record(
            audit_root=audit_root,
            actor=actor,
            target_dir=target_dir,
            files=[filename],
            changed_fields=[f"advanced_config.{file_id}"],
            result="validation_failed",
        )
        raise

    backed_up = backup_single_config_file(
        source=target_path,
        backup_root=backup_root,
        scope=backup_scope,
    )
    text = content if content.endswith("\n") else f"{content}\n"
    _atomic_write_text(target_path, text)

    try:
        from ai_gen_reimbursement_docs.config_utils import clear_config_caches

        clear_config_caches()
    except Exception:
        pass

    append_config_audit_record(
        audit_root=audit_root,
        actor=actor,
        target_dir=target_dir,
        files=[filename],
        changed_fields=[f"advanced_config.{file_id}"],
        result="success",
    )
    return {
        **validation,
        "id": file_id,
        "backed_up": [backed_up] if backed_up else [],
        "content": target_path.read_text(encoding="utf-8"),
    }


def _resolve_backup_path(*, backup_root: Path, scope: str, backup_id: str) -> tuple[Path, str]:
    if "/" in backup_id or "\\" in backup_id or ".." in backup_id:
        raise ValueError("备份 ID 无效")
    if backup_id.startswith(".env."):
        config_file = ".env"
    elif backup_id.startswith("system_config.yaml."):
        config_file = "system_config.yaml"
    else:
        raise ValueError("只支持恢复 .env 或 system_config.yaml 备份")
    if not backup_id.endswith(".bak"):
        raise ValueError("备份 ID 无效")

    backup_dir = _backup_scope_dir(backup_root, scope)
    candidate = (backup_dir / backup_id).resolve()
    backup_dir_resolved = backup_dir.resolve()
    if candidate.parent != backup_dir_resolved:
        raise ValueError("备份 ID 无效")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError("备份不存在")
    return candidate, config_file


def restore_config_backup(
    *,
    target_dir: Path,
    backup_root: Path,
    scope: str,
    backup_id: str,
    actor: str,
    audit_root: Path | None = None,
) -> dict:
    """Restore a single config backup after backing up the current target file."""
    backup_path, config_file = _resolve_backup_path(
        backup_root=backup_root,
        scope=scope,
        backup_id=backup_id,
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    backup_config_files(
        target_dir=target_dir,
        backup_root=backup_root,
        scope=scope,
    )

    _atomic_copy_file(backup_path, target_dir / config_file)
    try:
        from ai_gen_reimbursement_docs.config_utils import clear_config_caches

        clear_config_caches()
    except Exception:
        pass

    field_name = "env" if config_file == ".env" else config_file
    append_config_audit_record(
        audit_root=audit_root or backup_root,
        actor=actor,
        target_dir=target_dir,
        files=[config_file],
        changed_fields=[f"restore.{field_name}"],
        result="success",
    )
    return read_config_from_dir(target_dir)


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
        _atomic_write_text(target_dir / ".env", "\n".join(lines) + "\n")

    if "_system" in data and data["_system"]:
        import yaml

        _atomic_write_text(
            target_dir / "system_config.yaml",
            yaml.dump(data["_system"], allow_unicode=True, default_flow_style=False),
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
    actor: str = "system",
    audit_root: Path | None = None,
    backup_root: Path | None = None,
    backup_scope: str = "global",
) -> dict:
    """Save the first-phase Web config payload without writing plaintext API keys."""
    audit_root = audit_root or target_dir
    backup_root = backup_root or target_dir
    existing = read_config_from_dir(target_dir)
    env = dict(existing.get("_env") if isinstance(existing.get("_env"), dict) else {})
    system = dict(existing.get("_system") if isinstance(existing.get("_system"), dict) else {})
    changed_fields: list[str] = []

    ai = payload.get("ai") if isinstance(payload.get("ai"), dict) else {}
    api_key = ai.get("api_key")
    clear_api_key = bool(ai.get("clear_api_key", False))
    if clear_api_key:
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_API_KEY_ENC", None)
        changed_fields.append("ai.api_key")
    elif isinstance(api_key, str) and api_key.strip() and api_key.strip() != "***":
        env.pop("ANTHROPIC_API_KEY", None)
        env["ANTHROPIC_API_KEY_ENC"] = encrypt_secret(api_key, config_root=target_dir)
        changed_fields.append("ai.api_key")

    base_url = _editable_value(payload, "ai", "base_url")
    if base_url is not None:
        env["ANTHROPIC_BASE_URL"] = str(base_url).strip()
        changed_fields.append("ai.base_url")
    model = _editable_value(payload, "ai", "model")
    if model is not None:
        env["ANTHROPIC_MODEL"] = str(model).strip()
        changed_fields.append("ai.model")
    max_tokens = _editable_value(payload, "ai", "max_tokens")
    if max_tokens is not None:
        system["max_tokens"] = max_tokens
        changed_fields.append("ai.max_tokens")
    if allow_shared_credentials_write:
        shared = _editable_value(payload, "ai", "allow_shared_ai_credentials")
        if shared is not None:
            system["allow_shared_ai_credentials"] = bool(shared)
            changed_fields.append("ai.allow_shared_ai_credentials")

    out_templates = _editable_value(payload, "templates", "out_templates")
    if out_templates is not None:
        system["out_templates"] = out_templates if isinstance(out_templates, dict) else {}
        changed_fields.append("templates.out_templates")

    run_defaults = payload.get("run_defaults") if isinstance(payload.get("run_defaults"), dict) else {}
    for key in ("project_name", "fpa_profile", "fpa_strategy", "fpa_rule_set", "fpa_confirmation_mode"):
        value = run_defaults.get(key)
        if isinstance(value, dict) and "value" in value:
            value = value.get("value")
        if value is not None:
            system[key] = value
            changed_fields.append(f"run_defaults.{key}")

    backed_up = backup_config_files(
        target_dir=target_dir,
        backup_root=backup_root,
        scope=backup_scope,
    )
    await save_config_to_dir(
        {"_env": env, "_system": system},
        target_dir,
        preserve_existing_sensitive=False,
    )
    try:
        from ai_gen_reimbursement_docs.config_utils import clear_config_caches

        clear_config_caches()
    except Exception:
        pass
    append_config_audit_record(
        audit_root=audit_root,
        actor=actor,
        target_dir=target_dir,
        files=backed_up or [".env", "system_config.yaml"],
        changed_fields=changed_fields,
        result="success",
    )
    return read_config_from_dir(target_dir)
