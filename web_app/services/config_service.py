import os
import json
import re
import shutil
import difflib
from contextlib import contextmanager
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
    "active_output_template_profile": "",
    "output_template_profiles": {},
    "project_name": "",
    "fpa_profile": "strict_fpa",
    "fpa_strategy": "",
    "fpa_rule_set": "",
    "fpa_core_rules": "",
    "fpa_system_prompt": "",
    "fpa_user_prompt": "",
    "fpa_base_profile": "",
    "fpa_confirmation_mode": "auto",
}

OUTPUT_TEMPLATE_PROFILE_RUN_DEFAULT_KEYS = (
    "fpa_profile",
    "fpa_strategy",
    "fpa_rule_set",
    "fpa_core_rules",
    "fpa_system_prompt",
    "fpa_user_prompt",
    "fpa_base_profile",
    "fpa_confirmation_mode",
)

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

RESTORABLE_CONFIG_FILES = (
    ".env",
    "system_config.yaml",
    *tuple(str(meta["filename"]) for meta in ADVANCED_CONFIG_FILES.values()),
)

CONFIG_PACKAGE_VERSION = 1
CONFIG_PACKAGE_FILES = RESTORABLE_CONFIG_FILES
SENSITIVE_ENV_KEY = re.compile(r'_(?:KEY|SECRET|TOKEN|PASSWORD)(?:_ENC)?$', re.IGNORECASE)

AI_TASK_MODES = {
    "from-excel-gen-all",
    "from-excel-gen-fpa",
    "from-excel-gen-cosmic",
    "from-excel-gen-list",
    "from-excel-gen-spec",
}


class AdvancedConfigError(ValueError):
    """Raised when an advanced config file cannot be parsed or validated."""


FPA_PROMPT_SAMPLE_GROUP: dict[str, object] = {
    "client_type": "后台",
    "l1": "业务管理",
    "l2": "客户管理",
    "l3": "客户资料维护",
    "l3_desc": "维护客户基础资料，支持新增、编辑、查询和导出客户信息。",
    "processes": [
        {
            "id": "P1",
            "process_id": "P1",
            "name": "新增客户",
            "process_name": "新增客户",
            "desc": "录入客户名称、证件号码、联系电话并保存客户资料。",
            "description": "录入客户名称、证件号码、联系电话并保存客户资料。",
        },
        {
            "id": "P2",
            "process_id": "P2",
            "name": "查询客户",
            "process_name": "查询客户",
            "desc": "按客户名称和证件号码查询客户列表。",
            "description": "按客户名称和证件号码查询客户列表。",
        },
        {
            "id": "P3",
            "process_id": "P3",
            "name": "导出客户清单",
            "process_name": "导出客户清单",
            "desc": "导出客户资料清单。",
            "description": "导出客户资料清单。",
        },
    ],
}

FPA_PROMPT_SAMPLE_JUDGEMENT_RULES = [
    "维护业务数据的外部输入，按 EI 识别。",
    "查询业务数据且无派生计算，按 EQ 识别。",
    "输出格式化清单或报表，按 EO 识别。",
    "本系统维护的逻辑数据组，按 ILF 识别。",
    "外部系统维护、本系统引用的数据组，按 EIF 识别。",
]


@contextmanager
def _temporary_fpa_config_dir(target_dir: Path):
    from ai_gen_reimbursement_docs.config_utils import FPA_CONFIG_DIR_ENV, clear_config_caches

    previous = os.environ.get(FPA_CONFIG_DIR_ENV)
    os.environ[FPA_CONFIG_DIR_ENV] = str(target_dir)
    clear_config_caches()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(FPA_CONFIG_DIR_ENV, None)
        else:
            os.environ[FPA_CONFIG_DIR_ENV] = previous
        clear_config_caches()


def _sample_judgement_rules(target_dir: Path) -> list[str]:
    try:
        view = build_fpa_judgement_rules_view(target_dir=target_dir)
    except AdvancedConfigError:
        return list(FPA_PROMPT_SAMPLE_JUDGEMENT_RULES)
    rules = [str(item).strip() for item in view.get("rules", []) if str(item).strip()]
    return rules or list(FPA_PROMPT_SAMPLE_JUDGEMENT_RULES)


def _fpa_quality_warnings_from_rows(rows: list[dict[str, object]]) -> list[str]:
    warnings: list[str] = []
    for row in rows:
        for hit in row.get("_规则命中详情", []) if isinstance(row.get("_规则命中详情"), list) else []:
            if not isinstance(hit, dict) or hit.get("rule_id") != "postprocess.explanation_quality":
                continue
            hit_warnings = hit.get("warnings", [])
            if isinstance(hit_warnings, list):
                warnings.extend(str(item) for item in hit_warnings if str(item).strip())
    return list(dict.fromkeys(warnings))


def _fpa_sample_row_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "序号": row.get("序号", ""),
        "新增/修改功能点": row.get("新增/修改功能点", ""),
        "类型": row.get("类型", ""),
        "生成方式": row.get("生成方式", ""),
        "计算依据归类": row.get("计算依据归类", ""),
        "计算依据说明": row.get("计算依据说明", ""),
        "后处理警告": row.get("后处理警告", ""),
        "源功能过程": row.get("源功能过程", ""),
    }


def _empty_fpa_prompt_sample_result(
    *,
    profile_name: str,
    prompt_diagnostics: dict[str, object],
) -> dict[str, object]:
    return {
        "profile": profile_name,
        "prompt_diagnostics": prompt_diagnostics,
        "sample_input": FPA_PROMPT_SAMPLE_GROUP,
        "ai_called": False,
        "parse_ok": False,
        "raw_response": "",
        "parsed_rows": [],
        "normalized_rows": [],
        "warnings": [],
        "quality_warnings": [],
        "rule_hits": [],
        "error": "",
        "model": "",
        "base_url": "",
        "api_key_source": "",
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


def max_concurrent_tasks(default: int = 1) -> int:
    """读取 Web 后台任务并发上限，非法配置按 1 处理。"""
    system_config = read_config().get("_system", {})
    web_config = system_config.get("web", {})
    value = None
    if isinstance(web_config, dict):
        value = web_config.get("max_concurrent_tasks")
    if value is None:
        value = system_config.get("web.max_concurrent_tasks")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return max(1, default)
    return parsed if parsed >= 1 else max(1, default)


def _mask_env_text(text: str) -> str:
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


def mask_env_content(path: Path) -> str:
    """读取 .env 文件内容，遮住敏感值，不暴露任何原文片段。"""
    return _mask_env_text(path.read_text(encoding="utf-8"))


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
        "fpa_core_rules": _effective_system_value(explicit, "fpa_core_rules", user_system, global_system),
        "fpa_system_prompt": _effective_system_value(explicit, "fpa_system_prompt", user_system, global_system),
        "fpa_user_prompt": _effective_system_value(explicit, "fpa_user_prompt", user_system, global_system),
        "fpa_base_profile": _effective_system_value(explicit, "fpa_base_profile", user_system, global_system),
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
            "active_output_template_profile": _pick_system_field(
                user_system,
                global_system,
                "active_output_template_profile",
                DEFAULT_WEB_CONFIG["active_output_template_profile"],
            ),
            "output_template_profiles": _pick_system_field(
                user_system,
                global_system,
                "output_template_profiles",
                DEFAULT_WEB_CONFIG["output_template_profiles"],
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
            "fpa_core_rules": _pick_system_field(
                user_system,
                global_system,
                "fpa_core_rules",
                DEFAULT_WEB_CONFIG["fpa_core_rules"],
            ),
            "fpa_system_prompt": _pick_system_field(
                user_system,
                global_system,
                "fpa_system_prompt",
                DEFAULT_WEB_CONFIG["fpa_system_prompt"],
            ),
            "fpa_user_prompt": _pick_system_field(
                user_system,
                global_system,
                "fpa_user_prompt",
                DEFAULT_WEB_CONFIG["fpa_user_prompt"],
            ),
            "fpa_base_profile": _pick_system_field(
                user_system,
                global_system,
                "fpa_base_profile",
                DEFAULT_WEB_CONFIG["fpa_base_profile"],
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
        config_file = _config_file_from_backup_id(path.name)
        if not config_file:
            continue
        stat = path.stat()
        items.append({
            "id": path.name,
            "file": config_file,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size_bytes": stat.st_size,
        })

    return sorted(items, key=lambda item: item["created_at"], reverse=True)


def _config_file_from_backup_id(backup_id: str) -> str | None:
    if not backup_id.endswith(".bak"):
        return None
    for filename in sorted(RESTORABLE_CONFIG_FILES, key=len, reverse=True):
        if backup_id.startswith(f"{filename}."):
            return filename
    return None


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


def _read_env_package_content(path: Path) -> str:
    lines: list[str] = []
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            lines.append(line)
            continue
        key, _value = stripped.split("=", 1)
        if SENSITIVE_ENV_KEY.search(key.strip()):
            continue
        lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


def build_config_export_package(*, target_dir: Path) -> dict:
    """Build a non-secret global config package for Web UI download."""
    files: dict[str, str] = {}
    for filename in CONFIG_PACKAGE_FILES:
        path = target_dir / filename
        if not path.exists():
            continue
        if filename == ".env":
            content = _read_env_package_content(path)
            if content:
                files[filename] = content
            continue
        files[filename] = path.read_text(encoding="utf-8")
    return {
        "version": CONFIG_PACKAGE_VERSION,
        "exported_at": datetime.now().isoformat(),
        "files": files,
    }


def _validate_package_env_content(content: str) -> None:
    for index, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise AdvancedConfigError(f".env 第 {index} 行必须是 KEY=VALUE")
        key, _value = stripped.split("=", 1)
        if SENSITIVE_ENV_KEY.search(key.strip()):
            raise AdvancedConfigError(".env 配置包不能包含 API Key、密钥或令牌字段")


def _validate_config_package_payload(package: object) -> dict[str, str]:
    if not isinstance(package, dict):
        raise AdvancedConfigError("配置包必须是 JSON 对象")
    files = package.get("files")
    if not isinstance(files, dict):
        raise AdvancedConfigError("配置包缺少 files 对象")
    unknown = sorted(set(files) - set(CONFIG_PACKAGE_FILES))
    if unknown:
        raise AdvancedConfigError(f"配置包包含不支持的文件: {', '.join(unknown)}")

    validated: dict[str, str] = {}
    for filename, content in files.items():
        if not isinstance(content, str):
            raise AdvancedConfigError(f"{filename} 内容必须是字符串")
        if filename == ".env":
            _validate_package_env_content(content)
        elif filename == "system_config.yaml":
            try:
                import yaml

                parsed = yaml.safe_load(content or "") or {}
            except Exception as exc:
                raise AdvancedConfigError(f"system_config.yaml 语法错误: {exc}") from exc
            _require_mapping_config(parsed, "system_config.yaml")
        else:
            file_id = next(
                (key for key, meta in ADVANCED_CONFIG_FILES.items() if meta["filename"] == filename),
                "",
            )
            if not file_id:
                raise AdvancedConfigError(f"配置包包含不支持的文件: {filename}")
            validate_advanced_config_content(file_id=file_id, content=content)
        validated[filename] = content if content.endswith("\n") else f"{content}\n"
    return validated


def import_config_package(
    *,
    package: object,
    target_dir: Path,
    actor: str,
    audit_root: Path | None = None,
    backup_root: Path | None = None,
    backup_scope: str = "global",
) -> dict:
    """Validate and import a non-secret config package."""
    audit_root = audit_root or target_dir
    backup_root = backup_root or target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        files = _validate_config_package_payload(package)
    except AdvancedConfigError:
        append_config_audit_record(
            audit_root=audit_root,
            actor=actor,
            target_dir=target_dir,
            files=[],
            changed_fields=["config_package"],
            result="validation_failed",
        )
        raise

    backed_up = []
    for filename in files:
        backed = backup_single_config_file(
            source=target_dir / filename,
            backup_root=backup_root,
            scope=backup_scope,
        )
        if backed:
            backed_up.append(backed)

    for filename, content in files.items():
        _atomic_write_text(target_dir / filename, content)

    try:
        from ai_gen_reimbursement_docs.config_utils import clear_config_caches

        clear_config_caches()
    except Exception:
        pass

    append_config_audit_record(
        audit_root=audit_root,
        actor=actor,
        target_dir=target_dir,
        files=sorted(files),
        changed_fields=["config_package"],
        result="success",
    )
    return {
        "ok": True,
        "imported": sorted(files),
        "backed_up": backed_up,
    }


def _read_fpa_config_from_dir(target_dir: Path) -> dict:
    path = target_dir / "fpa_config.yaml"
    if not path.exists():
        raise AdvancedConfigError("未找到 FPA 配置文件：fpa_config.yaml")
    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise AdvancedConfigError(f"读取 FPA 配置失败: {exc}") from exc
    if not isinstance(loaded, dict):
        raise AdvancedConfigError("fpa_config.yaml 必须是 YAML 映射")
    return loaded


def build_fpa_strategy_settings_view(*, target_dir: Path) -> dict:
    """Build structured settings for common FPA strategy fields."""
    from ai_gen_reimbursement_docs.config_utils import diagnose_fpa_prompt_config

    cfg = _read_fpa_config_from_dir(target_dir)
    profiles = cfg.get("profiles")
    rule_sets = cfg.get("rule_sets")
    if not isinstance(profiles, dict) or not isinstance(rule_sets, dict):
        raise AdvancedConfigError("fpa_config.yaml 中的 profiles 和 rule_sets 必须是对象")

    profile_items: list[dict] = []
    prompt_diagnostics: list[dict] = []
    for name, entry in profiles.items():
        if not isinstance(entry, dict):
            continue
        diagnostics = diagnose_fpa_prompt_config(str(name), cfg=cfg).to_dict()
        prompt_diagnostics.append(diagnostics)
        profile_items.append({
            "name": str(name),
            "kind": str(entry.get("kind") or ""),
            "strategy": str(entry.get("strategy") or ""),
            "rule_set": str(entry.get("rule_set") or ""),
            "core_rules": str(entry.get("core_rules") or ""),
            "system_prompt": str(entry.get("system_prompt") or ""),
            "user_prompt": str(entry.get("user_prompt") or ""),
            "prompt_diagnostics": diagnostics,
        })

    rule_set_items = []
    for name, entry in rule_sets.items():
        entry_map = entry if isinstance(entry, dict) else {}
        rule_set_items.append({
            "name": str(name),
            "extends": str(entry_map.get("extends") or ""),
        })

    return {
        "default_profile": str(cfg.get("default-profile") or ""),
        "profiles": profile_items,
        "rule_sets": rule_set_items,
        "prompt_diagnostics": prompt_diagnostics,
    }


def save_fpa_strategy_settings(
    *,
    payload: dict,
    target_dir: Path,
    actor: str,
    audit_root: Path | None = None,
    backup_root: Path | None = None,
    backup_scope: str = "global",
) -> dict:
    """Save structured FPA profile strategy/rule_set settings."""
    audit_root = audit_root or target_dir
    backup_root = backup_root or target_dir
    target_path = target_dir / "fpa_config.yaml"
    cfg = _read_fpa_config_from_dir(target_dir)
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict):
        raise AdvancedConfigError("fpa_config.yaml 中的 profiles 必须是对象")

    default_profile = str(payload.get("default_profile") or "").strip()
    if default_profile:
        cfg["default-profile"] = default_profile

    changed_fields: list[str] = []
    if default_profile:
        changed_fields.append("fpa_strategy.default_profile")

    incoming_profiles = payload.get("profiles")
    if not isinstance(incoming_profiles, list):
        raise AdvancedConfigError("profiles 必须是列表")

    for item in incoming_profiles:
        if not isinstance(item, dict):
            raise AdvancedConfigError("profiles 中的每一项必须是对象")
        name = str(item.get("name") or "").strip()
        if not name or name not in profiles or not isinstance(profiles.get(name), dict):
            raise AdvancedConfigError(f"未知 FPA profile: {name}")
        entry = dict(profiles[name])
        if "strategy" in item:
            entry["strategy"] = str(item.get("strategy") or "").strip()
            changed_fields.append(f"fpa_strategy.profiles.{name}.strategy")
        if "rule_set" in item:
            entry["rule_set"] = str(item.get("rule_set") or "").strip()
            changed_fields.append(f"fpa_strategy.profiles.{name}.rule_set")
        profiles[name] = entry

    try:
        from ai_gen_reimbursement_docs.config_utils import validate_fpa_config

        validate_fpa_config(cfg)
    except Exception as exc:
        append_config_audit_record(
            audit_root=audit_root,
            actor=actor,
            target_dir=target_dir,
            files=["fpa_config.yaml"],
            changed_fields=changed_fields or ["fpa_strategy"],
            result="validation_failed",
        )
        raise AdvancedConfigError(str(exc)) from exc

    backed_up = backup_single_config_file(
        source=target_path,
        backup_root=backup_root,
        scope=backup_scope,
    )
    import yaml

    text = yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False)
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
        files=["fpa_config.yaml"],
        changed_fields=changed_fields or ["fpa_strategy"],
        result="success",
    )
    result = build_fpa_strategy_settings_view(target_dir=target_dir)
    result["backed_up"] = [backed_up] if backed_up else []
    return result


def run_fpa_prompt_sample_preview(
    *,
    profile_name: str,
    target_dir: Path,
) -> dict[str, object]:
    """Run the configured FPA prompt against a fixed sample module without writing artifacts."""
    from ai_gen_reimbursement_docs.config_utils import diagnose_fpa_prompt_config
    from ai_gen_reimbursement_docs.fpa_profiles import resolve_fpa_execution_config
    from ai_gen_reimbursement_docs.gen_fpa import (
        _ai_plan_fpa_rows_for_l3_debug,
        _build_domain_context,
        _normalize_ai_fpa_rows_for_l3,
        _trace_rule_hits_for_rows,
        reset_current_fpa_rule_set_config,
        set_current_fpa_rule_set_config,
    )

    cfg = _read_fpa_config_from_dir(target_dir)
    profile_key = str(profile_name or cfg.get("default-profile") or "strict_fpa").strip()
    diagnostics = diagnose_fpa_prompt_config(profile_key, cfg=cfg).to_dict()
    diagnostics["fragments"] = [{
        "name": "calculation_explanation_rules",
        **diagnostics["calculation_explanation_rules"],
    }]
    diagnostics["rendered_prompt"] = diagnostics["final_prompt_preview"]
    if diagnostics.get("errors"):
        result = _empty_fpa_prompt_sample_result(
            profile_name=profile_key,
            prompt_diagnostics=diagnostics,
        )
        result["warnings"] = ["prompt diagnostics 存在 error，未调用模型"]
        return result

    runtime_config = resolve_task_start_config(
        explicit={},
        global_config=read_config_from_dir(target_dir),
        local_mode=True,
        global_config_root=target_dir,
    )
    api_key = str(runtime_config.get("api_key") or "").strip()
    model = str(runtime_config.get("model") or "").strip()
    base_url = str(runtime_config.get("base_url") or "").strip()
    if not api_key:
        raise AdvancedConfigError("当前运行配置没有可用 API Key，无法试运行 prompt")

    group = json.loads(json.dumps(FPA_PROMPT_SAMPLE_GROUP, ensure_ascii=False))
    judgement_rules = _sample_judgement_rules(target_dir)
    meta = {
        "子系统（模块）": "样例系统",
        "资产标识": "PROMPT-SAMPLE",
    }

    with _temporary_fpa_config_dir(target_dir):
        execution = resolve_fpa_execution_config(profile_key)
        profile = execution.profile
        rule_set_token = set_current_fpa_rule_set_config(execution.rule_set_config)
        try:
            try:
                raw_rows, debug = _ai_plan_fpa_rows_for_l3_debug(
                    group,
                    judgement_rules,
                    _build_domain_context(meta),
                    api_key,
                    model,
                    base_url,
                    profile=profile,
                )
            except Exception as exc:
                debug = getattr(exc, "debug", {})
                raw_response = str(debug.get("raw_response", "")) if isinstance(debug, dict) else ""
                parsed_rows = debug.get("parsed_rows", []) if isinstance(debug, dict) else []
                return {
                    "profile": profile_key,
                    "prompt_diagnostics": diagnostics,
                    "sample_input": group,
                    "ai_called": bool(debug.get("ai_called", True)) if isinstance(debug, dict) else True,
                    "parse_ok": False,
                    "raw_response": raw_response,
                    "parsed_rows": parsed_rows if isinstance(parsed_rows, list) else [],
                    "normalized_rows": [],
                    "warnings": [str(exc)],
                    "quality_warnings": [],
                    "rule_hits": [],
                    "error": str(exc),
                    "model": model,
                    "base_url": base_url,
                    "api_key_source": runtime_config.get("api_key_source", ""),
                }

            normalized_rows, warnings = _normalize_ai_fpa_rows_for_l3(
                group=group,
                meta=meta,
                ai_rows=raw_rows,
                judgement_rules=judgement_rules,
                start_seq=1,
                profile=profile,
                strategy="ai_only",
            )
            quality_warnings = _fpa_quality_warnings_from_rows(normalized_rows)
            rule_hits = _trace_rule_hits_for_rows(normalized_rows)
            raw_response = str(debug.get("raw_response", "")) if isinstance(debug, dict) else ""
            return {
                "profile": profile_key,
                "prompt_diagnostics": diagnostics,
                "sample_input": group,
                "ai_called": True,
                "parse_ok": True,
                "raw_response": raw_response,
                "parsed_rows": raw_rows,
                "normalized_rows": [_fpa_sample_row_payload(row) for row in normalized_rows],
                "warnings": warnings,
                "quality_warnings": quality_warnings,
                "rule_hits": rule_hits,
                "error": "",
                "model": model,
                "base_url": base_url,
                "api_key_source": runtime_config.get("api_key_source", ""),
            }
        finally:
            reset_current_fpa_rule_set_config(rule_set_token)


def build_fpa_judgement_rules_view(*, target_dir: Path) -> dict:
    """Read FPA judgement rules as a structured list for Web editing."""
    path = target_dir / "fpa_judgement_rules.yaml"
    if not path.exists():
        return {"rules": [], "exists": False}
    parsed = _parse_advanced_config_content("fpa_judgement_rules", path.read_text(encoding="utf-8"))
    _validate_fpa_judgement_rules_payload(parsed)
    rules = parsed.get("judgement_rules") if isinstance(parsed, dict) else []
    return {
        "rules": [str(rule).strip() for rule in rules],
        "exists": True,
    }


def save_fpa_judgement_rules(
    *,
    rules: list[object],
    target_dir: Path,
    actor: str,
    audit_root: Path | None = None,
    backup_root: Path | None = None,
    backup_scope: str = "global",
) -> dict:
    """Save structured FPA judgement rules after validation."""
    audit_root = audit_root or target_dir
    backup_root = backup_root or target_dir
    filename = "fpa_judgement_rules.yaml"
    target_path = target_dir / filename
    normalized = [str(rule).strip() for rule in rules if str(rule).strip()]
    payload = {"judgement_rules": normalized}

    try:
        _validate_fpa_judgement_rules_payload(payload)
    except AdvancedConfigError:
        append_config_audit_record(
            audit_root=audit_root,
            actor=actor,
            target_dir=target_dir,
            files=[filename],
            changed_fields=["fpa_judgement_rules"],
            result="validation_failed",
        )
        raise

    backed_up = backup_single_config_file(
        source=target_path,
        backup_root=backup_root,
        scope=backup_scope,
    )
    import yaml

    text = yaml.dump(payload, allow_unicode=True, default_flow_style=False, sort_keys=False)
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
        changed_fields=["fpa_judgement_rules"],
        result="success",
    )
    result = build_fpa_judgement_rules_view(target_dir=target_dir)
    result["backed_up"] = [backed_up] if backed_up else []
    return result


def build_business_rules_view(*, target_dir: Path) -> dict:
    """Read currently supported business_rules.yaml fields."""
    from ai_gen_reimbursement_docs.config_utils import DEFAULT_CFP_FORMULA

    path = target_dir / "business_rules.yaml"
    if not path.exists():
        return {
            "cfp_formula": DEFAULT_CFP_FORMULA,
            "exists": False,
        }
    parsed = _parse_advanced_config_content("business_rules", path.read_text(encoding="utf-8"))
    cfg = _require_mapping_config(parsed, "business_rules.yaml")
    return {
        "cfp_formula": str(cfg.get("cfp_formula") or DEFAULT_CFP_FORMULA),
        "exists": True,
    }


def save_business_rules(
    *,
    cfp_formula: object,
    target_dir: Path,
    actor: str,
    audit_root: Path | None = None,
    backup_root: Path | None = None,
    backup_scope: str = "global",
) -> dict:
    """Save structured business rules fields while preserving unknown YAML keys."""
    audit_root = audit_root or target_dir
    backup_root = backup_root or target_dir
    filename = "business_rules.yaml"
    target_path = target_dir / filename
    formula = str(cfp_formula or "").strip()
    if not formula:
        append_config_audit_record(
            audit_root=audit_root,
            actor=actor,
            target_dir=target_dir,
            files=[filename],
            changed_fields=["business_rules.cfp_formula"],
            result="validation_failed",
        )
        raise AdvancedConfigError("CFP 计算公式不能为空")

    if target_path.exists():
        parsed = _parse_advanced_config_content("business_rules", target_path.read_text(encoding="utf-8"))
        payload = dict(_require_mapping_config(parsed, filename))
    else:
        payload = {}
    payload["cfp_formula"] = formula

    backed_up = backup_single_config_file(
        source=target_path,
        backup_root=backup_root,
        scope=backup_scope,
    )
    import yaml

    text = yaml.dump(payload, allow_unicode=True, default_flow_style=False, sort_keys=False)
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
        changed_fields=["business_rules.cfp_formula"],
        result="success",
    )
    result = build_business_rules_view(target_dir=target_dir)
    result["backed_up"] = [backed_up] if backed_up else []
    return result


def build_ai_prompt_settings_view(*, target_dir: Path) -> dict:
    """Read ai_system_prompts_config.yaml as structured prompt scenes."""
    filename = "ai_system_prompts_config.yaml"
    path = target_dir / filename
    if not path.exists():
        return {"prompts": [], "exists": False}
    parsed = _parse_advanced_config_content("ai_system_prompts_config", path.read_text(encoding="utf-8"))
    cfg = _require_mapping_config(parsed, filename)
    _validate_ai_system_prompts_payload(cfg)
    prompts = cfg.get("ai_prompts") if isinstance(cfg.get("ai_prompts"), dict) else {}
    items = []
    for name, entry in prompts.items():
        entry_map = entry if isinstance(entry, dict) else {}
        items.append({
            "name": str(name),
            "scene": str(entry_map.get("scene") or ""),
            "system": str(entry_map.get("system") or ""),
            "examples": str(entry_map.get("examples") or ""),
        })
    return {"prompts": items, "exists": True}


def save_ai_prompt_settings(
    *,
    prompts: list[object],
    target_dir: Path,
    actor: str,
    audit_root: Path | None = None,
    backup_root: Path | None = None,
    backup_scope: str = "global",
) -> dict:
    """Save structured AI prompt settings while preserving unknown YAML keys."""
    audit_root = audit_root or target_dir
    backup_root = backup_root or target_dir
    filename = "ai_system_prompts_config.yaml"
    target_path = target_dir / filename
    if not isinstance(prompts, list):
        raise AdvancedConfigError("prompts 必须是列表")

    if target_path.exists():
        parsed = _parse_advanced_config_content("ai_system_prompts_config", target_path.read_text(encoding="utf-8"))
        payload = dict(_require_mapping_config(parsed, filename))
    else:
        payload = {}

    prompt_map: dict[str, dict[str, str]] = {}
    for item in prompts:
        if not isinstance(item, dict):
            raise AdvancedConfigError("prompts 中的每一项必须是对象")
        name = str(item.get("name") or "").strip()
        if not name:
            raise AdvancedConfigError("Prompt 场景名称不能为空")
        prompt_map[name] = {
            "scene": str(item.get("scene") or "").strip(),
            "system": str(item.get("system") or ""),
            "examples": str(item.get("examples") or ""),
        }
    payload["ai_prompts"] = prompt_map

    try:
        _validate_ai_system_prompts_payload(payload)
    except AdvancedConfigError:
        append_config_audit_record(
            audit_root=audit_root,
            actor=actor,
            target_dir=target_dir,
            files=[filename],
            changed_fields=["ai_prompts"],
            result="validation_failed",
        )
        raise

    backed_up = backup_single_config_file(
        source=target_path,
        backup_root=backup_root,
        scope=backup_scope,
    )
    import yaml

    text = yaml.dump(payload, allow_unicode=True, default_flow_style=False, sort_keys=False)
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
        changed_fields=["ai_prompts"],
        result="success",
    )
    result = build_ai_prompt_settings_view(target_dir=target_dir)
    result["backed_up"] = [backed_up] if backed_up else []
    return result


def _default_domain_context_payload() -> dict:
    return {
        "system_boundary": "",
        "internal_data_groups": [],
        "external_data_groups": [],
        "external_services": [],
    }


def _domain_context_items(items: object, *, require_source: bool = False) -> list[dict]:
    if not isinstance(items, list):
        raise AdvancedConfigError("领域上下文数据组必须是列表")
    normalized: list[dict] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AdvancedConfigError(f"领域上下文第 {index + 1} 项必须是对象")
        name = str(item.get("name") or "").strip()
        if not name:
            raise AdvancedConfigError(f"领域上下文第 {index + 1} 项名称不能为空")
        normalized_item: dict[str, object] = {"name": name}
        if require_source:
            source = str(item.get("source") or "").strip()
            if not source:
                raise AdvancedConfigError(f"领域上下文第 {index + 1} 项来源不能为空")
            normalized_item["source"] = source
        aliases = item.get("aliases", [])
        if aliases in (None, ""):
            aliases = []
        if not isinstance(aliases, list):
            raise AdvancedConfigError(f"领域上下文第 {index + 1} 项 aliases 必须是列表")
        clean_aliases = [str(alias).strip() for alias in aliases if str(alias).strip()]
        if clean_aliases:
            normalized_item["aliases"] = clean_aliases
        description = str(item.get("description") or "")
        if description:
            normalized_item["description"] = description
        normalized.append(normalized_item)
    return normalized


def _normalize_domain_context_payload(payload: object) -> dict:
    cfg = _require_mapping_config(payload, "domain_context.json")
    normalized = {
        "system_boundary": str(cfg.get("system_boundary") or ""),
        "internal_data_groups": _domain_context_items(cfg.get("internal_data_groups", [])),
        "external_data_groups": _domain_context_items(cfg.get("external_data_groups", []), require_source=True),
        "external_services": _domain_context_items(cfg.get("external_services", [])),
    }
    try:
        from ai_gen_reimbursement_docs.config_utils import validate_fpa_domain_context

        validate_fpa_domain_context(normalized)
    except Exception as exc:
        raise AdvancedConfigError(str(exc)) from exc
    return normalized


def build_domain_context_view(*, target_dir: Path) -> dict:
    """Read domain_context.json as a structured Web UI form view."""
    filename = "domain_context.json"
    path = target_dir / filename
    if path.exists():
        parsed = _parse_advanced_config_content("domain_context", path.read_text(encoding="utf-8"))
        payload = _normalize_domain_context_payload(parsed)
        exists = True
    else:
        payload = _default_domain_context_payload()
        exists = False
    payload["exists"] = exists
    return payload


def save_domain_context_settings(
    *,
    payload: object,
    target_dir: Path,
    actor: str,
    audit_root: Path | None = None,
    backup_root: Path | None = None,
    backup_scope: str = "global",
) -> dict:
    """Validate and save domain_context.json from the structured Web UI form."""
    filename = "domain_context.json"
    target_dir.mkdir(parents=True, exist_ok=True)
    audit_root = audit_root or target_dir
    backup_root = backup_root or target_dir
    target_path = target_dir / filename

    if target_path.exists():
        parsed = _parse_advanced_config_content("domain_context", target_path.read_text(encoding="utf-8"))
        saved_payload = dict(_require_mapping_config(parsed, filename))
    else:
        saved_payload = {}

    try:
        normalized = _normalize_domain_context_payload(payload)
        saved_payload.update(normalized)
        from ai_gen_reimbursement_docs.config_utils import validate_fpa_domain_context

        validate_fpa_domain_context(saved_payload)
    except AdvancedConfigError:
        append_config_audit_record(
            audit_root=audit_root,
            actor=actor,
            target_dir=target_dir,
            files=[filename],
            changed_fields=["domain_context"],
            result="validation_failed",
        )
        raise
    except Exception as exc:
        append_config_audit_record(
            audit_root=audit_root,
            actor=actor,
            target_dir=target_dir,
            files=[filename],
            changed_fields=["domain_context"],
            result="validation_failed",
        )
        raise AdvancedConfigError(str(exc)) from exc

    backed_up = backup_single_config_file(
        source=target_path,
        backup_root=backup_root,
        scope=backup_scope,
    )
    _atomic_write_text(target_path, json.dumps(saved_payload, ensure_ascii=False, indent=2) + "\n")
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
        changed_fields=["domain_context"],
        result="success",
    )
    result = build_domain_context_view(target_dir=target_dir)
    result["backed_up"] = [backed_up] if backed_up else []
    return result


def _resolve_backup_path(*, backup_root: Path, scope: str, backup_id: str) -> tuple[Path, str]:
    if "/" in backup_id or "\\" in backup_id or ".." in backup_id:
        raise ValueError("备份 ID 无效")
    config_file = _config_file_from_backup_id(backup_id)
    if not config_file:
        raise ValueError("备份 ID 无效")

    backup_dir = _backup_scope_dir(backup_root, scope)
    candidate = (backup_dir / backup_id).resolve()
    backup_dir_resolved = backup_dir.resolve()
    if candidate.parent != backup_dir_resolved:
        raise ValueError("备份 ID 无效")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError("备份不存在")
    return candidate, config_file


def _read_diff_text(path: Path, config_file: str) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if config_file == ".env":
        return _mask_env_text(text)
    return text


def build_config_backup_diff(
    *,
    target_dir: Path,
    backup_root: Path,
    scope: str,
    backup_id: str,
) -> dict:
    """Build a redacted unified diff between a backup and the current config file."""
    backup_path, config_file = _resolve_backup_path(
        backup_root=backup_root,
        scope=scope,
        backup_id=backup_id,
    )
    target_path = target_dir / config_file
    backup_text = _read_diff_text(backup_path, config_file)
    current_text = _read_diff_text(target_path, config_file)
    diff_lines = list(difflib.unified_diff(
        backup_text.splitlines(),
        current_text.splitlines(),
        fromfile=f"backup/{config_file}",
        tofile=f"current/{config_file}",
        lineterm="",
    ))
    return {
        "id": backup_id,
        "file": config_file,
        "current_exists": target_path.exists(),
        "backup_created_at": datetime.fromtimestamp(backup_path.stat().st_mtime).isoformat(),
        "diff": "\n".join(diff_lines),
        "has_changes": bool(diff_lines),
    }


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

    backup_single_config_file(
        source=target_dir / config_file,
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

    if "_system" in data:
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


def _linked_run_defaults_from_output_template_profile(system: dict, profile_name: str) -> dict[str, str]:
    profiles = system.get("output_template_profiles")
    if not isinstance(profiles, dict):
        return {}
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        return {}
    linked: dict[str, str] = {}
    for key in OUTPUT_TEMPLATE_PROFILE_RUN_DEFAULT_KEYS:
        value = str(profile.get(key) or "").strip()
        if value:
            linked[key] = value
    return linked


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
    active_output_template_profile = _editable_value(payload, "templates", "active_output_template_profile")
    if active_output_template_profile is not None:
        active_profile = str(active_output_template_profile).strip()
        if active_profile:
            system["active_output_template_profile"] = active_profile
            for key, value in _linked_run_defaults_from_output_template_profile(system, active_profile).items():
                system[key] = value
                changed_fields.append(f"run_defaults.{key}")
        else:
            system.pop("active_output_template_profile", None)
        changed_fields.append("templates.active_output_template_profile")

    run_defaults = payload.get("run_defaults") if isinstance(payload.get("run_defaults"), dict) else {}
    for key in (
        "project_name",
        "fpa_profile",
        "fpa_strategy",
        "fpa_rule_set",
        "fpa_core_rules",
        "fpa_system_prompt",
        "fpa_user_prompt",
        "fpa_base_profile",
        "fpa_confirmation_mode",
    ):
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
