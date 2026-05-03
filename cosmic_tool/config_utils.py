"""Configuration utilities for loading API keys and settings."""

import json
import os
from pathlib import Path


def _config_dir() -> Path:
    """Path to config/ directory (project root /config)."""
    return Path(__file__).parent.parent / "config"


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


def load_api_key(override: bool = True) -> str:
    """Load ANTHROPIC_API_KEY.

    override=True: config/.env > system env var > config.json
    override=False: system env var > config/.env > config.json
    """
    env_path = _config_dir() / ".env"
    loader = _from_env_override if override else _from_env
    key = loader("ANTHROPIC_API_KEY", env_path)
    if key:
        return key

    # config.json fallback
    config_path = Path(__file__).parent / "config.json"
    key = _read_json_value("anthropic_api_key", config_path)
    if key:
        return key
    return ""


def load_base_url(override: bool = True) -> str:
    """Load ANTHROPIC_BASE_URL.

    override=True: config/.env > system env var > config.json
    override=False: system env var > config/.env > config.json
    """
    env_path = _config_dir() / ".env"
    loader = _from_env_override if override else _from_env
    url = loader("ANTHROPIC_BASE_URL", env_path)
    if url:
        return url

    config_path = Path(__file__).parent / "config.json"
    url = _read_json_value("anthropic_base_url", config_path)
    if url:
        return url
    return ""


def load_model_name(default: str = "deepseek-v4-flash", override: bool = True) -> str:
    """Load ANTHROPIC_MODEL.

    override=True: config/.env > system env var > config.json > default
    override=False: system env var > config/.env > config.json > default
    """
    env_path = _config_dir() / ".env"
    loader = _from_env_override if override else _from_env
    model = loader("ANTHROPIC_MODEL", env_path)
    if model:
        return _clean_model(model)

    config_path = Path(__file__).parent / "config.json"
    model = _read_json_value("anthropic_model", config_path)
    if model:
        return _clean_model(model)
    return default


def _clean_model(name: str) -> str:
    """Remove markdown artifacts from model name, e.g. deepseek-v4-flash[1m]."""
    import re
    return re.sub(r'\[.*?\]', '', name).strip().rstrip()


# Backward compatibility alias
clean_model_name = _clean_model


def _load_business_rules() -> dict:
    """Load config/business_rules.yaml and return as dict."""
    yaml_path = _config_dir() / "business_rules.yaml"
    if not yaml_path.exists():
        return {}
    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_cfp_formula(default: str = 'IF(L{row}="新增",1,IF(L{row}="复用",1/3,0))') -> str:
    """Load cfp_formula from business_rules.yaml."""
    cfg = _load_business_rules()
    formula = cfg.get('cfp_formula', '')
    return formula if formula else default


def load_user_defaults() -> tuple[str, str]:
    """Load user_initiator_default and user_receiver_default from business_rules.yaml."""
    cfg = _load_business_rules()
    return (
        cfg.get('user_initiator_default', '操作员'),
        cfg.get('user_receiver_default', '地市后台'),
    )


def load_initiator_rules() -> list[tuple[str, str]]:
    """Load user_initiator_rules from business_rules.yaml."""
    cfg = _load_business_rules()
    raw = cfg.get('user_initiator_rules', {})
    if not isinstance(raw, dict):
        return []
    return list(raw.items())


def load_receiver_rules() -> list[tuple[str, str]]:
    """Load user_receiver_rules from business_rules.yaml."""
    cfg = _load_business_rules()
    raw = cfg.get('user_receiver_rules', {})
    if not isinstance(raw, dict):
        return []
    return list(raw.items())


def load_max_tokens(default: int = 2000) -> int:
    """Load max_tokens from system_config.yaml, supporting K/M units.

    Examples: 2000, 384K, 1M
    """
    yaml_path = _config_dir() / "system_config.yaml"
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
            logger = logging.getLogger('cosmic_tool.config_utils')
            logger.warning(f"system_config.yaml 读取失败: {e}，使用默认值 {default}")
    return default


def load_business_config() -> dict:
    """Load business process flags from system_config.yaml.

    Returns dict with keys: regenerate_md, regenerate_filled, regenerate_excel,
    regenerate_all, enable_ai.
    """
    config = {
        'regenerate_md': False,
        'regenerate_filled': False,
        'regenerate_excel': False,
        'regenerate_all': False,
        'enable_ai': True,
    }
    yaml_path = _config_dir() / "system_config.yaml"
    if not yaml_path.exists():
        return config

    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}

        for key in ('regenerate_md', 'regenerate_filled', 'regenerate_excel',
                    'regenerate_all', 'enable_ai'):
            if key in cfg:
                config[key] = bool(cfg[key])
    except Exception:
        pass

    if config['regenerate_all']:
        config['regenerate_md'] = True
        config['regenerate_filled'] = True
        config['regenerate_excel'] = True

    return config
