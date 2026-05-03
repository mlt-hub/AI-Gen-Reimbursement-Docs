"""Configuration utilities for loading API keys and settings."""

import json
import os
from pathlib import Path


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


def load_api_key() -> str:
    """Load ANTHROPIC_API_KEY from env, .env file, or config.json."""
    # 1. Environment variable
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key

    # 2. .env in cosmic_tool directory
    env_path = Path(__file__).parent / ".env"
    key = _read_env_value("ANTHROPIC_API_KEY", env_path)
    if key:
        return key

    # 3. config.json
    config_path = Path(__file__).parent / "config.json"
    key = _read_json_value("anthropic_api_key", config_path)
    if key:
        return key

    return ""


def load_base_url() -> str:
    """Load ANTHROPIC_BASE_URL from env, .env file, or config.json."""
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    if url:
        return url

    # .env in cosmic_tool directory
    env_path = Path(__file__).parent / ".env"
    url = _read_env_value("ANTHROPIC_BASE_URL", env_path)
    if url:
        return url

    # config.json
    config_path = Path(__file__).parent / "config.json"
    url = _read_json_value("anthropic_base_url", config_path)
    if url:
        return url

    return ""


def load_model_name(default: str = "deepseek-v4-flash") -> str:
    """Load ANTHROPIC_MODEL from env, .env file, or config.json."""
    # Priority: .env > env var > config.json > default
    env_path = Path(__file__).parent / ".env"
    model = _read_env_value("ANTHROPIC_MODEL", env_path)
    if model:
        return _clean_model(model)

    model = os.environ.get("ANTHROPIC_MODEL", "")
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


def _business_env_path() -> Path:
    """Path to the business config file (同目录下的 business.env)."""
    return Path(__file__).parent / "business.env"


def load_cfp_formula(default: str = 'IF(L{row}="新增",1,IF(L{row}="复用",1/3,0))') -> str:
    """Load CFP_FORMULA from business.env."""
    env_path = _business_env_path()
    formula = _read_env_value("CFP_FORMULA", env_path)
    if formula:
        return formula
    return default


def load_user_defaults() -> tuple[str, str]:
    """Load default initiator and receiver from business.env."""
    env_path = _business_env_path()
    default_initiator = "操作员"
    default_receiver = "地市后台"

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("USER_INITIATOR_DEFAULT="):
                    default_initiator = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("USER_RECEIVER_DEFAULT="):
                    default_receiver = line.split("=", 1)[1].strip().strip('"').strip("'")
    return default_initiator, default_receiver


def load_initiator_rules() -> list[tuple[str, str]]:
    """Load USER_INITIATOR_关键词=值 rules from business.env."""
    env_path = _business_env_path()
    rules: list[tuple[str, str]] = []

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("USER_INITIATOR_") and not line.startswith("USER_INITIATOR_DEFAULT="):
                    rest = line[len("USER_INITIATOR_"):]
                    key, _, val = rest.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and val:
                        rules.append((key, val))
    return rules


def load_receiver_rules() -> list[tuple[str, str]]:
    """Load USER_RECEIVER_关键词=值 rules from business.env."""
    env_path = _business_env_path()
    rules: list[tuple[str, str]] = []

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("USER_RECEIVER_") and not line.startswith("USER_RECEIVER_DEFAULT="):
                    rest = line[len("USER_RECEIVER_"):]
                    key, _, val = rest.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and val:
                        rules.append((key, val))
    return rules


def load_max_tokens(default: int = 2000) -> int:
    """Load MAX_TOKENS from .env, supporting K/M units.

    Examples: 2000, 384K, 1M
    """
    env_path = Path(__file__).parent / ".env"
    val = _read_env_value("MAX_TOKENS", env_path)
    if not val:
        return default

    val = val.strip().upper()
    try:
        if val.endswith("M"):
            return int(float(val[:-1]) * 1_000_000)
        elif val.endswith("K"):
            return int(float(val[:-1]) * 1_000)
        else:
            return int(val)
    except (ValueError, OverflowError):
        logger = logging.getLogger('cosmic_tool.config_utils')
        logger.warning(f"MAX_TOKENS 格式无效「{val}」，使用默认值 {default}")
        return default
