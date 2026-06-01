import os
import re
from pathlib import Path


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


async def save_config_to_dir(data: dict, target_dir: Path):
    """保存配置到指定目录。"""
    target_dir.mkdir(parents=True, exist_ok=True)

    if "_env" in data and data["_env"]:
        env = {
            str(k): str(v)
            for k, v in data["_env"].items()
            if str(v) and str(v) != "***"
        }
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
