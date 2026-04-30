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
