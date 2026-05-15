"""Configuration utilities for loading API keys and settings."""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path


def config_dir() -> Path:
    """Path to user config directory: ~/.ai-gen-reimbursement-docs/."""
    return Path.home() / ".ai-gen-reimbursement-docs"


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
    env_path = config_dir() / ".env"
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


def _load_business_rules() -> dict:
    """Load config/business_rules.yaml and return as dict."""
    yaml_path = config_dir() / "business_rules.yaml"
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
    """读取流程对应的 AI 限制数。优先走专有参数，fallback 到 max_ai_l3_modules。
    
    Args:
        flow_name: 'gen_fpa', 'gen_spec', 'gen_cosmic'
    """
    key = f"{flow_name}_max_ai_l3_modules"
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


def load_out_templates() -> dict[str, str]:
    """读取 system_config.yaml 中 out_templates 配置。

    Returns:
        {'FPA工作量评估-模板': 'data/out_templates/...', ...}
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


def load_gen_spec_ai_limit() -> int:
    """读取 gen_spec_ai_limit，限制 spec AI 完善的功能过程描述数（0=不限制）。"""
    val = _get_system_config_value('gen_spec_ai_limit', 0)
    return max(val, 0)


@lru_cache(maxsize=1)
def load_sheet_names() -> dict[str, str]:
    """读取功能清单-录入模板.xlsx 的 Sheet 名称映射。

    返回 key → Sheet 名的字典，未配置则返回空 dict 并提醒用户。
    """
    yaml_path = config_dir() / "system_config.yaml"
    if not yaml_path.exists():
        _log = logging.getLogger('ai_gen_reimbursement_docs.config_utils')
        _log.warning("未找到 system_config.yaml，Sheet 名称将为空，请运行 --init-config 初始化")
        return {}
    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
        sheets = cfg.get('sheets', {})
        if not sheets:
            _log = logging.getLogger('ai_gen_reimbursement_docs.config_utils')
            _log.warning("system_config.yaml 中未配置 sheets 段，Sheet 名称将为空，请补充 sheets 配置")
        return sheets
    except Exception:
        _log = logging.getLogger('ai_gen_reimbursement_docs.config_utils')
        _log.warning("system_config.yaml 读取失败，Sheet 名称将为空")
        return {}


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
            logger.info(f"配置迁移: .env 新增 {len(new_lines)//2} 个配置项")

    # --- YAML 合并 ---
    # 对比 .example 和用户配置，自动追加新增的顶层键（含嵌套块）
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
    yaml_path = config_dir() / "system_config.yaml"
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
