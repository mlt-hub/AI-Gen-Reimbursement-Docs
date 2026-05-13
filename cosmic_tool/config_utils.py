"""Configuration utilities for loading API keys and settings."""

import json
import logging
import os
from pathlib import Path


def _config_dir() -> Path:
    """Path to user config directory: ~/.cosmic-tool/."""
    return Path.home() / ".cosmic-tool"


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
    """Return model name as-is (保留原始值，不过滤)。"""
    return name.strip()


# Backward compatibility alias
clean_model_name = _clean_model


def _get_system_config_value(key: str, default):
    """从 system_config.yaml 中读取指定 key 的值（带缓存）。

    Args:
        key: 配置键名
        default: 默认值（同时确定返回类型）

    Returns:
        配置值，未找到或读取失败返回 default
    """
    yaml_path = _config_dir() / "system_config.yaml"
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



def load_max_tokens(default: int = 2000) -> int:
    """Load max_tokens from system_config.yaml, supporting K/M units.
    CLI --max-tokens 通过环境变量 COSMIC_MAX_TOKENS 覆盖。

    Examples: 2000, 384K, 1M
    """
    import os as _os
    _env = _os.environ.get('COSMIC_MAX_TOKENS', '').strip()
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



def load_flow_max_ai(flow_name: str) -> int:
    """读取流程对应的 AI 限制数。优先走专有参数，fallback 到 max_ai_l3_modules。
    
    Args:
        flow_name: 'gen_fpa', 'gen_spec', 'gen_cosmic'
    """
    key = f"{flow_name}_max_ai_l3_modules"
    yaml_path = _config_dir() / "system_config.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
            # 专有参数 > 通用参数 > 0
            val = cfg.get(key, 0)
            if val and int(val) > 0:
                return int(val)
            common = cfg.get('max_ai_l3_modules', 0)
            if common and int(common) > 0:
                return int(common)
        except Exception:
            pass
    return 0




def load_cosmic_warn_marker() -> bool:
    """读取 cosmic_warn_marker，true 时在拆分表中标记数据异常警告。"""
    return _get_system_config_value('cosmic_warn_marker', True)


def load_fpa_reduced_use_workload() -> bool:
    """读取 fpa_reduced_use_workload，true 时直接用 FPA 工作量值。"""
    return _get_system_config_value('fpa_reduced_use_workload', False)


def load_max_ai_l3_modules(default: int = 0) -> int:
    """读取 max_ai_l3_modules，0=不限制。"""
    return _get_system_config_value('max_ai_l3_modules', default)


def load_spec_remind_update_toc() -> bool:
    """读取 spec_remind_update_toc，true 时在 docx 文件名加提醒前缀。"""
    return _get_system_config_value('spec_remind_update_toc', True)


def load_gen_fpa_ai_limit() -> int:
    """读取 gen_fpa_ai_limit，限制 FPA AI 处理的功能过程数（0=不限制）。"""
    val = _get_system_config_value('gen_fpa_ai_limit', 0)
    return max(val, 0)


def load_gen_cosmic_ai_limit() -> int:
    """读取 gen_cosmic_ai_limit，限制 COSMIC AI 处理的功能过程数（0=不限制）。"""
    val = _get_system_config_value('gen_cosmic_ai_limit', 0)
    return max(val, 0)


def load_ai_system_prompt(name: str) -> str:
    """从 ai_system_prompts_config.yaml 读取指定场景的 system prompt。"""
    yaml_path = _config_dir() / "ai_system_prompts_config.yaml"
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
    yaml_path = _config_dir() / "ai_system_prompts_config.yaml"
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




def _migrate_config() -> None:
    """自动迁移配置：将模板中的新键追加到用户配置文件末尾。

    比对 config/*.example 与 ~/.cosmic-tool/*，发现新键时自动追加。
    """
    home = Path.home() / ".cosmic-tool"
    local = Path(__file__).parent.parent / "config"
    if not home.exists():
        return

    logger = logging.getLogger('cosmic_tool.config_utils')

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
            logger.info(f"配置迁移: .env 新增 {len(new_lines)//2} 个配置项")

    # --- YAML 合并（基于文本解析，支持注释中的键） ---
    yaml_pairs = [
        (home / "system_config.yaml", local / "system_config.yaml.example", "system_config"),
        (home / "business_rules.yaml", local / "business_rules.yaml.example", "business_rules"),
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
            # 读取用户已有的 YAML 键（含注释中的默认值）
            with open(yaml_file, 'r', encoding='utf-8') as f:
                user_content = f.read()
            user_keys = set()
            for line in user_content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and ':' in line:
                    user_keys.add(line.split(':', 1)[0].strip())

            # 读取示例中的键（包括被注释的，排除描述性文字）
            import re
            example_keys = {}
            with open(example_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 只匹配 key: value 或 # key: value 格式（key 为字母下划线组成）
                    m = re.match(r'^#?\s*([a-zA-Z_]\w*)\s*:\s*(.+)$', line)
                    if not m:
                        continue
                    key = m.group(1)
                    if key not in user_keys:
                        example_keys[key] = m.group(2).strip()

            if example_keys:
                new_lines = []
                for key, val in example_keys.items():
                    new_lines.append(f"\n# {key} 已新增至模板，请按需配置\n")
                    new_lines.append(f"#{key}: {val}\n" if val.startswith('#') else f"{key}: {val}\n")
                with open(yaml_file, 'a', encoding='utf-8') as f:
                    f.writelines(new_lines)
                logger.info(f"配置迁移: {name} 新增 {len(example_keys)} 个配置项")
        except Exception as e:
            logger.debug(f"配置迁移跳过 {name}: {e}")



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
        'enable_ai_generate_cosmic': True,
        'parse_docx_by_ai': False,
        'docx_parse_by_template_style': True,
        'docx_parse_by_marker': True,
    }
    yaml_path = _config_dir() / "system_config.yaml"
    if not yaml_path.exists():
        return config

    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}

        for key in ('regenerate_md', 'regenerate_filled', 'regenerate_excel',
                    'regenerate_all', 'enable_ai_generate_cosmic',
                    'parse_docx_by_ai', 'docx_parse_by_template_style',
                    'docx_parse_by_marker'):
            if key in cfg:
                config[key] = bool(cfg[key])
    except Exception:
        pass

    if config['regenerate_all']:
        config['regenerate_md'] = True
        config['regenerate_filled'] = True
        config['regenerate_excel'] = True

    return config
