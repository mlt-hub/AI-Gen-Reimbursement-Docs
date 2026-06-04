"""Configuration utilities for loading API keys and settings."""

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Formatter, Template

DEFAULT_CFP_FORMULA = (
    'IF(OR(L{row}="新增",L{row}="修改"),1,'
    'IF(L{row}="复用",1/3,0))'
)

DEFAULT_CONFIG_TEMPLATE_FILES = (
    (".env.example", ".env"),
    ("system_config.yaml.example", "system_config.yaml"),
    ("fpa_config.yaml.example", "fpa_config.yaml"),
    ("fpa_judgement_rules.yaml.example", "fpa_judgement_rules.yaml"),
    ("domain_context.json.example", "domain_context.json"),
)

DEFAULT_SHEET_NAMES = {
    "work_order_meta": "1、工单需求-元数据录入",
    "func_list": "2、功能清单-内容录入",
    "fpa_meta": "3、FPA工作量评估-元数据录入",
    "spec_meta": "4、项目需求说明书-元数据录入",
    "cosmic_meta": "5、项目功能点拆分表-元数据录入",
    "list_meta": "6、项目需求清单-元数据录入",
    "stats_meta": "9、测试元数据自动统计",
}


def config_dir() -> Path:
    """Path to user config directory: ~/.ai-gen-reimbursement-docs/."""
    return Path.home() / ".ai-gen-reimbursement-docs"


def copy_default_config_files(
    target_dir: Path,
    source_dir: Path | None = None,
) -> list[Path]:
    """Copy default user config templates into target_dir without overwriting."""
    source_dir = source_dir or Path(__file__).parent.parent / "config"
    target_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for example_name, target_name in DEFAULT_CONFIG_TEMPLATE_FILES:
        src = source_dir / example_name
        dst = target_dir / target_name
        if not src.exists() or dst.exists():
            continue
        shutil.copy2(src, dst)
        created.append(dst)
    return created


def _read_env_value(key: str, env_path: Path) -> str:
    """Read a specific key from a .env file."""
    if not env_path.exists():
        return ""
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and "your_" not in val:
                    return val
    return ""


def _read_json_value(key: str, config_path: Path) -> str:
    """Read a specific key from a config.json file."""
    if not config_path.exists():
        return ""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        return config.get(key, "")


def _from_env(key: str, alt_path: Path, default: str = "") -> str:
    """Read key from env var first, then alt_path. Returns '' if not found."""
    val = os.environ.get(key, "")
    if val:
        return val
    return _read_env_value(key, alt_path)


def _from_env_override(key: str, alt_path: Path, default: str = "") -> str:
    """Read key from alt_path first (overriding env var), then env var."""
    val = _read_env_value(key, alt_path)
    if val:
        return val
    return os.environ.get(key, "")


@dataclass(frozen=True)
class ApiKeyResolution:
    """Resolved API Key plus non-sensitive observability metadata."""

    value: str
    source: str
    fingerprint: str

    @property
    def configured(self) -> bool:
        return bool(self.value)

    def log_summary(self) -> str:
        if not self.configured:
            return "missing, source=missing"
        return f"configured, source={self.source}, fingerprint={self.fingerprint}"


@dataclass(frozen=True)
class PromptConfig:
    """Prompt text plus user-safe source metadata."""

    text: str
    source_label: str


class FpaPromptConfigError(ValueError):
    """Raised when required FPA prompt configuration is missing or invalid."""


class FpaConfigError(ValueError):
    """Raised when required FPA configuration is missing or invalid."""


def api_key_fingerprint(api_key: str, length: int = 12) -> str:
    """Return a short irreversible fingerprint for log correlation."""
    key = api_key.strip()
    if not key:
        return ""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:length]}"


def resolve_api_key(
    provided: str | None = "",
    *,
    provided_source: str = "explicit_argument",
    override: bool = True,
) -> ApiKeyResolution:
    """Resolve ANTHROPIC_API_KEY and keep track of where it came from.

    override=True: provided > config/.env > system env var > config.json
    override=False: provided > system env var > config/.env > config.json
    """
    key = provided.strip() if isinstance(provided, str) else ""
    if key:
        return ApiKeyResolution(
            value=key,
            source=provided_source,
            fingerprint=api_key_fingerprint(key),
        )

    env_path = config_dir() / ".env"
    config_path = Path(__file__).parent / "config.json"
    candidates = (
        (
            ("user_env_file", _read_env_value("ANTHROPIC_API_KEY", env_path)),
            ("system_env", os.environ.get("ANTHROPIC_API_KEY", "")),
        )
        if override
        else (
            ("system_env", os.environ.get("ANTHROPIC_API_KEY", "")),
            ("user_env_file", _read_env_value("ANTHROPIC_API_KEY", env_path)),
        )
    )
    for source, candidate in candidates:
        key = candidate.strip()
        if key:
            return ApiKeyResolution(
                value=key,
                source=source,
                fingerprint=api_key_fingerprint(key),
            )

    json_value = _read_json_value("anthropic_api_key", config_path)
    key = json_value.strip() if isinstance(json_value, str) else ""
    if key:
        return ApiKeyResolution(
            value=key,
            source="config_json",
            fingerprint=api_key_fingerprint(key),
        )

    return ApiKeyResolution(value="", source="missing", fingerprint="")


def log_api_key_resolution(
    logger: logging.Logger,
    resolution: ApiKeyResolution,
    *,
    context: str,
    level: int = logging.INFO,
) -> None:
    """Log API Key source metadata without exposing original key fragments."""
    logger.log(level, "API Key [%s]: %s", context, resolution.log_summary())


def load_api_key(override: bool = True) -> str:
    """Load ANTHROPIC_API_KEY.

    override=True: config/.env > system env var > config.json
    override=False: system env var > config/.env > config.json
    """
    return resolve_api_key(override=override).value


def load_base_url(override: bool = True) -> str:
    """Load ANTHROPIC_BASE_URL.

    override=True: config/.env > system env var > config.json
    override=False: system env var > config/.env > config.json
    """
    env_path = config_dir() / ".env"
    loader = _from_env_override if override else _from_env
    url = loader("ANTHROPIC_BASE_URL", env_path)
    if url:
        return url

    config_path = Path(__file__).parent / "config.json"
    url = _read_json_value("anthropic_base_url", config_path)
    if url:
        return url
    return ""


def load_model_name(default: str = "", override: bool = True) -> str:
    """Load ANTHROPIC_MODEL。

    override=True: config/.env > system env var > config.json
    override=False: system env var > config/.env > config.json
    未配置时返回空字符串，由调用方决定是否提醒用户。
    """
    env_path = config_dir() / ".env"
    loader = _from_env_override if override else _from_env
    model = loader("ANTHROPIC_MODEL", env_path)
    if model:
        return clean_model_name(model)

    config_path = Path(__file__).parent / "config.json"
    model = _read_json_value("anthropic_model", config_path)
    if model:
        return clean_model_name(model)

    if not default:
        _log = logging.getLogger('ai_gen_reimbursement_docs.config_utils')
        _log.warning("未配置 ANTHROPIC_MODEL，请在 ~/.ai-gen-reimbursement-docs/.env 中设置")
    return default


def clean_model_name(name: str) -> str:
    """返回模型名（去除首尾空白）。"""
    return name.strip()


def _get_system_config_value(key: str, default):
    """从 system_config.yaml 中读取指定 key 的值（带缓存）。

    Args:
        key: 配置键名
        default: 默认值（同时确定返回类型）

    Returns:
        配置值，未找到或读取失败返回 default
    """
    yaml_path = config_dir() / "system_config.yaml"
    if not yaml_path.exists():
        return default
    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
        val = cfg.get(key)
        if val is None:
            return default
        return type(default)(val) if not isinstance(val, type(default)) else val
    except Exception:
        return default


def load_web_port(default: int = 3000) -> int:
    """读取 system_config.yaml 中的 web_port，默认 3000。"""
    return _get_system_config_value('web_port', default)


def load_web_work_mode(default: str = "auto") -> str:
    """读取 system_config.yaml 中的 web_work_mode。
    auto=IP 自动判断, local=强制本机模式, remote=强制远程服务模式。
    """
    val = _get_system_config_value('web_work_mode', default).lower()
    return val if val in ('auto', 'local', 'remote') else default


def load_log_level(default: str = "INFO") -> str:
    """读取 system_config.yaml 中的 log_level。
    返回 Python logging 级别名：DEBUG / INFO / WARNING / ERROR。
    """
    return _get_system_config_value('log_level', default).upper()


def load_llm_timeout(default: int = 120) -> int:
    """读取 LLM API 单次调用超时时间（秒）。"""
    return _get_system_config_value('llm_api_timeout_seconds', default)


def load_max_tokens(default: int = 2000) -> int:
    """Load max_tokens from system_config.yaml, supporting K/M units.
    CLI --max-tokens 通过环境变量 AI_REIMBURSEMENT_MAX_TOKENS 覆盖。

    Examples: 2000, 384K, 1M
    """
    import os as _os
    _env = _os.environ.get('AI_REIMBURSEMENT_MAX_TOKENS', '').strip()
    if _env:
        try:
            _env = _env.upper()
            if _env.endswith("M"):
                return int(float(_env[:-1]) * 1_000_000)
            elif _env.endswith("K"):
                return int(float(_env[:-1]) * 1_000)
            else:
                return int(_env)
        except Exception:
            pass
    yaml_path = config_dir() / "system_config.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
            val = cfg.get('max_tokens', '')
            if val:
                val = str(val).strip().upper()
                if val.endswith("M"):
                    return int(float(val[:-1]) * 1_000_000)
                elif val.endswith("K"):
                    return int(float(val[:-1]) * 1_000)
                else:
                    return int(val)
        except Exception as e:
            logger = logging.getLogger('ai_gen_reimbursement_docs.config_utils')
            logger.warning(f"system_config.yaml 读取失败: {e}，使用默认值 {default}")
    return default


def load_flow_max_ai(flow_name: str) -> int:
    """读取流程对应的 AI 限制数。优先走专有参数，fallback 到 l3_modules_ai__limit。

    Args:
        flow_name: 'gen_fpa', 'gen_spec', 'gen_cosmic'
    """
    key = f"{flow_name}_l3_modules_ai__limit"
    yaml_path = config_dir() / "system_config.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
            # 专有参数 > 通用参数 > 0
            val = cfg.get(key, 0)
            if val and int(val) > 0:
                return int(val)
            common = cfg.get('l3_modules_ai__limit', 0)
            if common and int(common) > 0:
                return int(common)
        except Exception:
            pass
    return 0


def load_cosmic_warn_marker() -> bool:
    """读取 cosmic_warn_marker，true 时在拆分表中标记数据异常警告。"""
    return _get_system_config_value('cosmic_warn_marker', True)


def load_cosmic_warn_log() -> bool:
    """读取 cosmic_warn_log，true 时在日志中输出数据异常警告。"""
    return _get_system_config_value('cosmic_warn_log', True)


def load_fpa_reduced_use_workload() -> bool:
    """读取 fpa_reduced_use_workload，true 时直接用 FPA 工作量值。"""
    return _get_system_config_value('fpa_reduced_use_workload', False)


def load_fpa_excel_recalc_check() -> bool:
    """读取 fpa_excel_recalc_check，true 时尝试复算 FPA Excel 公式并仅输出 warning。"""
    return _get_system_config_value('fpa_excel_recalc_check', False)


FPA_CONFIG_FILENAME = "fpa_config.yaml"
FPA_DOMAIN_CONTEXT_FILENAME = "domain_context.json"
FPA_JUDGEMENT_RULES_FILENAME = "fpa_judgement_rules.yaml"
VALID_FPA_PROFILE_KINDS = {"strict_fpa", "unified_ui", "ui_api_mapping"}
VALID_FPA_STRATEGIES = {"rules_first", "ai_first", "rules_only", "ai_only"}
VALID_FPA_JUDGEMENT_RULES_SOURCES = {"config", "template"}
VALID_FPA_TYPES = {"EI", "EQ", "EO", "ILF", "EIF"}
VALID_FPA_TRANSACTION_TYPES = {"EI", "EQ", "EO"}
VALID_FPA_RULE_MERGE_MODES = {"append", "replace"}
FPA_USER_PROMPT_PLACEHOLDERS = frozenset({"core_rules", "judgement_rules", "payload_json"})


def _validate_domain_context_string_list(value: object, key_path: str) -> None:
    if not isinstance(value, list):
        raise FpaConfigError(
            f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 中的 {key_path} 必须是字符串列表"
        )
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise FpaConfigError(
                f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 中的 {key_path}[{index}] 必须是非空字符串"
            )


def _validate_domain_context_items(value: object, key_path: str, *, require_source: bool = False) -> None:
    if not isinstance(value, list):
        raise FpaConfigError(
            f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 中的 {key_path} 必须是列表"
        )
    for index, item in enumerate(value):
        item_path = f"{key_path}[{index}]"
        if not isinstance(item, dict):
            raise FpaConfigError(
                f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 中的 {item_path} 必须是对象"
            )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise FpaConfigError(
                f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 中的 {item_path}.name 必须是非空字符串"
            )
        if require_source:
            source = item.get("source")
            if not isinstance(source, str) or not source.strip():
                raise FpaConfigError(
                    f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 中的 {item_path}.source 必须是非空字符串"
                )
        if "aliases" in item:
            _validate_domain_context_string_list(item.get("aliases"), f"{item_path}.aliases")
        if "description" in item and not isinstance(item.get("description"), str):
            raise FpaConfigError(
                f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 中的 {item_path}.description 必须是字符串"
            )


def validate_fpa_domain_context(context: dict[str, object]) -> None:
    """Validate project-level FPA domain boundary context."""
    if not isinstance(context, dict):
        raise FpaConfigError(f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 必须是对象")
    system_boundary = context.get("system_boundary")
    if not isinstance(system_boundary, str):
        raise FpaConfigError(
            f"FPA 领域上下文无效：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME} 中的 system_boundary 必须是字符串"
        )
    _validate_domain_context_items(context.get("internal_data_groups"), "internal_data_groups")
    _validate_domain_context_items(context.get("external_data_groups"), "external_data_groups", require_source=True)
    _validate_domain_context_items(context.get("external_services"), "external_services")


def load_fpa_domain_context() -> dict[str, object]:
    """Strictly read project-level FPA domain boundary context."""
    json_path = config_dir() / FPA_DOMAIN_CONTEXT_FILENAME
    if not json_path.exists():
        raise FpaConfigError(f"未找到 FPA 领域上下文文件：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME}")
    try:
        context = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FpaConfigError(f"读取 FPA 领域上下文失败：配置目录/{FPA_DOMAIN_CONTEXT_FILENAME}") from exc
    validate_fpa_domain_context(context)
    return context


def load_optional_fpa_domain_context() -> dict[str, object]:
    """Read project-level FPA domain context when configured."""
    if not (config_dir() / FPA_DOMAIN_CONTEXT_FILENAME).exists():
        return {}
    return load_fpa_domain_context()


def _fpa_key_path(*parts: object) -> str:
    return ".".join(str(part) for part in parts if str(part))


def _require_mapping(value: object, key_path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 必须是对象")
    return value


def _require_non_empty_string(value: object, key_path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 必须是非空字符串")
    return value.strip()


def _validate_rule_section(value: object, key_path: str) -> list[object] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 必须是对象")
    merge = str(value.get("merge") or "append").strip()
    if merge not in VALID_FPA_RULE_MERGE_MODES:
        raise FpaConfigError(
            f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}.merge 必须是 append 或 replace"
        )
    items = value.get("items")
    if not isinstance(items, list):
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}.items 必须是列表")
    return items


def _validate_external_data_rules(value: object, key_path: str) -> None:
    items = _validate_rule_section(value, key_path)
    if items is None:
        return
    for index, item in enumerate(items):
        item_path = f"{key_path}.items[{index}]"
        if not isinstance(item, dict):
            raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path} 必须是对象")
        aliases = item.get("source_aliases")
        if not isinstance(aliases, list) or not [str(alias).strip() for alias in aliases if str(alias).strip()]:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path}.source_aliases 必须是非空字符串列表"
            )
        for alias_index, alias in enumerate(aliases):
            if not isinstance(alias, str) or not alias.strip():
                raise FpaConfigError(
                    f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path}.source_aliases[{alias_index}] 必须是非空字符串"
                )
        _require_non_empty_string(item.get("data_name"), f"{item_path}.data_name")
        data_nouns = item.get("data_nouns", [])
        if data_nouns is None:
            data_nouns = []
        if not isinstance(data_nouns, list):
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path}.data_nouns 必须是字符串列表"
            )
        for noun_index, noun in enumerate(data_nouns):
            if not isinstance(noun, str) or not noun.strip():
                raise FpaConfigError(
                    f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path}.data_nouns[{noun_index}] 必须是非空字符串"
                )


def _validate_non_empty_string_list(value: object, key_path: str) -> None:
    if not isinstance(value, list) or not value:
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 必须是非空字符串列表")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}[{index}] 必须是非空字符串"
            )


def _validate_keyword_rules(value: object, key_path: str) -> None:
    items = _validate_rule_section(value, key_path)
    if items is None:
        return
    for index, item in enumerate(items):
        item_path = f"{key_path}.items[{index}]"
        if not isinstance(item, dict):
            raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path} 必须是对象")
        fpa_type = _require_non_empty_string(item.get("type"), f"{item_path}.type").upper()
        if fpa_type not in VALID_FPA_TRANSACTION_TYPES:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path}.type 必须是 EI / EQ / EO"
            )
        _validate_non_empty_string_list(item.get("keywords"), f"{item_path}.keywords")
        if "reason" in item:
            _require_non_empty_string(item.get("reason"), f"{item_path}.reason")


def _validate_type_mapping_rules(value: object, key_path: str) -> None:
    items = _validate_rule_section(value, key_path)
    if items is None:
        return
    for index, item in enumerate(items):
        item_path = f"{key_path}.items[{index}]"
        if not isinstance(item, dict):
            raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path} 必须是对象")
        fpa_type = _require_non_empty_string(item.get("type"), f"{item_path}.type").upper()
        if fpa_type not in VALID_FPA_TYPES:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path}.type 必须是 EI / EQ / EO / ILF / EIF"
            )
        _validate_non_empty_string_list(item.get("keywords"), f"{item_path}.keywords")
        if "reason" in item:
            _require_non_empty_string(item.get("reason"), f"{item_path}.reason")


def _validate_ai_type_conflict_rules(value: object, key_path: str) -> None:
    items = _validate_rule_section(value, key_path)
    if items is None:
        return
    for index, item in enumerate(items):
        item_path = f"{key_path}.items[{index}]"
        if not isinstance(item, dict):
            raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path} 必须是对象")
        for type_key in ("expected_type", "ai_type"):
            fpa_type = _require_non_empty_string(item.get(type_key), f"{item_path}.{type_key}").upper()
            if fpa_type not in VALID_FPA_TYPES:
                raise FpaConfigError(
                    f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path}.{type_key} 必须是 EI / EQ / EO / ILF / EIF"
                )
        _validate_non_empty_string_list(item.get("keywords"), f"{item_path}.keywords")
        if "conflict" in item and not isinstance(item.get("conflict"), bool):
            raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path}.conflict 必须是布尔值")
        if "reason" in item:
            _require_non_empty_string(item.get("reason"), f"{item_path}.reason")


def _validate_internal_data_rules(value: object, key_path: str) -> None:
    items = _validate_rule_section(value, key_path)
    if items is None:
        return
    for index, item in enumerate(items):
        item_path = f"{key_path}.items[{index}]"
        if not isinstance(item, dict):
            raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {item_path} 必须是对象")
        _validate_non_empty_string_list(item.get("keywords"), f"{item_path}.keywords")
        _require_non_empty_string(item.get("data_name"), f"{item_path}.data_name")
        if "reason" in item:
            _require_non_empty_string(item.get("reason"), f"{item_path}.reason")


def _validate_coverage_rules(value: object, key_path: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 必须是对象")
    for key in ("require_process_coverage", "require_data_function"):
        if key in value and not isinstance(value.get(key), bool):
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}.{key} 必须是布尔值"
            )


def _validate_row_planning_bool(value: dict[str, object], key: str, key_path: str) -> None:
    if key in value and not isinstance(value.get(key), bool):
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}.{key} 必须是布尔值")


def _validate_format_template(
    value: object,
    key_path: str,
    allowed_fields: set[str],
    required_fields: set[str],
) -> None:
    template_text = _require_non_empty_string(value, key_path)
    fields: set[str] = set()
    try:
        parsed = Formatter().parse(template_text)
        for _, field_name, _, _ in parsed:
            if not field_name:
                continue
            fields.add(field_name.split(".", 1)[0].split("[", 1)[0])
    except ValueError as exc:
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 格式化模板非法") from exc
    unknown = sorted(fields - allowed_fields)
    if unknown:
        raise FpaConfigError(
            f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 包含未知占位符: "
            f"{', '.join('{' + name + '}' for name in unknown)}"
        )
    missing = sorted(required_fields - fields)
    if missing:
        raise FpaConfigError(
            f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 必须包含占位符: "
            f"{', '.join('{' + name + '}' for name in missing)}"
        )


def _validate_row_planning_rules(value: object, key_path: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 必须是对象")

    ui_row = value.get("ui_row")
    if ui_row is not None:
        if not isinstance(ui_row, dict):
            raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}.ui_row 必须是对象")
        ui_path = f"{key_path}.ui_row"
        _validate_row_planning_bool(ui_row, "enabled", ui_path)
        if ui_row.get("enabled") is not False:
            for required_key in ("scope", "merge", "name_suffix", "type", "reason", "empty_process_text", "explanation_template"):
                if required_key not in ui_row:
                    raise FpaConfigError(
                        f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {ui_path}.{required_key} 为必填项"
                    )
        if "scope" in ui_row:
            scope = _require_non_empty_string(ui_row.get("scope"), f"{ui_path}.scope")
            if scope != "l3":
                raise FpaConfigError(f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {ui_path}.scope 必须是 l3")
        if "merge" in ui_row:
            merge = _require_non_empty_string(ui_row.get("merge"), f"{ui_path}.merge")
            if merge != "single_row":
                raise FpaConfigError(
                    f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {ui_path}.merge 必须是 single_row"
                )
        if "name_suffix" in ui_row:
            _require_non_empty_string(ui_row.get("name_suffix"), f"{ui_path}.name_suffix")
        if "type" in ui_row:
            fpa_type = _require_non_empty_string(ui_row.get("type"), f"{ui_path}.type").upper()
            if fpa_type not in VALID_FPA_TYPES:
                raise FpaConfigError(
                    f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {ui_path}.type 必须是 EI / EQ / EO / ILF / EIF"
                )
        if "reason" in ui_row:
            _require_non_empty_string(ui_row.get("reason"), f"{ui_path}.reason")
        if "empty_process_text" in ui_row:
            _require_non_empty_string(ui_row.get("empty_process_text"), f"{ui_path}.empty_process_text")
        if "explanation_template" in ui_row:
            _validate_format_template(
                ui_row.get("explanation_template"),
                f"{ui_path}.explanation_template",
                {"name", "items"},
                {"name", "items"},
            )

    process_rows = value.get("process_rows")
    if process_rows is not None:
        if not isinstance(process_rows, dict):
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}.process_rows 必须是对象"
            )
        process_path = f"{key_path}.process_rows"
        _validate_row_planning_bool(process_rows, "enabled", process_path)
        _validate_row_planning_bool(process_rows, "one_row_per_process", process_path)
        if process_rows.get("enabled") is not False:
            for required_key in ("one_row_per_process", "default_name_suffix", "type_suffixes", "explanation_template"):
                if required_key not in process_rows:
                    raise FpaConfigError(
                        f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {process_path}.{required_key} 为必填项"
                    )
            if process_rows.get("one_row_per_process") is not True:
                raise FpaConfigError(
                    f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {process_path}.one_row_per_process 第一版必须为 true"
                )
        if "default_name_suffix" in process_rows:
            _require_non_empty_string(process_rows.get("default_name_suffix"), f"{process_path}.default_name_suffix")
        type_suffixes = process_rows.get("type_suffixes")
        if type_suffixes is not None:
            if not isinstance(type_suffixes, dict):
                raise FpaConfigError(
                    f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {process_path}.type_suffixes 必须是对象"
                )
            for fpa_type, suffix in type_suffixes.items():
                type_key = str(fpa_type).strip().upper()
                if type_key not in VALID_FPA_TYPES:
                    raise FpaConfigError(
                        f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {process_path}.type_suffixes 包含非法类型: {fpa_type}"
                    )
                _require_non_empty_string(suffix, f"{process_path}.type_suffixes.{fpa_type}")
        if "explanation_template" in process_rows:
            _validate_format_template(
                process_rows.get("explanation_template"),
                f"{process_path}.explanation_template",
                {"name", "description"},
                {"name", "description"},
            )


def _validate_fpa_user_prompt_template(template_text: str, key_path: str) -> None:
    template = Template(template_text)
    if not template.is_valid():
        raise FpaConfigError(
            f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 包含非法占位符，"
            "请使用 ${core_rules} / ${judgement_rules} / ${payload_json}"
        )
    identifiers = set(template.get_identifiers())
    unknown = sorted(identifiers - FPA_USER_PROMPT_PLACEHOLDERS)
    if unknown:
        raise FpaConfigError(
            f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 包含未知占位符: "
            f"{', '.join('${' + name + '}' for name in unknown)}"
        )
    missing = sorted(FPA_USER_PROMPT_PLACEHOLDERS - identifiers)
    if missing:
        raise FpaConfigError(
            f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path} 必须包含占位符: "
            f"{', '.join('${' + name + '}' for name in missing)}"
        )


def validate_fpa_config(cfg: dict[str, object]) -> None:
    """Validate fpa_config.yaml structure and cross references."""
    if not isinstance(cfg, dict) or not cfg:
        raise FpaConfigError(f"FPA 配置为空：配置目录/{FPA_CONFIG_FILENAME}")

    judgement_rules_source = cfg.get("judgement_rules_source", "config")
    if not isinstance(judgement_rules_source, str) or judgement_rules_source.strip() not in VALID_FPA_JUDGEMENT_RULES_SOURCES:
        raise FpaConfigError(f"未知 FPA judgement_rules_source: {judgement_rules_source}")

    raw_default_profile = cfg.get("default-profile")
    if isinstance(raw_default_profile, str) and raw_default_profile.strip() == "custom_rules":
        raise FpaConfigError("custom_rules 已替换为 unified_ui，请更新 fpa_config.yaml")

    profiles = _require_mapping(cfg.get("profiles"), "profiles")
    if "custom_rules" in profiles:
        raise FpaConfigError("profiles.custom_rules 已废弃，请迁移到 profiles.unified_ui")
    core_rules = _require_mapping(cfg.get("core_rules"), "core_rules")
    system_prompt_sets = _require_mapping(cfg.get("system_prompt_sets"), "system_prompt_sets")
    user_prompt_sets = _require_mapping(cfg.get("user_prompt_sets"), "user_prompt_sets")
    rule_sets = _require_mapping(cfg.get("rule_sets"), "rule_sets")

    profile = _require_non_empty_string(cfg.get("default-profile"), "default-profile")
    if profile not in profiles:
        raise FpaConfigError(f"未找到 FPA profile 配置：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles.{profile}")

    for core_rule_name, core_rule_text in core_rules.items():
        core_rule_path = _fpa_key_path("core_rules", core_rule_name)
        _require_non_empty_string(core_rule_text, core_rule_path)

    for prompt_name, prompt_text in system_prompt_sets.items():
        prompt_path = _fpa_key_path("system_prompt_sets", prompt_name)
        _require_non_empty_string(prompt_text, prompt_path)

    for prompt_name, prompt_text in user_prompt_sets.items():
        prompt_path = _fpa_key_path("user_prompt_sets", prompt_name)
        user_template = _require_non_empty_string(prompt_text, prompt_path)
        _validate_fpa_user_prompt_template(user_template, prompt_path)

    for rule_set_name, rule_set in rule_sets.items():
        rule_set_path = _fpa_key_path("rule_sets", rule_set_name)
        rule_entry = _require_mapping(rule_set, rule_set_path)
        if "version" in rule_entry:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {rule_set_path}.version 已废弃，请删除该字段"
            )
        extends = str(rule_entry.get("extends") or "").strip()
        if extends and extends not in rule_sets:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {rule_set_path}.extends 指向不存在的 rule_set: {extends}"
            )
        _validate_external_data_rules(rule_entry.get("external_data_rules"), f"{rule_set_path}.external_data_rules")
        _validate_keyword_rules(rule_entry.get("keyword_rules"), f"{rule_set_path}.keyword_rules")
        _validate_type_mapping_rules(rule_entry.get("type_mapping_rules"), f"{rule_set_path}.type_mapping_rules")
        _validate_ai_type_conflict_rules(rule_entry.get("ai_type_conflict_rules"), f"{rule_set_path}.ai_type_conflict_rules")
        _validate_internal_data_rules(rule_entry.get("internal_data_rules"), f"{rule_set_path}.internal_data_rules")
        _validate_coverage_rules(rule_entry.get("coverage_rules"), f"{rule_set_path}.coverage_rules")
        _validate_row_planning_rules(rule_entry.get("row_planning_rules"), f"{rule_set_path}.row_planning_rules")

    visited: set[str] = set()
    visiting: list[str] = []

    def _visit_rule_set(name: str) -> None:
        if name in visiting:
            start = visiting.index(name)
            cycle_path = " -> ".join([*visiting[start:], name])
            raise FpaConfigError(f"FPA rule_set 继承出现循环: {cycle_path}")
        if name in visited:
            return
        visiting.append(name)
        entry = rule_sets.get(name)
        if isinstance(entry, dict):
            parent = str(entry.get("extends") or "").strip()
            if parent:
                _visit_rule_set(parent)
        visiting.pop()
        visited.add(name)

    for rule_set_name in rule_sets:
        _visit_rule_set(str(rule_set_name))

    for profile_name, profile_entry in profiles.items():
        profile_path = _fpa_key_path("profiles", profile_name)
        entry = _require_mapping(profile_entry, profile_path)
        unknown_fields = sorted(
            str(key)
            for key in entry
            if str(key) not in {"kind", "strategy", "rule_set", "core_rules", "system_prompt", "user_prompt"}
        )
        if unknown_fields:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {profile_path} 包含未知字段: "
                f"{', '.join(unknown_fields)}"
            )
        kind = _require_non_empty_string(entry.get("kind"), f"{profile_path}.kind")
        if kind not in VALID_FPA_PROFILE_KINDS:
            raise FpaConfigError(
                f"未知 FPA profile kind: {kind}，支持的 kind: {', '.join(sorted(VALID_FPA_PROFILE_KINDS))}"
            )
        strategy = _require_non_empty_string(entry.get("strategy"), f"{profile_path}.strategy")
        if strategy not in VALID_FPA_STRATEGIES:
            raise FpaConfigError(f"未知 FPA strategy: {strategy}")
        rule_set = _require_non_empty_string(entry.get("rule_set"), f"{profile_path}.rule_set")
        if rule_set not in rule_sets:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {profile_path}.rule_set 指向不存在的 rule_set: {rule_set}"
            )
        core_rule = _require_non_empty_string(entry.get("core_rules"), f"{profile_path}.core_rules")
        if core_rule not in core_rules:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {profile_path}.core_rules 指向不存在的 core_rules: {core_rule}"
            )
        system_prompt = _require_non_empty_string(entry.get("system_prompt"), f"{profile_path}.system_prompt")
        if system_prompt not in system_prompt_sets:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {profile_path}.system_prompt 指向不存在的 system_prompt_set: {system_prompt}"
            )
        user_prompt = _require_non_empty_string(entry.get("user_prompt"), f"{profile_path}.user_prompt")
        if user_prompt not in user_prompt_sets:
            raise FpaConfigError(
                f"FPA 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {profile_path}.user_prompt 指向不存在的 user_prompt_set: {user_prompt}"
            )


def load_fpa_config() -> dict[str, object]:
    """严格读取 FPA 专用配置。"""
    yaml_path = config_dir() / FPA_CONFIG_FILENAME
    if not yaml_path.exists():
        raise FpaConfigError(f"未找到 FPA 配置文件：配置目录/{FPA_CONFIG_FILENAME}")
    try:
        cfg = _load_yaml_file(yaml_path)
    except Exception as exc:
        raise FpaConfigError(f"读取 FPA 配置失败：配置目录/{FPA_CONFIG_FILENAME}") from exc
    if not cfg:
        raise FpaConfigError(f"FPA 配置为空：配置目录/{FPA_CONFIG_FILENAME}")
    validate_fpa_config(cfg)
    return cfg


def load_fpa_judgement_rules_source() -> str:
    """读取 FPA 计算依据归类判定原则来源。"""
    cfg = load_fpa_config()
    value = cfg.get("judgement_rules_source", "config")
    if not isinstance(value, str) or value.strip() not in VALID_FPA_JUDGEMENT_RULES_SOURCES:
        raise FpaConfigError(f"未知 FPA judgement_rules_source: {value}")
    return value.strip()


def load_fpa_judgement_rules_config() -> list[str]:
    """严格读取独立 FPA 计算依据归类判定原则配置。"""
    yaml_path = config_dir() / FPA_JUDGEMENT_RULES_FILENAME
    if not yaml_path.exists():
        raise FpaConfigError(f"未找到 FPA 判定原则配置文件：配置目录/{FPA_JUDGEMENT_RULES_FILENAME}")
    try:
        cfg = _load_yaml_file(yaml_path)
    except Exception as exc:
        raise FpaConfigError(f"读取 FPA 判定原则配置失败：配置目录/{FPA_JUDGEMENT_RULES_FILENAME}") from exc
    rules = cfg.get("judgement_rules") if isinstance(cfg, dict) else None
    if not isinstance(rules, list) or not rules:
        raise FpaConfigError(
            f"FPA 判定原则配置无效：配置目录/{FPA_JUDGEMENT_RULES_FILENAME} 中的 judgement_rules 必须是非空字符串列表"
        )
    normalized: list[str] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, str) or not rule.strip():
            raise FpaConfigError(
                f"FPA 判定原则配置无效：配置目录/{FPA_JUDGEMENT_RULES_FILENAME} 中的 judgement_rules[{index}] 必须是非空字符串"
            )
        normalized.append(rule.strip())
    return normalized


def load_fpa_profiles_config() -> dict[str, object]:
    cfg = load_fpa_config()
    profiles = cfg.get("profiles", {})
    if not isinstance(profiles, dict):
        raise FpaConfigError(f"FPA profiles 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles")
    return profiles


def load_fpa_profile_entry(profile_name: str) -> dict[str, object]:
    profile_key = str(profile_name or "").strip()
    profiles = load_fpa_profiles_config()
    entry = profiles.get(profile_key)
    if not isinstance(entry, dict):
        raise FpaConfigError(f"未找到 FPA profile 配置：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles.{profile_key}")
    return entry


def load_fpa_profile(default: str = "") -> str:
    """读取默认 FPA 规划口径名称。"""
    cfg = load_fpa_config()
    value = str(cfg.get("default-profile", default) or "").strip()
    load_fpa_profile_entry(value)
    return value


def load_fpa_profile_kind(profile_name: str) -> str:
    """读取指定 profile 绑定的行为 kind。"""
    profile_key = str(profile_name or "").strip()
    entry = load_fpa_profile_entry(profile_key)
    value = str(entry.get("kind", "") or "").strip()
    if not value:
        raise FpaConfigError(f"未找到 FPA kind 配置：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles.{profile_key}.kind")
    return value


def load_fpa_strategy(profile_name: str = "") -> str:
    """读取指定 profile 的默认 FPA 执行策略。"""
    profile_key = profile_name or load_fpa_profile()
    entry = load_fpa_profile_entry(profile_key)
    value = str(entry.get("strategy", "") or "").strip()
    if not value:
        raise FpaConfigError(f"未找到 FPA strategy 配置：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles.{profile_key}.strategy")
    return value


def load_fpa_rule_set(profile_name: str = "") -> str:
    """读取指定 profile 的默认 FPA 规则集名称。"""
    profile_key = profile_name or load_fpa_profile()
    entry = load_fpa_profile_entry(profile_key)
    value = str(entry.get("rule_set", "") or "").strip()
    if not value:
        raise FpaConfigError(f"未找到 FPA rule_set 配置：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles.{profile_key}.rule_set")
    return value


def load_fpa_core_rules_config(profile_name: str) -> PromptConfig:
    """严格读取当前 profile 的 FPA 核心口径文本。"""
    profile_key = str(profile_name or "").strip()
    entry = load_fpa_profile_entry(profile_key)
    core_rule_key = str(entry.get("core_rules", "") or "").strip()
    if not core_rule_key:
        raise FpaPromptConfigError(
            f"未找到 FPA 核心口径绑定：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles.{profile_key}.core_rules"
        )
    cfg = load_fpa_config()
    core_rule_sets = cfg.get("core_rules", {})
    if not isinstance(core_rule_sets, dict):
        raise FpaPromptConfigError(f"FPA core_rules 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 core_rules")
    key_path = f"core_rules.{core_rule_key}"
    value = core_rule_sets.get(core_rule_key, "")
    if not isinstance(value, str) or not value.strip():
        raise FpaPromptConfigError(f"未找到 FPA 核心口径配置：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}")
    return PromptConfig(text=value.strip(), source_label=_user_config_key_source_label(FPA_CONFIG_FILENAME, key_path))


def load_fpa_check_columns() -> dict[str, list[str]]:
    """读取 FPA 审核副本列配置。

    system_config.yaml 示例：
      fpa_check_columns:
        FPA结果: ["序号", "新增/修改功能点", "类型"]

    返回值只做基础类型规范化；未知 Sheet 或列名由写表侧按默认列过滤。
    """
    raw = _get_system_config_value('fpa_check_columns', {})
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[str]] = {}
    for sheet_name, columns in raw.items():
        name = str(sheet_name or "").strip()
        if not name:
            continue
        if isinstance(columns, str):
            columns = [columns]
        if not isinstance(columns, list):
            continue
        values = [str(column).strip() for column in columns if str(column).strip()]
        if values:
            result[name] = values
    return result


def load_fpa_rule_sets_config() -> dict[str, object]:
    """读取 fpa_config.yaml 中的 rule_sets。"""
    cfg = load_fpa_config()
    rule_sets = cfg.get("rule_sets", {})
    if not isinstance(rule_sets, dict):
        raise FpaConfigError(f"FPA rule_sets 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 rule_sets")
    return rule_sets

def load_cfp_formula(default: str = DEFAULT_CFP_FORMULA) -> str:
    """读取 CFP 计算公式，优先从 business_rules.yaml 获取。"""
    rules_path = config_dir() / "business_rules.yaml"
    if not rules_path.exists():
        return default
    try:
        import yaml
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f) or {}
        return str(rules.get('cfp_formula') or default)
    except Exception:
        return default


def load_out_templates() -> dict[str, str]:
    """读取 system_config.yaml 中 out_templates 配置。

    Returns:
        {'fpa_out_template': 'data/out_templates/...', ...}
        未配置时返回空 dict。
    """
    yaml_path = config_dir() / "system_config.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
            templates = cfg.get('out_templates', {})
            if isinstance(templates, dict):
                return {str(k): str(v) for k, v in templates.items() if v}
        except Exception:
            pass
    return {}


def load_l3_modules_ai__limit(default: int = 0) -> int:
    """读取 l3_modules_ai__limit，0=不限制。"""
    return _get_system_config_value('l3_modules_ai__limit', default)


def load_spec_remind_update_toc() -> bool:
    """读取 spec_remind_update_toc，true 时在 docx 文件名加提醒前缀。"""
    return _get_system_config_value('spec_remind_update_toc', True)


def load_spec_auto_update_toc() -> bool:
    """读取 spec_auto_update_toc，true 时用 Word COM 自动更新目录。"""
    return _get_system_config_value('spec_auto_update_toc', False)


def load_gen_fpa_ai_limit() -> int:
    """读取 gen_fpa_ai_limit，限制 FPA AI 处理的功能过程数（0=不限制）。"""
    return max(_get_system_config_value('gen_fpa_ai_limit', 0), 0)


def load_gen_cosmic_ai_limit() -> int:
    """读取 gen_cosmic_ai_limit，限制 COSMIC AI 处理的功能过程数（0=不限制）。"""
    return max(_get_system_config_value('gen_cosmic_ai_limit', 0), 0)


def load_gen_spec_ai_limit() -> int:
    """读取 gen_spec_ai_limit，限制 spec AI 完善的功能过程描述数（0=不限制）。"""
    return max(_get_system_config_value('gen_spec_ai_limit', 0), 0)


@lru_cache(maxsize=1)
def load_sheet_names() -> dict[str, str]:
    """读取功能清单-录入模板.xlsx 的 Sheet 名称映射。

    返回 key → Sheet 名的字典，未配置则返回内置模板默认值。
    """
    yaml_path = config_dir() / "system_config.yaml"
    if not yaml_path.exists():
        _log = logging.getLogger('ai_gen_reimbursement_docs.config_utils')
        _log.warning("未找到 system_config.yaml，Sheet 名称将使用内置默认值，请运行 --init-config 初始化")
        return DEFAULT_SHEET_NAMES.copy()
    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
        sheets = cfg.get('sheets', {})
        if not sheets:
            _log = logging.getLogger('ai_gen_reimbursement_docs.config_utils')
            _log.warning("system_config.yaml 中未配置 sheets 段，Sheet 名称将使用内置默认值")
            return DEFAULT_SHEET_NAMES.copy()
        return {**DEFAULT_SHEET_NAMES, **sheets}
    except Exception:
        _log = logging.getLogger('ai_gen_reimbursement_docs.config_utils')
        _log.warning("system_config.yaml 读取失败，Sheet 名称将使用内置默认值")
        return DEFAULT_SHEET_NAMES.copy()


def load_enable_ai_fill_meta() -> bool:
    """读取 enable_ai_fill_meta，控制是否对 #AI生成# 标记走 AI 填充。"""
    return _get_system_config_value('enable_ai_fill_meta', True)


def load_ai_system_prompt(name: str) -> str:
    """从 ai_system_prompts_config.yaml 读取指定场景的 system prompt。"""
    yaml_path = config_dir() / "ai_system_prompts_config.yaml"
    if not yaml_path.exists():
        return ""
    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        prompts = cfg.get("ai_prompts", {})
        return prompts.get(name, {}).get("system", "")
    except Exception:
        return ""


def load_ai_examples(name: str) -> str:
    """从 ai_system_prompts_config.yaml 读取指定场景的示例。"""
    yaml_path = config_dir() / "ai_system_prompts_config.yaml"
    if not yaml_path.exists():
        return ""
    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        val = cfg.get("ai_prompts", {}).get(name, {}).get("examples", "")
        if isinstance(val, str):
            return val
        return ""
    except Exception:
        return ""


def _user_config_source_label(filename: str) -> str:
    return f"用户配置（配置目录/{filename}）"


def _user_config_key_source_label(filename: str, key_path: str) -> str:
    return f"用户配置（配置目录/{filename}: {key_path}）"


def _load_yaml_file(yaml_path: Path) -> dict:
    import yaml

    with open(yaml_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    return cfg if isinstance(cfg, dict) else {}


def _load_fpa_prompt_text(prompt_key: str, prompt_type: str) -> PromptConfig:
    cfg = load_fpa_config()
    set_key = "system_prompt_sets" if prompt_type == "system" else "user_prompt_sets"
    prompt_sets = cfg.get(set_key, {})
    if not isinstance(prompt_sets, dict):
        raise FpaPromptConfigError(f"FPA {set_key} 配置无效：配置目录/{FPA_CONFIG_FILENAME} 中的 {set_key}")
    key_path = f"{set_key}.{prompt_key}"
    val = prompt_sets.get(prompt_key, "")
    if not isinstance(val, str) or not val.strip():
        label = "系统提示词" if prompt_type == "system" else "用户提示词"
        raise FpaPromptConfigError(f"未找到 FPA {label}配置：配置目录/{FPA_CONFIG_FILENAME} 中的 {key_path}")
    return PromptConfig(text=val, source_label=_user_config_key_source_label(FPA_CONFIG_FILENAME, key_path))


def load_fpa_system_prompt_config(profile_name: str) -> PromptConfig:
    """严格读取当前 profile 绑定的 FPA system prompt。"""
    entry = load_fpa_profile_entry(profile_name)
    prompt_key = str(entry.get("system_prompt", "") or "").strip()
    if not prompt_key:
        raise FpaPromptConfigError(
            f"未找到 FPA 系统提示词绑定：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles.{profile_name}.system_prompt"
        )
    return _load_fpa_prompt_text(prompt_key, "system")


def load_fpa_user_prompt_config(profile_name: str) -> PromptConfig:
    """严格读取当前 profile 绑定的 FPA user prompt 模板。"""
    entry = load_fpa_profile_entry(profile_name)
    prompt_key = str(entry.get("user_prompt", "") or "").strip()
    if not prompt_key:
        raise FpaPromptConfigError(
            f"未找到 FPA 用户提示词绑定：配置目录/{FPA_CONFIG_FILENAME} 中的 profiles.{profile_name}.user_prompt"
        )
    return _load_fpa_prompt_text(prompt_key, "user")


def load_fpa_user_prompt_template(profile_name: str) -> str:
    """从 fpa_config.yaml 读取 FPA 用户提示词模板。"""
    return load_fpa_user_prompt_config(profile_name).text


def migrate_config() -> None:
    """自动迁移配置：将模板中的新键追加到用户配置文件末尾。

    比对 config/*.example 与 ~/.ai-gen-reimbursement-docs/*，发现新键时自动追加。
    """
    home = Path.home() / ".ai-gen-reimbursement-docs"
    local = Path(__file__).parent.parent / "config"
    if not home.exists():
        return

    logger = logging.getLogger('ai_gen_reimbursement_docs.config_utils')

    # --- .env 合并 ---
    env_file = home / ".env"
    env_example = local / ".env.example"
    if env_file.exists() and env_example.exists():
        # 读取用户已有键
        user_keys = set()
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key = line.split('=', 1)[0].strip()
                    user_keys.add(key)
        # 检查示例中的新键
        new_lines = []
        with open(env_example, 'r', encoding='utf-8') as f:
            for line in f:
                line_stripped = line.strip()
                if '=' in line_stripped and not line_stripped.startswith('#'):
                    key = line_stripped.split('=', 1)[0].strip()
                    if key not in user_keys:
                        new_lines.append(f"\n# {key} 已新增至模板，请按需配置")
                        new_lines.append(line_stripped)
        if new_lines:
            with open(env_file, 'a', encoding='utf-8') as f:
                f.writelines(new_lines)
            logger.info(f"配置迁移: .env 新增 {len(new_lines) // 2} 个配置项")

    # --- YAML 合并 ---
    # 对比 .example 和用户配置，自动追加新增的顶层键（含嵌套块）
    yaml_pairs = [
        (home / "system_config.yaml", local / "system_config.yaml.example", "system_config"),
        (home / "fpa_config.yaml", local / "fpa_config.yaml.example", "fpa_config"),
    ]
    try:
        import yaml
    except ImportError:
        logger.warning("yaml 模块未安装，跳过配置迁移")
        return
    for yaml_file, example_file, name in yaml_pairs:
        if not yaml_file.exists() or not example_file.exists():
            continue
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                user_yaml = yaml.safe_load(f) or {}
            with open(example_file, 'r', encoding='utf-8') as f:
                example_content = f.read()
            example_yaml = yaml.safe_load(example_content) or {}

            # 找出 example 中存在但用户配置中不存在的顶层键
            missing_keys = [k for k in example_yaml if k not in user_yaml]

            if missing_keys:
                # 从 example 文件中提取缺失键的原始文本块
                import re
                example_lines = example_content.split('\n')
                new_blocks = []
                for key in missing_keys:
                    block = _extract_yaml_block(example_lines, key)
                    if block:
                        new_blocks.append(f"\n# {key} 已新增至模板，请按需配置\n")
                        new_blocks.append(block + '\n')

                if new_blocks:
                    with open(yaml_file, 'a', encoding='utf-8') as f:
                        f.writelines(new_blocks)
                    logger.info(f"配置迁移: {name} 新增 {len(missing_keys)} 个配置项: {', '.join(missing_keys)}")
        except Exception as e:
            logger.debug(f"配置迁移跳过 {name}: {e}")


def _extract_yaml_block(lines: list[str], key: str) -> str:
    """从 YAML 行列表中提取一个顶层键的完整文本块（含嵌套子键）。"""
    import re
    # 找到 key: 开头（可选前缀注释或空行）
    start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 匹配顶层键：以 key: 开头（行首无缩进）
        if re.match(rf'^{re.escape(key)}\s*:', stripped) and not line.startswith((' ', '\t')):
            start = i
            break
    if start is None:
        return ""

    # 收集从 start 到下一个顶层键或文件末尾的所有行
    block_lines = [lines[start]]
    for i in range(start + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        # 空行或仅注释行 → 属于当前块
        if not stripped or stripped.startswith('#'):
            block_lines.append(line)
            continue
        # 顶层键（行首无缩进，有 :）→ 新块开始，停止
        if not line.startswith((' ', '\t')) and ':' in stripped:
            break
        # 缩进行 → 属于当前块的子键
        block_lines.append(line)

    return '\n'.join(block_lines).rstrip()


