"""用户认证模块 — 简易多用户系统。

仅 Web 远程模式启用；CLI 和 Web 本机模式不受影响。

存储：
  - 用户表: ~/.ai-gen-reimbursement-docs/users.db (SQLite)
  - 会话表: remember me 登录 token 哈希持久化，普通登录 token 仅保存在内存
  - 用户配置: ~/.ai-gen-reimbursement-docs/users/<username>/
"""

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
import sqlite3
import string
from pathlib import Path

import yaml

_log = logging.getLogger("ai_gen_reimbursement_docs.auth")

# ── 常量 ──────────────────────────────────────────────────

_LOCAL_IPS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
ADMIN_USERNAME = "admin"
ADMIN_INITIAL_PASSWORD = "mlt123"
REMEMBER_ME_DAYS = 30
SESSION_TOKEN_HOURS = 12
DEFAULT_INVITE_DAYS = 7
DEFAULT_INVITE_USES = 1
INVITE_CODE_LENGTH = 16

# ── Token 管理（内存） ────────────────────────────────────

_tokens: dict[str, dict[str, object]] = {}  # token → session metadata


class InviteError(ValueError):
    """邀请码不可用。"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dt_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_token(username: str, *, remember_me: bool = False) -> str:
    """创建登录 token 并返回。"""
    cleanup_expired_sessions()
    username = username.strip().lower()
    session_version = _user_session_version(username)
    if session_version is None:
        raise ValueError("用户不存在或已停用")
    token = secrets.token_hex(32)
    expires_at = _utc_now() + timedelta(
        days=REMEMBER_ME_DAYS,
    ) if remember_me else _utc_now() + timedelta(hours=SESSION_TOKEN_HOURS)
    _tokens[token] = {
        "username": username,
        "expires_at": expires_at,
        "session_version": session_version,
    }
    if remember_me:
        _init_db()
        with sqlite3.connect(str(_db_path())) as conn:
            conn.execute(
                """
                INSERT INTO auth_sessions (token_hash, username, expires_at, last_seen_at, session_version)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _hash_token(token),
                    username,
                    _dt_text(expires_at),
                    _dt_text(_utc_now()),
                    session_version,
                ),
            )
            conn.commit()
    return token


def _remove_token_record(token: str) -> None:
    _tokens.pop(token, None)
    if token:
        _init_db()
        with sqlite3.connect(str(_db_path())) as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_hash_token(token),))
            conn.commit()


def remove_token(token: str) -> None:
    """移除 token（登出）。"""
    cleanup_expired_sessions()
    _remove_token_record(token)


def get_username_by_token(token: str) -> str | None:
    """根据 token 返回用户名，token 无效返回 None。"""
    cleanup_expired_sessions()
    if not token:
        return None
    now_dt = _utc_now()
    cached = _tokens.get(token)
    if cached:
        username = str(cached.get("username") or "")
        expires_at = cached.get("expires_at")
        raw_session_version = cached.get("session_version")
        session_version = int(raw_session_version) if raw_session_version is not None else -1
        if isinstance(expires_at, datetime) and expires_at > now_dt and _user_session_version(username) == session_version:
            return username
        _remove_token_record(token)
        return None

    _init_db()
    now = _dt_text(now_dt)
    token_hash = _hash_token(token)
    with sqlite3.connect(str(_db_path())) as conn:
        row = conn.execute(
            """
            SELECT username, expires_at, session_version
            FROM auth_sessions
            WHERE token_hash = ? AND expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
        if not row:
            return None
        username = str(row[0])
        session_version = int(row[2])
        if _user_session_version(username) != session_version:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
            conn.commit()
            return None
        conn.execute(
            "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
            (now, token_hash),
        )
        conn.commit()
    try:
        expires_at = datetime.fromisoformat(str(row[1]))
    except ValueError:
        _remove_token_record(token)
        return None
    _tokens[token] = {
        "username": username,
        "expires_at": expires_at,
        "session_version": session_version,
    }
    return username


def _user_session_version(username: str) -> int | None:
    username = username.strip().lower()
    if not username:
        return None
    _init_db()
    with sqlite3.connect(str(_db_path())) as conn:
        row = conn.execute(
            "SELECT session_version FROM users WHERE username = ? AND disabled = 0",
            (username,),
        ).fetchone()
    return int(row[0]) if row else None


def revoke_user_tokens(username: str) -> None:
    """撤销指定用户的所有 token。"""
    username = username.strip().lower()
    if not username:
        return
    for token, meta in list(_tokens.items()):
        if str(meta.get("username") or "") == username:
            _tokens.pop(token, None)
    _init_db()
    with sqlite3.connect(str(_db_path())) as conn:
        conn.execute("DELETE FROM auth_sessions WHERE username = ?", (username,))
        conn.commit()


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
    admin_created = False
    with sqlite3.connect(str(db)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                salt        TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT 'user',
                disabled    INTEGER NOT NULL DEFAULT 0,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                session_version INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _ensure_user_schema(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash   TEXT UNIQUE NOT NULL,
                username     TEXT NOT NULL,
                expires_at   TIMESTAMP NOT NULL,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP,
                session_version INTEGER NOT NULL DEFAULT 0
            )
        """)
        _ensure_auth_session_schema(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registration_invites (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code_hash   TEXT UNIQUE NOT NULL,
                created_by  TEXT NOT NULL,
                expires_at  TIMESTAMP,
                max_uses    INTEGER NOT NULL DEFAULT 1,
                used_count  INTEGER NOT NULL DEFAULT 0,
                disabled    INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        if not conn.execute("SELECT 1 FROM users WHERE username = ?", (ADMIN_USERNAME,)).fetchone():
            pw_hash, salt = _hash_password(ADMIN_INITIAL_PASSWORD)
            conn.execute(
                """
                INSERT INTO users (username, password, salt, role)
                VALUES (?, ?, ?, 'admin')
                """,
                (ADMIN_USERNAME, pw_hash, salt),
            )
            conn.execute(
                "UPDATE users SET must_change_password = 1 WHERE username = ?",
                (ADMIN_USERNAME,),
            )
            admin_created = True
        else:
            conn.execute(
                "UPDATE users SET role = 'admin' WHERE username = ? AND role != 'admin'",
                (ADMIN_USERNAME,),
            )
            row = conn.execute(
                "SELECT password, salt, must_change_password FROM users WHERE username = ?",
                (ADMIN_USERNAME,),
            ).fetchone()
            if row:
                computed, _ = _hash_password(ADMIN_INITIAL_PASSWORD, row[1])
                if row[0] == computed and not row[2]:
                    conn.execute(
                        "UPDATE users SET must_change_password = 1 WHERE username = ?",
                        (ADMIN_USERNAME,),
                    )
        conn.commit()
    if admin_created:
        init_user_dir(ADMIN_USERNAME)


def _ensure_user_schema(conn: sqlite3.Connection) -> None:
    """补齐开发期旧 users 表缺失的轻量字段。"""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "role" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "disabled" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0")
    if "must_change_password" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
    if "session_version" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0")


def _ensure_auth_session_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(auth_sessions)").fetchall()}
    if "session_version" not in columns:
        conn.execute("ALTER TABLE auth_sessions ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0")


def register_user(username: str, password: str, *, role: str = "user") -> bool:
    """注册用户。成功返回 True，用户名已存在返回 False。"""
    username = username.strip().lower()
    if role not in {"admin", "user"}:
        return False
    if not username or len(password) < 6:
        return False

    _init_db()
    pw_hash, salt = _hash_password(password)

    try:
        with sqlite3.connect(str(_db_path())) as conn:
            conn.execute(
                "INSERT INTO users (username, password, salt, role) VALUES (?, ?, ?, ?)",
                (username, pw_hash, salt, role),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def register_user_with_invite(username: str, password: str, invite_code: str) -> bool:
    """使用邀请码注册用户，用户写入和邀请码计数更新保持同一数据库事务。"""
    username = username.strip().lower()
    if not username or len(password) < 6:
        return False

    code = invite_code.strip()
    if not code:
        raise InviteError("邀请码无效")

    _init_db()
    now = _dt_text(_utc_now())
    pw_hash, salt = _hash_password(password)
    code_hash = _hash_token(code)

    try:
        with sqlite3.connect(str(_db_path())) as conn:
            row = conn.execute(
                """
                SELECT id, expires_at, max_uses, used_count, disabled
                FROM registration_invites
                WHERE code_hash = ?
                """,
                (code_hash,),
            ).fetchone()
            if not row:
                raise InviteError("邀请码无效")
            if row[4]:
                raise InviteError("邀请码已停用")
            if row[1] and row[1] <= now:
                raise InviteError("邀请码已过期")
            if row[3] >= row[2]:
                raise InviteError("邀请码使用次数已耗尽")

            conn.execute(
                "INSERT INTO users (username, password, salt, role) VALUES (?, ?, ?, 'user')",
                (username, pw_hash, salt),
            )
            conn.execute(
                "UPDATE registration_invites SET used_count = used_count + 1 WHERE id = ?",
                (row[0],),
            )
            conn.commit()
        init_user_dir(username)
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
            "SELECT password, salt FROM users WHERE username = ? AND disabled = 0", (username,)
        ).fetchone()

    if not row:
        return False

    pw_hash, salt = row[0], row[1]
    computed, _ = _hash_password(password, salt)
    return computed == pw_hash


def user_exists(username: str) -> bool:
    """判断用户名是否已存在。"""
    username = username.strip().lower()
    if not username:
        return False
    _init_db()
    with sqlite3.connect(str(_db_path())) as conn:
        row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
    return row is not None


def get_user_role(username: str) -> str | None:
    """返回用户角色。"""
    username = username.strip().lower()
    if not username:
        return None
    _init_db()
    with sqlite3.connect(str(_db_path())) as conn:
        row = conn.execute(
            "SELECT role FROM users WHERE username = ? AND disabled = 0", (username,)
        ).fetchone()
    return row[0] if row else None


def is_admin(username: str) -> bool:
    """判断用户是否为管理员。"""
    return get_user_role(username) == "admin"


def user_must_change_password(username: str) -> bool:
    """判断用户是否必须修改初始密码。"""
    username = username.strip().lower()
    if not username:
        return False
    _init_db()
    with sqlite3.connect(str(_db_path())) as conn:
        row = conn.execute(
            "SELECT must_change_password FROM users WHERE username = ? AND disabled = 0",
            (username,),
        ).fetchone()
    return bool(row and row[0])


def change_password(username: str, current_password: str, new_password: str) -> bool:
    """修改密码，成功后清除 must_change_password 标记。"""
    username = username.strip().lower()
    if not username or len(new_password) < 6:
        return False
    if not verify_user(username, current_password):
        return False

    pw_hash, salt = _hash_password(new_password)
    with sqlite3.connect(str(_db_path())) as conn:
        cursor = conn.execute(
            """
            UPDATE users
            SET password = ?, salt = ?, must_change_password = 0,
                session_version = session_version + 1
            WHERE username = ? AND disabled = 0
            """,
            (pw_hash, salt, username),
        )
        conn.commit()
    changed = cursor.rowcount > 0
    if changed:
        revoke_user_tokens(username)
    return changed


def allow_register() -> bool:
    """读取 system_config.yaml 中的 allow_register，默认 False。"""
    cfg_path = Path.home() / ".ai-gen-reimbursement-docs" / "system_config.yaml"
    if not cfg_path.exists():
        return False
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("allow_register", False)
    except Exception:
        return False


def cleanup_expired_sessions() -> int:
    """清理已过期自动登录会话。"""
    _init_db_without_admin()
    now = _dt_text(_utc_now())
    with sqlite3.connect(str(_db_path())) as conn:
        cursor = conn.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
        conn.commit()
        return cursor.rowcount


def _init_db_without_admin() -> None:
    """仅确保数据库目录存在，供会话清理避免递归初始化。"""
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash   TEXT UNIQUE NOT NULL,
                username     TEXT NOT NULL,
                expires_at   TIMESTAMP NOT NULL,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP,
                session_version INTEGER NOT NULL DEFAULT 0
            )
        """)
        _ensure_auth_session_schema(conn)
        conn.commit()


# ── 邀请注册 ──────────────────────────────────────────────


def _random_invite_code() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(INVITE_CODE_LENGTH))


def _positive_int_or_default(value: object, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def create_invite(created_by: str, *, expires_in_days: int | None = None, max_uses: int | None = None) -> dict:
    """创建邀请码，返回含明文 code 的结果。"""
    created_by = created_by.strip().lower()
    if not is_admin(created_by):
        raise PermissionError("仅管理员可创建邀请码")
    days = _positive_int_or_default(expires_in_days, DEFAULT_INVITE_DAYS)
    uses = _positive_int_or_default(max_uses, DEFAULT_INVITE_USES)
    code = _random_invite_code()
    expires_at = _utc_now() + timedelta(days=days)
    _init_db()
    with sqlite3.connect(str(_db_path())) as conn:
        cursor = conn.execute(
            """
            INSERT INTO registration_invites (code_hash, created_by, expires_at, max_uses)
            VALUES (?, ?, ?, ?)
            """,
            (_hash_token(code), created_by, _dt_text(expires_at), uses),
        )
        conn.commit()
        invite_id = cursor.lastrowid
    return {
        "id": invite_id,
        "code": code,
        "created_by": created_by,
        "expires_at": _dt_text(expires_at),
        "max_uses": uses,
        "used_count": 0,
        "disabled": False,
        "status": "active",
    }


def list_invites() -> list[dict]:
    """返回邀请码列表，不包含明文邀请码。"""
    _init_db()
    now = _dt_text(_utc_now())
    with sqlite3.connect(str(_db_path())) as conn:
        rows = conn.execute(
            """
            SELECT id, created_by, expires_at, max_uses, used_count, disabled, created_at
            FROM registration_invites
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    invites = []
    for row in rows:
        disabled = bool(row[5])
        status = "active"
        if disabled:
            status = "disabled"
        elif row[2] and row[2] <= now:
            status = "expired"
        elif row[4] >= row[3]:
            status = "exhausted"
        invites.append({
            "id": row[0],
            "created_by": row[1],
            "expires_at": row[2],
            "max_uses": row[3],
            "used_count": row[4],
            "disabled": disabled,
            "created_at": row[6],
            "status": status,
        })
    return invites


def disable_invite(invite_id: int) -> bool:
    """停用邀请码。"""
    _init_db()
    with sqlite3.connect(str(_db_path())) as conn:
        cursor = conn.execute(
            "UPDATE registration_invites SET disabled = 1 WHERE id = ?",
            (invite_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def consume_invite(code: str) -> None:
    """消费邀请码，不可用时抛出 InviteError。"""
    code = code.strip()
    if not code:
        raise InviteError("邀请码无效")
    _init_db()
    now = _dt_text(_utc_now())
    code_hash = _hash_token(code)
    with sqlite3.connect(str(_db_path())) as conn:
        row = conn.execute(
            """
            SELECT id, expires_at, max_uses, used_count, disabled
            FROM registration_invites
            WHERE code_hash = ?
            """,
            (code_hash,),
        ).fetchone()
        if not row:
            raise InviteError("邀请码无效")
        if row[4]:
            raise InviteError("邀请码已停用")
        if row[1] and row[1] <= now:
            raise InviteError("邀请码已过期")
        if row[3] >= row[2]:
            raise InviteError("邀请码使用次数已耗尽")
        conn.execute(
            "UPDATE registration_invites SET used_count = used_count + 1 WHERE id = ?",
            (row[0],),
        )
        conn.commit()


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
