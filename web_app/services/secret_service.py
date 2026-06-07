import base64
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


class SecretServiceError(RuntimeError):
    """Raised when a secret cannot be encrypted or decrypted."""


def _master_key_path(config_root: Path) -> Path:
    return config_root / "secrets" / "master.key"


def _load_or_create_master_key(config_root: Path) -> bytes:
    path = _master_key_path(config_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes().strip()

    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _encrypt_with_dpapi(value: str) -> str:
    if sys.platform != "win32":
        raise SecretServiceError("DPAPI is only available on Windows")
    try:
        import win32crypt
    except Exception as exc:  # pragma: no cover - depends on host package state
        raise SecretServiceError("DPAPI package is unavailable") from exc

    blob = win32crypt.CryptProtectData(value.encode("utf-8"), None, None, None, None, 0)
    return "dpapi:" + base64.b64encode(blob).decode("ascii")


def _decrypt_with_dpapi(token: str) -> str:
    if sys.platform != "win32":
        raise SecretServiceError("DPAPI is only available on Windows")
    try:
        import win32crypt
    except Exception as exc:  # pragma: no cover - depends on host package state
        raise SecretServiceError("DPAPI package is unavailable") from exc

    blob = base64.b64decode(token.encode("ascii"))
    _desc, data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
    return data.decode("utf-8")


def _encrypt_with_fernet(value: str, config_root: Path) -> str:
    key = _load_or_create_master_key(config_root)
    token = Fernet(key).encrypt(value.encode("utf-8"))
    return "fernet:" + token.decode("ascii")


def _decrypt_with_fernet(token: str, config_root: Path) -> str:
    key = _load_or_create_master_key(config_root)
    return Fernet(key).decrypt(token.encode("ascii")).decode("utf-8")


def encrypt_secret(value: str, *, config_root: Path) -> str:
    secret = value.strip()
    if not secret:
        return ""

    try:
        return _encrypt_with_dpapi(secret)
    except SecretServiceError:
        return _encrypt_with_fernet(secret, config_root)


def decrypt_secret(value: str, *, config_root: Path) -> str:
    token = value.strip()
    if not token:
        return ""
    if token.startswith("dpapi:"):
        return _decrypt_with_dpapi(token.removeprefix("dpapi:"))
    if token.startswith("fernet:"):
        return _decrypt_with_fernet(token.removeprefix("fernet:"), config_root)
    raise SecretServiceError("Unsupported secret format")
