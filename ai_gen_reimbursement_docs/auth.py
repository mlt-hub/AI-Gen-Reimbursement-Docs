"""用户认证模块 — 简易多用户系统。

仅 Web 远程模式启用；CLI 和 Web 本机模式不受影响。

存储：
  - 用户表: ~/.ai-gen-reimbursement-docs/users.db (SQLite)
  - Token: 内存 dict（服务重启后所有用户需重新登录）
  - 用户配置: ~/.ai-gen-reimbursement-docs/users/<username>/
"""

import hashlib
import logging
import os
import secrets
import sqlite3
from pathlib import Path

import yaml

_log = logging.getLogger("ai_gen_reimbursement_docs.auth")

# ── 常量 ──────────────────────────────────────────────────

_LOCAL_IPS = frozenset({"127.0.0.1", "::1", "localhost"})

# ── Token 管理（内存） ────────────────────────────────────

_tokens: dict[str, str] = {}  # token → username


def create_token(username: str) -> str:
    """创建登录 token 并返回。"""
    token = secrets.token_hex(32)
    _tokens[token] = username
    return token


def remove_token(token: str) -> None:
    """移除 token（登出）。"""
    _tokens.pop(token, None)


def get_username_by_token(token: str) -> str | None:
    """根据 token 返回用户名，token 无效返回 None。"""
    return _tokens.get(token)


# ── 密码处理 ──────────────────────────────────────────────


def _hash_password(password: str, salt: str = "") -> tuple[str, str]:
    """PBKDF2-SHA256 哈希密码，返回 (hash_hex, salt_hex)。"""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex(), salt


# ── 数据库 ────────────────────────────────────────────────


def _db_path() -> Path:
    return Path.home() / ".ai-gen-reimbursement-docs" / "users.db"


def _init_db() -> None:
    """初始化用户表（幂等）。"""
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                salt        TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def register_user(username: str, password: str) -> bool:
    """注册用户。成功返回 True，用户名已存在返回 False。"""
    username = username.strip().lower()
    if not username or len(password) < 4:
        return False

    _init_db()
    pw_hash, salt = _hash_password(password)

    try:
        with sqlite3.connect(str(_db_path())) as conn:
            conn.execute(
                "INSERT INTO users (username, password, salt) VALUES (?, ?, ?)",
                (username, pw_hash, salt),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username: str, password: str) -> bool:
    """验证用户名密码。"""
    username = username.strip().lower()
    if not username:
        return False

    _init_db()
    with sqlite3.connect(str(_db_path())) as conn:
        row = conn.execute(
            "SELECT password, salt FROM users WHERE username = ?", (username,)
        ).fetchone()

    if not row:
        return False

    pw_hash, salt = row[0], row[1]
    computed, _ = _hash_password(password, salt)
    return computed == pw_hash


def allow_register() -> bool:
    """读取 system_config.yaml 中的 allow_register，默认 True。"""
    cfg_path = Path.home() / ".ai-gen-reimbursement-docs" / "system_config.yaml"
    if not cfg_path.exists():
        return True
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("allow_register", True)
    except Exception:
        return True


# ── 用户目录 ──────────────────────────────────────────────


def user_config_dir(username: str) -> Path:
    """返回用户配置目录路径。"""
    return Path.home() / ".ai-gen-reimbursement-docs" / "users" / username


def _project_root() -> Path:
    """返回项目根目录。"""
    return Path(__file__).resolve().parent.parent


def init_user_dir(username: str) -> None:
    """初始化用户目录：从项目 example 模板拷贝配置。"""
    from ai_gen_reimbursement_docs.config_utils import copy_default_config_files

    user_dir = user_config_dir(username)
    for dest in copy_default_config_files(user_dir, _project_root() / "config"):
        _log.info(f"已初始化用户配置: {dest}")

    # 创建模板和任务目录
    (user_dir / "templates").mkdir(exist_ok=True)
    (user_dir / "tasks").mkdir(exist_ok=True)


# ── IP 校验 ───────────────────────────────────────────────


def is_local_host(host: str) -> bool:
    """判断 IP/host 是否为本机。"""
    return host in _LOCAL_IPS
