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


def remote_session_ttl_seconds(default: int = 24 * 3600) -> int:
    """读取远程 session 过期清理 TTL，配置缺失或非法时使用默认值。"""
    value = read_config().get("_system", {}).get("remote_session_ttl_seconds", default)
    try:
        ttl = int(value)
    except (TypeError, ValueError):
        return default
    return ttl if ttl > 0 else default


def mask_env_content(path: Path) -> str:
    """读取 .env 文件内容，遮住敏感值（远程用户查看全局默认时使用）。"""
    text = path.read_text(encoding="utf-8")
    sensitive_keys = re.compile(
        r'^(.*_(?:KEY|SECRET|TOKEN|PASSWORD)\s*=)(.+)$',
        re.IGNORECASE,
    )
    lines = []
    for line in text.splitlines():
        m = sensitive_keys.match(line.strip())
        if m:
            val = m.group(2).strip().strip('"').strip("'")
            masked = val[:4] + "***" + val[-4:] if len(val) > 8 else "***"
            lines.append(f"{m.group(1)} {masked}")
        else:
            lines.append(line)
    return "\n".join(lines)


async def save_config_to_dir(data: dict, target_dir: Path):
    """保存配置到指定目录。"""
    target_dir.mkdir(parents=True, exist_ok=True)

    if "_env" in data and data["_env"]:
        lines = []
        for k, v in data["_env"].items():
            lines.append(f"{k}={v}")
        (target_dir / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if "_system" in data and data["_system"]:
        import yaml

        path = target_dir / "system_config.yaml"
        path.write_text(
            yaml.dump(data["_system"], allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
